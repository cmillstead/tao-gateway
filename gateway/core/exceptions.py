class GatewayError(Exception):
    """Base exception for all gateway errors."""

    def __init__(
        self, message: str, status_code: int = 500, error_type: str = "internal_error"
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message)


class MinerTimeoutError(GatewayError):
    def __init__(self, miner_uid: int, subnet: str) -> None:
        super().__init__(f"Miner {miner_uid} timed out on {subnet}", 504, "gateway_timeout")
        self.miner_uid = miner_uid
        self.subnet = subnet


class MinerInvalidResponseError(GatewayError):
    def __init__(self, miner_uid: int, subnet: str) -> None:
        super().__init__(
            f"Miner {miner_uid} returned invalid response on {subnet}",
            502,
            "bad_gateway",
        )
        self.miner_uid = miner_uid
        self.subnet = subnet


class SubnetUnavailableError(GatewayError):
    def __init__(self, subnet: str) -> None:
        super().__init__(f"Subnet {subnet} is unavailable", 503, "subnet_unavailable")
        self.subnet = subnet


class RateLimitExceededError(GatewayError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, 429, "rate_limit_exceeded")


class AuthenticationError(GatewayError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, 401, "authentication_error")
