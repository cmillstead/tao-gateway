import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_name: str = "TaoGateway"
    app_version: str = "0.1.0"
    debug: bool = False

    # Auth
    jwt_secret_key: str = _INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Bittensor
    wallet_name: str = "default"
    wallet_path: str = "~/.bittensor/wallets"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def warn_insecure_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key == _INSECURE_DEFAULT_SECRET:
            warnings.warn(
                "JWT_SECRET_KEY is using the insecure default. Set JWT_SECRET_KEY in your env.",
                stacklevel=2,
            )
        return self


settings = Settings()
