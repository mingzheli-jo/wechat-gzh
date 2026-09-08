"""每日出稿的持久化进度、进程锁和只读草稿核实。"""
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DAY_TZ = timezone(timedelta(hours=8))


def business_day():
    return datetime.now(DAY_TZ).date().isoformat()


def pushed_today(draft, day):
    stamp = draft.get('wechat_pushed_at')
    return bool(
        draft.get('status') == 'published_to_wechat' and stamp
        and datetime.fromisoformat(stamp).astimezone(DAY_TZ).date().isoformat() == day
    )


def publish_failure_kind(draft):
    if draft.get('status') != 'failed':
        return 'unknown'
    error = draft.get('error_msg') or ''
    match = re.match(r'WeChatDraftError: errcode=(-?[1-9]\d*),', error)
    if match:
        # 认证、IP 白名单和每日配额问题不会因为换文章而恢复。
        return 'blocked' if int(match[1]) in (40001, 40013, 40125, 40164, 45009, 48001, 50001) else 'retry'
    if error.startswith(('本草稿无封面图片',)) or '张图片未完成上传' in error:
        return 'blocked'
    # 包括 ReadTimeout：后端虽然记 failed，微信却可能已经接收。
    return 'unknown'


class Progress:
    def __init__(self, directory, account_id, day, dry_run):
        account_id = str(uuid.UUID(account_id))
        self.path = Path(directory) / f"daily-{'dry' if dry_run else 'live'}-{account_id}.json"
        self.data = {'version': 1, 'day': day, 'dry_count': 0, 'pending': None}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('version') != 1:
                raise ValueError('不支持的出稿进度版本')
        if self.data['day'] != day:
            self.data.update(day=day, dry_count=0)

    @property
    def pending(self):
        return self.data['pending']

    @pending.setter
    def pending(self, value):
        self.data['pending'] = value

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 临时文件与目标位于同一目录，原子替换避免中断留下半份 JSON。
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                         prefix='.daily-', delete=False) as stream:
            json.dump(self.data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = stream.name
        os.replace(temporary, self.path)


@contextmanager
def single_run(directory):
    import fcntl

    Path(directory).mkdir(parents=True, exist_ok=True)
    with (Path(directory) / 'daily-creator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


# 草稿 API 没暴露 source_creation_id，不能靠标题猜关联关系。
# 沿用现有服务器任务的 sudo/docker 权限，在 API 容器内做参数化只读查询。
_READ_DRAFTS = '''
import asyncio, json, sys, uuid
from datetime import datetime, timedelta, timezone
import asyncpg
from app.config import get_settings

async def main():
    args = json.load(sys.stdin)
    start = datetime.fromisoformat(args['day']).replace(tzinfo=timezone(timedelta(hours=8)))
    cid = uuid.UUID(args['creation_id']) if args.get('creation_id') else None
    conn = await asyncpg.connect(get_settings().database_url.replace('postgresql+asyncpg://', 'postgresql://', 1))
    try:
        async with conn.transaction(readonly=True):
            await conn.execute("SET LOCAL statement_timeout = '10s'")
            rows = await conn.fetch(
                """SELECT id, source_creation_id, account_id, status, error_msg,
                          created_at, wechat_pushed_at
                   FROM drafts
                   WHERE account_id=$1 AND source_creation_id IS NOT NULL
                     AND (source_creation_id=$2 OR (created_at >= $3 AND created_at < $4)
                          OR (wechat_pushed_at >= $3 AND wechat_pushed_at < $4))
                   ORDER BY created_at""",
                uuid.UUID(args['account_id']), cid, start, start + timedelta(days=1))
            print(json.dumps([dict(row) for row in rows], default=str))
    finally:
        await conn.close()

asyncio.run(main())
'''


def read_account_drafts(account_id, day, creation_id=None):
    result = subprocess.run(
        ['sudo', '-n', 'docker', 'exec', '-i', 'wechat-batch-rewriter-api-1',
         'python', '-B', '-c', _READ_DRAFTS],
        input=json.dumps({'account_id': account_id, 'day': day, 'creation_id': creation_id}),
        text=True, encoding='utf-8', capture_output=True, timeout=30, check=True,
    )
    return json.loads(result.stdout)
