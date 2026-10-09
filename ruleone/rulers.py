"""RULERS analyst: weekly living dossiers (Radar, Understand, Love, Event, Reduce basis, Story).

    python -m ruleone.rulers prepare [--tickers A,B]   # pick names + fact packs -> .work/rulers/inputs.json
    (Claude writes/updates research/rulers/<TICKER>.md per agents/rulers/PROMPT.md)
    python -m ruleone.rulers record                     # rebuild research/rulers/index.json from the dossiers

Python does the arithmetic (fresh screen numbers, ten-year history, a default tranche ladder) so the
analyst spends its effort on judgement: understanding, moat, management, event and story.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .analysts import load as load_analysts
from .companyfacts import load_company
from .http import Fetcher
from .knowledge import lookup as invested_mentions
from .metrics import MARKER_LABELS, bvps, fcf, normalize_splits, owner_earnings, roic, wonderful_markers
from .normalize import normalize
from .screener import analyze
from .universe import load_universe

ROOT = Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists" / "latest"
OUT = ROOT / "research" / "rulers"
WORK = ROOT / ".work" / "rulers"
RADAR = ROOT / "research" / "radar"
WATCHLIST = ROOT / "research" / "watchlist.txt"
MAX_NAMES = 12
VERDICTS = ("BUY", "ACCUMULATE", "WATCH", "AVOID", "TOO HARD")


# ---------------------------------------------------------------- tranche ladder
def tranche_plan(price: float | None, mos: float | None, payback: float | None, ten_cap: float | None,
                 sticker: float | None) -> dict | None:
    """Default Reduce-basis ladder: three equal dollar tranches set in advance (InvestED 199, 266, 352).

    Tranche 1 sits at the highest of the three Rule #1 buy prices (never above Sticker), the others step
    down through the remaining prices, keeping dry powder for a further fall (InvestED 314, 390).
    Tranche buying only: RuleOne excludes options."""
    levels = sorted({round(min(v, sticker) if sticker else v, 2) for v in (ten_cap, payback, mos) if v and v > 0},
                    reverse=True)
    if not levels:
        return None
    top = levels[0]
    if len(levels) >= 3:
        steps = levels[:3]
    elif len(levels) == 2:
        steps = [levels[0], levels[1], round(levels[1] * 0.85, 2)]
    else:
        steps = [top, round(top * 0.85, 2), round(top * 0.7, 2)]
    plan = {"tranches": [{"n": i + 1, "price": p, "size": "1/3 of the intended position (in dollars)"}
                         for i, p in enumerate(steps)],
            "stop_buying_above": top, "trim_above": round(sticker, 2) if sticker else None,
            # Triangulate (InvestED 071, 280): a lowest level under half the highest means the methods disagree.
            "methods_spread": round(levels[-1] / top, 3), "methods_disagree": levels[-1] < 0.5 * top}
    if price is not None:
        plan["price_vs_tranche1"] = round(price / top - 1, 4)
        plan["tranches_triggered"] = sum(1 for p in steps if price <= p)
    return plan


# ---------------------------------------------------------------- scope
def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def pick_names(candidates: list[dict], radar_hist: dict, watchlist: list[str], existing: dict[str, str],
               today: date, forced: list[str] | None = None, limit: int = MAX_NAMES) -> list[tuple[str, str]]:
    """[(ticker, reason)]: forced names, your watchlist, buy-range leaders, fresh Radar events, then
    stale dossiers due a refresh. Micro-caps only when tier A (as the scout did)."""
    out: dict[str, str] = {}
    for t in forced or []:
        out.setdefault(t, "requested")
    for t in watchlist:
        out.setdefault(t, "on research/watchlist.txt")
    ranked = sorted((r for r in candidates if r.get("status") in ("BUY", "BUY*")
                     and ("micro-cap" not in (r.get("flags") or "") or r.get("tier") == "A")),
                    key=lambda r: -(_f(r.get("rank_score")) or 0))
    for r in ranked[:10]:
        out.setdefault(r["ticker"], f"buy range ({r['status']}, tier {r['tier']}, rank {r.get('rank_score')})")
    cutoff = (today - timedelta(days=7)).isoformat()
    for t, items in radar_hist.items():
        if any(it.get("verdict") in ("EVENT", "PROBLEM") and (it.get("date") or "") >= cutoff for it in items):
            out.setdefault(t, f"Radar {items[0]['verdict']} {items[0]['date']}")
    for t in sorted(existing, key=lambda t: existing[t]):          # stalest dossier first
        out.setdefault(t, f"existing dossier (updated {existing[t] or 'never'}): refresh")
    return list(out.items())[:limit]


# ---------------------------------------------------------------- fact pack
def history(annual: dict) -> list[dict]:
    rows = []
    for y in sorted(normalize_splits(annual))[-11:]:
        r = annual[y]
        rows.append({"fy": y, "revenue": r.get("revenue"), "net_income": r.get("net_income"), "eps": r.get("eps"),
                     "bvps": bvps(r), "ocf": r.get("ocf"), "fcf": fcf(r), "owner_earnings": owner_earnings(r),
                     "roic": roic(r), "lt_debt": r.get("lt_debt"), "shares": r.get("shares")})
    return rows


def _round(v):
    if isinstance(v, float):
        return round(v, 4) if abs(v) < 1000 else round(v)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def street_pack(ticker: str) -> dict | None:
    """Analyst consensus from lists/latest/analysts.csv plus the target's path from research/analysts/history.json."""
    row = load_analysts().get(ticker)
    if not row:
        return None
    hp = ROOT / "research" / "analysts" / "history.json"
    hist = json.loads(hp.read_text()).get(ticker, []) if hp.exists() else []
    keep = ("as_of", "target_low", "target_mean", "target_median", "target_high", "n_analysts", "rec_mean", "rec_key",
            "strong_buy", "buy", "hold", "sell", "strong_sell", "eps_growth_cy", "eps_growth_ny", "upside_mean",
            "mean_vs_sticker", "revision_30d", "street_signal", "recent_actions")
    return {**{k: (_f(row[k]) if k not in ("as_of", "rec_key", "street_signal", "recent_actions") else row[k]) for k in keep},
            "target_history": hist[-8:]}


def fact_pack(fetcher: Fetcher, listing, today: date, radar_hist: dict, gurus: dict, snaps: list[dict]) -> dict | None:
    rec = analyze(fetcher, listing, None, today, with_events=True)
    if not rec:
        return None
    cf = load_company(fetcher, listing.cik)
    nz = normalize(fetcher, listing, cf, today) if cf else None
    t = listing.ticker
    markers = wonderful_markers(cf["annual"], cf["ttm"], nz["debt"] if nz else None, cf.get("latest")) if cf else {}
    review = json.loads((ROOT / "research" / "reviews" / "latest.json").read_text()) \
        if (ROOT / "research" / "reviews" / "latest.json").exists() else {}
    dossier = OUT / f"{t}.md"
    cfg = ROOT / "reports" / "config" / f"{t}.json"
    model = ROOT / "reports" / "model" / f"{t}.md"
    return _round({
        "ticker": t, "cik": listing.cik,
        "screen": {k: rec.get(k) for k in (
            "name", "exchange", "sector", "status", "tier", "price", "price_date", "market_cap", "sticker", "mos_price",
            "payback_price", "ten_cap_price", "methods_agree", "price_to_sticker", "windage_growth", "future_pe",
            "hist_pe_median", "pe_ttm", "eps_ttm", "fcf_ttm", "owner_earnings_ttm", "net_debt", "cash_conversion",
            "debt", "debt_years_total", "big5_score", "big5_tests", "roic10", "roic5", "roic1", "sales_g10", "sales_g5",
            "eps_g10", "eps_g5", "bvps_g10", "bvps_g5", "ocf_g10", "ocf_g5", "drawdown_52w", "events",
            "next_report_est", "flags", "rank_score", "marker_score")},
        "history_usd": history(nz["annual_usd"]) if nz else [],
        "tranche_plan": tranche_plan(rec["price"], rec.get("mos_price"), rec.get("payback_price"),
                                     rec.get("ten_cap_price"), rec.get("sticker")),
        "markers": {k: {**v, "label": MARKER_LABELS[k]} for k, v in markers.items()},
        "street": street_pack(t),                          # sell-side consensus: a lead and a ceiling, never value
        "invested_episodes": invested_mentions(t, 8),      # what Phil and Danielle said about this company
        "last_review": next((r for r in review.get("reviews", []) if r.get("ticker") == t), None),
        "radar": radar_hist.get(t, [])[:6],
        "gurus": gurus.get("by_ticker", {}).get(t, []),
        "screen_history": snaps,
        "dossier": str(dossier.relative_to(ROOT)), "dossier_exists": dossier.exists(),
        "deepdive_config": str(cfg.relative_to(ROOT)) if cfg.exists() else None,
        "deepdive_model": str(model.relative_to(ROOT)) if model.exists() else None,
        "sec_filings": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={listing.cik}&type=10-K",
    })


def prepare(fetcher: Fetcher, today: date, forced: list[str] | None = None, limit: int = MAX_NAMES, log=print) -> dict:
    candidates = read_csv(LISTS / "all_candidates.csv")
    radar_hist = json.loads((RADAR / "history.json").read_text()) if (RADAR / "history.json").exists() else {}
    gurus = json.loads((LISTS / "gurus.json").read_text()) if (LISTS / "gurus.json").exists() else {}
    watch = [l.strip().upper() for l in WATCHLIST.read_text().splitlines()
             if l.strip() and not l.startswith("#")] if WATCHLIST.exists() else []
    existing = {p.stem: parse_front(p.read_text()).get("updated", "") for p in OUT.glob("*.md")} if OUT.exists() else {}
    picks = pick_names(candidates, radar_hist, watch, existing, today, forced, limit)
    snapshots = read_csv(ROOT / "lists" / "history.csv")
    uni = load_universe(fetcher)
    by_ticker = {l.ticker: l for l in (uni.values() if isinstance(uni, dict) else uni)}
    packs = []
    for t, why in picks:
        listing = by_ticker.get(t)
        if not listing:
            log(f"[rulers] {t}: not an NYSE/Nasdaq listing, skipped")
            continue
        snaps = [{k: s[k] for k in ("run_date", "status", "price", "sticker", "mos_price")}
                 for s in snapshots if s.get("ticker") == t][-8:]
        pack = fact_pack(fetcher, listing, today, radar_hist, gurus, snaps)
        if pack:
            pack["why_selected"] = why
            packs.append(pack)
            log(f"[rulers] {t}: {why}")
    payload = {"date": today.isoformat(), "names": packs,
               "screen_counts": {s: sum(1 for r in candidates if r.get("status") == s) for s in ("BUY", "BUY*", "ON DECK")}}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "inputs.json").write_text(json.dumps(payload, indent=1, default=str))
    return payload


# ---------------------------------------------------------------- index
def parse_front(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    meta: dict = {}
    if not m:
        return meta
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w+):\s*(.*)$", line)
        if not kv:
            continue
        v = kv.group(2).strip().strip('"')
        if v.startswith("["):
            meta[kv.group(1)] = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
        else:
            meta[kv.group(1)] = v
    return meta


def record() -> int:
    """Index every dossier's front matter (the site and Holdings read research/rulers/index.json)."""
    rows = []
    for p in sorted(OUT.glob("*.md")) if OUT.exists() else []:
        meta = parse_front(p.read_text())
        if not meta.get("ticker"):
            continue
        num = lambda v: _f(v) if isinstance(v, str) else None
        rows.append({"ticker": meta["ticker"], "name": meta.get("name", ""),
                     "verdict": meta.get("verdict", "").upper(), "confidence": num(meta.get("confidence")),
                     "entry": [x for x in (num(e) for e in meta.get("entry", [])) if x is not None],
                     "trim": num(meta.get("trim")), "updated": meta.get("updated", ""),
                     "price_at_update": num(meta.get("price_at_update")), "summary": meta.get("summary", "")})
    rows.sort(key=lambda r: (VERDICTS.index(r["verdict"]) if r["verdict"] in VERDICTS else 9, r["ticker"]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(json.dumps(rows, indent=1) + "\n")
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "record"])
    ap.add_argument("--tickers", default="", help="comma list to analyse first")
    ap.add_argument("--limit", type=int, default=MAX_NAMES)
    args = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    if args.cmd == "prepare":
        forced = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        p = prepare(Fetcher(ROOT / ".cache"), today, forced, args.limit)
        print(f"prepared {len(p['names'])} dossier(s)")
    else:
        print(f"indexed {record()} dossier(s)")


if __name__ == "__main__":
    main()
