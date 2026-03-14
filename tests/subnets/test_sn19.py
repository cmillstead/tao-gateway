import base64

import pytest

from gateway.core.exceptions import MinerInvalidResponseError
from gateway.subnets.sn19_image import ImageGenSynapse, SN19ImageAdapter

# Minimal valid PNG: 8-byte header
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
_VALID_PNG_B64 = base64.b64encode(_PNG_HEADER).decode()

# Minimal valid JPEG: SOI marker + padding
_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 28
_VALID_JPEG_B64 = base64.b64encode(_JPEG_HEADER).decode()

# Invalid image data (plain text)
_INVALID_B64 = base64.b64encode(b"This is not an image at all").decode()


class TestImageGenSynapse:
    def test_creation_defaults(self):
        synapse = ImageGenSynapse()
        assert synapse.prompt == ""
        assert synapse.size == "1024x1024"
        assert synapse.style == "natural"
        assert synapse.image_data == ""
        assert synapse.revised_prompt == ""
        assert synapse.required_hash_fields == ["prompt"]

    def test_creation_with_values(self):
        synapse = ImageGenSynapse(
            prompt="A sunset",
            size="512x512",
            style="vivid",
        )
        assert synapse.prompt == "A sunset"
        assert synapse.size == "512x512"
        assert synapse.style == "vivid"


class TestSN19ImageAdapter:
    def setup_method(self):
        self.adapter = SN19ImageAdapter()

    def test_get_config(self):
        config = self.adapter.get_config()
        assert config.netuid == 19
        assert config.subnet_name == "sn19"
        assert config.timeout_seconds == 90

    def test_to_synapse(self):
        request_data = {
            "prompt": "A beautiful mountain",
            "size": "512x512",
            "style": "vivid",
        }
        synapse = self.adapter.to_synapse(request_data)
        assert isinstance(synapse, ImageGenSynapse)
        assert synapse.prompt == "A beautiful mountain"
        assert synapse.size == "512x512"
        assert synapse.style == "vivid"

    def test_to_synapse_defaults(self):
        request_data = {"prompt": "A cat"}
        synapse = self.adapter.to_synapse(request_data)
        assert synapse.size == "1024x1024"
        assert synapse.style == "natural"

    def test_from_response_b64_json(self):
        synapse = ImageGenSynapse(
            image_data=_VALID_PNG_B64,
            revised_prompt="A stunning sunset",
        )
        request_data = {"response_format": "b64_json", "model": "tao-sn19"}
        result = self.adapter.from_response(synapse, request_data)

        assert "created" in result
        assert isinstance(result["created"], int)
        assert len(result["data"]) == 1
        assert result["data"][0]["b64_json"] == _VALID_PNG_B64
        assert result["data"][0]["revised_prompt"] == "A stunning sunset"
        assert result["data"][0].get("url") is None

    def test_from_response_empty_image_data(self):
        synapse = ImageGenSynapse(image_data="")
        request_data = {"response_format": "b64_json"}
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.from_response(synapse, request_data)

    def test_from_response_no_revised_prompt(self):
        synapse = ImageGenSynapse(image_data=_VALID_PNG_B64)
        request_data = {"response_format": "b64_json"}
        result = self.adapter.from_response(synapse, request_data)
        assert result["data"][0]["revised_prompt"] is None

    def test_sanitize_output_strips_html_from_revised_prompt(self):
        response_data = {
            "created": 123,
            "data": [
                {
                    "b64_json": _VALID_PNG_B64,
                    "revised_prompt": '<script>alert("xss")</script>A beautiful sunset',
                }
            ],
        }
        result = self.adapter.sanitize_output(response_data)
        prompt = result["data"][0]["revised_prompt"]
        assert "<script>" not in prompt
        assert "A beautiful sunset" in prompt

    def test_sanitize_output_validates_png_header(self):
        response_data = {
            "created": 123,
            "data": [{"b64_json": _VALID_PNG_B64, "revised_prompt": None}],
        }
        # Should not raise
        self.adapter.sanitize_output(response_data)

    def test_sanitize_output_validates_jpeg_header(self):
        response_data = {
            "created": 123,
            "data": [{"b64_json": _VALID_JPEG_B64, "revised_prompt": None}],
        }
        # Should not raise
        self.adapter.sanitize_output(response_data)

    def test_sanitize_output_rejects_invalid_image(self):
        response_data = {
            "created": 123,
            "data": [{"b64_json": _INVALID_B64, "revised_prompt": None}],
        }
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.sanitize_output(response_data)

    def test_sanitize_output_rejects_non_base64(self):
        response_data = {
            "created": 123,
            "data": [{"b64_json": "not-valid-base64!!!", "revised_prompt": None}],
        }
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.sanitize_output(response_data)

    def test_streaming_not_supported(self):
        with pytest.raises(NotImplementedError):
            self.adapter.to_streaming_synapse({})

        with pytest.raises(NotImplementedError):
            self.adapter.format_stream_chunk("test", "id", "model", 123)

        with pytest.raises(NotImplementedError):
            self.adapter.format_stream_done("id", "model", 123)
