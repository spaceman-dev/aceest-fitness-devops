"""Application level exceptions and their HTTP mappings."""

from __future__ import annotations


class ACEestError(Exception):
    """Base class for all domain errors raised by the service layer."""

    status_code = 400

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, str]:
        payload = {"error": self.__class__.__name__, "message": self.message}
        if self.field:
            payload["field"] = self.field
        return payload


class ValidationError(ACEestError):
    """Raised when caller supplied data fails domain validation."""

    status_code = 400


class NotFoundError(ACEestError):
    """Raised when a requested resource does not exist."""

    status_code = 404


class ConflictError(ACEestError):
    """Raised when a resource already exists (e.g. duplicate client name)."""

    status_code = 409
