from typing import Literal

from pydantic import BaseModel, Field, model_validator

_ALLOWED_SIZES = {"256x256", "512x512", "1024x1024", "1024x1792", "1792x1024"}


class ImageGenerationRequest(BaseModel):
    model: str = Field(default="tao-sn19", min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=4000)
    n: Literal[1] = 1
    size: str = Field(default="1024x1024", max_length=20)
    style: Literal["natural", "vivid"] | None = None
    response_format: Literal["b64_json"] = "b64_json"

    @model_validator(mode="after")
    def validate_size(self) -> "ImageGenerationRequest":
        if self.size not in _ALLOWED_SIZES:
            raise ValueError(
                f"size must be one of: {', '.join(sorted(_ALLOWED_SIZES))}"
            )
        return self


class ImageData(BaseModel):
    b64_json: str | None = None
    url: str | None = None
    revised_prompt: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]
