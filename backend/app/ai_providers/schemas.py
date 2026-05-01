import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.ai_providers.models import Role


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1)
    models: list[str] = []
    enabled: bool = True


class ProviderUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    base_url: str
    models: list[str]
    enabled: bool


class RoleBindingIn(BaseModel):
    role: Role
    provider_id: uuid.UUID
    model: str


class RoleBindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: Role
    provider_id: uuid.UUID
    model: str
