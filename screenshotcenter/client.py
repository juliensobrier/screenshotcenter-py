"""ScreenshotCenter Python SDK — main client."""

from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .errors import ApiError, ScreenshotFailedError
from .errors import TimeoutError as WaitTimeoutError
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

DEFAULT_BASE_URL = "https://api.screenshotcenter.com/api/v1"
DEFAULT_TIMEOUT = 30          # seconds
DEFAULT_POLL_INTERVAL = 2.0   # seconds
DEFAULT_WAIT_TIMEOUT = 120.0  # seconds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_query(params: Dict[str, Any]) -> str:
    """Encode a dict as a URL query string.

    Lists of primitives are expanded as repeated keys (``tag=a&tag=b``).
    Lists containing dicts (e.g. ``steps``, ``trackers``) are JSON-serialised
    as a single value.  Dicts are JSON-serialised.  ``None`` values are skipped.
    """
    parts: list = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, list):
            if any(isinstance(item, dict) for item in v):
                parts.append((k, json.dumps(v)))
            else:
                for item in v:
                    parts.append((k, str(item)))
        elif isinstance(v, dict):
            parts.append((k, json.dumps(v)))
        elif isinstance(v, bool):
            parts.append((k, "true" if v else "false"))
        else:
            parts.append((k, str(v)))
    return urllib.parse.urlencode(parts)


def _encode_multipart(
    fields: Dict[str, str],
    files: Dict[str, tuple],
) -> tuple[bytes, str]:
    """Encode ``fields`` and ``files`` as ``multipart/form-data``.

    Returns ``(body_bytes, content_type_header)``.
    Each entry in ``files`` is ``(filename, content_bytes, mime_type)``.
    """
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )

    for name, (filename, content, mime) in files.items():
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
        parts.append(header + content + b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ScreenshotCenterClient:
    """Thin HTTP wrapper around the ScreenshotCenter REST API.

    Args:
        api_key:  Your ScreenshotCenter API key (required).
        base_url: Override the API base URL.  Defaults to the production
                  endpoint ``https://api.screenshotcenter.com/api/v1``.
        timeout:  Per-request timeout in seconds (default: 30).

    Example::

        from screenshotcenter import ScreenshotCenterClient

        client = ScreenshotCenterClient(api_key="your_key")
        shot = client.screenshot.create(url="https://example.com")
        result = client.wait_for(shot["id"])
        print(result["url"])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self.screenshot = ScreenshotNamespace(self)
        self.batch = BatchNamespace(self)
        self.crawl = CrawlNamespace(self)
        self.account = AccountNamespace(self)

    # ------------------------------------------------------------------
    # Internal request helpers (used by namespaces)
    # ------------------------------------------------------------------

    def _url(self, endpoint: str, params: Dict[str, Any]) -> str:
        all_params = {"key": self._api_key, **params}
        qs = _build_query(all_params)
        return f"{self._base_url}{endpoint}?{qs}"

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = self._url(endpoint, params or {})
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
                ct = resp.getheader("Content-Type", "")
        except urllib.error.HTTPError as exc:
            self._raise_api_error(exc)
        return self._parse(body, ct)

    def _get_bytes(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> bytes:
        url = self._url(endpoint, params or {})
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            self._raise_api_error(exc)

    def _post(
        self,
        endpoint: str,
        body: bytes,
        content_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = self._url(endpoint, params or {})
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_body = resp.read()
                ct = resp.getheader("Content-Type", "")
        except urllib.error.HTTPError as exc:
            self._raise_api_error(exc)
        return self._parse(resp_body, ct)

    @staticmethod
    def _raise_api_error(exc: urllib.error.HTTPError) -> None:
        raw = exc.read()
        try:
            data = json.loads(raw)
            msg = data.get("error") or str(exc)
            code = data.get("code")
            fields = data.get("fields")
        except Exception:
            msg = str(exc)
            code = None
            fields = None
        raise ApiError(msg, exc.code, code, fields) from None

    @staticmethod
    def _parse(body: bytes, content_type: str) -> Any:
        if "application/json" not in content_type:
            return body.decode("utf-8")
        data = json.loads(body)
        if isinstance(data, dict) and "success" in data:
            if not data["success"]:
                raise ApiError(
                    data.get("error") or "API request failed",
                    200,
                    data.get("code"),
                    data.get("fields"),
                )
            return data.get("data")
        return data

    # ------------------------------------------------------------------
    # Polling helper
    # ------------------------------------------------------------------

    def wait_for(
        self,
        screenshot_id: int,
        interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
    ) -> Screenshot:
        """Poll until a screenshot reaches ``finished`` or ``error``.

        Args:
            screenshot_id: ID returned by :meth:`screenshot.create`.
            interval:      Seconds between polls (default: 2).
            timeout:       Maximum total wait in seconds (default: 120).

        Returns:
            The final :class:`~screenshotcenter.types.Screenshot` dict.

        Raises:
            :class:`~screenshotcenter.errors.ScreenshotFailedError`:
                The screenshot reached ``status: "error"``.
            :class:`~screenshotcenter.errors.TimeoutError`:
                The screenshot did not finish before ``timeout`` seconds.

        Example::

            shot = client.screenshot.create(url="https://example.com")
            result = client.wait_for(shot["id"], timeout=60)
            print(result["url"])
        """
        deadline = time.monotonic() + timeout
        while True:
            s = self.screenshot.info(screenshot_id)
            if s["status"] == "finished":
                return s
            if s["status"] == "error":
                raise ScreenshotFailedError(screenshot_id, s.get("error"))
            if time.monotonic() + interval > deadline:
                raise WaitTimeoutError(screenshot_id, int(timeout * 1000))
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Screenshot namespace
# ---------------------------------------------------------------------------

class ScreenshotNamespace:
    """All screenshot-related API methods.

    Access via ``client.screenshot.*``.
    """

    def __init__(self, client: ScreenshotCenterClient) -> None:
        self._client = client

    def create(self, url: str, **kwargs: Any) -> Screenshot:
        """Request a new screenshot.

        Args:
            url:      Page URL to capture (required).
            **kwargs: Any additional API parameters
                      (``country``, ``pdf``, ``shots``, etc.).

        Returns:
            A :class:`~screenshotcenter.types.Screenshot` dict.

        Example::

            shot = client.screenshot.create(
                url="https://example.com",
                country="fr",
                pdf=True,
            )
        """
        if not url:
            raise ValueError('"url" is required')
        return self._client._get("/screenshot/create", {"url": url, **kwargs})

    def info(self, screenshot_id: int) -> Screenshot:
        """Get screenshot status and details.

        Example::

            shot = client.screenshot.info(12345)
            print(shot["status"])
        """
        return self._client._get("/screenshot/info", {"id": screenshot_id})

    def list(self, **kwargs: Any) -> List[Screenshot]:
        """List recent screenshots.

        Args:
            **kwargs: ``limit``, ``offset``, ``status``, ``country``, ``tag``.

        Example::

            shots = client.screenshot.list(limit=10)
        """
        return self._client._get("/screenshot/list", kwargs)

    def search(self, url: str, **kwargs: Any) -> List[Screenshot]:
        """Search screenshots by URL pattern.

        Args:
            url:      URL pattern to search for (required).
            **kwargs: ``limit``, ``offset``.

        Example::

            shots = client.screenshot.search(url="example.com", limit=5)
        """
        if not url:
            raise ValueError('"url" is required')
        return self._client._get("/screenshot/search", {"url": url, **kwargs})

    def thumbnail(self, screenshot_id: int, **kwargs: Any) -> bytes:
        """Download the screenshot thumbnail as raw bytes.

        Args:
            screenshot_id: Screenshot ID.
            **kwargs:      ``format`` (``"png"``/``"jpeg"``/``"webp"``),
                           ``width``, ``height``, ``shot`` (1-based index).

        Example::

            data = client.screenshot.thumbnail(12345, width=400)
            with open("thumb.png", "wb") as f:
                f.write(data)
        """
        return self._client._get_bytes(
            "/screenshot/thumbnail", {"id": screenshot_id, **kwargs}
        )

    def html(self, screenshot_id: int) -> str:
        """Fetch the captured HTML source as a string."""
        return self._client._get_bytes(
            "/screenshot/html", {"id": screenshot_id}
        ).decode("utf-8")

    def pdf(self, screenshot_id: int) -> bytes:
        """Fetch the rendered PDF as bytes."""
        return self._client._get_bytes("/screenshot/pdf", {"id": screenshot_id})

    def video(self, screenshot_id: int) -> bytes:
        """Fetch the recorded video as bytes."""
        return self._client._get_bytes("/screenshot/video", {"id": screenshot_id})

    def delete(
        self,
        screenshot_id: int,
        data: str = "all",
    ) -> None:
        """Delete screenshot data.

        Args:
            screenshot_id: Screenshot to delete.
            data:          What to delete: ``"image"``, ``"metadata"``,
                           ``"url"``, or ``"all"`` (default).
        """
        self._client._get("/screenshot/delete", {"id": screenshot_id, "data": data})

    # ------------------------------------------------------------------
    # File-save helpers
    # ------------------------------------------------------------------

    def save_image(
        self,
        screenshot_id: int,
        file_path: Union[str, Path],
        **kwargs: Any,
    ) -> None:
        """Download the thumbnail and save it to *file_path*.

        Intermediate directories are created automatically.

        Example::

            client.screenshot.save_image(12345, "shots/homepage.png")
            client.screenshot.save_image(12345, "shots/shot2.png", shot=2)
        """
        data = self.thumbnail(screenshot_id, **kwargs)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_pdf(
        self, screenshot_id: int, file_path: Union[str, Path]
    ) -> None:
        """Download the rendered PDF and save it to *file_path*.

        Example::

            client.screenshot.save_pdf(12345, "docs/page.pdf")
        """
        data = self.pdf(screenshot_id)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_html(
        self, screenshot_id: int, file_path: Union[str, Path]
    ) -> None:
        """Download the captured HTML and save it to *file_path*.

        Example::

            client.screenshot.save_html(12345, "html/page.html")
        """
        content = self.html(screenshot_id)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def save_video(
        self, screenshot_id: int, file_path: Union[str, Path]
    ) -> None:
        """Download the recorded video and save it to *file_path*.

        Example::

            client.screenshot.save_video(12345, "videos/recording.webm")
        """
        data = self.video(screenshot_id)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_all(
        self,
        screenshot_id: int,
        directory: Union[str, Path],
        basename: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Save all available outputs (image, HTML, PDF, video) to *directory*.

        Files that were not captured (``has_html=False``, etc.) are silently
        skipped.

        Args:
            screenshot_id: Screenshot to download.
            directory:     Target directory (created if it does not exist).
            basename:      File stem to use (default: the screenshot ID).

        Returns:
            A dict with keys ``"image"``, ``"html"``, ``"pdf"``, ``"video"``
            — each value is the absolute path string or ``None`` if skipped.

        Example::

            saved = client.screenshot.save_all(12345, "./output/")
            print(saved["image"])   # ./output/12345.png
        """
        s = self.info(screenshot_id)
        stem = basename or str(screenshot_id)
        dest = Path(directory)
        dest.mkdir(parents=True, exist_ok=True)
        result: Dict[str, Optional[str]] = {
            "image": None, "html": None, "pdf": None, "video": None
        }

        if s.get("status") == "finished":
            p = str(dest / f"{stem}.png")
            self.save_image(screenshot_id, p)
            result["image"] = p

        if s.get("has_html"):
            p = str(dest / f"{stem}.html")
            self.save_html(screenshot_id, p)
            result["html"] = p

        if s.get("has_pdf"):
            p = str(dest / f"{stem}.pdf")
            self.save_pdf(screenshot_id, p)
            result["pdf"] = p

        if s.get("has_video"):
            ext = s.get("video_format") or "webm"
            p = str(dest / f"{stem}.{ext}")
            self.save_video(screenshot_id, p)
            result["video"] = p

        return result


# ---------------------------------------------------------------------------
# Batch namespace
# ---------------------------------------------------------------------------

class BatchNamespace:
    """All batch-related API methods.

    Access via ``client.batch.*``.
    """

    def __init__(self, client: ScreenshotCenterClient) -> None:
        self._client = client

    def create(
        self,
        urls: Union[str, List[str], bytes],
        country: str,
        **kwargs: Any,
    ) -> Batch:
        """Submit a batch job from a list of URLs.

        Args:
            urls:    URLs to screenshot.  May be a newline-separated string,
                     a list of URL strings, or raw bytes (file contents).
            country: ISO 3166-1 alpha-2 country code (required).
            **kwargs: Any additional batch parameters.

        Example::

            batch = client.batch.create(
                ["https://example.com", "https://example.org"],
                country="us",
            )
        """
        if not country:
            raise ValueError('"country" is required')

        if isinstance(urls, (bytes, bytearray)):
            file_content = bytes(urls)
        elif isinstance(urls, list):
            file_content = "\n".join(urls).encode("utf-8")
        else:
            file_content = urls.encode("utf-8")

        fields = {"country": country}
        for k, v in kwargs.items():
            if v is not None:
                fields[k] = str(v)

        files = {"file": ("urls.txt", file_content, "text/plain")}
        body, content_type = _encode_multipart(fields, files)
        return self._client._post("/batch/create", body, content_type)

    def info(self, batch_id: int) -> Batch:
        """Get batch status and progress.

        Example::

            b = client.batch.info(42)
            print(f"{b['processed']}/{b['count']} processed")
        """
        return self._client._get("/batch/info", {"id": batch_id})

    def list(self, **kwargs: Any) -> List[Batch]:
        """List recent batches.

        Args:
            **kwargs: ``limit``, ``offset``.
        """
        return self._client._get("/batch/list", kwargs)

    def cancel(self, batch_id: int) -> None:
        """Cancel a running batch."""
        body = json.dumps({"id": batch_id}).encode("utf-8")
        self._client._post("/batch/cancel", body, "application/json")

    def download(self, batch_id: int) -> bytes:
        """Download the batch results ZIP as bytes.

        Example::

            data = client.batch.download(42)
            with open("results.zip", "wb") as f:
                f.write(data)
        """
        return self._client._get_bytes("/batch/download", {"id": batch_id})

    def save_zip(
        self, batch_id: int, file_path: Union[str, Path]
    ) -> None:
        """Download the batch results ZIP and save it to *file_path*.

        Example::

            client.batch.save_zip(42, "./output/results.zip")
        """
        data = self.download(batch_id)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def wait_for(
        self,
        batch_id: int,
        interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
    ) -> Batch:
        """Poll until the batch reaches ``finished`` or ``error``.

        Args:
            batch_id:  Batch ID to poll.
            interval:  Seconds between polls (default: 2).
            timeout:   Maximum total wait in seconds (default: 120).

        Example::

            result = client.batch.wait_for(42, timeout=60)
            print(f"Done: {result['processed']}/{result['count']}")
        """
        deadline = time.monotonic() + timeout
        while True:
            b = self.info(batch_id)
            if b["status"] in ("finished", "error"):
                return b
            if time.monotonic() + interval > deadline:
                raise WaitTimeoutError(batch_id, int(timeout * 1000))
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Crawl namespace
# ---------------------------------------------------------------------------

class CrawlNamespace:
    """All crawl-related API methods.

    Access via ``client.crawl.*``.
    """

    def __init__(self, client: ScreenshotCenterClient) -> None:
        self._client = client

    def create(
        self,
        url: str,
        domain: str,
        max_urls: int,
        **kwargs: Any,
    ) -> dict:
        """Start a new crawl job.

        Args:
            url:      Starting URL for the crawl (required).
            domain:   Domain to restrict crawling to (required).
            max_urls: Maximum number of URLs to crawl (required).
            **kwargs: Any additional crawl parameters.

        Example::

            crawl = client.crawl.create(
                url="https://example.com",
                domain="example.com",
                max_urls=100,
            )
        """
        if not url:
            raise ValueError('"url" is required')
        if not domain:
            raise ValueError('"domain" is required')
        body_dict: Dict[str, Any] = {
            "url": url,
            "domain": domain,
            "max_urls": max_urls,
            **kwargs,
        }
        body = json.dumps(body_dict).encode("utf-8")
        return self._client._post("/crawl/create", body, "application/json")

    def info(self, crawl_id: int) -> dict:
        """Get crawl status and details.

        Example::

            c = client.crawl.info(42)
            print(c["status"])
        """
        return self._client._get("/crawl/info", {"id": crawl_id})

    def list(self, **kwargs: Any) -> list:
        """List recent crawls.

        Args:
            **kwargs: ``limit``, ``offset``, etc.
        """
        return self._client._get("/crawl/list", kwargs)

    def cancel(self, crawl_id: int) -> None:
        """Cancel a running crawl."""
        body = json.dumps({"id": crawl_id}).encode("utf-8")
        self._client._post("/crawl/cancel", body, "application/json")

    def wait_for(
        self,
        crawl_id: int,
        interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
    ) -> dict:
        """Poll until the crawl reaches ``finished`` or ``error``.

        Args:
            crawl_id: Crawl ID to poll.
            interval: Seconds between polls (default: 2).
            timeout:  Maximum total wait in seconds (default: 120).

        Example::

            result = client.crawl.wait_for(42, timeout=60)
            print(result["status"])
        """
        deadline = time.monotonic() + timeout
        while True:
            c = self.info(crawl_id)
            if c["status"] in ("finished", "error"):
                return c
            if time.monotonic() + interval > deadline:
                raise WaitTimeoutError(crawl_id, int(timeout * 1000))
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Account namespace
# ---------------------------------------------------------------------------

class AccountNamespace:
    """Account-related API methods.

    Access via ``client.account.*``.
    """

    def __init__(self, client: ScreenshotCenterClient) -> None:
        self._client = client

    def info(self) -> Account:
        """Get account information including the current credit balance.

        Example::

            acc = client.account.info()
            print(f"Credits remaining: {acc['balance']}")
        """
        return self._client._get("/account/info")
