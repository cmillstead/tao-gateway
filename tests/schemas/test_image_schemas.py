import pytest
from pydantic import ValidationError

from gateway.schemas.images import ImageData, ImageGenerationRequest, ImageGenerationResponse


class TestImageGenerationRequest:
    def test_valid_minimal(self):
        req = ImageGenerationRequest(prompt="A sunset over mountains")
        assert req.model == "tao-sn19"
        assert req.prompt == "A sunset over mountains"
        assert req.n == 1
        assert req.size == "1024x1024"
        assert req.style is None
        assert req.response_format == "b64_json"

    def test_valid_all_fields(self):
        req = ImageGenerationRequest(
            model="tao-sn19",
            prompt="A cat",
            n=1,
            size="512x512",
            style="vivid",
            response_format="b64_json",
        )
        assert req.n == 1
        assert req.size == "512x512"
        assert req.style == "vivid"
        assert req.response_format == "b64_json"

    def test_prompt_required(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest()

    def test_prompt_empty_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="")

    def test_prompt_max_length(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="x" * 4001)

    def test_prompt_at_max_length(self):
        req = ImageGenerationRequest(prompt="x" * 4000)
        assert len(req.prompt) == 4000

    def test_n_must_be_1(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", n=2)

    def test_n_zero_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", n=0)

    def test_invalid_response_format(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", response_format="png")

    def test_url_response_format_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", response_format="url")

    def test_model_empty_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", model="")

    def test_invalid_size_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", size="banana")

    def test_valid_sizes(self):
        for size in ("256x256", "512x512", "1024x1024", "1024x1792", "1792x1024"):
            req = ImageGenerationRequest(prompt="test", size=size)
            assert req.size == size

    def test_style_natural(self):
        req = ImageGenerationRequest(prompt="test", style="natural")
        assert req.style == "natural"

    def test_style_vivid(self):
        req = ImageGenerationRequest(prompt="test", style="vivid")
        assert req.style == "vivid"

    def test_style_invalid_rejected(self):
        with pytest.raises(ValidationError):
            ImageGenerationRequest(prompt="test", style="abstract")


class TestImageData:
    def test_b64_json_only(self):
        data = ImageData(b64_json="abc123")
        assert data.b64_json == "abc123"
        assert data.url is None
        assert data.revised_prompt is None

    def test_url_only(self):
        data = ImageData(url="https://example.com/image.png")
        assert data.url == "https://example.com/image.png"
        assert data.b64_json is None

    def test_with_revised_prompt(self):
        data = ImageData(b64_json="abc", revised_prompt="A beautiful sunset")
        assert data.revised_prompt == "A beautiful sunset"

    def test_all_none(self):
        data = ImageData()
        assert data.b64_json is None
        assert data.url is None
        assert data.revised_prompt is None


class TestImageGenerationResponse:
    def test_valid_response(self):
        resp = ImageGenerationResponse(
            created=1234567890,
            data=[ImageData(b64_json="abc123")],
        )
        assert resp.created == 1234567890
        assert len(resp.data) == 1

    def test_multiple_images(self):
        resp = ImageGenerationResponse(
            created=1234567890,
            data=[
                ImageData(b64_json="img1"),
                ImageData(b64_json="img2"),
            ],
        )
        assert len(resp.data) == 2

    def test_empty_data_list(self):
        resp = ImageGenerationResponse(created=1234567890, data=[])
        assert resp.data == []
