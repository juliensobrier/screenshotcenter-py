"""Public type definitions for the ScreenshotCenter SDK.

All types are :class:`typing.TypedDict` subclasses — they are plain dicts at
runtime, so you can pass any ``dict`` returned by the API where these types
are expected.  The extra ``**kwargs`` / index signature means new API fields
introduced in future versions are automatically available without a library
update.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from typing import TypedDict


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

class Screenshot(TypedDict, total=False):
    """A screenshot object returned by the API."""

    id: int
    status: Literal["processing", "finished", "error"]
    url: str
    final_url: Optional[str]
    error: Optional[str]
    cost: int
    tag: List[str]
    created_at: str
    finished_at: Optional[str]
    country: str
    region: Optional[str]
    language: Optional[str]
    timezone: Optional[str]
    size: str
    shots: int
    html: bool
    pdf: bool
    video: bool
    has_html: bool
    has_pdf: bool
    has_video: bool
    video_format: Optional[str]


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

class Batch(TypedDict, total=False):
    """A batch job object returned by the API."""

    id: int
    status: Literal["processing", "finished", "error"]
    error: Optional[str]
    count: int
    processed: int
    failed: int
    zip_url: Optional[str]


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class Account(TypedDict, total=False):
    """Account information returned by ``account.info()``."""

    balance: int


# ---------------------------------------------------------------------------
# Request parameter helpers
# ---------------------------------------------------------------------------

class CreateParams(TypedDict, total=False):
    """Parameters for :meth:`~screenshotcenter.ScreenshotNamespace.create`.

    Only ``url`` is required.  All other fields are optional and forwarded
    to the API as query parameters, so future API parameters work without a
    library update — just pass them as keyword arguments.
    """

    url: str  # Required

    # Output & format
    size: Literal["screen", "page"]
    format: Literal["png", "jpeg", "webp"]
    width: int
    height: int
    html: bool
    pdf: bool
    video: bool

    # Geo
    country: str
    language: str
    timezone: str
    geo_enable: bool
    geo_latitude: float
    geo_longitude: float

    # Device
    screen_width: int
    screen_height: int
    device_name: str
    device_scale: int
    device_mobile: bool
    device_touch: bool
    device_landscape: bool

    # Request
    header: str
    referer: str
    cookie: str
    post_data: str
    user_agent: str

    # Automation
    delay: int
    max_wait: int
    script: str
    shots: int
    shot_interval: int
    cache: bool
    max_height: int
    target: str
    strict_ssl: bool
    hide_popups: bool
    hide_ads: bool

    # App
    dark: bool
    tag: Any
    priority: int


class ThumbnailParams(TypedDict, total=False):
    """Optional parameters for :meth:`~screenshotcenter.ScreenshotNamespace.thumbnail`."""

    format: Literal["png", "jpeg", "webp"]
    width: int
    height: int
    shot: int  # 1-based index for multi-shot screenshots


class ListParams(TypedDict, total=False):
    """Optional parameters for :meth:`~screenshotcenter.ScreenshotNamespace.list`."""

    limit: int
    offset: int
    status: str
    country: str
    tag: str


class SearchParams(TypedDict, total=False):
    """Parameters for :meth:`~screenshotcenter.ScreenshotNamespace.search`.

    ``url`` is required.
    """

    url: str  # Required
    limit: int
    offset: int


class BatchCreateParams(TypedDict, total=False):
    """Parameters for :meth:`~screenshotcenter.BatchNamespace.create`.

    ``country`` is required.
    """

    country: str  # Required
    size: Literal["screen", "page"]


# Re-export everything that callers might want to import directly.
__all__ = [
    "Account",
    "Batch",
    "BatchCreateParams",
    "CreateParams",
    "ListParams",
    "Screenshot",
    "SearchParams",
    "ThumbnailParams",
]
