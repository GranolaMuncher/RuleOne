"""Rule #1 "Big Five" numbers and related quality metrics.

Big Five (Phil Town, *Rule #1*, 2006): ROIC, sales growth, EPS growth,
equity (book value per share) growth and operating-cash-flow growth should
each be >= 10% per year over 10, 5 and 1 year windows.
"""
from __future__ import annotations

from statistics import mean, median

WINDOWS = (10, 5, 1)
HURDLE = 0.10


def growth(a, b, years: int):
    """Compound annual growth from a -> b. None when undefined (missing or
    non-positive base/end), mirroring how Rule #1 treats losses."""
    if a is None or b is None or years <= 0 or a <= 0 or b <= 0:
        return None
    return (b / a) ** (1.0 / years) - 1.0


def tax_rate(row) -> float:
    pt, tx = row.get("pretax"), row.get("tax")
    if pt and tx is not None and pt > 0:
        return min(max(tx / pt, 0.0), 0.35)
    return 0.21


def roic(row):
    """NOPAT / (equity + long-term debt)  — Town's definition of invested capital."""
    eq = row.get("equity")
    if eq is None:
        return None
    ic = eq + (row.get("lt_debt") or 0.0)
    if ic <= 0:
        return None
    if row.get("op_income") is not None:
        nopat = row["op_income"] * (1 - tax_rate(row))
    elif row.get("net_income") is not None:
        nopat = row["net_income"]
    else:
        return None
    return nopat / ic


def bvps(row):
    eq, sh = row.get("equity"), row.get("shares")
    if eq is None or not sh:
        return None
    return eq / sh


def fcf(row):
    if row.get("ocf") is None:
        return None
    return row["ocf"] - abs(row.get("capex") or 0.0)


SPLIT_FACTORS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50)


def _implied_shares(r):
    if r.get("shares"):
        return r["shares"]
    if r.get("net_income") and r.get("eps"):
        return r["net_income"] / r["eps"]
    return None


def normalize_splits(years: dict[int, dict]) -> dict[int, dict]:
    """Restate per-share data to the latest share basis.

    XBRL keeps each 10-K as filed, so EPS from years before a split is not
    comparable with later years. A year-over-year jump in (diluted or implied)
    share count that matches a common split ratio is treated as a split and
    every earlier year's shares / EPS / DPS is restated.
    """
    ys = sorted(years)
    factor = {y: 1.0 for y in ys}
    cum = 1.0
    for prev, cur in reversed(list(zip(ys, ys[1:]))):
        a, b = _implied_shares(years[prev]), _implied_shares(years[cur])
        if a and b and a > 0 and b > 0:
            r = b / a
            for f in SPLIT_FACTORS:
                if abs(r / f - 1) <= 0.12:
                    cum *= f
                    break
                if abs(r * f - 1) <= 0.12:
                    cum /= f
                    break
        factor[prev] = cum
    out = {}
    for y in ys:
        row = dict(years[y])
        f = factor[y]
        if f != 1.0:
            if row.get("shares"):
                row["shares"] *= f
            for k in ("eps", "dps"):
                if row.get(k) is not None:
                    row[k] /= f
            row["split_factor"] = f
        out[y] = row
    return out


def post_filing_split(xbrl_shares, market_shares) -> float:
    """Split factor between the latest filed share count and a current market
    data share count (a split after the last 10-Q). 1.0 when none detected."""
    if not xbrl_shares or not market_shares:
        return 1.0
    r = market_shares / xbrl_shares
    for f in SPLIT_FACTORS:
        if abs(r / f - 1) <= 0.12:
            return float(f)
        if abs(r * f - 1) <= 0.12:
            return 1.0 / f
    return 1.0


SERIES = {
    "sales": lambda r: r.get("revenue"),
    "eps": lambda r: r.get("eps"),
    "bvps": bvps,
    "ocf": lambda r: r.get("ocf"),
}


def big_five(years: dict[int, dict]) -> dict:
    """Compute Big Five growth/ROIC windows from {fiscal_year: row}."""
    if not years:
        return {}
    years = normalize_splits(years)
    last = max(y for y, r in years.items() if r.get("revenue") or r.get("net_income"))
    cur = years[last]
    out = {"fy": last, "fy_end": cur.get("end"), "years_of_data": len(
        [y for y in years if y <= last and years[y].get("revenue")])}
    tests_passed = tests_total = 0
    for name, fn in SERIES.items():
        for w in WINDOWS:
            base = years.get(last - w)
            g = growth(fn(base), fn(cur), w) if base else None
            out[f"{name}_g{w}"] = g
            if base is not None and fn(base) is not None and fn(cur) is not None:
                tests_total += 1
                tests_passed += int(g is not None and g >= HURDLE)
    rs = {y: roic(years[y]) for y in years if y <= last}
    for w in WINDOWS:
        vals = [rs[y] for y in range(last - w + 1, last + 1) if rs.get(y) is not None]
        out[f"roic{w}"] = mean(vals) if vals else None
        if vals:
            tests_total += 1
            tests_passed += int(out[f"roic{w}"] >= HURDLE)
    out["tests_passed"], out["tests_total"] = tests_passed, tests_total
    out["big5_score"] = tests_passed / tests_total if tests_total else 0.0
    f = fcf(cur)
    debt = cur.get("lt_debt") or 0.0
    out["fcf"] = f
    out["debt_payoff_years"] = (debt / f) if f and f > 0 else (0.0 if debt == 0 else None)
    out["revenue"] = cur.get("revenue")
    out["net_income"] = cur.get("net_income")
    out["eps"] = cur.get("eps")
    out["equity"] = cur.get("equity")
    return out


def windage_growth(b5: dict, cap: float = 0.15):
    """Conservative growth rate for the Sticker Price.

    Rule #1 takes the lower of historical equity (BVPS) growth and analysts'
    5-year estimate. Without analyst data we use:
        g = min(median EPS growth, max(median BVPS growth, median sales growth), 15%)
    over the 10y and 5y windows. Taking max(BVPS, sales) stops heavy buyback
    programmes (which shrink book value) from zeroing out great businesses,
    while EPS growth still caps the result.
    """
    def med(name):
        vals = [b5.get(f"{name}_g{w}") for w in (10, 5)]
        vals = [v for v in vals if v is not None]
        return median(vals) if vals else None

    eps_g, bv_g, sales_g = med("eps"), med("bvps"), med("sales")
    base = max((v for v in (bv_g, sales_g) if v is not None), default=None)
    cands = [v for v in (eps_g, base) if v is not None]
    if not cands:
        return None
    return min(min(cands), cap)
