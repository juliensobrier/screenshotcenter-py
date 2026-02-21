# screenshotcenter

Python SDK for the [ScreenshotCenter](https://screenshotcenter.com) API — capture web screenshots, PDFs, HTML, and video at scale.

## Requirements

- Python 3.9 or later
- No runtime dependencies (uses only the Python standard library)

## Installation

```bash
pip install screenshotcenter
```

## Quick start

```python
from screenshotcenter import ScreenshotCenterClient

client = ScreenshotCenterClient(api_key="your_api_key")

shot = client.screenshot.create(url="https://example.com", country="us")
result = client.wait_for(shot["id"])

print(result["url"])          # https://example.com/
print(result["status"])       # finished
client.screenshot.save_image(result["id"], "homepage.png")
```

## Authentication

Pass your API key to the constructor:

```python
client = ScreenshotCenterClient(api_key="your_api_key")
```

You can also override the base URL for self-hosted instances:

```python
client = ScreenshotCenterClient(
    api_key="your_api_key",
    base_url="https://your-instance.example.com/api/v1",
)
```

---

## Use cases

### Basic screenshot

```python
shot = client.screenshot.create(url="https://example.com")
result = client.wait_for(shot["id"])
client.screenshot.save_image(result["id"], "screenshot.png")
```

### Country / geolocation

```python
# Capture from France
shot = client.screenshot.create(url="https://example.com", country="fr")

# Exact coordinates
shot = client.screenshot.create(
    url="https://example.com",
    country="us",
    geo_enable=True,
    geo_latitude=37.7749,
    geo_longitude=-122.4194,
)
```

### PDF generation

```python
shot = client.screenshot.create(url="https://example.com", pdf=True)
result = client.wait_for(shot["id"])
assert result["has_pdf"] is True
client.screenshot.save_pdf(result["id"], "page.pdf")
```

### HTML capture

```python
shot = client.screenshot.create(url="https://example.com", html=True)
result = client.wait_for(shot["id"])
client.screenshot.save_html(result["id"], "page.html")
```

### Video recording

```python
shot = client.screenshot.create(
    url="https://example.com",
    video=True,
    video_duration=10,   # seconds
)
result = client.wait_for(shot["id"])
client.screenshot.save_video(result["id"], "recording.webm")
```

### Multi-shot (time-lapse)

```python
# Capture 5 screenshots at 3-second intervals
shot = client.screenshot.create(
    url="https://example.com",
    shots=5,
    shot_interval=3,
)
result = client.wait_for(shot["id"])

for i in range(1, 6):
    client.screenshot.save_image(result["id"], f"shot_{i}.png", shot=i)
```

### Step automation

```python
shot = client.screenshot.create(
    url="https://example.com/login",
    steps=[
        {"command": "type",  "selector": "#email",    "value": "user@example.com"},
        {"command": "type",  "selector": "#password", "value": "secret"},
        {"command": "click", "selector": "#submit"},
        {"command": "wait",  "value": "2000"},
        {"command": "screenshot"},
    ],
)
result = client.wait_for(shot["id"])
```

### Save all outputs at once

```python
shot = client.screenshot.create(url="https://example.com", html=True, pdf=True)
result = client.wait_for(shot["id"])

saved = client.screenshot.save_all(result["id"], "./output/", basename="homepage")
print(saved["image"])   # ./output/homepage.png
print(saved["html"])    # ./output/homepage.html
print(saved["pdf"])     # ./output/homepage.pdf
```

### Batch processing

```python
batch = client.batch.create(
    urls=["https://example.com", "https://example.org", "https://python.org"],
    country="us",
)

result = client.batch.wait_for(batch["id"], timeout=300)
print(f"Processed: {result['processed']}/{result['count']}")

if result["status"] == "finished":
    client.batch.save_zip(result["id"], "results.zip")
```

### Credit balance

```python
acc = client.account.info()
print(f"Credits remaining: {acc['balance']}")
```

### Error handling

```python
from screenshotcenter import ApiError, ScreenshotFailedError, TimeoutError

try:
    shot = client.screenshot.create(url="https://example.com")
    result = client.wait_for(shot["id"], timeout=60)

except ScreenshotFailedError as e:
    print(f"Screenshot {e.screenshot_id} failed: {e.error}")

except TimeoutError as e:
    print(f"Timed out after {e.timeout_ms}ms")

except ApiError as e:
    print(f"API error {e.status}: {e}")
    if e.fields:
        for field, messages in e.fields.items():
            print(f"  {field}: {', '.join(messages)}")
```

---

## API reference

### `ScreenshotCenterClient(api_key, *, base_url=None, timeout=30)`

| Parameter  | Type  | Description |
|---|---|---|
| `api_key`  | `str` | Your ScreenshotCenter API key (required) |
| `base_url` | `str` | Override the API base URL (default: `https://api.screenshotcenter.com/api/v1`) |
| `timeout`  | `int` | Per-request timeout in seconds (default: `30`) |

---

### `client.screenshot`

| Method | Required | Returns | Description |
|---|---|---|---|
| `create(url, **kwargs)` | `url` | `Screenshot` | Request a new screenshot |
| `info(screenshot_id)` | `screenshot_id` | `Screenshot` | Get status and details |
| `list(**kwargs)` | — | `list[Screenshot]` | List recent screenshots |
| `search(url, **kwargs)` | `url` | `list[Screenshot]` | Search by URL pattern |
| `thumbnail(screenshot_id, **kwargs)` | `screenshot_id` | `bytes` | Download thumbnail |
| `html(screenshot_id)` | `screenshot_id` | `str` | Get captured HTML |
| `pdf(screenshot_id)` | `screenshot_id` | `bytes` | Get rendered PDF |
| `video(screenshot_id)` | `screenshot_id` | `bytes` | Get recorded video |
| `delete(screenshot_id, data="all")` | `screenshot_id` | `None` | Delete data |
| `save_image(screenshot_id, path, **kwargs)` | `screenshot_id`, `path` | `None` | Download and save thumbnail |
| `save_html(screenshot_id, path)` | `screenshot_id`, `path` | `None` | Download and save HTML |
| `save_pdf(screenshot_id, path)` | `screenshot_id`, `path` | `None` | Download and save PDF |
| `save_video(screenshot_id, path)` | `screenshot_id`, `path` | `None` | Download and save video |
| `save_all(screenshot_id, dir, basename=None)` | `screenshot_id`, `dir` | `dict` | Save all available outputs |

---

### `client.batch`

| Method | Required | Returns | Description |
|---|---|---|---|
| `create(urls, country, **kwargs)` | `urls`, `country` | `Batch` | Submit a batch job |
| `info(batch_id)` | `batch_id` | `Batch` | Get batch status |
| `list(**kwargs)` | — | `list[Batch]` | List recent batches |
| `cancel(batch_id)` | `batch_id` | `None` | Cancel a running batch |
| `download(batch_id)` | `batch_id` | `bytes` | Download results ZIP |
| `save_zip(batch_id, path)` | `batch_id`, `path` | `None` | Download and save ZIP |
| `wait_for(batch_id, *, interval=2, timeout=120)` | `batch_id` | `Batch` | Poll until done |

---

### `client.account`

| Method | Required | Returns | Description |
|---|---|---|---|
| `info()` | — | `Account` | Get balance and account info |

---

### `client.wait_for(screenshot_id, *, interval=2, timeout=120)`

Poll until a screenshot reaches `finished` or `error`.

| Parameter     | Default | Description |
|---|---|---|
| `screenshot_id` | — | Screenshot ID to poll |
| `interval`    | `2`     | Seconds between polls |
| `timeout`     | `120`   | Maximum total wait in seconds |

Raises `ScreenshotFailedError` on `status: "error"`, `TimeoutError` when the deadline is exceeded.

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Unit tests only (no credentials needed)
pytest tests/test_client.py

# Unit tests + integration tests against the production API
SCREENSHOTCENTER_API_KEY=your_key pytest

# Unit tests + integration tests against a local instance
SCREENSHOTCENTER_API_KEY=your_key \
SCREENSHOTCENTER_BASE_URL=http://localhost:3000/api/v1 \
pytest

# Integration tests only
SCREENSHOTCENTER_API_KEY=your_key pytest tests/test_integration.py
```

| Variable | Required | Description |
|---|---|---|
| `SCREENSHOTCENTER_API_KEY` | Required for integration tests | API key for live requests |
| `SCREENSHOTCENTER_BASE_URL` | Optional | Override the API base URL |

## Type hints

All methods are fully type-annotated. Response objects are typed as
[`TypedDict`](https://docs.python.org/3/library/typing.html#typing.TypedDict)
subclasses (`Screenshot`, `Batch`, `Account`) — they are plain dicts at
runtime, so all standard dict operations apply. Unknown future API fields
are accessible directly on the returned dict.

```python
from screenshotcenter import Screenshot

def print_info(shot: Screenshot) -> None:
    print(shot["id"], shot["status"], shot["url"])
```

## License

[MIT](LICENSE)
