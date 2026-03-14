import pytest

from gateway.core.exceptions import MinerInvalidResponseError
from gateway.subnets.sn62_code import CodeSynapse, SN62CodeAdapter


class TestCodeSynapse:
    def test_creation_defaults(self):
        synapse = CodeSynapse()
        assert synapse.prompt == ""
        assert synapse.language == ""
        assert synapse.context == ""
        assert synapse.code == ""
        assert synapse.completion_language == ""
        assert synapse.required_hash_fields == ["prompt"]

    def test_creation_with_values(self):
        synapse = CodeSynapse(
            prompt="Write a fibonacci function",
            language="python",
            context="# existing module code",
        )
        assert synapse.prompt == "Write a fibonacci function"
        assert synapse.language == "python"
        assert synapse.context == "# existing module code"


class TestSN62CodeAdapter:
    def setup_method(self):
        self.adapter = SN62CodeAdapter()

    def test_get_config(self):
        config = self.adapter.get_config()
        assert config.netuid == 62
        assert config.subnet_name == "sn62"
        assert config.timeout_seconds == 30

    def test_to_synapse(self):
        request_data = {
            "prompt": "Write hello world",
            "language": "python",
            "context": "# utils module",
        }
        synapse = self.adapter.to_synapse(request_data)
        assert isinstance(synapse, CodeSynapse)
        assert synapse.prompt == "Write hello world"
        assert synapse.language == "python"
        assert synapse.context == "# utils module"

    def test_to_synapse_defaults(self):
        request_data = {"prompt": "Write code"}
        synapse = self.adapter.to_synapse(request_data)
        assert synapse.language == ""
        assert synapse.context == ""

    def test_to_synapse_none_context(self):
        request_data = {"prompt": "Write code", "language": "go", "context": None}
        synapse = self.adapter.to_synapse(request_data)
        assert synapse.context == ""

    def test_from_response_success(self):
        synapse = CodeSynapse(
            code="def hello():\n    print('Hello')",
            completion_language="python",
        )
        request_data = {"model": "tao-sn62", "language": "python"}
        result = self.adapter.from_response(synapse, request_data)

        assert result["object"] == "code.completion"
        assert result["model"] == "tao-sn62"
        assert "id" in result
        assert result["id"].startswith("codecmpl-")
        assert isinstance(result["created"], int)
        assert len(result["choices"]) == 1
        assert result["choices"][0]["code"] == "def hello():\n    print('Hello')"
        assert result["choices"][0]["language"] == "python"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["choices"][0]["index"] == 0

    def test_from_response_empty_code_raises(self):
        synapse = CodeSynapse(code="")
        request_data = {"model": "tao-sn62"}
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.from_response(synapse, request_data)

    def test_from_response_uses_request_language_as_fallback(self):
        synapse = CodeSynapse(code="console.log('hi')", completion_language="")
        request_data = {"model": "tao-sn62", "language": "javascript"}
        result = self.adapter.from_response(synapse, request_data)
        assert result["choices"][0]["language"] == "javascript"

    def test_from_response_prefers_miner_language(self):
        synapse = CodeSynapse(code="print('hi')", completion_language="python3")
        request_data = {"model": "tao-sn62", "language": "python"}
        result = self.adapter.from_response(synapse, request_data)
        assert result["choices"][0]["language"] == "python3"

    def test_sanitize_output_preserves_code_with_angle_brackets(self):
        """Code must NOT be HTML-sanitized — nh3 mangles <, >, <=, generics."""
        code_with_angles = "if n <= 1:\n    return n\nvector<int> v;"
        response_data = {
            "id": "codecmpl-test",
            "object": "code.completion",
            "created": 123,
            "model": "tao-sn62",
            "choices": [
                {
                    "index": 0,
                    "code": code_with_angles,
                    "language": "python",
                    "finish_reason": "stop",
                }
            ],
        }
        result = self.adapter.sanitize_output(response_data)
        # Code must pass through untouched — no HTML entity encoding
        assert result["choices"][0]["code"] == code_with_angles

    def test_sanitize_output_does_not_strip_html_from_code(self):
        """Code field is not sanitized — consumers handle XSS in their rendering."""
        code = '<script>alert("hi")</script>print("hello")'
        response_data = {
            "id": "codecmpl-test",
            "object": "code.completion",
            "created": 123,
            "model": "tao-sn62",
            "choices": [
                {
                    "index": 0,
                    "code": code,
                    "language": "python",
                    "finish_reason": "stop",
                }
            ],
        }
        result = self.adapter.sanitize_output(response_data)
        # Code passes through as-is — API returns JSON, not HTML
        assert result["choices"][0]["code"] == code

    def test_sanitize_output_strips_html_from_language(self):
        response_data = {
            "id": "codecmpl-test",
            "object": "code.completion",
            "created": 123,
            "model": "tao-sn62",
            "choices": [
                {
                    "index": 0,
                    "code": "x = 1",
                    "language": '<img src=x onerror=alert(1)>python',
                    "finish_reason": "stop",
                }
            ],
        }
        result = self.adapter.sanitize_output(response_data)
        assert "<img" not in result["choices"][0]["language"]
        assert "python" in result["choices"][0]["language"]

    def test_sanitize_output_preserves_clean_code(self):
        code = "def fib(n):\n    if n == 1:\n        return n\n    return fib(n-1) + fib(n-2)"
        response_data = {
            "id": "codecmpl-test",
            "object": "code.completion",
            "created": 123,
            "model": "tao-sn62",
            "choices": [
                {
                    "index": 0,
                    "code": code,
                    "language": "python",
                    "finish_reason": "stop",
                }
            ],
        }
        result = self.adapter.sanitize_output(response_data)
        assert result["choices"][0]["code"] == code

    def test_streaming_not_supported(self):
        with pytest.raises(NotImplementedError):
            self.adapter.to_streaming_synapse({})

        with pytest.raises(NotImplementedError):
            self.adapter.format_stream_chunk("test", "id", "model", 123)

        with pytest.raises(NotImplementedError):
            self.adapter.format_stream_done("id", "model", 123)
