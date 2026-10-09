"""Decision journal and scorecard: every RULERS verdict and Radar EVENT/PROBLEM is logged with the
price at the time, then checked against what happened (vs the S&P 500) once it is old enough.

    python -m ruleone.scorecard record    # append this week's calls to research/scorecard/calls.csv
    python -m ruleone.scorecard evaluate  # -> research/scorecard/latest.json + scorecard.md

"Judge process, not outcomes" (InvestED 294, 319): the Professor's review reads this to find calls
where the *method* missed something (a flag that was ignored, a story that changed), not to chase
returns. "Mistakes are the curriculum" (201, 275).
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from .http import Fetcher

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "scorecard"
CALLS = OUT / "calls.csv"
FIELDS = ["date", "agent", "ticker", "verdict", "price", "spy", "tranche1", "note"]
SPY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5d&interval=1d"
HORIZONS = [("1m", 28), ("3m", 91), ("6m", 182), ("1y", 365)]


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def spy_price(fetcher: Fetcher | None = None) -> float | None:
    try:
        data = (fetcher or Fetcher(ROOT / ".cache")).get_json(SPY_URL, ttl_hours=6)
        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception:
        return None


def prices_now() -> dict[str, float]:
    f = ROOT / "lists" / "latest" / "universe.csv"
    if not f.exists():
        return {}
    with f.open() as fh:
        return {r["ticker"]: float(r["price"]) for r in csv.DictReader(fh) if _f(r.get("price"))}


def load_calls() -> list[dict]:
    if not CALLS.exists():
        return []
    with CALLS.open() as fh:
        return list(csv.DictReader(fh))


def new_calls(today: date, existing: list[dict], dossiers: list[dict], radar: dict, px: dict, spy: float | None) -> list[dict]:
    """One row per new verdict: a dossier verdict that changed, or a Radar EVENT/PROBLEM not yet logged."""
    last = {}
    for c in existing:
        last[(c["agent"], c["ticker"])] = c
    out = []
    for d in dossiers:
        prev = last.get(("rulers", d["ticker"]))
        if prev and prev["verdict"] == d["verdict"]:
            continue
        out.append({"date": d.get("updated") or today.isoformat(), "agent": "rulers", "ticker": d["ticker"],
                    "verdict": d["verdict"], "price": d.get("price_at_update") or px.get(d["ticker"]),
                    "spy": spy, "tranche1": (d.get("entry") or [None])[0], "note": (d.get("summary") or "")[:160]})
    seen = {(c["agent"], c["ticker"], c["date"]) for c in existing}
    for t, items in radar.items():
        for it in items:
            if it.get("verdict") in ("EVENT", "PROBLEM") and ("radar", t, it.get("date")) not in seen:
                seen.add(("radar", t, it.get("date")))
                out.append({"date": it.get("date"), "agent": "radar", "ticker": t, "verdict": it["verdict"],
                            "price": px.get(t), "spy": spy, "tranche1": None, "note": (it.get("headline") or "")[:160]})
    return out


def record(today: date) -> int:
    dossiers = json.loads((ROOT / "research" / "rulers" / "index.json").read_text()) \
        if (ROOT / "research" / "rulers" / "index.json").exists() else []
    radar = json.loads((ROOT / "research" / "radar" / "history.json").read_text()) \
        if (ROOT / "research" / "radar" / "history.json").exists() else {}
    existing = load_calls()
    rows = new_calls(today, existing, dossiers, radar, prices_now(), spy_price())
    OUT.mkdir(parents=True, exist_ok=True)
    write_header = not CALLS.exists()
    with CALLS.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def evaluate(today: date, spy_now: float | None = None, px: dict | None = None) -> dict:
    calls, px = load_calls(), px if px is not None else prices_now()
    spy_now = spy_now if spy_now is not None else spy_price()
    graded = []
    for c in calls:
        p0, s0, p1 = _f(c["price"]), _f(c["spy"]), px.get(c["ticker"])
        if not (p0 and p1):
            continue
        age = (today - date.fromisoformat(c["date"])).days
        ret = p1 / p0 - 1
        excess = ret - (spy_now / s0 - 1) if s0 and spy_now else None
        graded.append({**c, "age_days": age, "return": round(ret, 4), "excess": None if excess is None else round(excess, 4)})
    summary = {}
    for v in sorted({g["verdict"] for g in graded}):
        g = [x for x in graded if x["verdict"] == v and x["age_days"] >= 28 and x["excess"] is not None]
        if g:
            summary[v] = {"calls": len(g), "avg_excess": round(sum(x["excess"] for x in g) / len(g), 4),
                          "beat_spy": round(sum(x["excess"] > 0 for x in g) / len(g), 3)}
    # Calls to learn from: BUY/EVENT names that fell >20% vs the market, AVOID/PROBLEM names that rose >20%.
    lessons = [x for x in graded if x["age_days"] >= 28 and x["excess"] is not None and (
        (x["verdict"] in ("BUY", "ACCUMULATE", "EVENT") and x["excess"] < -0.2) or
        (x["verdict"] in ("AVOID", "PROBLEM") and x["excess"] > 0.2))]
    out = {"date": today.isoformat(), "calls": len(calls), "graded": len(graded), "by_verdict": summary,
           "review_candidates": lessons, "recent": sorted(graded, key=lambda x: x["date"], reverse=True)[:40]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(out, indent=1) + "\n")
    md = [f"# Scorecard: {today.isoformat()}", "",
          "Every RULERS verdict and Radar EVENT/PROBLEM, with the price when it was made. Returns are versus the "
          "S&P 500 (SPY), graded after 4 weeks. **Judge the process, not the outcome**: a sound pass that later rose "
          "is not a mistake [339]. The Professor reviews the outliers for lessons.", "",
          f"{len(calls)} calls logged, {len(graded)} priced.", "", "| Verdict | Graded calls | Avg vs S&P | Beat S&P |", "|---|---:|---:|---:|"]
    md += [f"| {v} | {s['calls']} | {s['avg_excess']:+.1%} | {s['beat_spy']:.0%} |" for v, s in summary.items()] or ["| – | 0 | – | – |"]
    if lessons:
        md += ["", "## Calls to learn from", ""] + [
            f"- {x['date']} {x['agent']} **{x['ticker']}** {x['verdict']} at ${float(x['price']):,.2f}: "
            f"{x['return']:+.0%} ({x['excess']:+.0%} vs S&P). {x['note']}" for x in lessons]
    (OUT / "scorecard.md").write_text("\n".join(md) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "evaluate"])
    a = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    if a.cmd == "record":
        print(f"logged {record(today)} new call(s)")
    else:
        r = evaluate(today)
        print(f"{r['calls']} calls, {r['graded']} graded, {len(r['review_candidates'])} to review")


if __name__ == "__main__":
    main()
