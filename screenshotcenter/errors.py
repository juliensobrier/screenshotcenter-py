"""Custom error classes for the ScreenshotCenter SDK."""

from __future__ import annotations

from typing import Optional


class ScreenshotCenterError(Exception):
    """Base class for all ScreenshotCenter SDK errors."""


class ApiError(ScreenshotCenterError):
    """Raised when the API returns a non-2xx HTTP response.

    Attributes:
        status: HTTP status code.
        code:   Machine-readable error code returned by the API (e.g. ``"MISSING_PARAMS"``).
        fields: Validation error details keyed by field name.
    """

    def __init__(
        self,
        message: str,
        status: int,
        code: Optional[str] = None,
        fields: Optional[dict] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.fields: dict = fields or {}

    def __repr__(self) -> str:
        return f"ApiError(status={self.status}, code={self.code!r}, message={str(self)!r})"


class TimeoutError(ScreenshotCenterError):
    """Raised when :meth:`~screenshotcenter.ScreenshotCenterClient.wait_for`
    or :meth:`~screenshotcenter.BatchNamespace.wait_for` exceeds the deadline.

    Attributes:
        screenshot_id: ID of the screenshot or batch that timed out.
        timeout_ms:    Timeout that was exceeded, in milliseconds.
    """

    def __init__(self, screenshot_id: int, timeout_ms: int) -> None:
        super().__init__(
            f"Screenshot {screenshot_id} did not complete within {timeout_ms}ms"
        )
        self.screenshot_id = screenshot_id
        self.timeout_ms = timeout_ms


class ScreenshotFailedError(ScreenshotCenterError):
    """Raised when a screenshot reaches ``status: "error"``.

    Attributes:
        screenshot_id: ID of the failed screenshot.
        error:         Error message from the API, if any.
    """

    def __init__(self, screenshot_id: int, error: Optional[str] = None) -> None:
        super().__init__(
            f"Screenshot {screenshot_id} failed: {error or 'unknown error'}"
        )
        self.screenshot_id = screenshot_id
        self.error = error
