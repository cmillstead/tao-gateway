import warnings
from importlib.metadata import version as _pkg_version

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_DEFAULT_SECRET = "change-me-in-production"


def _get_app_version() -> str:
    try:
        return _pkg_version("tao-gateway")
    except Exception:
        return "0.0.0-dev"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_name: str = "TaoGateway"
    app_version: str = _get_app_version()
    debug: bool = False

    # Auth
    jwt_secret_key: str = _INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    auth_rate_limit_per_minute: int = 30

    # Rate limiting
    trusted_proxies: list[str] = []

    # Bittensor
    wallet_name: str = "default"
    wallet_path: str = "~/.bittensor/wallets"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key == _INSECURE_DEFAULT_SECRET:
            if self.debug:
                warnings.warn(
                    "JWT_SECRET_KEY is using the insecure default. Set JWT_SECRET_KEY in your env.",
                    stacklevel=2,
                )
            else:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
        return self


settings = Settings()
