import warnings
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Literal

from pydantic import Field, model_validator
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
    database_url: str = Field(
        default="postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway", repr=False
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)

    # Pool sizes
    db_pool_size: int = 20
    db_max_overflow: int = 10
    redis_max_connections: int = 20

    # App
    app_name: str = "TaoGateway"
    app_version: str = _get_app_version()
    debug: bool = False
    log_format: Literal["console", "json"] = "console"

    # Auth
    jwt_secret_key: str = Field(default=_INSECURE_DEFAULT_SECRET, repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    auth_rate_limit_per_minute: int = 30

    # Rate limiting
    trusted_proxies: list[str] = []

    # CORS
    allowed_origins: list[str] = []

    # Bittensor
    wallet_name: str = "default"
    wallet_path: str = "~/.bittensor/wallets"
    hotkey_name: str = "default"
    subtensor_network: str = "finney"
    sn1_netuid: int = 1
    sn19_netuid: int = 19
    sn62_netuid: int = 62

    # Subnet toggle — only these are registered at startup
    enabled_subnets: list[int] = [32, 22]  # Default: new T&S subnets

    # SN32 config
    sn32_netuid: int = 32
    sn32_timeout_seconds: int = 30
    detection_rate_limit_per_minute: int = 60

    # SN22 config
    sn22_netuid: int = 22
    sn22_timeout_seconds: int = 30
    search_rate_limit_per_minute: int = 30

    metagraph_sync_interval_seconds: int = 120
    dendrite_timeout_seconds: int = 30
    sn19_timeout_seconds: int = 90
    sn62_timeout_seconds: int = 30
    enable_bittensor: bool = True

    # Miner quality scoring
    score_ema_alpha: float = Field(default=0.3, ge=0.0, le=1.0)
    score_flush_interval_seconds: int = Field(default=60, ge=1)
    quality_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    quality_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    score_retention_days: int = Field(default=30, ge=1)

    # Usage aggregation
    usage_aggregation_interval_seconds: int = Field(default=86400, ge=1)
    usage_retention_days: int = Field(default=90, ge=1)

    # Debug log cleanup
    debug_log_cleanup_interval_seconds: int = Field(default=3600, ge=1)
    debug_log_retention_hours: int = Field(default=48, ge=1)

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


def reset_settings() -> None:
    """Clear LRU cache and re-create the settings singleton.

    Used by tests that need to verify behavior with different settings.
    """
    global settings  # noqa: PLW0603
    get_settings.cache_clear()
    settings = get_settings()
