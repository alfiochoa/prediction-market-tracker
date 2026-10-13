"""Resilient HTTP client: timeout, retries with backoff, rate limit, disk cache, UA."""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from . import USER_AGENT
from .log import event, get_logger

log = get_logger("pmtracker.http")
RETRY_STATUS = {429, 500, 502, 503, 504}


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, *, timeout: float = 15.0, retries: int = 4,
                 backoff: float = 1.0, min_interval: float = 0.3,
                 cache_dir: Optional[Path] = None, cache_ttl: float = 300.0,
                 transport: Optional[httpx.BaseTransport] = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.base_url = base_url.rstrip("/")
        self.retries, self.backoff, self.min_interval = retries, backoff, min_interval
        self.cache_dir, self.cache_ttl, self._sleep = cache_dir, cache_ttl, sleep
        self._last = 0.0
        self._client = httpx.Client(timeout=timeout, transport=transport,
                                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    def _cache_path(self, key: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return Path(self.cache_dir) / (hashlib.sha1(key.encode()).hexdigest() + ".json")

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = time.monotonic()

    def get_json(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        key = url + "?" + json.dumps(params or {}, sort_keys=True)
        cp = self._cache_path(key)
        if cp and cp.exists() and time.time() - cp.stat().st_mtime < self.cache_ttl:
            event(log, "cache_hit", path=path)
            return json.loads(cp.read_text())
        last_err: Optional[str] = None
        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                r = self._client.get(url, params=params)
                if r.status_code in RETRY_STATUS:
                    last_err = f"HTTP {r.status_code}"
                    delay = float(r.headers.get("Retry-After", 0) or 0)
                else:
                    r.raise_for_status()
                    data = r.json()
                    if cp:
                        cp.parent.mkdir(parents=True, exist_ok=True)
                        cp.write_text(json.dumps(data))
                    return data
            except (httpx.TransportError, ValueError) as e:
                last_err, delay = repr(e), 0.0
            except httpx.HTTPStatusError as e:
                raise ApiError(f"{path}: HTTP {e.response.status_code}") from e
            if attempt < self.retries:
                delay = max(delay, self.backoff * 2 ** attempt) + random.uniform(0, 0.25)
                event(log, "retry", logging.WARNING, path=path, attempt=attempt + 1, error=last_err, delay=round(delay, 2))
                self._sleep(delay)
        raise ApiError(f"{path}: gave up after {self.retries + 1} attempts ({last_err})")
