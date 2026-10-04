"""Whole-market Rule #1 screener.

    python -m ruleone.screener                # full NYSE + Nasdaq run
    python -m ruleone.screener --limit 50     # quick test
    python -m ruleone.screener --tickers MSFT,V,MA

Stage 1  SEC XBRL frames -> Big Five for ~4,600 filers -> quality shortlist
Stage 2  companyfacts (TTM) + Yahoo prices + EDGAR events -> Sticker / MOS /
         Payback / Ten Cap -> ranked lists written to lists/
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .companyfacts import load_company
from .events import event_score, event_summary, load_events
from .frames import load_frames
from .http import Fetcher
from .marketwide import (build_universe, dividend_stats, sector_fields, load_current_shares, load_spark, load_total_return,
                         write_price_history, write_universe)
from .metrics import big_five, fcf, windage_growth
from .sectors import load_reference, refresh_reference
from .normalize import normalize
from .prices import load_prices, price_near
from .universe import load_universe
from .valuation import historical_pe, payback_price, sticker_price, ten_cap_price


def log(*a):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)


def stage1_pass(b: dict, min_score: float, min_revenue: float, today: date) -> bool:
    if not b or b.get("tests_total", 0) < 8:
        return False
    if (b.get("revenue") or 0) < min_revenue or (b.get("net_income") or 0) <= 0 or (b.get("eps") or 0) <= 0:
        return False
    if b.get("fy_end") and (today - date.fromisoformat(b["fy_end"])).days > 550:
        return False                         # stale filer
    roics = [b.get(f"roic{w}") for w in (10, 5)]
    if not any(r is not None and r >= 0.10 for r in roics):
        return False
    return b["big5_score"] >= min_score


def quality_tier(b: dict) -> str:
    roic_ok = all((b.get(f"roic{w}") or 0) >= 0.10 for w in (10, 5, 1) if b.get(f"roic{w}") is not None)
    debt_ok = b.get("debt_payoff_years") is not None and b["debt_payoff_years"] <= 3
    if b["big5_score"] >= 0.8 and roic_ok and debt_ok:
        return "A"
    if b["big5_score"] >= 0.67 and roic_ok:
        return "B"
    return "C"


def analyze(fetcher: Fetcher, listing, s1: dict | None, today: date, with_events: bool = True) -> dict | None:
    cf = load_company(fetcher, listing.cik)
    if not cf or not cf["annual"]:
        return None
    b = big_five(cf["annual"]) or s1
    if not b:
        return None
    px = load_prices(fetcher, listing.ticker)
    if not px or not px.get("price") or px.get("currency") != "USD":
        return None
    nz = normalize(fetcher, listing, cf, today)
    if not nz:
        return None
    ttm, shares, eps = nz["ttm"], nz["shares"], nz["eps"]
    price = px["price"]
    mcap = price * shares
    eps_by_end = nz["eps_by_end"]
    hpe = historical_pe(eps_by_end, lambda d: price_near(px["series"], d))
    g = windage_growth(b)
    st = sticker_price(eps, g, hpe["median"]) if g else None
    fcf_ttm = fcf(ttm)
    pb = payback_price(fcf_ttm, shares, g) if g is not None else None
    tc = ten_cap_price(fcf_ttm, shares)
    sticker = st["sticker"] if st else None
    mos = st["mos_price"] if st else None
    buy_signals = [n for n, v in (("MOS", mos), ("PaybackTime", pb), ("TenCap", tc)) if v and price <= v]
    if "MOS" in buy_signals:
        status = "BUY"
    elif buy_signals:
        status = "BUY*"                      # in range on Payback/TenCap but not on MOS
    elif sticker and price <= sticker:
        status = "ON DECK"
    elif sticker:
        status = "ABOVE STICKER"
    else:
        status = "NO STICKER"
    ev = load_events(fetcher, listing.cik, px, today) if with_events else {}
    rec_pe = price / eps if eps and eps > 0 else None
    debt = nz["debt"]
    rec = {
        "ticker": listing.ticker, "name": cf["name"] or listing.name, "exchange": listing.exchange,
        "cik": listing.cik, "sector": ev.get("sic"), "status": status, "tier": quality_tier(b),
        "price": price, "price_date": px["as_of"], "market_cap": mcap,
        "sticker": sticker, "mos_price": mos, "payback_price": pb, "ten_cap_price": tc,
        "price_to_sticker": price / sticker if sticker else None,
        "buy_signals": "+".join(buy_signals),
        "windage_growth": g, "future_pe": st["future_pe"] if st else None,
        "hist_pe_median": hpe["median"], "pe_ttm": price / eps if eps and eps > 0 else None,
        "eps_ttm": eps, "fcf_ttm": fcf_ttm, "ttm_end": ttm.get("_end"),
        "fcf_yield": fcf_ttm / mcap if fcf_ttm and mcap else None,
        "debt": debt, "debt_payoff_years": b.get("debt_payoff_years"),
        "big5_score": b["big5_score"], "big5_tests": f"{b['tests_passed']}/{b['tests_total']}",
        **{k: b.get(k) for k in ("roic10", "roic5", "roic1", "sales_g10", "sales_g5", "sales_g1",
                                 "eps_g10", "eps_g5", "eps_g1", "bvps_g10", "bvps_g5", "bvps_g1",
                                 "ocf_g10", "ocf_g5", "ocf_g1")},
        "flags": ";".join(f for f, c in (
            ("PE<5: check one-off gains", rec_pe is not None and rec_pe < 5),
            ("financial (bank/insurer/broker): OCF-based tests less meaningful", any(w in (ev.get("sic") or "") for w in
                                                                  ("Bank", "Insurance", "Savings", "Credit", "Finance",
                                                                   "Brokers", "Security"))),
            ("; ".join(nz["notes"]), bool(nz["notes"])),
            ("micro-cap", mcap is not None and mcap < 1e9)) if c),
        "drawdown_52w": ev.get("drawdown_52w"), "event_score": event_score(ev) if ev else 0.0,
        "events": event_summary(ev) if ev else "", "next_report_est": ev.get("next_earnings_est"),
    }
    disc = 1 - rec["price_to_sticker"] if rec["price_to_sticker"] else -1
    rec["rank_score"] = round(2 * b["big5_score"] + max(min(disc, 1.0), -1.0) * 2
                              + {"A": 1.0, "B": 0.5, "C": 0}[rec["tier"]] + 0.25 * rec["event_score"], 3)
    return rec


# ---------------------------------------------------------------- output
COLUMNS = ["ticker", "name", "exchange", "sector", "industry", "status", "tier", "price", "price_date", "market_cap",
           "sticker", "mos_price", "payback_price", "ten_cap_price", "price_to_sticker", "buy_signals",
           "windage_growth", "future_pe", "hist_pe_median", "pe_ttm", "eps_ttm", "fcf_ttm", "fcf_yield",
           "ttm_end", "div_ttm", "div_yield", "div_growth_5y", "tr_5y", "tr_10y", "debt", "debt_payoff_years", "big5_score", "big5_tests", "roic10", "roic5", "roic1",
           "sales_g10", "sales_g5", "sales_g1", "eps_g10", "eps_g5", "eps_g1", "bvps_g10", "bvps_g5",
           "bvps_g1", "ocf_g10", "ocf_g5", "ocf_g1", "drawdown_52w", "event_score", "events",
           "next_report_est", "flags", "rank_score", "cik"]


def _fmt(v, kind=""):
    if v is None or v == "":
        return "–"
    if kind == "pct":
        return f"{v:.0%}"
    if kind == "pct1":
        return f"{v:.1%}"
    if kind == "usd":
        return f"${v:,.2f}"
    if kind == "big":
        return f"${v/1e9:,.1f}B" if abs(v) >= 1e9 else f"${v/1e6:,.0f}M"
    if kind == "x":
        return f"{v:.2f}"
    return str(v)


def write_csv(path: Path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


def md_table(rows, n=None):
    head = ("| # | Ticker | Company | Tier | Price | Sticker | MOS (Buy) | Payback | Ten Cap | P/Sticker "
            "| Growth | Div yld | ROIC 5y | Big5 | Events |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for i, r in enumerate(rows[:n] if n else rows, 1):
        lines.append(f"| {i} | **{r['ticker']}** | {r['name'][:30]} | {r['tier']} | {_fmt(r['price'],'usd')} | "
                     f"{_fmt(r['sticker'],'usd')} | {_fmt(r['mos_price'],'usd')} | {_fmt(r['payback_price'],'usd')} | "
                     f"{_fmt(r['ten_cap_price'],'usd')} | {_fmt(r['price_to_sticker'],'x')} | "
                     f"{_fmt(r['windage_growth'],'pct')} | {_fmt(r.get('div_yield'),'pct1')} | {_fmt(r['roic5'],'pct')} | {r['big5_tests']} | "
                     f"{(r['events'] or '').replace('|','/')[:120]}"
                     f"{' ⚠ ' + r['flags'] if r.get('flags') else ''} |")
    return head + "\n".join(lines) + "\n"


def write_outputs(results: list[dict], outdir: Path, meta: dict):
    today = meta["run_date"]
    latest = outdir / "latest"
    arch = outdir / "archive" / today
    for d in (latest, arch):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    results.sort(key=lambda r: r["rank_score"], reverse=True)
    buy = [r for r in results if r["status"] == "BUY"]
    buy_alt = [r for r in results if r["status"] == "BUY*"]
    on_deck = [r for r in results if r["status"] == "ON DECK"]
    events = [r for r in results if r["event_score"] >= 1.0 and r["tier"] in ("A", "B")]
    events.sort(key=lambda r: r["event_score"], reverse=True)
    wonderful = [r for r in results if r["tier"] == "A"]
    lists = {"buy_range": buy, "buy_range_alt_methods": buy_alt, "on_deck": on_deck,
             "event_watch": events, "wonderful_companies": wonderful, "all_candidates": results}
    for name, rows in lists.items():
        for d in (latest, arch):
            write_csv(d / f"{name}.csv", rows)

    md = [f"# Rule #1 Screen — {today}\n",
          f"Universe: **{meta['universe']:,}** NYSE + Nasdaq common stocks → "
          f"**{meta['with_data']:,}** with SEC XBRL history → **{meta['stage1']:,}** passed the Big Five "
          f"quality screen → **{len(results):,}** fully valued (USD-priced, current filings).\n",
          f"Prices as of {meta['price_date']}. Fundamentals: SEC EDGAR 10-K/10-Q XBRL (TTM through latest 10-Q).\n",
          "> Screening output, not investment advice. Automated XBRL extraction can mis-tag items; "
          "verify against the filings before acting. See `README.md` for methodology.\n",
          f"\n## 1. BUY range — price ≤ Margin-of-Safety price (50% of Sticker) ({len(buy)})\n",
          md_table(buy) if buy else "_None this run._\n",
          f"\n## 2. BUY range on Payback Time / Ten Cap only ({len(buy_alt)})\n",
          md_table(buy_alt, 40) if buy_alt else "_None this run._\n",
          f"\n## 3. ON DECK — below Sticker, above Buy price ({len(on_deck)})\n",
          md_table(on_deck, 40) if on_deck else "_None this run._\n",
          f"\n## 4. Event watch — tier A/B with drawdowns, insider buying, 13D or negative 8-Ks ({len(events)})\n",
          md_table(events, 30) if events else "_None this run._\n",
          f"\n## 5. Wonderful companies (tier A) — full list ({len(wonderful)})\n",
          md_table(wonderful) if wonderful else "_None this run._\n",
          "\n### Legend\n",
          "* **Tier A**: ≥80% of Big Five tests ≥10% (sales, EPS, BVPS, OCF growth over 10/5/1y; ROIC), "
          "every ROIC window ≥10%, long-term debt payable from ≤3 years of FCF. **B**: ≥67% and ROIC ≥10%. **C**: ≥60%.\n",
          "* **Sticker** = TTM EPS × (1+g)^10 × min(2g×100, 10y median P/E) ÷ 1.15^10. g = min(median EPS growth, "
          "max(median BVPS growth, median sales growth), 15%) over 10y/5y windows. **MOS (Buy)** = 50% of Sticker. "
          "Automated g has no analyst haircut: treat Sticker as an upper bound and see `reports/` for adjusted values.\n",
          "* **Payback** = price at which 8 years of FCF growing at g repays the purchase. **Ten Cap** = 10 × TTM FCF per share.\n",
          "* **Events**: drawdown from 52-week high, Form 4 open-market insider purchases (120d), SC 13D (180d), "
          "8-K items (60d), estimated next report date.\n"]
    for d in (latest, arch):
        (d / "README.md").write_text("".join(md))
        (d / "meta.json").write_text(json.dumps(meta, indent=2))
    hist = outdir / "history.csv"
    header = ["run_date", "ticker", "status", "tier", "price", "sticker", "mos_price",
              "payback_price", "ten_cap_price", "rank_score"]
    kept = []
    if hist.exists():   # a same-day re-run replaces that day's rows instead of duplicating them
        with open(hist, newline="") as fh:
            kept = [r for r in list(csv.reader(fh))[1:] if r and r[0] != today]
    with open(hist, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(kept)
        for r in results:
            if r["status"] in ("BUY", "BUY*", "ON DECK"):
                w.writerow([today, r["ticker"], r["status"], r["tier"], round(r["price"], 2),
                            *(round(r[k], 2) if r[k] else "" for k in
                              ("sticker", "mos_price", "payback_price", "ten_cap_price")), r["rank_score"]])
    return lists


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="lists")
    ap.add_argument("--cache", default=".cache")
    ap.add_argument("--min-score", type=float, default=0.6, help="min share of Big Five tests passed")
    ap.add_argument("--min-revenue", type=float, default=50e6)
    ap.add_argument("--min-mcap", type=float, default=300e6)
    ap.add_argument("--limit", type=int, default=0, help="cap stage-2 names (testing)")
    ap.add_argument("--tickers", default="", help="comma list: skip stage-1 filter, analyze these")
    ap.add_argument("--no-events", action="store_true")
    ap.add_argument("--first-year", type=int, default=date.today().year - 14)
    ap.add_argument("--no-universe", action="store_true", help="skip the all-stocks table")
    a = ap.parse_args(argv)

    today = date.today()
    fetcher = Fetcher(a.cache)
    universe = load_universe(fetcher)
    log(f"universe: {len(universe)} NYSE/Nasdaq listings")
    by_ticker = {l.ticker: l for l in universe.values()}

    if a.tickers:
        picks = [by_ticker[t.strip().upper()] for t in a.tickers.split(",") if t.strip().upper() in by_ticker]
        s1map, with_data, stage1 = {}, len(picks), len(picks)
    else:
        frames = load_frames(fetcher, set(universe), a.first_year, today.year, log=log)
        quality_pass = set()
        s1map = {}
        for cik, years in frames.items():
            try:
                s1map[cik] = big_five(years)
            except ValueError:
                continue
        with_data = len(s1map)
        picks = [universe[c] for c, b in s1map.items() if stage1_pass(b, a.min_score, a.min_revenue, today)]
        picks.sort(key=lambda l: -s1map[l.cik]["big5_score"])
        quality_pass = {l.cik for l in picks}
        stage1 = len(picks)
        log(f"stage 1: {with_data} with data, {stage1} pass quality screen")
    if a.limit:
        picks = picks[: a.limit]

    results = []
    for i, l in enumerate(picks, 1):
        try:
            r = analyze(fetcher, l, s1map.get(l.cik), today, with_events=not a.no_events)
        except Exception as e:                            # keep the batch going
            log(f"  {l.ticker}: error {e!r}")
            continue
        if r and (r["market_cap"] or 0) >= a.min_mcap:
            results.append(r)
        if i % 25 == 0:
            log(f"stage 2: {i}/{len(picks)} analyzed, {len(results)} kept")
    price_date = max((r["price_date"] for r in results), default=today.isoformat())
    meta = {"run_date": today.isoformat(), "generated_utc": datetime.now(timezone.utc).isoformat(),
            "universe": len(universe), "with_data": with_data, "stage1": stage1,
            "valued": len(results), "price_date": price_date,
            "params": {k: v for k, v in vars(a).items() if k not in ("cache", "out")}}
    rows = None
    if not a.tickers and not a.no_universe:
        tickers = [l.ticker for l in universe.values()]
        weekly = load_spark(fetcher, tickers, "1y", "1wk", log=log)
        monthly = load_spark(fetcher, tickers, "10y", "1mo", log=log)
        shares = load_current_shares(fetcher, today)
        sectors = refresh_reference(fetcher, set(universe), Path(a.out) / "reference" / "sic.csv", today, log=log)
        total_return = load_total_return(fetcher, tickers, log=log)
        rows = build_universe(universe, frames, results, weekly, monthly, shares, quality_pass, quality_tier,
                              sectors, total_return)
    else:
        total_return = load_total_return(fetcher, [r["ticker"] for r in results], log=log)
    # Same sector / industry as the All stocks table (reference file; refreshed above on full runs)
    sector_ref = sectors if rows is not None else load_reference(Path(a.out) / "reference" / "sic.csv")
    for r in results:
        r.update(sector_fields(sector_ref.get(r["cik"])) if sector_ref.get(r["cik"]) else
                 {"industry": r.get("sector") or "", "sector": ""})
    for r in results:   # dividend yield / growth / total return on the screen lists too
        r.update({k: v for k, v in dividend_stats(total_return.get(r["ticker"]), r["price"]).items()
                  if k != "div_special"})
    lists = write_outputs(results, Path(a.out), meta)
    if rows is not None:
        write_universe(rows, Path(a.out) / "latest", Path(a.out) / "archive" / meta["run_date"])
        write_price_history(monthly, Path(a.out) / "latest", total_return)
        meta["universe_rows"] = len(rows)
        meta["universe_priced"] = sum(1 for r in rows if r.get("price"))
        for d in (Path(a.out) / "latest", Path(a.out) / "archive" / meta["run_date"]):
            (d / "meta.json").write_text(json.dumps(meta, indent=2))
        log(f"universe table: {meta['universe_rows']} rows, {meta['universe_priced']} priced")
    log("done: " + ", ".join(f"{k}={len(v)}" for k, v in lists.items()))


if __name__ == "__main__":
    main()
