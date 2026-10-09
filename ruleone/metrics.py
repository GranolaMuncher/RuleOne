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


def owner_earnings(row):
    """Town's refined owner earnings (InvestED 278, 341): operating cash flow, less *maintenance*
    capex, plus the tax provision (the Ten Cap is a pre-tax yield).

    Maintenance capex is "the art" (ep. 184/186): use depreciation as the proxy, capped at total
    capex; without D&A fall back to Town's default of half of capex."""
    ocf = row.get("ocf")
    if ocf is None:
        return None
    capex = abs(row.get("capex") or 0.0)
    da = row.get("da")
    maint = min(capex, abs(da)) if da else 0.5 * capex
    return ocf - maint + max(row.get("tax") or 0.0, 0.0)


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


def sane_shares(shares, net_income, eps):
    """Fix share counts tagged in the wrong scale (e.g. Nova's 2025 20-F: 32,800 "shares" meaning
    32.8 million). If the count is off from net income / EPS by 100x or more, use the implied count."""
    if not shares or not net_income or not eps or net_income <= 0 or eps <= 0:
        return shares
    implied = net_income / eps
    return implied if not 0.01 < implied / shares < 100 else shares


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


# ---------------------------------------------------------------- wonderful-company markers
# Machine-checkable markers distilled from InvestED (see knowledge/rule1/MARKERS.md for the
# rationale and episode citations). Each returns pass True/False, or None when data is missing.
MARKER_LABELS = {
    "roic_consistent": "ROIC ≥10% in at least 8 of the last 10 years",
    "roic_not_falling": "ROIC not falling (latest 3-yr avg ≥ 75% of the 10-yr avg)",
    "growth_coherent": "Sales, net income and operating cash flow growing together (within 10 points)",
    "margin_stable": "Gross (or operating) margin stable over 10 years: pricing power",
    "fcf_margin": "Free cash flow ≥ 10% of revenue",
    "cash_real": "Owner earnings ≥ 75% of net income",
    "low_debt": "Total debt ≤ 2 years of free cash flow",
    "no_dilution": "Share count flat or falling over 5 years",
    "predictable": "Revenue grew in at least 8 of the last 10 years",
    "recession_tested": "Profitable with ROIC ≥10% through 2020",
}


def _ratio(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def wonderful_markers(annual: dict, ttm: dict | None = None, debt: float | None = None,
                      balance: dict | None = None) -> dict:
    """{marker: {"pass": bool|None, "value": float|None}} from up to 11 fiscal years of filings."""
    from statistics import mean, pstdev
    years = normalize_splits(annual) if annual else {}
    ys = sorted(y for y in years if years[y].get("revenue"))[-11:]
    rows = [years[y] for y in ys]
    out: dict[str, dict] = {}

    def put(k, ok, val):
        out[k] = {"pass": None if ok is None else bool(ok), "value": None if val is None else round(val, 4)}

    rs = [roic(r) for r in rows[-10:]]
    rs_ok = [r for r in rs if r is not None]
    put("roic_consistent", (sum(r >= 0.10 for r in rs_ok) >= 8) if len(rs_ok) >= 8 else None,
        sum(r >= 0.10 for r in rs_ok) / len(rs_ok) if rs_ok else None)
    if len(rs_ok) >= 6 and mean(rs_ok) > 0:
        recent = mean(rs_ok[-3:])
        put("roic_not_falling", recent >= 0.75 * mean(rs_ok), recent / mean(rs_ok))
    else:
        put("roic_not_falling", None, None)

    first, last = (rows[0], rows[-1]) if len(rows) >= 6 else (None, None)
    n = (ys[-1] - ys[0]) if first else 0
    def cagr(fn):
        a, b = (fn(first), fn(last)) if first else (None, None)
        return growth(a, b, n) if a is not None and b is not None and n else None
    # Whole-company figures, so splits and buybacks can't tangle the lines (InvestED 019, 020).
    gs = [g for g in (cagr(lambda r: r.get("revenue")), cagr(lambda r: r.get("net_income")),
                      cagr(lambda r: r.get("ocf"))) if g is not None]
    spread = max(gs) - min(gs) if len(gs) == 3 else None
    put("growth_coherent", (spread <= 0.10 and min(gs) > 0) if spread is not None else None, spread)

    margins = [_ratio(r.get("gross_profit"), r.get("revenue")) for r in rows[-10:]]
    if sum(m is not None for m in margins) < 6:
        margins = [_ratio(r.get("op_income"), r.get("revenue")) for r in rows[-10:]]
    ms = [m for m in margins if m is not None]
    put("margin_stable", (pstdev(ms) <= 0.03 and ms[-1] >= sorted(ms)[len(ms) // 2] - 0.02) if len(ms) >= 6 else None,
        pstdev(ms) if len(ms) >= 6 else None)

    src = ttm or (rows[-1] if rows else {})
    f, rev = fcf(src) if src else None, src.get("revenue") if src else None
    fm = _ratio(f, rev)
    put("fcf_margin", fm >= 0.10 if fm is not None else None, fm)
    oe, ni = owner_earnings(src) if src else None, src.get("net_income") if src else None
    conv = _ratio(oe - max(src.get("tax") or 0, 0), ni) if oe is not None and ni and ni > 0 else None
    put("cash_real", conv >= 0.75 if conv is not None else None, conv)
    bal = balance or (rows[-1] if rows else {})
    d = debt if debt is not None else ((bal.get("lt_debt") or 0) + (bal.get("debt_current") or 0)
                                        if bal and ("lt_debt" in bal or "debt_current" in bal) else None)
    dy = (d / f if f and f > 0 else (0.0 if not d else None)) if d is not None else None
    put("low_debt", (dy is not None and dy <= 2) if d is not None else None, dy)

    sh = [r.get("shares") for r in rows[-6:] if r.get("shares")]
    sg = growth(sh[0], sh[-1], len(sh) - 1) if len(sh) >= 4 else None
    put("no_dilution", sg <= 0.005 if sg is not None else None, sg)
    revs = [r.get("revenue") for r in rows[-11:]]
    ups = [b > a for a, b in zip(revs, revs[1:]) if a and b]
    put("predictable", sum(ups) >= 8 if len(ups) >= 9 else None, sum(ups) / len(ups) if ups else None)
    y2020 = years.get(2020)
    r20 = roic(y2020) if y2020 else None
    put("recession_tested", (r20 >= 0.10 and (y2020.get("net_income") or 0) > 0) if r20 is not None else None, r20)
    return out


def marker_summary(markers: dict) -> tuple[float | None, str]:
    """(share of known markers passed, compact 'name=1|name=0|name=?' string for CSV)."""
    known = [m["pass"] for m in markers.values() if m["pass"] is not None]
    score = sum(known) / len(known) if len(known) >= 5 else None
    return score, "|".join(f"{k}={'?' if m['pass'] is None else int(m['pass'])}" for k, m in markers.items())
