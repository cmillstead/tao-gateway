import warnings

import pytest


class TestJwtSecretValidation:
    def test_rejects_insecure_default_in_production(self) -> None:
        """The hardcoded insecure default is rejected when DEBUG=false."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
            Settings(
                debug=False,
                jwt_secret_key="change-me-in-production",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_rejects_docker_compose_default_in_production(self) -> None:
        """The docker-compose dev-only key is rejected in production."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                debug=False,
                jwt_secret_key="dev-only-insecure-key-do-not-use-in-prod",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_rejects_key_containing_insecure_markers(self) -> None:
        """Keys containing 'insecure', 'change-me', or 'do-not-use' are rejected."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                debug=False,
                jwt_secret_key="a]" * 20 + "insecure",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_accepts_strong_secret_in_production(self) -> None:
        """A 64-char hex secret passes validation."""
        from gateway.core.config import Settings

        s = Settings(
            debug=False,
            jwt_secret_key="a" * 64,
            database_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.jwt_secret_key == "a" * 64

    def test_allows_insecure_default_in_debug(self) -> None:
        """Debug mode allows the insecure default with a warning."""
        from gateway.core.config import Settings

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            with pytest.warns(UserWarning, match="insecure default"):
                s = Settings(
                    debug=True,
                    jwt_secret_key="change-me-in-production",
                    database_url="postgresql+asyncpg://x:x@localhost/x",
                )
        assert s.jwt_secret_key == "change-me-in-production"
