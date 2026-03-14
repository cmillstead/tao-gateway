from pydantic import BaseModel


class SubnetHealthStatus(BaseModel):
    netuid: int
    last_sync: str | None = None
    is_stale: bool = True
    sync_error: str | None = None
