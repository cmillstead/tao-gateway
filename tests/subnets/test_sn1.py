from unittest.mock import MagicMock


class TestTextGenSynapse:
    def test_synapse_default_fields(self):
        from gateway.subnets.sn1_text import TextGenSynapse

        s = TextGenSynapse()
        assert s.roles == []
        assert s.messages == []
        assert s.completion == ""

    def test_synapse_with_data(self):
        from gateway.subnets.sn1_text import TextGenSynapse

        s = TextGenSynapse(
            roles=["user", "system"],
            messages=["Hello", "Be helpful"],
        )
        assert s.roles == ["user", "system"]
        assert s.messages == ["Hello", "Be helpful"]

    def test_synapse_required_hash_fields(self):
        from gateway.subnets.sn1_text import TextGenSynapse

        s = TextGenSynapse()
        assert "roles" in s.required_hash_fields
        assert "messages" in s.required_hash_fields


class TestSN1TextAdapterToSynapse:
    def test_converts_messages_to_parallel_arrays(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        request_data = {
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]
        }
        synapse = adapter.to_synapse(request_data)
        assert synapse.roles == ["system", "user"]
        assert synapse.messages == ["You are helpful", "Hello"]

    def test_single_user_message(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        synapse = adapter.to_synapse({"messages": [{"role": "user", "content": "Hi"}]})
        assert synapse.roles == ["user"]
        assert synapse.messages == ["Hi"]


class TestSN1TextAdapterFromResponse:
    def test_wraps_completion_in_openai_format(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        mock_synapse = MagicMock()
        mock_synapse.completion = "Hello! I'm a decentralized AI assistant."

        result = adapter.from_response(mock_synapse, {"model": "tao-sn1"})

        assert result["object"] == "chat.completion"
        assert result["model"] == "tao-sn1"
        assert result["id"].startswith("chatcmpl-")
        assert result["choices"][0]["message"]["role"] == "assistant"
        expected = "Hello! I'm a decentralized AI assistant."
        assert result["choices"][0]["message"]["content"] == expected
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 0
        assert result["usage"]["completion_tokens"] == 0
        assert result["usage"]["total_tokens"] == 0
        assert isinstance(result["created"], int)

    def test_response_id_is_unique(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        mock_synapse = MagicMock()
        mock_synapse.completion = "test"
        req = {"model": "tao-sn1"}

        r1 = adapter.from_response(mock_synapse, req)
        r2 = adapter.from_response(mock_synapse, req)
        assert r1["id"] != r2["id"]

    def test_response_echoes_requested_model(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        mock_synapse = MagicMock()
        mock_synapse.completion = "test"

        result = adapter.from_response(mock_synapse, {"model": "sn1-text"})
        assert result["model"] == "sn1-text"


class TestSN1TextAdapterSanitize:
    def test_strips_script_tags_with_content(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello<script>alert('xss')</script> world"
                    }
                }
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<script" not in content
        assert "alert" not in content
        assert content == "Hello world"

    def test_strips_null_bytes(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [{"message": {"content": "Hello\x00World"}}]
        }
        result = adapter.sanitize_output(response_data)
        assert "\x00" not in result["choices"][0]["message"]["content"]

    def test_strips_img_with_event_handler(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": 'Hi<img onerror="alert(1)" src=x> there'}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "onerror" not in content
        assert "Hi" in content
        assert "there" in content

    def test_strips_iframe_tags(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": 'Before<iframe src="evil.com"></iframe>After'}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<iframe" not in content
        assert "BeforeAfter" in content

    def test_strips_svg_onload(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": '<svg onload="alert(1)">x</svg>safe'}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<svg" not in content
        assert "safe" in content

    def test_clean_content_unchanged(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [{"message": {"content": "Normal safe content"}}]
        }
        result = adapter.sanitize_output(response_data)
        assert result["choices"][0]["message"]["content"] == "Normal safe content"

    def test_strips_all_html_tags(self):
        """nh3 strips ALL HTML tags — no safe tags in miner output."""
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": "Use <div> for layout and <span> for inline"}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<div>" not in content
        assert "<span>" not in content
        assert "Use" in content
        assert "layout" in content

    def test_handles_angle_brackets_in_text(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": "if x < 10 and y > 5, then z = x + y"}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        # nh3 may entity-encode angle brackets in ambiguous contexts
        assert "10" in content
        assert "then z = x + y" in content

    def test_strips_javascript_protocol_in_href(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": 'Click <a href="javascript:alert(1)">here</a> now'}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "javascript:" not in content
        assert "here" in content

    def test_strips_style_tag_with_content(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": "Hello<style>.evil{background:url(evil)}</style> world"}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<style" not in content
        assert ".evil" not in content
        assert content == "Hello world"

    def test_handles_none_completion(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [{"message": {"content": None}}]
        }
        result = adapter.sanitize_output(response_data)
        assert result["choices"][0]["message"]["content"] == ""

    def test_strips_html_in_code_examples(self):
        """All HTML tags stripped — even in code examples from miners."""
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        response_data = {
            "choices": [
                {"message": {"content": "Here is HTML: <div class='main'><p>Hello</p></div>"}}
            ]
        }
        result = adapter.sanitize_output(response_data)
        content = result["choices"][0]["message"]["content"]
        assert "<div" not in content
        assert "<p>" not in content
        assert "Hello" in content


class TestSN1TextAdapterConfig:
    def test_returns_sn1_config(self):
        from gateway.subnets.sn1_text import SN1TextAdapter

        adapter = SN1TextAdapter()
        config = adapter.get_config()
        assert config.subnet_name == "sn1"
        assert config.netuid == 1  # default from settings
        assert config.timeout_seconds > 0
