"""Shared helpers: polite HTTP client, paths, constants."""
import json
import os
import threading
import time

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("LAWCODEX_RAW", os.path.join(os.path.dirname(ROOT), "_raw", "nz"))

WAYBACK = "https://web.archive.org"
SITE = "https://www.legislation.govt.nz"

# Minimum seconds between the start of two requests (global, across threads).
MIN_INTERVAL = float(os.environ.get("LAWCODEX_MIN_INTERVAL", "1.0"))

_lock = threading.Lock()
_last = [0.0]
_local = threading.local()


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def _throttle():
    with _lock:
        now = time.monotonic()
        wait = _last[0] + MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def get(url, params=None, timeout=180, tries=7):
    """GET with global rate limiting and exponential backoff. Returns Response, or None for 404."""
    delay = 10
    err = None
    for attempt in range(tries):
        _throttle()
        try:
            r = _session().get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            err = str(e)
        else:
            if r.status_code == 200:
                return r
            if r.status_code in (404, 410):
                return None
            err = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (429, 503, 509):
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    delay = max(delay, int(ra))
        if attempt < tries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 600)
    raise RuntimeError(f"GET {url} {params} failed: {err}")


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
