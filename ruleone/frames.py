"""Stage 1: universe-wide annual fundamentals from SEC XBRL frames.

One frames request returns a concept/period for *every* filer, so ~600
requests cover ~5,800 companies x 14 years.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .concepts import FLOW, INSTANT, STAGE1_FLOW, STAGE1_INSTANT
from .http import Fetcher

FRAME_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/{unit}/{period}.json"


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _fetch_frame(fetcher: Fetcher, tag: str, unit: str, period: str, ttl: float):
    data = fetcher.get_json(FRAME_URL.format(tag=tag, unit=unit, period=period), ttl_hours=ttl)
    return (data or {}).get("data", [])


def load_frames(fetcher: Fetcher, ciks: set[int], first_year: int, last_year: int,
                workers: int = 6, ttl_recent: float = 24 * 6, ttl_old: float = 24 * 60,
                log=print) -> dict[int, dict[int, dict]]:
    """Return {cik: {fiscal_year: {field: value, 'end': date}}}.

    Annual flows come from CY#### frames. Balance-sheet values come from the
    quarterly instant frame (CY####Q#I) whose date is closest to that
    company's fiscal year end.
    """
    jobs = []
    this_year = date.today().year
    for field in STAGE1_FLOW:
        unit, tags = FLOW[field]
        for prio, tag in enumerate(tags):
            for y in range(first_year, last_year + 1):
                jobs.append(("flow", field, prio, tag, unit, f"CY{y}", y))
    for field in STAGE1_INSTANT:
        unit, tags = INSTANT[field]
        for prio, tag in enumerate(tags):
            for y in range(first_year, last_year + 1):
                for q in (1, 2, 3, 4):
                    jobs.append(("inst", field, prio, tag, unit, f"CY{y}Q{q}I", y))
    log(f"[frames] {len(jobs)} frame requests")

    def run(job):
        kind, field, prio, tag, unit, period, y = job
        ttl = ttl_recent if y >= this_year - 1 else ttl_old
        return job, _fetch_frame(fetcher, tag, unit, period, ttl)

    # flows[cik][year][field] = (prio, val, end)
    flows: dict = defaultdict(lambda: defaultdict(dict))
    insts: dict = defaultdict(lambda: defaultdict(dict))   # insts[cik][field][end] = (prio, val)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for job, rows in ex.map(run, jobs):
            kind, field, prio, tag, unit, period, y = job
            for r in rows:
                cik = r["cik"]
                if cik not in ciks:
                    continue
                if kind == "flow":
                    cur = flows[cik][y].get(field)
                    if cur is None or prio < cur[0]:
                        flows[cik][y][field] = (prio, r["val"], r["end"])
                else:
                    cur = insts[cik][field].get(r["end"])
                    if cur is None or prio < cur[0]:
                        insts[cik][field][r["end"]] = (prio, r["val"])
            done += 1
            if done % 100 == 0:
                log(f"[frames] {done}/{len(jobs)}")

    out: dict[int, dict[int, dict]] = {}
    for cik, years in flows.items():
        rec: dict[int, dict] = {}
        for y, fields in years.items():
            ends = [v[2] for v in fields.values()]
            fy_end = max(set(ends), key=ends.count)
            row = {"end": fy_end}
            row.update({f: v[1] for f, v in fields.items()})
            for field, by_end in insts.get(cik, {}).items():
                best = min(by_end, key=lambda e: abs((_d(e) - _d(fy_end)).days), default=None)
                if best and abs((_d(best) - _d(fy_end)).days) <= 50:
                    row[field] = by_end[best][1]
            rec[y] = row
        out[cik] = rec
    return out
