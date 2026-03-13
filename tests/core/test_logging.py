"""Tests for structured logging redaction."""

from gateway.core.logging import _is_sensitive_key, _redact_sensitive_keys, _redact_value


class TestIsSensitiveKey:
    def test_exact_pattern_match(self) -> None:
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("token") is True
        assert _is_sensitive_key("password") is True

    def test_case_insensitive(self) -> None:
        assert _is_sensitive_key("API_KEY") is True
        assert _is_sensitive_key("Authorization") is True
        assert _is_sensitive_key("JWT_SECRET") is True

    def test_substring_match(self) -> None:
        """Pattern matches anywhere in the key name."""
        assert _is_sensitive_key("x_api_key_header") is True
        assert _is_sensitive_key("auth_token_value") is True

    def test_non_sensitive_keys(self) -> None:
        assert _is_sensitive_key("model") is False
        assert _is_sensitive_key("status") is False
        assert _is_sensitive_key("elapsed_ms") is False


class TestRedactValue:
    def test_redacts_sensitive_dict_keys(self) -> None:
        result = _redact_value({"api_key": "sk-123", "model": "gpt-4"})
        assert result == {"api_key": "****", "model": "gpt-4"}

    def test_redacts_nested_dicts(self) -> None:
        result = _redact_value({"outer": {"password": "secret", "name": "ok"}})
        assert result == {"outer": {"password": "****", "name": "ok"}}

    def test_redacts_in_lists(self) -> None:
        result = _redact_value([{"token": "abc"}, {"status": "ok"}])
        assert result == [{"token": "****"}, {"status": "ok"}]

    def test_stops_at_max_depth(self) -> None:
        """Beyond depth 5, values pass through unredacted."""
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"password": "visible"}}}}}}}
        result = _redact_value(deep)
        # depth 0->a, 1->b, 2->c, 3->d, 4->e, 5->f, 6->password exceeds limit
        assert result["a"]["b"]["c"]["d"]["e"]["f"] == {"password": "visible"}

    def test_scalar_passthrough(self) -> None:
        assert _redact_value("hello") == "hello"
        assert _redact_value(42) == 42
        assert _redact_value(None) is None


class TestRedactSensitiveKeys:
    def test_redacts_top_level_sensitive_keys(self) -> None:
        event_dict = {"event": "login", "password": "secret123", "user": "alice"}
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert result["password"] == "****"
        assert result["user"] == "alice"

    def test_redacts_nested_structures(self) -> None:
        event_dict = {"event": "request", "headers": {"authorization": "Bearer xyz"}}
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert result["headers"] == {"authorization": "****"}

    def test_preserves_non_sensitive_keys(self) -> None:
        event_dict = {"event": "startup", "version": "1.0", "debug": True}
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert result == event_dict
