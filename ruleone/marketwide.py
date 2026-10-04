"""Market-wide table: every NYSE + Nasdaq stock, not just the quality shortlist.

Uses only bulk sources so it stays cheap enough to run weekly:
  * SEC XBRL frames (already loaded for stage 1): last fiscal-year financials
  * SEC dei frames: current shares outstanding + filer location (to spot
    stock splits after the last 10-K and non-US filers)
  * Yahoo spark (20 symbols per call): price, 52-week range, 1y weekly and
    10y monthly closes

Valuation here is based on the last fiscal year. The detailed stage-2 rows
(TTM, ADR/currency normalised, events) replace these for the ~260 stocks that
pass the quality screen.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .http import Fetcher
from .metrics import big_five, fcf, normalize_splits, post_filing_split, windage_growth
from .prices import price_near
from .valuation import historical_pe, payback_price, sticker_price, ten_cap_price

SPARK_URL = "https://query1.finance.yahoo.com/v7/finance/spark?symbols={syms}&range={rng}&interval={iv}"
DEI_URL = "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{period}.json"
SPARK_BATCH = 20   # Yahoo's limit


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def load_spark(fetcher: Fetcher, tickers: list[str], rng: str, interval: str, log=print) -> dict[str, dict]:
    """{ticker: {"meta": {...}, "series": [(date, close, close)]}} for every ticker Yahoo knows."""
    out: dict[str, dict] = {}
    for i in range(0, len(tickers), SPARK_BATCH):
        batch = tickers[i:i + SPARK_BATCH]
        url = SPARK_URL.format(syms=quote(",".join(batch), safe=","), rng=rng, iv=interval)
        try:
            data = fetcher.get_json(url, ttl_hours=12)
        except Exception as e:                       # one bad batch shouldn't stop the run
            log(f"[spark] batch {i // SPARK_BATCH} failed: {e!r}")
            continue
        for item in ((data or {}).get("spark") or {}).get("result") or []:
            try:
                resp = item["response"][0]
                closes = resp["indicators"]["quote"][0]["close"]
            except (KeyError, IndexError, TypeError):
                continue
            pts = [(t, c) for t, c in zip(resp.get("timestamp") or [], closes) if c is not None]
            # Yahoo appends the live quote after the current (in-progress) bar: keep only the latest of the two
            if len(pts) >= 2 and pts[-1][0] - pts[-2][0] < (6 if interval == "1wk" else 27) * 86400:
                pts.pop(-2)
            series = [(_iso(t), c, c) for t, c in pts]
            out[item["symbol"]] = {"meta": resp.get("meta", {}), "series": series}
        if (i // SPARK_BATCH) % 50 == 0:
            log(f"[spark {rng}] {min(i + SPARK_BATCH, len(tickers))}/{len(tickers)}")
    return out


def load_current_shares(fetcher: Fetcher, today: date) -> dict[int, dict]:
    """Latest cover-page shares outstanding per CIK (last ~4 quarters of dei frames)."""
    out: dict[int, dict] = {}
    y, q = today.year, (today.month - 1) // 3 + 1
    periods = []
    for _ in range(5):
        periods.append(f"CY{y}Q{q}I")
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    for period in reversed(periods):            # oldest first, newer overwrite
        data = fetcher.get_json(DEI_URL.format(period=period), ttl_hours=24) or {}
        for r in data.get("data", []):
            out[r["cik"]] = {"shares": r["val"], "end": r["end"], "loc": r.get("loc") or ""}
    return out


def _chg(series, weeks_back: int):
    if len(series) <= weeks_back:
        return None
    a, b = series[-1 - weeks_back][1], series[-1][1]
    return b / a - 1 if a else None


def price_stats(meta: dict, weekly: list) -> dict:
    price = meta.get("regularMarketPrice")
    hi, lo = meta.get("fiftyTwoWeekHigh"), meta.get("fiftyTwoWeekLow")
    ytd = None
    if weekly and price:
        jan = [c for d, c, _ in weekly if d >= f"{date.today().year}-01-01"]
        ytd = price / jan[0] - 1 if jan and jan[0] else None
    return {
        "price": price,
        "price_date": _iso(meta["regularMarketTime"]) if meta.get("regularMarketTime") else "",
        "high52": hi, "low52": lo,
        "off_high": price / hi - 1 if price and hi else None,
        "above_low": price / lo - 1 if price and lo else None,
        "chg_1w": _chg(weekly, 1), "chg_1m": _chg(weekly, 4), "chg_3m": _chg(weekly, 13),
        "chg_6m": _chg(weekly, 26), "chg_1y": _chg(weekly, len(weekly) - 1) if len(weekly) > 40 else None,
        "chg_ytd": ytd,
        "spark_1y": " ".join(f"{c:.4g}" for _, c, _ in weekly[-53:]),
    }


def fy_valuation(years: dict, b5: dict, price: float | None, monthly: list, cur_shares: float | None) -> dict:
    """Rule #1 numbers from last-fiscal-year data (no TTM, no events)."""
    out = {"eps": None, "pe": None, "sticker": None, "mos_price": None, "payback_price": None,
           "ten_cap_price": None, "windage_growth": None, "hist_pe_median": None, "market_cap": None,
           "fcf_yield": None, "split_after_fy": 1.0}
    if not years or not b5:
        return out
    yn = normalize_splits(years)
    last = max(yn)
    row = yn[last]
    fy_shares = row.get("shares")
    factor = post_filing_split(fy_shares, cur_shares)        # split after the last 10-K
    out["split_after_fy"] = factor
    eps = row.get("eps")
    if eps is None and row.get("net_income") and fy_shares:
        eps = row["net_income"] / fy_shares
    eps = eps / factor if eps is not None else None
    shares = cur_shares or (fy_shares * factor if fy_shares else None)
    out["eps"] = eps
    if price and shares:
        out["market_cap"] = price * shares
    if price and eps and eps > 0:
        out["pe"] = price / eps
    eps_by_end = {r["end"]: r["eps"] / factor for r in yn.values() if r.get("eps") and r.get("end")}
    hpe = historical_pe(eps_by_end, lambda d: price_near(monthly, d))
    out["hist_pe_median"] = hpe["median"]
    g = windage_growth(b5)
    out["windage_growth"] = g
    st = sticker_price(eps, g, hpe["median"]) if g else None
    if st:
        out["sticker"], out["mos_price"] = st["sticker"], st["mos_price"]
    f = fcf(row)
    if f is not None and shares:
        out["ten_cap_price"] = ten_cap_price(f, shares)
        out["payback_price"] = payback_price(f, shares, g) if g is not None else None
        if price:
            out["fcf_yield"] = f / (price * shares)
    return out


def status_of(price, mos, payback, ten_cap, sticker) -> str:
    if not price:
        return "NO PRICE"
    if mos and price <= mos:
        return "BUY"
    if (payback and price <= payback) or (ten_cap and price <= ten_cap):
        return "BUY*"
    if sticker and price <= sticker:
        return "ON DECK"
    return "ABOVE STICKER" if sticker else "NO STICKER"


def sector_fields(ref: dict | None) -> dict:
    """Sector/industry columns. Filers with no SIC are almost all closed-end funds and BDCs."""
    if not ref:
        return {"sector": "", "industry": "", "sic": ""}
    if not ref.get("sic"):
        return {"sector": "Funds & BDCs", "industry": "Closed-end fund / BDC (no SIC code)", "sic": ""}
    return {"sector": ref.get("sector", ""), "industry": ref.get("industry", ""), "sic": ref.get("sic", "")}


def valuation_label(price, mos, sticker) -> str:
    if not price:
        return "NO PRICE"
    if not sticker:
        return "NO STICKER"
    if mos and price <= mos:
        return "BELOW MOS"
    return "BELOW STICKER" if price <= sticker else "ABOVE STICKER"


UNIVERSE_COLUMNS = [
    "ticker", "name", "exchange", "sector", "industry", "sic", "detail", "status", "tier", "quality_pass",
    "price", "price_date", "market_cap", "chg_1w", "chg_1m", "chg_3m", "chg_6m", "chg_ytd", "chg_1y",
    "off_high", "above_low", "high52", "low52",
    "eps", "eps_basis", "pe", "hist_pe_median", "windage_growth", "sticker", "mos_price", "price_to_sticker",
    "payback_price", "ten_cap_price", "fcf_yield",
    "big5_score", "big5_tests", "roic10", "roic5", "roic1",
    "sales_g10", "sales_g5", "sales_g1", "eps_g10", "eps_g5", "eps_g1",
    "bvps_g10", "bvps_g5", "bvps_g1", "ocf_g10", "ocf_g5", "ocf_g1",
    "revenue", "net_income", "debt_payoff_years", "fy", "fy_end",
    "events", "flags", "spark_1y", "cik",
]
SNAPSHOT_COLUMNS = ["ticker", "price", "sticker", "mos_price", "pe", "off_high", "big5_score", "status", "tier"]


def build_universe(universe: dict, frames: dict, detailed: list[dict], weekly: dict, monthly: dict,
                   cur_shares: dict, quality_pass: set, tier_of, sectors: dict | None = None) -> list[dict]:
    """One row per listed stock; stage-2 rows override the FY-based numbers."""
    detail_by_ticker = {r["ticker"]: r for r in detailed}
    rows = []
    for cik, listing in universe.items():
        t = listing.ticker
        years = frames.get(cik) or {}
        try:
            b5 = big_five(years) if years else {}
        except ValueError:
            b5 = {}
        sp_w = weekly.get(t) or {}
        meta = sp_w.get("meta") or (monthly.get(t) or {}).get("meta") or {}
        ps = price_stats(meta, sp_w.get("series") or [])
        cs = cur_shares.get(cik) or {}
        val = fy_valuation(years, b5, ps["price"], (monthly.get(t) or {}).get("series") or [], cs.get("shares"))
        flags = []
        loc = cs.get("loc", "")
        if loc and not loc.startswith("US"):
            flags.append(f"non-US filer ({loc}): per-share basis may be per ordinary share, not ADS")
        if meta.get("currency") and meta["currency"] != "USD":
            flags.append(f"quoted in {meta['currency']}")
        if val["pe"] is not None and val["pe"] < 4:
            flags.append("P/E<4: check one-offs or data")
        if val["split_after_fy"] != 1.0:
            flags.append(f"split since last 10-K (×{val['split_after_fy']:g}) adjusted")
        if val["market_cap"] is not None and val["market_cap"] < 3e8:
            flags.append("micro-cap")
        row = {
            "ticker": t, "name": meta.get("longName") or listing.name, "exchange": listing.exchange,
            **sector_fields((sectors or {}).get(cik)), "detail": "fy", "tier": tier_of(b5) if b5.get("tests_total", 0) >= 6 else "",
            "quality_pass": "yes" if cik in quality_pass else "", **ps, **{k: v for k, v in val.items() if k != "split_after_fy"},
            "eps_basis": f"FY{b5.get('fy')}" if b5.get("fy") else "",
            "price_to_sticker": ps["price"] / val["sticker"] if ps["price"] and val["sticker"] else None,
            "big5_score": b5.get("big5_score") if b5 else None,
            "big5_tests": f"{b5['tests_passed']}/{b5['tests_total']}" if b5.get("tests_total") else "",
            **{k: b5.get(k) for k in ("roic10", "roic5", "roic1", "sales_g10", "sales_g5", "sales_g1",
                                      "eps_g10", "eps_g5", "eps_g1", "bvps_g10", "bvps_g5", "bvps_g1",
                                      "ocf_g10", "ocf_g5", "ocf_g1", "revenue", "net_income",
                                      "debt_payoff_years", "fy", "fy_end")},
            "events": "", "flags": ";".join(flags), "cik": cik,
        }
        if cik in quality_pass:
            row["status"] = status_of(row["price"], row["mos_price"], row["payback_price"],
                                      row["ten_cap_price"], row["sticker"])
        else:
            # Rule #1 buys only wonderful businesses: below-value stocks that fail the
            # quality screen get a valuation label, not a buy signal.
            row["status"] = valuation_label(row["price"], row["mos_price"], row["sticker"])
        d = detail_by_ticker.get(t)
        if d:   # detailed TTM / ADR-normalised analysis wins
            for k in ("status", "tier", "market_cap", "sticker", "mos_price", "payback_price",
                      "ten_cap_price", "price_to_sticker", "windage_growth", "hist_pe_median", "fcf_yield",
                      "big5_score", "big5_tests", "events", "flags",
                      "roic10", "roic5", "roic1", "sales_g10", "sales_g5", "sales_g1", "eps_g10", "eps_g5",
                      "eps_g1", "bvps_g10", "bvps_g5", "bvps_g1", "ocf_g10", "ocf_g5", "ocf_g1",
                      "debt_payoff_years"):
                row[k] = d.get(k)
            row["eps"], row["pe"] = d.get("eps_ttm"), d.get("pe_ttm")
            row["eps_basis"] = f"TTM {d.get('ttm_end') or ''}".strip()
            row["detail"] = "ttm"
        rows.append(row)
    rows.sort(key=lambda r: (r["market_cap"] is None, -(r["market_cap"] or 0)))
    return rows


def _cell(v):
    return round(v, 4) if isinstance(v, float) else ("" if v is None else v)


def write_universe(rows: list[dict], latest: Path, arch: Path):
    for d in (latest,):
        with open(d / "universe.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=UNIVERSE_COLUMNS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: _cell(r.get(k)) for k in UNIVERSE_COLUMNS})
    # compact weekly snapshot for trends across runs (keeps the repo small)
    for d in (latest, arch):
        with open(d / "universe_snapshot.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=SNAPSHOT_COLUMNS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                if r.get("price"):
                    w.writerow({k: _cell(r.get(k)) for k in SNAPSHOT_COLUMNS})


def _contiguous_months(months: list[str]) -> bool:
    y, m = map(int, months[0].split("-"))
    for ym in months[1:]:
        m += 1
        if m == 13:
            y, m = y + 1, 1
        if ym != f"{y:04d}-{m:02d}":
            return False
    return True


def write_price_history(monthly: dict, latest: Path):
    """10-year monthly closes per ticker for the site's price charts (latest only, not archived).

    Row: ticker, start (YYYY-MM of the first close, or every month space-separated if the
    series has gaps), live (date of the final close, which is the live quote), closes.
    """
    with open(latest / "prices_monthly.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "start", "live", "closes"])
        for t in sorted(monthly):
            series = monthly[t].get("series") or []
            if len(series) < 2:
                continue
            months = [d[:7] for d, _, _ in series[:-1]]
            start = months[0] if _contiguous_months(months) else " ".join(months)
            w.writerow([t, start, series[-1][0], " ".join(f"{c:.5g}" for _, c, _ in series)])
