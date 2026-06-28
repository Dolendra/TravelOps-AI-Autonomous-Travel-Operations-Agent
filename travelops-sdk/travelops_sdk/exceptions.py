class TravelOpsError(Exception):
    """Base exception class for TravelOps AI SDK."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class AuthError(TravelOpsError):
    """Exception raised for 401 Unauthorized or 403 Forbidden errors."""

    pass


class ValidationError(TravelOpsError):
    """Exception raised for 400 Bad Request errors (validation or business policy)."""

    pass


class RateLimitError(TravelOpsError):
    """Exception raised for 429 Too Many Requests rate-limiting."""

    pass


class APIError(TravelOpsError):
    """Exception raised for 500 Internal Server errors."""

    pass
