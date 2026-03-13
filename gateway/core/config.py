from pydantic_settings import BaseSettings


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
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Bittensor
    wallet_name: str = "default"
    wallet_path: str = "~/.bittensor/wallets"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
