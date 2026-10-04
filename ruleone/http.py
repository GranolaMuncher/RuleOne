"""Rate-limited, disk-cached HTTP fetcher.

SEC fair-access policy: <= 10 requests/second and a User-Agent that identifies
you with a contact address. Set SEC_USER_AGENT="Your Name you@example.com".
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import requests

# SEC rejects some no-reply domains; set SEC_USER_AGENT to your own "Name email".
DEFAULT_UA = "RuleOne Screener contact@ruleone.invalid"


class Fetcher:
    def __init__(self, cache_dir: str | os.PathLike = ".cache", sec_rps: float = 8.0,
                 user_agent: str | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ua = user_agent or os.environ.get("SEC_USER_AGENT") or DEFAULT_UA
        self.session = requests.Session()
        self._min_interval = {"sec": 1.0 / sec_rps, "yahoo": 0.15}
        self._last = {"sec": 0.0, "yahoo": 0.0}
        self._lock = threading.Lock()

    # -- internals -------------------------------------------------------
    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last[host] + self._min_interval[host] - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha1(url.encode()).hexdigest()
        return self.cache_dir / h[:2] / f"{h}.json.gz"

    # -- public ----------------------------------------------------------
    def get_json(self, url: str, ttl_hours: float = 24.0, retries: int = 4):
        """GET a JSON document; returns None on 404. Cached for ttl_hours."""
        path = self._cache_path(url)
        if path.exists() and (time.time() - path.stat().st_mtime) < ttl_hours * 3600:
            with gzip.open(path, "rt") as fh:
                return json.load(fh)
        text = self.get_text(url, retries=retries)
        if text is None:
            return None
        data = json.loads(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt") as fh:
            json.dump(data, fh)
        return data

    def get_text_cached(self, url: str, ttl_hours: float = 24 * 365) -> str | None:
        """Cached text GET for immutable documents (e.g. EDGAR archive filings)."""
        path = self._cache_path(url).with_suffix(".txt.gz")
        if path.exists() and (time.time() - path.stat().st_mtime) < ttl_hours * 3600:
            with gzip.open(path, "rt") as fh:
                return fh.read()
        text = self.get_text(url)
        if text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wt") as fh:
                fh.write(text)
        return text

    def get_text(self, url: str, retries: int = 4) -> str | None:
        host = "sec" if "sec.gov" in url else "yahoo"
        headers = {"User-Agent": self.ua if host == "sec" else
                   "Mozilla/5.0 (X11; Linux x86_64) RuleOne/0.1",
                   "Accept-Encoding": "gzip, deflate"}
        delay = 2.0
        for attempt in range(retries + 1):
            self._throttle(host)
            try:
                r = self.session.get(url, headers=headers, timeout=60)
            except requests.RequestException:
                if attempt == retries:
                    raise
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.text
        return None
