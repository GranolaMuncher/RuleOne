"""Put a company's numbers on the same basis as its US-listed share price.

Converts reporting-currency financials to USD and restates per-share data to
the listed security, covering both stock splits after the last filing and ADRs
(one ADS = N ordinary shares). Shared by the screener and the deep dive so
both value the same thing.
"""
from __future__ import annotations

from datetime import date

from .http import Fetcher
from .metrics import normalize_splits, post_filing_split, sane_shares
from .prices import load_fx, load_share_fallback, price_near

NOT_MONEY = {"shares", "diluted_shares", "shares_outstanding", "split_factor"}
PER_SHARE = {"eps", "dps", "dps_latest"}


def convert(row: dict, fx: float, per_share_factor: float = 1.0) -> dict:
    """Divide money fields by fx (units of currency per USD); per-share fields are
    also divided by per_share_factor (listed-security shares per ordinary share)."""
    out = {}
    for k, v in row.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or k in NOT_MONEY:
            out[k] = v
        elif k in PER_SHARE:
            out[k] = v / fx / per_share_factor
        else:
            out[k] = v / fx
    return out


def _fresh(latest: dict, key: str, today: date):
    d = latest.get(key + "_date")
    return latest.get(key) if d and (today - date.fromisoformat(d)).days <= 460 else None


def normalize(fetcher: Fetcher, listing, cf: dict, today: date) -> dict | None:
    """USD, listed-security-basis view of a company. None when it can't be built."""
    cur = cf.get("currency", "USD")
    fxd = load_fx(fetcher, cur)
    if not fxd:
        return None
    fx = fxd["price"]
    fx_at = (lambda d: price_near(fxd["series"], d) or fx) if cur != "USD" else (lambda d: 1.0)

    shares = _fresh(cf["latest"], "diluted_shares", today) or _fresh(cf["latest"], "shares_outstanding", today)
    shares = sane_shares(shares, cf["ttm"].get("net_income"), cf["ttm"].get("eps"))
    yf = load_share_fallback(fetcher, listing.ticker)
    # >1: split after the latest filing; <1: ADR (1 ADS = 1/factor ordinary shares)
    factor = post_filing_split(shares, yf.get("quarterlyDilutedAverageShares"))
    ttm = convert(cf["ttm"], fx, factor)
    latest = convert(cf["latest"], fx, factor)
    if shares:
        shares *= factor
    eps, eps_source = ttm.get("eps"), "xbrl"

    # 20-F filers file no XBRL 10-Qs, so XBRL TTM can be a year old. Yahoo's
    # trailing EPS is per listed security, in the currency it reports.
    ttm_end = cf["ttm"].get("_end")
    yf_eps, yf_date = yf.get("trailingDilutedEPS"), yf.get("trailingDilutedEPS_date")
    stale = not ttm_end or (today - date.fromisoformat(ttm_end)).days > 200
    if yf_eps and yf_date and (not eps or (stale and (not ttm_end or yf_date > ttm_end))):
        yf_fx = fx if yf.get("eps_currency", "USD") == cur else (load_fx(fetcher, yf["eps_currency"]) or {}).get("price")
        if yf_fx:
            eps, eps_source = yf_eps / yf_fx, f"yahoo TTM to {yf_date}"
    shares = shares or yf.get("quarterlyDilutedAverageShares")

    # TTM EPS spliced across a split (FY pre-split + YTD post-split) is garbage:
    # cross-check against TTM net income / current shares.
    # Only correct positive figures: a negative reported EPS is a real loss, not a splice
    # artefact, and must not be replaced by a near-zero positive implied value.
    if eps_source == "xbrl" and eps and eps > 0 and shares and ttm.get("net_income"):
        implied = ttm["net_income"] / shares
        if implied > 0 and not 0.75 <= eps / implied <= 1.33:
            eps = implied
    if not eps and ttm.get("net_income") and shares:
        eps = ttm["net_income"] / shares
    if not shares or not eps:
        return None

    annual_n = normalize_splits(cf["annual"])
    last_sh = next((annual_n[y]["shares"] for y in sorted(annual_n, reverse=True) if annual_n[y].get("shares")), None)
    hist_factor = post_filing_split(last_sh, shares)
    annual_usd = {y: convert(r, fx_at(r["end"]), hist_factor) for y, r in annual_n.items()}
    notes = []
    if cur != "USD":
        notes.append(f"reports in {cur}, converted at {fx:,.4g} {cur}/USD")
    if factor < 1:
        notes.append(f"ADR: 1 ADS = {round(1 / factor)} shares")
    if eps_source != "xbrl":
        notes.append(f"EPS from {eps_source}")
    debt = (latest.get("lt_debt") or 0) + (latest.get("debt_current") or 0)
    return {"currency": cur, "fx": fx, "share_factor": factor, "shares": shares, "eps": eps,
            "eps_source": eps_source, "ttm": ttm, "latest": latest, "annual_usd": annual_usd,
            "eps_by_end": {r["end"]: r["eps"] for r in annual_usd.values() if r.get("eps")},
            "debt": debt, "cash": latest.get("cash") or 0, "notes": notes}
