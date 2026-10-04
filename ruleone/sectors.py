"""Sector and industry for every listed company.

Industry = the SEC's SIC description for the filer (e.g. "Services-Prepackaged
Software"). Sector = that SIC code mapped onto 11 GICS-style sectors so the
site can offer a short, familiar sector filter.

SIC codes rarely change, so they live in a committed reference file
(lists/reference/sic.csv). Each run fetches only companies missing from it
plus a small rotating batch of the oldest entries.
"""
from __future__ import annotations

import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .http import Fetcher

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FIELDS = ["cik", "sic", "industry", "sector", "updated"]

# (low, high, sector), checked in order, so specific ranges come before broad ones.
_RANGES = [
    (100, 999, "Consumer Staples"),
    (1000, 1099, "Materials"), (1200, 1399, "Energy"), (1400, 1499, "Materials"),
    (1500, 1799, "Industrials"),
    (2000, 2199, "Consumer Staples"),
    (2200, 2399, "Consumer Discretionary"),
    (2400, 2499, "Materials"), (2500, 2599, "Consumer Discretionary"), (2600, 2699, "Materials"),
    (2700, 2799, "Communication Services"),
    (2830, 2836, "Health Care"), (2840, 2844, "Consumer Staples"), (2800, 2899, "Materials"),
    (2900, 2999, "Energy"),
    (3021, 3021, "Consumer Discretionary"), (3000, 3099, "Materials"),
    (3100, 3199, "Consumer Discretionary"),
    (3200, 3399, "Materials"),
    (3400, 3499, "Industrials"),
    (3570, 3579, "Information Technology"), (3500, 3599, "Industrials"),
    (3630, 3639, "Consumer Discretionary"), (3600, 3699, "Information Technology"),
    (3710, 3716, "Consumer Discretionary"), (3750, 3751, "Consumer Discretionary"), (3700, 3799, "Industrials"),
    (3812, 3812, "Industrials"), (3840, 3851, "Health Care"), (3860, 3873, "Consumer Discretionary"),
    (3800, 3899, "Information Technology"),
    (3900, 3999, "Consumer Discretionary"),
    (4000, 4799, "Industrials"),
    (4800, 4899, "Communication Services"),
    (4950, 4959, "Industrials"), (4900, 4999, "Utilities"),
    (5045, 5045, "Information Technology"), (5122, 5122, "Health Care"), (5140, 5149, "Consumer Staples"),
    (5000, 5199, "Industrials"),
    (5400, 5499, "Consumer Staples"), (5912, 5912, "Consumer Staples"), (5200, 5999, "Consumer Discretionary"),
    (6500, 6599, "Real Estate"), (6798, 6798, "Real Estate"), (6000, 6799, "Financials"),
    (7000, 7099, "Consumer Discretionary"), (7200, 7299, "Consumer Discretionary"),
    (7310, 7319, "Communication Services"), (7370, 7379, "Information Technology"), (7300, 7399, "Industrials"),
    (7500, 7599, "Consumer Discretionary"), (7800, 7899, "Communication Services"),
    (7900, 7999, "Consumer Discretionary"),
    (8000, 8099, "Health Care"), (8731, 8731, "Health Care"),
    (8200, 8299, "Consumer Discretionary"), (8100, 8999, "Industrials"),
]
SECTORS = sorted({s for _, _, s in _RANGES})


def sic_to_sector(sic) -> str:
    try:
        code = int(sic)
    except (TypeError, ValueError):
        return ""
    for lo, hi, sector in _RANGES:
        if lo <= code <= hi:
            return sector
    return "Other"


def load_reference(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    with open(path, newline="") as fh:
        return {int(r["cik"]): r for r in csv.DictReader(fh)}


def save_reference(path: Path, ref: dict[int, dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for cik in sorted(ref):
            w.writerow({k: ref[cik].get(k, "") for k in FIELDS})


def _fetch_one(fetcher: Fetcher, cik: int, today: str) -> dict | None:
    # Not cached on disk: these files are ~160 KB each and only three fields are kept.
    try:
        text = fetcher.get_text(SUBMISSIONS_URL.format(cik=cik))
    except Exception:
        return None
    if not text:
        return None
    d = json.loads(text)
    sic = d.get("sic") or ""
    return {"cik": cik, "sic": sic, "industry": (d.get("sicDescription") or "").strip(),
            "sector": sic_to_sector(sic), "updated": today}


def refresh_reference(fetcher: Fetcher, ciks, path: Path, today: date, rotate: int = 300,
                      workers: int = 6, log=print) -> dict[int, dict]:
    """Fetch SIC for CIKs missing from the reference plus the `rotate` oldest entries."""
    ref = load_reference(path)
    ciks = set(ciks)
    missing = [c for c in ciks if c not in ref]
    stale = sorted((c for c in ciks if c in ref), key=lambda c: ref[c].get("updated", ""))[:rotate]
    todo = missing + stale
    if todo:
        log(f"[sectors] fetching {len(missing)} new + {len(stale)} refresh")
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for rec in ex.map(lambda c: _fetch_one(fetcher, c, today.isoformat()), todo):
                if rec:
                    ref[rec["cik"]] = rec
                done += 1
                if done % 500 == 0:
                    log(f"[sectors] {done}/{len(todo)}")
                    save_reference(path, ref)       # checkpoint long first builds
        save_reference(path, ref)
    # re-derive sectors in case the mapping changed
    for r in ref.values():
        r["sector"] = sic_to_sector(r.get("sic"))
    return ref
