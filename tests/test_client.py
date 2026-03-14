"""Unit tests for the ScreenshotCenter Python SDK.

All HTTP calls are mocked — no network access or API key required.

Run with:
    pytest tests/test_client.py
"""

from __future__ import annotations

import json
import os
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError

import pytest

from screenshotcenter import (
    ApiError,
    ScreenshotCenterClient,
    ScreenshotFailedError,
    TimeoutError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_SCREENSHOT = {
    "id": 1001,
    "status": "finished",
    "url": "https://example.com",
    "final_url": "https://example.com/",
    "error": None,
    "cost": 1,
    "tag": [],
    "created_at": "2026-01-01T00:00:00.000Z",
    "finished_at": "2026-01-01T00:00:05.000Z",
    "country": "us",
    "region": None,
    "language": "en-US",
    "timezone": "America/New_York",
    "size": "screen",
    "shots": 1,
    "html": False,
    "pdf": False,
    "video": False,
    "has_html": False,
    "has_pdf": False,
    "has_video": False,
}

FIXTURE_BATCH = {
    "id": 2001,
    "status": "finished",
    "count": 3,
    "processed": 3,
    "failed": 0,
    "zip_url": "https://api.screenshotcenter.com/api/v1/batch/download?id=2001",
}

FIXTURE_ACCOUNT = {"balance": 500}


def _json_resp(data, status=200):
    """Return a mock context-manager response that yields JSON."""
    body = json.dumps({"success": True, "data": data}).encode()
    mock = MagicMock()
    mock.read.return_value = body
    mock.getheader.side_effect = lambda h, d="": "application/json" if h == "Content-Type" else d
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _binary_resp(content: bytes, mime="image/png"):
    """Return a mock context-manager response that yields binary data."""
    mock = MagicMock()
    mock.read.return_value = content
    mock.getheader.side_effect = lambda h, d="": mime if h == "Content-Type" else d
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _http_error(message: str, status: int = 400, code: str | None = None):
    """Return a urllib HTTPError with a JSON body."""
    body = json.dumps({"success": False, "error": message, "code": code}).encode()
    return HTTPError(
        url="http://test", code=status, msg=message, hdrs={}, fp=BytesIO(body)
    )


@pytest.fixture
def client():
    return ScreenshotCenterClient(api_key="test-key-123")


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_raises_when_api_key_missing(self):
        with pytest.raises(ValueError, match="api_key is required"):
            ScreenshotCenterClient(api_key="")

    def test_raises_when_api_key_none(self):
        with pytest.raises((ValueError, TypeError)):
            ScreenshotCenterClient(api_key=None)  # type: ignore

    def test_default_base_url(self, client):
        assert client._base_url == "https://api.screenshotcenter.com/api/v1"

    def test_custom_base_url(self):
        c = ScreenshotCenterClient(
            api_key="k", base_url="http://localhost:3000/api/v1"
        )
        assert c._base_url == "http://localhost:3000/api/v1"

    def test_trailing_slash_stripped_from_base_url(self):
        c = ScreenshotCenterClient(api_key="k", base_url="http://example.com/api/")
        assert not c._base_url.endswith("/")

    def test_namespaces_attached(self, client):
        assert hasattr(client, "screenshot")
        assert hasattr(client, "batch")
        assert hasattr(client, "account")


# ---------------------------------------------------------------------------
# screenshot.create
# ---------------------------------------------------------------------------

class TestScreenshotCreate:
    def test_returns_screenshot(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)):
            result = client.screenshot.create(url="https://example.com")
        assert result["id"] == 1001
        assert result["status"] == "finished"

    def test_sends_url_and_key_as_query_params(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com")
        called_url = m.call_args[0][0].full_url
        assert "url=https%3A%2F%2Fexample.com" in called_url
        assert "key=test-key-123" in called_url

    def test_passes_optional_params(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", country="fr", shots=3)
        called_url = m.call_args[0][0].full_url
        assert "country=fr" in called_url
        assert "shots=3" in called_url

    def test_passes_unknown_future_params(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", future_param="xyz")
        called_url = m.call_args[0][0].full_url
        assert "future_param=xyz" in called_url

    def test_raises_when_url_missing(self, client):
        with pytest.raises(ValueError, match='"url" is required'):
            client.screenshot.create(url="")

    def test_raises_api_error_on_401(self, client):
        with patch("urllib.request.urlopen", side_effect=_http_error("Unauthorized", 401)):
            with pytest.raises(ApiError) as exc_info:
                client.screenshot.create(url="https://example.com")
        assert exc_info.value.status == 401

    def test_raises_api_error_on_422_with_fields(self, client):
        err = HTTPError(
            url="http://test",
            code=422,
            msg="Validation error",
            hdrs={},
            fp=BytesIO(
                json.dumps({
                    "success": False,
                    "error": "Validation failed",
                    "code": "VALIDATION_ERROR",
                    "fields": {"url": ["Invalid URL"]},
                }).encode()
            ),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ApiError) as exc_info:
                client.screenshot.create(url="not-a-url")
        assert exc_info.value.status == 422
        assert exc_info.value.fields == {"url": ["Invalid URL"]}


# ---------------------------------------------------------------------------
# screenshot.info
# ---------------------------------------------------------------------------

class TestScreenshotInfo:
    def test_returns_screenshot(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)):
            result = client.screenshot.info(1001)
        assert result["id"] == 1001

    def test_sends_id_as_query_param(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.info(1001)
        called_url = m.call_args[0][0].full_url
        assert "id=1001" in called_url

    def test_raises_api_error_on_404(self, client):
        with patch("urllib.request.urlopen", side_effect=_http_error("Not found", 404)):
            with pytest.raises(ApiError) as exc_info:
                client.screenshot.info(999)
        assert exc_info.value.status == 404


# ---------------------------------------------------------------------------
# screenshot.list
# ---------------------------------------------------------------------------

class TestScreenshotList:
    def test_returns_list(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([FIXTURE_SCREENSHOT])):
            result = client.screenshot.list()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_passes_limit_and_offset(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([])) as m:
            client.screenshot.list(limit=5, offset=10)
        url = m.call_args[0][0].full_url
        assert "limit=5" in url
        assert "offset=10" in url

    def test_returns_empty_list(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([])):
            result = client.screenshot.list()
        assert result == []


# ---------------------------------------------------------------------------
# screenshot.search
# ---------------------------------------------------------------------------

class TestScreenshotSearch:
    def test_returns_list(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([FIXTURE_SCREENSHOT])):
            result = client.screenshot.search(url="example.com")
        assert isinstance(result, list)

    def test_sends_url_param(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([])) as m:
            client.screenshot.search(url="example.com")
        url = m.call_args[0][0].full_url
        assert "url=example.com" in url

    def test_raises_when_url_missing(self, client):
        with pytest.raises(ValueError, match='"url" is required'):
            client.screenshot.search(url="")


# ---------------------------------------------------------------------------
# screenshot.thumbnail
# ---------------------------------------------------------------------------

class TestScreenshotThumbnail:
    def test_returns_bytes(self, client):
        fake_png = b"\x89PNG\r\n\x1a\nDATA"
        with patch("urllib.request.urlopen", return_value=_binary_resp(fake_png)):
            result = client.screenshot.thumbnail(1001)
        assert result == fake_png

    def test_passes_thumbnail_options(self, client):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"x")) as m:
            client.screenshot.thumbnail(1001, width=400, shot=2)
        url = m.call_args[0][0].full_url
        assert "width=400" in url
        assert "shot=2" in url

    def test_raises_api_error_on_http_error(self, client):
        with patch("urllib.request.urlopen", side_effect=_http_error("Not found", 404)):
            with pytest.raises(ApiError):
                client.screenshot.thumbnail(9999)


# ---------------------------------------------------------------------------
# screenshot.html / pdf / video
# ---------------------------------------------------------------------------

class TestScreenshotBinaryEndpoints:
    def test_html_returns_string(self, client):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"<html></html>", "text/html")):
            result = client.screenshot.html(1001)
        assert isinstance(result, str)
        assert "<html>" in result

    def test_pdf_returns_bytes(self, client):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"%PDF-1.4")):
            result = client.screenshot.pdf(1001)
        assert result == b"%PDF-1.4"

    def test_video_returns_bytes(self, client):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"WEBM", "video/webm")):
            result = client.screenshot.video(1001)
        assert result == b"WEBM"


# ---------------------------------------------------------------------------
# File-save helpers
# ---------------------------------------------------------------------------

class TestSaveImage:
    def test_writes_file_to_disk(self, client, tmp_path):
        fake_png = b"\x89PNG-DATA"
        with patch("urllib.request.urlopen", return_value=_binary_resp(fake_png)):
            dest = tmp_path / "shot.png"
            client.screenshot.save_image(1001, dest)
        assert dest.read_bytes() == fake_png

    def test_creates_intermediate_directories(self, client, tmp_path):
        fake_png = b"PNG"
        with patch("urllib.request.urlopen", return_value=_binary_resp(fake_png)):
            dest = tmp_path / "a" / "b" / "c" / "shot.png"
            client.screenshot.save_image(1001, dest)
        assert dest.exists()

    def test_passes_shot_param(self, client, tmp_path):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"x")) as m:
            client.screenshot.save_image(1001, tmp_path / "s.png", shot=2)
        url = m.call_args[0][0].full_url
        assert "shot=2" in url


class TestSavePDF:
    def test_writes_pdf_to_disk(self, client, tmp_path):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"%PDF")):
            dest = tmp_path / "page.pdf"
            client.screenshot.save_pdf(1001, dest)
        assert dest.read_bytes() == b"%PDF"


class TestSaveHTML:
    def test_writes_html_to_disk(self, client, tmp_path):
        html = b"<html><body>Hello</body></html>"
        with patch("urllib.request.urlopen", return_value=_binary_resp(html, "text/html")):
            dest = tmp_path / "page.html"
            client.screenshot.save_html(1001, dest)
        assert dest.read_text("utf-8") == html.decode("utf-8")


class TestSaveVideo:
    def test_writes_video_to_disk(self, client, tmp_path):
        with patch("urllib.request.urlopen", return_value=_binary_resp(b"WEBM", "video/webm")):
            dest = tmp_path / "rec.webm"
            client.screenshot.save_video(1001, dest)
        assert dest.read_bytes() == b"WEBM"


class TestSaveAll:
    def _shot(self, **overrides):
        s = {**FIXTURE_SCREENSHOT, "status": "finished"}
        s.update(overrides)
        return s

    def test_saves_image_when_finished(self, client, tmp_path):
        shot = self._shot()
        responses = [_json_resp(shot), _binary_resp(b"PNG")]
        with patch("urllib.request.urlopen", side_effect=responses):
            result = client.screenshot.save_all(1001, tmp_path)
        assert result["image"] is not None
        assert Path(result["image"]).exists()

    def test_saves_html_when_has_html(self, client, tmp_path):
        shot = self._shot(has_html=True)
        responses = [_json_resp(shot), _binary_resp(b"PNG"), _binary_resp(b"<html>", "text/html")]
        with patch("urllib.request.urlopen", side_effect=responses):
            result = client.screenshot.save_all(1001, tmp_path)
        assert result["html"] is not None

    def test_skips_html_when_not_captured(self, client, tmp_path):
        shot = self._shot(has_html=False)
        responses = [_json_resp(shot), _binary_resp(b"PNG")]
        with patch("urllib.request.urlopen", side_effect=responses):
            result = client.screenshot.save_all(1001, tmp_path)
        assert result["html"] is None

    def test_uses_custom_basename(self, client, tmp_path):
        shot = self._shot()
        responses = [_json_resp(shot), _binary_resp(b"PNG")]
        with patch("urllib.request.urlopen", side_effect=responses):
            result = client.screenshot.save_all(1001, tmp_path, basename="mypage")
        assert result["image"] and "mypage" in result["image"]


# ---------------------------------------------------------------------------
# screenshot.delete
# ---------------------------------------------------------------------------

class TestScreenshotDelete:
    def test_sends_delete_request(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp({"deleted": True})) as m:
            client.screenshot.delete(1001)
        url = m.call_args[0][0].full_url
        assert "id=1001" in url
        assert "data=all" in url

    def test_accepts_data_param(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp({})) as m:
            client.screenshot.delete(1001, data="image")
        url = m.call_args[0][0].full_url
        assert "data=image" in url


# ---------------------------------------------------------------------------
# wait_for
# ---------------------------------------------------------------------------

class TestWaitFor:
    def test_resolves_immediately_when_finished(self, client):
        finished = {**FIXTURE_SCREENSHOT, "status": "finished"}
        with patch("urllib.request.urlopen", return_value=_json_resp(finished)):
            result = client.wait_for(1001)
        assert result["status"] == "finished"

    def test_polls_until_finished(self, client):
        processing = {**FIXTURE_SCREENSHOT, "status": "processing"}
        finished = {**FIXTURE_SCREENSHOT, "status": "finished"}
        responses = [_json_resp(processing), _json_resp(processing), _json_resp(finished)]
        with patch("urllib.request.urlopen", side_effect=responses):
            with patch("time.sleep"):
                result = client.wait_for(1001, interval=0.01)
        assert result["status"] == "finished"

    def test_raises_screenshot_failed_error_on_error_status(self, client):
        error_shot = {**FIXTURE_SCREENSHOT, "status": "error", "error": "Page unreachable"}
        with patch("urllib.request.urlopen", return_value=_json_resp(error_shot)):
            with pytest.raises(ScreenshotFailedError) as exc_info:
                client.wait_for(1001)
        assert exc_info.value.screenshot_id == 1001
        assert "Page unreachable" in str(exc_info.value)

    def test_raises_timeout_error_when_deadline_exceeded(self, client):
        processing = {**FIXTURE_SCREENSHOT, "status": "processing"}
        with patch("urllib.request.urlopen", return_value=_json_resp(processing)):
            with patch("time.sleep"):
                with pytest.raises(TimeoutError) as exc_info:
                    client.wait_for(1001, interval=0.001, timeout=0.001)
        assert exc_info.value.screenshot_id == 1001

    def test_error_class_properties(self, client):
        error_shot = {**FIXTURE_SCREENSHOT, "status": "error", "error": "DNS failure"}
        with patch("urllib.request.urlopen", return_value=_json_resp(error_shot)):
            with pytest.raises(ScreenshotFailedError) as exc_info:
                client.wait_for(1001)
        assert exc_info.value.error == "DNS failure"


# ---------------------------------------------------------------------------
# batch.create
# ---------------------------------------------------------------------------

class TestBatchCreate:
    def test_creates_batch_from_list(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)):
            result = client.batch.create(
                ["https://example.com", "https://example.org"], country="us"
            )
        assert result["id"] == 2001

    def test_creates_batch_from_string(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)):
            result = client.batch.create(
                "https://example.com\nhttps://example.org", country="us"
            )
        assert result["id"] == 2001

    def test_creates_batch_from_bytes(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)):
            result = client.batch.create(
                b"https://example.com\nhttps://example.org", country="us"
            )
        assert result["id"] == 2001

    def test_sends_multipart_post(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)) as m:
            client.batch.create(["https://example.com"], country="us")
        req = m.call_args[0][0]
        assert req.method == "POST"
        assert "multipart/form-data" in req.get_header("Content-type")

    def test_raises_when_country_missing(self, client):
        with pytest.raises(ValueError, match='"country" is required'):
            client.batch.create(["https://example.com"], country="")


# ---------------------------------------------------------------------------
# batch.info / list / cancel
# ---------------------------------------------------------------------------

class TestBatchInfo:
    def test_returns_batch(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)):
            result = client.batch.info(2001)
        assert result["id"] == 2001
        assert result["status"] == "finished"

    def test_sends_id_param(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_BATCH)) as m:
            client.batch.info(2001)
        url = m.call_args[0][0].full_url
        assert "id=2001" in url


class TestBatchList:
    def test_returns_list(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp([FIXTURE_BATCH])):
            result = client.batch.list()
        assert isinstance(result, list)
        assert len(result) == 1


class TestBatchWaitFor:
    def test_resolves_on_finished(self, client):
        finished = {**FIXTURE_BATCH, "status": "finished"}
        with patch("urllib.request.urlopen", return_value=_json_resp(finished)):
            result = client.batch.wait_for(2001)
        assert result["status"] == "finished"

    def test_resolves_on_error_status(self, client):
        """batch.wait_for() resolves (does NOT raise) on error status."""
        error_batch = {**FIXTURE_BATCH, "status": "error"}
        with patch("urllib.request.urlopen", return_value=_json_resp(error_batch)):
            result = client.batch.wait_for(2001)
        assert result["status"] == "error"

    def test_raises_timeout_error(self, client):
        processing = {**FIXTURE_BATCH, "status": "processing"}
        with patch("urllib.request.urlopen", return_value=_json_resp(processing)):
            with patch("time.sleep"):
                with pytest.raises(TimeoutError):
                    client.batch.wait_for(2001, interval=0.001, timeout=0.001)


# ---------------------------------------------------------------------------
# account.info
# ---------------------------------------------------------------------------

class TestAccountInfo:
    def test_returns_account(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_ACCOUNT)):
            result = client.account.info()
        assert result["balance"] == 500

    def test_sends_key_param(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_ACCOUNT)) as m:
            client.account.info()
        url = m.call_args[0][0].full_url
        assert "key=test-key-123" in url


# ---------------------------------------------------------------------------
# steps / trackers serialization
# ---------------------------------------------------------------------------

class TestStepsAndTrackersSerialization:
    def test_steps_serialized_as_json(self, client):
        steps = [{"command": "click", "element": "#accept"}, {"command": "sleep", "value": 2}]
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", steps=steps)
        called_url = m.call_args[0][0].full_url
        assert "steps=" in called_url
        import urllib.parse
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        assert "steps" in parsed
        decoded = json.loads(parsed["steps"][0])
        assert decoded == steps

    def test_trackers_serialized_as_json(self, client):
        trackers = [{"id": "ga", "name": "GA", "value": "UA-12345"}]
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", trackers=trackers)
        called_url = m.call_args[0][0].full_url
        import urllib.parse
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        assert "trackers" in parsed
        decoded = json.loads(parsed["trackers"][0])
        assert decoded == trackers

    def test_primitive_list_expanded_as_repeated_keys(self, client):
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", tag=["homepage", "prod"])
        called_url = m.call_args[0][0].full_url
        import urllib.parse
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        assert parsed["tag"] == ["homepage", "prod"]

    def test_steps_not_stringified_as_python_repr(self, client):
        steps = [{"command": "click", "element": "button"}]
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", steps=steps)
        called_url = m.call_args[0][0].full_url
        assert "%27command%27" not in called_url
        assert "'command'" not in called_url

    def test_dict_param_serialized_as_json(self, client):
        geo = {"lat": 48.8566, "lon": 2.3522}
        with patch("urllib.request.urlopen", return_value=_json_resp(FIXTURE_SCREENSHOT)) as m:
            client.screenshot.create(url="https://example.com", geo_overrides=geo)
        called_url = m.call_args[0][0].full_url
        import urllib.parse
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        decoded = json.loads(parsed["geo_overrides"][0])
        assert decoded == geo


# ---------------------------------------------------------------------------
# Error class properties
# ---------------------------------------------------------------------------

class TestErrorClasses:
    def test_api_error_properties(self):
        err = ApiError("Bad request", 400, code="INVALID_PARAMS", fields={"url": ["required"]})
        assert err.status == 400
        assert err.code == "INVALID_PARAMS"
        assert err.fields == {"url": ["required"]}
        assert str(err) == "Bad request"

    def test_timeout_error_properties(self):
        err = TimeoutError(1001, 30_000)
        assert err.screenshot_id == 1001
        assert err.timeout_ms == 30_000
        assert "1001" in str(err)
        assert "30000" in str(err)

    def test_screenshot_failed_error_properties(self):
        err = ScreenshotFailedError(1001, "DNS failure")
        assert err.screenshot_id == 1001
        assert err.error == "DNS failure"
        assert "DNS failure" in str(err)
