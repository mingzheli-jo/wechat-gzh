"""Image provider abstraction."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageGenRequest:
    prompt: str
    reference_image_b64: str | None = None
    size: str = "1024x1024"
    negative_prompt: str | None = None


@dataclass
class ImageGenResult:
    url: str
    raw: dict[str, Any] = field(default_factory=dict)


class BaseImageProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, req: ImageGenRequest) -> ImageGenResult: ...
