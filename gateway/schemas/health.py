from pydantic import BaseModel


class SubnetHealthStatus(BaseModel):
    netuid: int
    last_sync: str | None = None
    is_stale: bool = True
    sync_error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str = "unknown"
    redis: str = "unknown"
    metagraph: dict[str, SubnetHealthStatus] | None = None
