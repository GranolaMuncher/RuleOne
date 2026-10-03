"""Stage 2: per-company detail from the SEC companyfacts API.

Builds fiscal-year annual series from 10-K filings plus trailing-twelve-month
(TTM) values: TTM = last FY + current YTD - prior-year YTD (from 10-Qs).
"""
from __future__ import annotations

from datetime import date

from .concepts import FLOW, INSTANT
from .http import Fetcher

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "40-F"}


def _d(s):
    return date.fromisoformat(s)


def _days(e):
    return (_d(e["end"]) - _d(e["start"])).days


def _entries(gaap: dict, tags, unit):
    """Merged fact list across alias tags; earlier tags win per (start, end)."""
    unit = unit.replace("-per-", "/")      # frames "USD-per-shares" == facts "USD/shares"
    seen, out = set(), []
    for tag in tags:
        ents = [e for e in gaap.get(tag, {}).get("units", {}).get(unit, [])
                if (e.get("start"), e["end"]) not in seen]
        seen.update((e.get("start"), e["end"]) for e in ents)
        out.extend(ents)
    return out


def _latest_filed(entries):
    best = {}
    for e in entries:
        k = (e.get("start"), e["end"])
        if k not in best or e["filed"] > best[k]["filed"]:
            best[k] = e
    return list(best.values())


def annual_series(entries):
    """{fy_end: value} for ~12-month periods, one per fiscal year."""
    ann = [e for e in _latest_filed(entries) if e.get("start") and 340 <= _days(e) <= 380]
    ann.sort(key=lambda e: e["end"])
    out = {}
    for e in ann:
        if out:
            prev = max(out)
            if (_d(e["end"]) - _d(prev)).days < 300:   # duplicate / 52-53 week overlap
                out.pop(prev)
        out[e["end"]] = e["val"]
    return out


def ttm(entries):
    """(ttm_value, period_end) using FY + YTD - prior YTD. Falls back to latest FY."""
    ents = _latest_filed([e for e in entries if e.get("start")])
    fys = sorted((e for e in ents if 340 <= _days(e) <= 380), key=lambda e: e["end"])
    if not fys:
        return None, None
    fy = fys[-1]
    ytds = sorted((e for e in ents if 80 <= _days(e) <= 290 and e["end"] > fy["end"]
                   and abs((_d(e["start"]) - _d(fy["end"])).days) <= 10), key=lambda e: e["end"])
    if not ytds:
        return fy["val"], fy["end"]
    cur = ytds[-1]
    for e in ents:
        if abs((_d(cur["end"]) - _d(e["end"])).days - 365) <= 10 and abs(_days(e) - _days(cur)) <= 10 \
                and e["end"] <= fy["end"]:
            return fy["val"] + cur["val"] - e["val"], cur["end"]
    return fy["val"], fy["end"]


def latest_instant(entries):
    ents = [e for e in entries if not e.get("start")] or entries
    if not ents:
        return None, None
    e = max(ents, key=lambda e: (e["end"], e["filed"]))
    return e["val"], e["end"]


def load_company(fetcher: Fetcher, cik: int, ttl_hours: float = 24 * 3) -> dict | None:
    facts = fetcher.get_json(FACTS_URL.format(cik=cik), ttl_hours=ttl_hours)
    if not facts:
        return None
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    out = {"name": facts.get("entityName"), "annual": {}, "ttm": {}, "latest": {}}
    by_end: dict[str, dict] = {}
    for field, (unit, tags) in FLOW.items():
        ents = _entries(gaap, tags, unit)
        if not ents:
            continue
        for end, v in annual_series(ents).items():
            by_end.setdefault(end, {})[field] = v
        if field in ("shares", "dps"):          # not additive: keep latest reported period
            dur = [e for e in _latest_filed(ents) if e.get("start")]
            if dur:
                e = max(dur, key=lambda e: (e["end"], _days(e)))
                key = "diluted_shares" if field == "shares" else "dps_latest"
                out["latest"][key], out["latest"][key + "_date"] = e["val"], e["end"]
            continue
        val, end = ttm(ents)
        if val is not None:
            out["ttm"][field] = val
            out["ttm"].setdefault("_end", end)
    fy_ends = sorted(e for e, r in by_end.items() if "revenue" in r or "net_income" in r)
    for field, (unit, tags) in INSTANT.items():
        ents = _entries(gaap, tags, unit)
        if not ents:
            continue
        for end in fy_ends:
            m = [e for e in ents if abs((_d(e["end"]) - _d(end)).days) <= 7]
            if m:
                by_end[end][field] = max(m, key=lambda e: e["filed"])["val"]
        out["latest"][field], out["latest"][field + "_date"] = latest_instant(ents)
    so = dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if so:   # multi-class issuers report one fact per class: sum the latest filing's facts
        last = max(so, key=lambda e: (e["filed"], e["end"]))
        same = {(e["end"], e["val"]) for e in so if e["accn"] == last["accn"]}
        out["latest"]["shares_outstanding"] = sum(v for _, v in same)
        out["latest"]["shares_outstanding_date"] = last["end"]
    # key annual rows by fiscal year = calendar year of FY end (Jan ends -> prior year)
    for end in fy_ends:
        d = _d(end)
        fy = d.year - 1 if d.month <= 1 else d.year
        row = dict(by_end[end])
        row["end"] = end
        out["annual"][fy] = row
    return out
