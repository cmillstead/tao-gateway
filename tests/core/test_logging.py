"""Tests for structured logging redaction."""

from gateway.core.logging import (
    _is_sensitive_key,
    _redact_sensitive_keys,
    _redact_value,
    redact_string_value,
)


class TestIsSensitiveKey:
    def test_exact_pattern_match(self) -> None:
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("auth_token") is True
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

    def test_token_count_fields_not_redacted(self) -> None:
        """Operational metadata like token counts must NOT be redacted (AC #4)."""
        assert _is_sensitive_key("token_count") is False
        assert _is_sensitive_key("total_tokens") is False
        assert _is_sensitive_key("max_tokens") is False
        assert _is_sensitive_key("prompt_tokens") is False

    def test_new_sensitive_patterns(self) -> None:
        """Subtask 1.1: Additional sensitive patterns added for Story 3.3."""
        assert _is_sensitive_key("mnemonic") is True
        assert _is_sensitive_key("wallet_mnemonic") is True
        assert _is_sensitive_key("seed_phrase") is True
        assert _is_sensitive_key("wallet_seed_phrase") is True
        assert _is_sensitive_key("seed") is False  # too broad — only seed_phrase matches
        assert _is_sensitive_key("private_key") is True
        assert _is_sensitive_key("access_token") is True
        assert _is_sensitive_key("refresh_token") is True


class TestRedactStringValue:
    """Subtask 1.2: Value-based redaction for sensitive patterns in string values."""

    def test_redacts_api_key_pattern_live(self) -> None:
        result = redact_string_value("Error for key tao_sk_live_abc123def456xyz")
        assert "tao_sk_live_" not in result or "****" in result
        assert "abc123def456xyz" not in result

    def test_redacts_api_key_pattern_test(self) -> None:
        result = redact_string_value("Key: tao_sk_test_somethingsecret")
        assert "somethingsecret" not in result

    def test_redacts_jwt_like_tokens(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
        result = redact_string_value(f"Failed with token {jwt}")
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_redacts_postgresql_connection_string(self) -> None:
        url = "postgresql+asyncpg://user:s3cret@host:5432/db"
        result = redact_string_value(f"Connection failed: {url}")
        assert "s3cret" not in result

    def test_redacts_redis_connection_string(self) -> None:
        url = "redis://admin:password123@redis-host:6379/0"
        result = redact_string_value(f"Redis error: {url}")
        assert "password123" not in result

    def test_preserves_safe_strings(self) -> None:
        safe = "Normal log message with no sensitive data"
        assert redact_string_value(safe) == safe

    def test_preserves_non_credential_urls(self) -> None:
        url = "redis://localhost:6379/0"
        assert redact_string_value(url) == url


class TestRedactValue:
    def test_redacts_sensitive_dict_keys(self) -> None:
        result = _redact_value({"api_key": "sk-123", "model": "gpt-4"})
        assert result == {"api_key": "****", "model": "gpt-4"}

    def test_redacts_nested_dicts(self) -> None:
        result = _redact_value({"outer": {"password": "secret", "name": "ok"}})
        assert result == {"outer": {"password": "****", "name": "ok"}}

    def test_redacts_in_lists(self) -> None:
        result = _redact_value([{"auth_token": "abc"}, {"status": "ok"}])
        assert result == [{"auth_token": "****"}, {"status": "ok"}]

    def test_depth_limit_increased(self) -> None:
        """Subtask 1.3: Depth limit increased from 5 to 10."""
        # Build a 9-level deep dict — should still redact at depth 9
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"password": "visible"}}}}}}}}}
        result = _redact_value(deep)
        assert result["a"]["b"]["c"]["d"]["e"]["f"]["g"]["h"] == {"password": "****"}

    def test_stops_dict_recursion_at_max_depth(self) -> None:
        """Beyond depth 10, dict/list recursion stops but key-based redaction is skipped."""
        # Build 12 levels deep so the innermost dict is at depth 11 (> 10)
        keys = list("abcdefghijkl")
        deep: dict = {"password": "visible"}
        for key in reversed(keys):
            deep = {key: deep}
        result = _redact_value(deep)
        # Navigate to the deepest level
        cursor = result
        for key in keys:
            cursor = cursor[key]
        # Key-based redaction stops at depth 10, so "password" key is NOT redacted
        assert cursor == {"password": "visible"}

    def test_string_redaction_beyond_max_depth(self) -> None:
        """Strings are leaf nodes — value-based redaction applies regardless of depth."""
        # Build 11 levels of dict nesting with a string as the direct leaf value.
        # At depth 11, the value is a string — isinstance(str) fires before depth check.
        keys = list("abcdefghijk")  # 11 keys → string at depth 11
        deep: str | dict = "Connection: postgresql+asyncpg://admin:s3cret@host/db"
        for key in reversed(keys):
            deep = {key: deep}
        result = _redact_value(deep)
        cursor = result
        for key in keys:
            cursor = cursor[key]
        # String value-based redaction still works even beyond depth 10
        assert "s3cret" not in cursor

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

    def test_redacts_sensitive_patterns_in_string_values(self) -> None:
        """Subtask 1.2: Value-based redaction on non-sensitive keys."""
        event_dict = {
            "event": "error",
            "error": "Connection failed: postgresql+asyncpg://user:secret@host/db",
        }
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert "secret" not in result["error"]

    def test_redacts_api_key_in_string_values(self) -> None:
        event_dict = {
            "event": "error",
            "detail": "Invalid key tao_sk_live_abc123def456 for org 5",
        }
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert "abc123def456" not in result["detail"]

    def test_redacts_jwt_in_string_values(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
        event_dict = {"event": "auth_failed", "error": f"Bad JWT: {jwt}"}
        result = _redact_sensitive_keys(None, "info", event_dict)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result["error"]


class TestSettingsRepr:
    """Subtask 1.4: Settings repr must not expose sensitive fields."""

    def test_database_url_hidden_in_repr(self) -> None:
        from gateway.core.config import Settings

        s = Settings(debug=True)
        r = repr(s)
        assert "tao:tao" not in r
        assert "postgresql" not in r

    def test_redis_url_hidden_in_repr(self) -> None:
        from gateway.core.config import Settings

        s = Settings(debug=True)
        r = repr(s)
        assert "redis://" not in r

    def test_jwt_secret_hidden_in_repr(self) -> None:
        from gateway.core.config import Settings

        s = Settings(debug=True)
        r = repr(s)
        assert s.jwt_secret_key not in r
