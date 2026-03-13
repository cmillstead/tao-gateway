import json

from gateway.subnets.sn1_text import SN1TextAdapter, TextGenStreamingSynapse


class TestTextGenStreamingSynapse:
    def test_default_fields(self):
        s = TextGenStreamingSynapse()
        assert s.roles == []
        assert s.messages == []
        assert s.completion == ""

    def test_with_data(self):
        s = TextGenStreamingSynapse(
            roles=["user"], messages=["Hello"]
        )
        assert s.roles == ["user"]
        assert s.messages == ["Hello"]

    def test_required_hash_fields(self):
        s = TextGenStreamingSynapse()
        assert "roles" in s.required_hash_fields
        assert "messages" in s.required_hash_fields


class TestSN1StreamingMethods:
    def test_to_streaming_synapse(self):
        adapter = SN1TextAdapter()
        request_data = {
            "messages": [
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hello"},
            ]
        }
        synapse = adapter.to_streaming_synapse(request_data)
        assert isinstance(synapse, TextGenStreamingSynapse)
        assert synapse.roles == ["system", "user"]
        assert synapse.messages == ["Be helpful", "Hello"]

    def test_format_stream_chunk(self):
        adapter = SN1TextAdapter()
        result = adapter.format_stream_chunk(
            "Hello", "chatcmpl-abc", "tao-sn1", 1234567890
        )
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result[6:].strip())
        assert data["object"] == "chat.completion.chunk"
        assert data["id"] == "chatcmpl-abc"
        assert data["model"] == "tao-sn1"
        assert data["choices"][0]["delta"]["content"] == "Hello"
        assert data["choices"][0]["finish_reason"] is None

    def test_format_stream_done(self):
        adapter = SN1TextAdapter()
        result = adapter.format_stream_done(
            "chatcmpl-abc", "tao-sn1", 1234567890
        )
        assert "finish_reason" in result
        assert '"stop"' in result
        assert "data: [DONE]\n\n" in result

    def test_format_stream_chunk_sanitizes_dangerous_content(self):
        adapter = SN1TextAdapter()
        result = adapter.format_stream_chunk(
            'Hello<script>alert("xss")</script> world',
            "chatcmpl-abc",
            "tao-sn1",
            1234567890,
        )
        data = json.loads(result[6:].strip())
        content = data["choices"][0]["delta"]["content"]
        assert "<script" not in content
        assert "alert" not in content
        assert "Hello" in content

    def test_format_stream_chunk_preserves_safe_content(self):
        adapter = SN1TextAdapter()
        result = adapter.format_stream_chunk(
            "Use <div> for layout",
            "chatcmpl-abc",
            "tao-sn1",
            1234567890,
        )
        data = json.loads(result[6:].strip())
        content = data["choices"][0]["delta"]["content"]
        assert "<div>" in content

    def test_sanitize_text_handles_none(self):
        adapter = SN1TextAdapter()
        assert adapter.sanitize_text(None) == ""  # type: ignore[arg-type]

    def test_sanitize_text_handles_empty(self):
        adapter = SN1TextAdapter()
        assert adapter.sanitize_text("") == ""
