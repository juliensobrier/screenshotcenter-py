"""ScreenshotCenter Python SDK.

Thin HTTP wrapper around the ScreenshotCenter REST API.

Quick start::

    from screenshotcenter import ScreenshotCenterClient

    client = ScreenshotCenterClient(api_key="your_key")
    shot = client.screenshot.create(url="https://example.com", country="us")
    result = client.wait_for(shot["id"])
    print(result["url"])
"""

from .client import ScreenshotCenterClient
from .errors import (
    ApiError,
    ScreenshotCenterError,
    ScreenshotFailedError,
    TimeoutError,
)
from .types import (
    Account,
    Batch,
    BatchCreateParams,
    CreateParams,
    ListParams,
    Screenshot,
    SearchParams,
    ThumbnailParams,
)

__version__ = "1.0.0"

__all__ = [
    # Client
    "ScreenshotCenterClient",
    # Errors
    "ScreenshotCenterError",
    "ApiError",
    "TimeoutError",
    "ScreenshotFailedError",
    # Types
    "Account",
    "Batch",
    "BatchCreateParams",
    "CreateParams",
    "ListParams",
    "Screenshot",
    "SearchParams",
    "ThumbnailParams",
]
