# MBTA V3 API Guide: Stops Endpoint + Staying Under the Rate Limit

Base URL: `https://api-v3.mbta.com`
Interactive docs: https://api-v3.mbta.com/docs/swagger/index.html

---

## 1. Rate limits at a glance

| Situation | Limit |
|---|---|
| No API key | 20 requests/minute |
| Valid API key | 1,000 requests/minute |

Higher limits can be requested through the V3 API Portal.

Every response includes these headers:

| Header | Meaning |
|---|---|
| `x-ratelimit-limit` | Max requests allowed per window |
| `x-ratelimit-remaining` | Requests left in the current window |
| `x-ratelimit-reset` | When the window ends (UTC epoch seconds) |

Going over returns **HTTP 429**.

**Get a key:** request one at https://api-v3.mbta.com (V3 API Portal). Store it in `.env` (see the API key safety guide):

```
# .env
MBTA_API_KEY=your-key-here
```

---

## 2. Authentication

Send the key in the `x-api-key` header (preferred over the `api_key` query parameter, because URLs end up in logs and browser history):

```python
headers = {"x-api-key": API_KEY}
```

Confirm the exact auth scheme with the **Authorize** button in Swagger UI if anything changes.

---

## 3. The `/stops` endpoint

`GET /stops` lists stops. Responses follow the [JSON:API](https://jsonapi.org/) format: records live under `data`, each with `id`, `attributes`, and `relationships`.

### Useful query parameters

| Parameter | Purpose |
|---|---|
| `filter[route]` | Stops served by a route (e.g. `Red`, `Orange`, `1`) |
| `filter[direction_id]` | `0` or `1`; only applies together with `filter[route]` |
| `filter[latitude]` + `filter[longitude]` | Find stops near a point (must be used together) |
| `filter[radius]` | Search radius **in degrees**, treated as a flat 2D plane (not meters). ~0.01 is roughly 1 km |
| `sort` | e.g. `name`, or `distance` (requires latitude + longitude) |
| `page[limit]`, `page[offset]` | Pagination |
| `fields[stop]` | Return only the attributes you need |
| `include` | Include related resources (`route` can only be included when `filter[route]` has exactly one route) |

The Swagger page lists the full set of filters.

### Example requests

```
# All Red Line stops, names and coordinates only
/stops?filter[route]=Red&fields[stop]=name,latitude,longitude

# 10 nearest stops to downtown Boston
/stops?filter[latitude]=42.3601&filter[longitude]=-71.0589&filter[radius]=0.01&sort=distance&page[limit]=10
```

---

## 4. Minimal Python client

```bash
pip install requests python-dotenv
```

```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["MBTA_API_KEY"]
BASE_URL = "https://api-v3.mbta.com"

def get_stops(params: dict) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/stops",
        headers={"x-api-key": API_KEY},
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    print("Remaining:", resp.headers.get("x-ratelimit-remaining"))
    return resp.json()["data"]

stops = get_stops({
    "filter[route]": "Red",
    "fields[stop]": "name,latitude,longitude",
})
for s in stops[:5]:
    print(s["id"], s["attributes"]["name"])
```

`requests` handles bracketed keys like `filter[route]` correctly when passed through `params`.

---

## 5. Staying under 1,000 requests/minute

Ordered by impact: **make fewer requests first, then throttle what's left.**

### 5.1 Make fewer requests

1. **Filter server-side.** `filter[route]=Red` beats downloading every stop and filtering in Python.
2. **Request only what you need.** `fields[stop]=name,latitude,longitude` shrinks the payload. `include=` pulls related data in one call instead of many.
3. **Use a large `page[limit]`** where allowed instead of many small pages.
4. **Cache stop data.** Stops rarely change. Fetch once, store to disk, refresh daily.
5. **Use conditional requests.** The API supports `Last-Modified` / `If-Modified-Since`. A `304 Not Modified` response is served from cache and **does not count against your limit**.
6. **Enable gzip** (`Accept-Encoding: gzip`). `requests` does this by default. It saves bandwidth, not request count.
7. **For live data (predictions, vehicles), don't poll.** The V3 API supports streaming (Server-Sent Events via `Accept: text/event-stream`): one long-lived connection replaces thousands of polling requests. See the Swagger/API docs for streaming details.

### 5.2 Conditional-request cache (`If-Modified-Since`)

```python
import requests

_cache: dict[str, tuple[str, dict]] = {}  # url -> (last_modified, json)

def cached_get(url: str, params: dict | None = None) -> dict:
    req = requests.Request("GET", url, params=params).prepare()
    key = req.url
    headers = {"x-api-key": API_KEY}

    if key in _cache:
        headers["If-Modified-Since"] = _cache[key][0]

    resp = requests.get(url, headers=headers, params=params, timeout=10)

    if resp.status_code == 304:           # free: doesn't count toward the limit
        return _cache[key][1]

    resp.raise_for_status()
    last_modified = resp.headers.get("Last-Modified")
    data = resp.json()
    if last_modified:
        _cache[key] = (last_modified, data)
    return data
```

### 5.3 Throttle yourself (client-side rate limiter)

A sliding-window limiter that never lets you exceed a target below the cap. Using ~900/min leaves headroom for retries and clock drift.

```python
import threading
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int = 900, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls: deque[float] = deque()
        self.lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                # drop timestamps outside the window
                while self.calls and now - self.calls[0] >= self.period:
                    self.calls.popleft()
                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return
                sleep_for = self.period - (now - self.calls[0])
            time.sleep(max(sleep_for, 0.01))

limiter = RateLimiter(max_calls=900, period=60)
```

Call `limiter.wait()` immediately before every request.

### 5.4 React to the server's headers and 429s

The server is the source of truth. Back off when you're nearly out, and wait until the reset time on a 429.

```python
import random
import time
import requests

def mbta_get(path: str, params: dict | None = None, max_retries: int = 5) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"x-api-key": API_KEY}

    for attempt in range(max_retries):
        limiter.wait()
        resp = requests.get(url, headers=headers, params=params, timeout=10)

        remaining = resp.headers.get("x-ratelimit-remaining")
        reset = resp.headers.get("x-ratelimit-reset")

        if resp.status_code == 429:
            if reset:
                delay = max(int(reset) - time.time(), 1)
            else:
                delay = 2 ** attempt + random.random()   # exponential backoff + jitter
            time.sleep(delay)
            continue

        resp.raise_for_status()

        # Proactive slowdown when nearly out of budget
        if remaining is not None and int(remaining) < 20 and reset:
            time.sleep(max(int(reset) - time.time(), 0))

        return resp.json()

    raise RuntimeError(f"Gave up after {max_retries} attempts: {path}")
```

### 5.5 Pagination without blowing the budget

```python
def get_all_stops(route: str, page_size: int = 100) -> list[dict]:
    results, offset = [], 0
    while True:
        page = mbta_get("/stops", {
            "filter[route]": route,
            "page[limit]": page_size,
            "page[offset]": offset,
            "fields[stop]": "name,latitude,longitude",
        })["data"]
        results.extend(page)
        if len(page) < page_size:
            return results
        offset += page_size
```

### 5.6 Other tips

- **Concurrency multiplies request rate.** If you use threads or `asyncio`, share **one** limiter across all workers.
- **One key per app/environment.** Limits apply per key, so separate keys for dev and prod keep a runaway test script from starving production. Don't use multiple keys to dodge the limit.
- **Need more?** Request a higher limit through the V3 API Portal.
- **Log `x-ratelimit-remaining`** during development so you can see which code paths are expensive.

---

## 6. Checklist

- [ ] API key in `.env`, `.env` in `.gitignore`
- [ ] Key sent via `x-api-key` header
- [ ] Server-side `filter[...]` and `fields[...]` on every call
- [ ] Stop data cached; `If-Modified-Since` used where it helps
- [ ] Client-side limiter set below 1,000/min (e.g. 900)
- [ ] 429 handling that waits until `x-ratelimit-reset`
- [ ] Streaming instead of polling for real-time data