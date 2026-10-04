"""Market prices from Yahoo Finance's public chart endpoint."""
from __future__ import annotations

from datetime import datetime, timezone

from .http import Fetcher

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"


def load_prices(fetcher: Fetcher, ticker: str, rng: str = "10y", interval: str = "1mo",
                ttl_hours: float = 12) -> dict | None:
    data = fetcher.get_json(CHART_URL.format(sym=ticker, rng=rng, iv=interval), ttl_hours=ttl_hours)
    try:
        res = data["chart"]["result"][0]
    except (TypeError, KeyError, IndexError):
        return None
    meta = res.get("meta", {})
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") \
        or res["indicators"]["quote"][0].get("close") or []
    closes = res["indicators"]["quote"][0].get("close") or []
    series = [(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), c, a)
              for t, c, a in zip(ts, closes, q) if c is not None]
    return {
        "price": meta.get("regularMarketPrice"),
        "currency": meta.get("currency"),
        "high52": meta.get("fiftyTwoWeekHigh"),
        "low52": meta.get("fiftyTwoWeekLow"),
        "as_of": datetime.fromtimestamp(meta.get("regularMarketTime", 0), tz=timezone.utc).date().isoformat(),
        "series": series,          # [(date, close, adjclose)]
    }


def price_near(series, iso_date: str):
    """Close of the bar nearest to iso_date (unadjusted, to pair with as-reported EPS)."""
    if not series:
        return None
    target = datetime.fromisoformat(iso_date).date()
    best = min(series, key=lambda s: abs((datetime.fromisoformat(s[0]).date() - target).days))
    if abs((datetime.fromisoformat(best[0]).date() - target).days) > 45:
        return None
    return best[1]


def monthly_returns(series):
    out = {}
    for (d0, _, a0), (d1, _, a1) in zip(series, series[1:]):
        if a0 and a1:
            out[d1[:7]] = a1 / a0 - 1
    return out


def beta(stock_series, market_series, months: int = 60):
    """OLS beta of monthly total returns vs the market (default 5y monthly)."""
    rs, rm = monthly_returns(stock_series), monthly_returns(market_series)
    keys = sorted(set(rs) & set(rm))[-months:]
    if len(keys) < 24:
        return None
    xs, ys = [rm[k] for k in keys], [rs[k] for k in keys]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var if var else None


TS_URL = ("https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}"
          "?type=quarterlyDilutedAverageShares,trailingDilutedEPS&period1={p1}&period2={p2}")


def load_share_fallback(fetcher: Fetcher, ticker: str) -> dict:
    """Latest diluted share count / trailing EPS from Yahoo, for filers whose XBRL
    only reports these per share class (e.g. Visa). For ADRs Yahoo reports both
    per ADS (share count in ADS-equivalents, EPS in the reporting currency)."""
    now = int(datetime.now(timezone.utc).timestamp())
    data = fetcher.get_json(TS_URL.format(sym=ticker, p1=now - 3 * 365 * 86400, p2=now), ttl_hours=24)
    out = {}
    for res in ((data or {}).get("timeseries", {}).get("result") or []):
        for key in ("quarterlyDilutedAverageShares", "trailingDilutedEPS"):
            pts = [p for p in (res.get(key) or []) if p and p.get("reportedValue")]
            if pts:
                last = max(pts, key=lambda p: p["asOfDate"])
                out[key] = last["reportedValue"]["raw"]
                out[key + "_date"] = last["asOfDate"]
                if key == "trailingDilutedEPS":
                    out["eps_currency"] = last.get("currencyCode") or "USD"
    return out


def load_fx(fetcher: Fetcher, currency: str) -> dict | None:
    """Units of `currency` per 1 USD: spot plus 10y monthly history."""
    if currency == "USD":
        return {"price": 1.0, "series": []}
    fx = load_prices(fetcher, f"{currency}=X", rng="10y", interval="1mo")
    if not fx or not fx.get("price"):
        return None
    return fx
