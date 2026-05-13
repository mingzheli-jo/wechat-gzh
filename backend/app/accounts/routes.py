import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service
from app.accounts.schemas import AccountIn, AccountOut, AccountUpdate
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.config import get_settings
from app.wechat.material import WeChatMaterialError, upload_image
from app.wechat.token import get_access_token

router = APIRouter(prefix="/accounts", tags=["accounts"])

_MAX_COVER_BYTES = 10 * 1024 * 1024
_ALLOWED_COVER_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/bmp",
}


@router.post("", response_model=AccountOut, status_code=201)
async def create(
    payload: AccountIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    return AccountOut.model_validate(await service.create_account(db, payload))


@router.get("", response_model=list[AccountOut])
async def list_all(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[AccountOut]:
    return [AccountOut.model_validate(r) for r in await service.list_accounts(db)]


@router.get("/{account_id}", response_model=AccountOut)
async def get_one(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(obj)


@router.patch("/{account_id}", response_model=AccountOut)
async def update(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(await service.update_account(db, obj, payload))


@router.delete("/{account_id}", status_code=204)
async def delete(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    await service.delete_account(db, obj)


@router.post("/{account_id}/default-cover", response_model=AccountOut)
async def upload_default_cover(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if file.content_type not in _ALLOWED_COVER_MIME:
        raise HTTPException(415, f"不支持的图片格式: {file.content_type}")
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    if len(content) > _MAX_COVER_BYTES:
        raise HTTPException(
            413, f"图片超过 {_MAX_COVER_BYTES // 1024 // 1024}MB 限制"
        )

    suffix = Path(file.filename or "cover.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        token = await get_access_token(
            account_id=str(obj.id),
            appid=obj.wechat_appid,
            secret=obj.wechat_secret,
        )
        try:
            result = await upload_image(access_token=token, file_path=tmp_path)
        except WeChatMaterialError as exc:
            raise HTTPException(502, f"微信素材上传失败: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    obj.default_thumb_media_id = result["media_id"]
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)


@router.delete("/{account_id}/default-cover", response_model=AccountOut)
async def clear_default_cover(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    obj.default_thumb_media_id = None
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)


_ALLOWED_CHAR_REF_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
}


@router.post("/{account_id}/character-reference", response_model=AccountOut)
async def upload_character_reference(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    from datetime import UTC, datetime

    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if file.content_type not in _ALLOWED_CHAR_REF_MIME:
        raise HTTPException(415, f"不支持的图片格式: {file.content_type}")
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    if len(content) > _MAX_COVER_BYTES:
        raise HTTPException(
            413, f"图片超过 {_MAX_COVER_BYTES // 1024 // 1024}MB 限制"
        )

    settings = get_settings()
    storage_dir = Path(settings.image_storage_dir) / "accounts" / str(obj.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "char.png").suffix or ".png"
    target = storage_dir / f"character{suffix}"
    target.write_bytes(content)

    obj.character_reference_path = str(target)
    obj.character_reference_updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)


@router.delete("/{account_id}/character-reference", response_model=AccountOut)
async def clear_character_reference(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if obj.character_reference_path:
        Path(obj.character_reference_path).unlink(missing_ok=True)
    obj.character_reference_path = None
    obj.character_reference_updated_at = None
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)
