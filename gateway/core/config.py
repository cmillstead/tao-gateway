import warnings
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_DEFAULT_SECRET = "change-me-in-production"
_MIN_JWT_SECRET_LENGTH = 32
_INSECURE_MARKERS = ["change-me", "insecure", "do-not-use", "example", "placeholder"]


def _get_app_version() -> str:
    try:
        return _pkg_version("tao-gateway")
    except PackageNotFoundError:
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
    hotkey_name: str = "default"
    subtensor_network: str = "finney"
    sn1_netuid: int = 1
    metagraph_sync_interval_seconds: int = 120
    dendrite_timeout_seconds: int = 30
    enable_bittensor: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        secret = self.jwt_secret_key
        if secret == _INSECURE_DEFAULT_SECRET:
            if self.debug:
                warnings.warn(
                    "JWT_SECRET_KEY is using the insecure default. Set JWT_SECRET_KEY in your env.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        elif not self.debug:
            lower = secret.lower()
            if any(marker in lower for marker in _INSECURE_MARKERS):
                raise ValueError(
                    "JWT_SECRET_KEY contains an insecure marker and cannot be used in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            if len(secret) < _MIN_JWT_SECRET_LENGTH:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_LENGTH} characters. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Module-level convenience alias — instantiated at first import.
# lru_cache ensures only one Settings instance exists across the process.
settings = get_settings()
