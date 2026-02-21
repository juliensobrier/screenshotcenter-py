"""Integration tests — run against a real ScreenshotCenter instance.

These tests are SKIPPED unless ``SCREENSHOTCENTER_API_KEY`` is set.

Environment variables:
    SCREENSHOTCENTER_API_KEY   Your API key (required to run these tests).
    SCREENSHOTCENTER_BASE_URL  Override the API base URL.
                               e.g. ``http://localhost:3000/api/v1``

Usage::

    # Run against the production API
    SCREENSHOTCENTER_API_KEY=your_key pytest tests/test_integration.py

    # Run against a local instance
    SCREENSHOTCENTER_API_KEY=your_key \\
    SCREENSHOTCENTER_BASE_URL=http://localhost:3000/api/v1 \\
    pytest tests/test_integration.py

Note: Batch tests require the batch worker service to be running on the server:
    cd services && npm run batches:worker
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from screenshotcenter import ApiError, ScreenshotCenterClient

# ---------------------------------------------------------------------------
# Guard — skip everything when no API key is set
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("SCREENSHOTCENTER_API_KEY", "")
BASE_URL = os.environ.get("SCREENSHOTCENTER_BASE_URL")

LIVE = pytest.mark.skipif(not API_KEY, reason="SCREENSHOTCENTER_API_KEY not set")

if not API_KEY:
    print(
        "\nℹ  Integration tests skipped — "
        "set SCREENSHOTCENTER_API_KEY to run them against a real instance.\n"
    )


# ---------------------------------------------------------------------------
# Client factory & helpers
# ---------------------------------------------------------------------------

def make_client() -> ScreenshotCenterClient:
    kwargs = {"api_key": API_KEY}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    return ScreenshotCenterClient(**kwargs)


# IDs created during this run — cleaned up in the module-scoped fixture.
_created_ids: list[int] = []


def create_and_wait(extra: dict | None = None) -> dict:
    """Create a screenshot and wait until it finishes."""
    client = make_client()
    params = {"url": "https://example.com", "country": "us", **(extra or {})}
    shot = client.screenshot.create(**params)
    _created_ids.append(shot["id"])
    return client.wait_for(shot["id"], interval=3, timeout=110)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup_screenshots():
    """Delete all screenshots created during the test run."""
    yield
    if not _created_ids:
        return
    client = make_client()
    for sid in _created_ids:
        try:
            client.screenshot.delete(sid, data="all")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# account
# ---------------------------------------------------------------------------

@LIVE
def test_account_info_returns_balance():
    client = make_client()
    acc = client.account.info()
    assert isinstance(acc["balance"], int)
    assert acc["balance"] >= 0


# ---------------------------------------------------------------------------
# screenshot.create + wait_for
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_create_returns_id():
    client = make_client()
    shot = client.screenshot.create(url="https://example.com", country="us")
    _created_ids.append(shot["id"])
    assert isinstance(shot["id"], int)
    assert shot["id"] > 0


@LIVE
def test_screenshot_create_status_is_processing_or_finished():
    client = make_client()
    shot = client.screenshot.create(url="https://example.com", country="us")
    _created_ids.append(shot["id"])
    assert shot["status"] in ("processing", "finished")


@LIVE
def test_wait_for_reaches_finished():
    result = create_and_wait()
    assert result["status"] == "finished"
    assert result["url"] == "https://example.com/"


# ---------------------------------------------------------------------------
# screenshot.info
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_info_returns_screenshot():
    created = create_and_wait()
    client = make_client()
    fetched = client.screenshot.info(created["id"])
    assert fetched["id"] == created["id"]
    assert fetched["status"] == "finished"


@LIVE
def test_screenshot_info_raises_404_for_unknown_id():
    client = make_client()
    with pytest.raises(ApiError) as exc_info:
        client.screenshot.info(999_999_999)
    assert exc_info.value.status in (404, 400)


# ---------------------------------------------------------------------------
# screenshot.list
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_list_returns_list():
    client = make_client()
    shots = client.screenshot.list(limit=5)
    assert isinstance(shots, list)


# ---------------------------------------------------------------------------
# screenshot.search
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_search_returns_list():
    client = make_client()
    shots = client.screenshot.search(url="example.com", limit=5)
    assert isinstance(shots, list)


# ---------------------------------------------------------------------------
# screenshot.thumbnail
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_thumbnail_returns_bytes():
    result = create_and_wait()
    client = make_client()
    data = client.screenshot.thumbnail(result["id"])
    assert isinstance(data, bytes)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# screenshot.save_image
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_save_image_writes_file():
    result = create_and_wait()
    client = make_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "shot.png"
        client.screenshot.save_image(result["id"], dest)
        assert dest.exists()
        assert dest.stat().st_size > 0


# ---------------------------------------------------------------------------
# screenshot with html=True
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_save_html_writes_file():
    result = create_and_wait({"html": True})
    assert result["has_html"] is True
    client = make_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "page.html"
        client.screenshot.save_html(result["id"], dest)
        content = dest.read_text("utf-8")
        assert len(content) > 0
        assert "<html" in content.lower()


# ---------------------------------------------------------------------------
# screenshot with pdf=True
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_save_pdf_writes_file():
    result = create_and_wait({"pdf": True})
    assert result["has_pdf"] is True
    client = make_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "page.pdf"
        client.screenshot.save_pdf(result["id"], dest)
        data = dest.read_bytes()
        assert data[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# screenshot.save_all
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_save_all_saves_image():
    result = create_and_wait({"html": True})
    client = make_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        saved = client.screenshot.save_all(result["id"], tmpdir, basename="test")
        assert saved["image"] is not None
        assert Path(saved["image"]).exists()
        if result.get("has_html"):
            assert saved["html"] is not None
            assert Path(saved["html"]).exists()


# ---------------------------------------------------------------------------
# screenshot.delete
# ---------------------------------------------------------------------------

@LIVE
def test_screenshot_delete_does_not_raise():
    result = create_and_wait()
    # Remove from cleanup list — we're deleting it here.
    if result["id"] in _created_ids:
        _created_ids.remove(result["id"])
    client = make_client()
    client.screenshot.delete(result["id"], data="image")  # should not raise


# ---------------------------------------------------------------------------
# Invalid API key
# ---------------------------------------------------------------------------

@LIVE
def test_invalid_api_key_raises_401():
    kwargs = {"api_key": "invalid-key-000"}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    client = ScreenshotCenterClient(**kwargs)
    with pytest.raises(ApiError) as exc_info:
        client.screenshot.create(url="https://example.com")
    assert exc_info.value.status == 401


# ---------------------------------------------------------------------------
# batch  (requires batch worker: cd services && npm run batches:worker)
# ---------------------------------------------------------------------------

@LIVE
def test_batch_create_and_wait():
    """Creates a batch and waits for it to finish or error."""
    client = make_client()
    batch = client.batch.create(
        ["https://example.com", "https://example.org"],
        country="us",
    )
    assert isinstance(batch["id"], int)
    assert batch["id"] > 0
    assert batch["status"] in ("processing", "finished")

    result = client.batch.wait_for(batch["id"], interval=3, timeout=110)
    assert result["status"] in ("finished", "error")

    if result["status"] == "finished" and result.get("zip_url"):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "results.zip"
            client.batch.save_zip(batch["id"], dest)
            assert dest.exists()
            assert dest.stat().st_size > 0
