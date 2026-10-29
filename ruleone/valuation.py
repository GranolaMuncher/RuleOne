"""Valuation models: Rule #1 (Sticker / MOS / Payback / Ten Cap), DCF, DDM, WACC."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median

MARR = 0.15          # Rule #1 minimum acceptable rate of return
MOS = 0.50           # margin of safety


# ---------------------------------------------------------------- Rule #1
def sticker_price(eps: float, growth: float, hist_pe: float | None, years: int = 10,
                  marr: float = MARR, pe_cap: float = 50.0) -> dict | None:
    """Town's Sticker Price.
    future EPS = EPS * (1+g)^10; future PE = min(2 * g%, historical avg PE);
    future price discounted at 15% for 10 years."""
    if eps is None or eps <= 0 or growth is None or growth <= 0:
        return None
    default_pe = 2 * growth * 100
    fpe = min(default_pe, hist_pe) if hist_pe and hist_pe > 0 else default_pe
    fpe = max(min(fpe, pe_cap), 1.0)
    future_eps = eps * (1 + growth) ** years
    future_price = future_eps * fpe
    sticker = future_price / (1 + marr) ** years
    return {"growth": growth, "future_pe": fpe, "future_eps": future_eps,
            "future_price": future_price, "sticker": sticker, "mos_price": sticker * (1 - MOS)}


def payback_price(fcf: float, shares: float, growth: float, years: int = 8) -> float | None:
    """Price at which 8 years of growing FCF repays the purchase (Town's Payback Time)."""
    if not fcf or fcf <= 0 or not shares or growth is None:
        return None
    g = max(growth, 0.0)
    return sum(fcf * (1 + g) ** t for t in range(1, years + 1)) / shares


def ten_cap_price(owner_earnings: float, shares: float, net_debt: float = 0.0) -> float | None:
    """Buy at 10x owner earnings (a 10% pre-tax owner yield), less net debt (InvestED 341, 467):
    interest is already inside owner earnings but the principal is not, so a buyer of the whole
    business pays it on top. Net cash is not added back (conservative)."""
    if not owner_earnings or owner_earnings <= 0 or not shares:
        return None
    value = owner_earnings * 10 - max(net_debt or 0.0, 0.0)
    return value / shares if value > 0 else None


# Lenders and loan platforms fund their loans from investing cash flow (originations), so FCF and owner
# earnings built on operating cash flow overstate what a buyer could take out (InvestED METHOD proposal 2026-10-10).
LENDER_INDUSTRIES = ("Personal Credit", "Business Credit", "Mortgage Bankers", "Loan Brokers")
LENDER_TICKERS = {"OPFI", "QFIN", "SOFI", "UPST", "SYF", "LC", "MFIN"}   # SIC 6199 "Finance Services" platforms
LENDER_FLAG = "lender: Payback and Ten Cap n/a (loan originations sit in investing cash flow)"


def is_lender(ticker: str | None, industry: str | None) -> bool:
    return (ticker or "").upper() in LENDER_TICKERS or any(w in (industry or "") for w in LENDER_INDUSTRIES)


# Stock-based compensation is a real cost paid in shares, but operating cash flow adds it back (InvestED METHOD
# proposal 2026-10-24: TTD Payback $28.78 -> ~$8.70, ADBE Ten Cap $307 -> ~$259 after SBC).
SBC_FLAG_SHARE = 0.10


def sbc_share(sbc: float | None, ocf: float | None) -> float | None:
    """Stock-based compensation as a share of operating cash flow; None when either is missing or OCF <= 0."""
    if sbc is None or not ocf or ocf <= 0:
        return None
    return max(sbc, 0.0) / ocf


def sbc_flag(share: float | None) -> str:
    return (f"SBC {share:.0%} of operating cash flow: see the after-SBC Payback and Ten Cap"
            if share is not None and share > SBC_FLAG_SHARE else "")


def methods_agree(price: float | None, mos: float | None, payback: float | None, ten_cap: float | None) -> int:
    """How many of the three Rule #1 prices the current price is at or below (InvestED 071, 280:
    triangulate; all three in one ballpark is the strongest signal)."""
    if not price:
        return 0
    return sum(1 for v in (mos, payback, ten_cap) if v and price <= v)


def street_capped_growth(g: float | None, street_eps_growth: float | None) -> tuple[float | None, str]:
    """Cap windage at the analysts' current-year EPS growth when that is negative (InvestED METHOD proposal
    2026-10-10): after a guidance cut the history-based rate describes a company that no longer exists.
    Returns (growth, flag). A negative growth gives no Sticker; the flag says the prices need a rebase."""
    if g is None or street_eps_growth is None or street_eps_growth >= 0:
        return g, ""
    return min(g, street_eps_growth), (f"rebase needed: Street EPS growth this year is {street_eps_growth:.0%}, "
                                       f"history-based growth {g:.1%} not used")


# Peak earnings (InvestED METHOD proposal 2026-10-24): PGR TTM EPS $19.9 was 2.1x its five-year average and KNSL 1.7x,
# yet the screen grew both at 15%. A steady 15% compounder also sits near 1.5x its five-year average (MSFT 1.53x),
# so outside insurance a name is a peak only if it is also well above its own earlier growth trend. Insurers keep the
# plain test: underwriting profits are cyclical (the proposal's combined-ratio point, which XBRL doesn't carry).
PEAK_RATIO = 1.5          # TTM EPS vs the five-year average
PEAK_TREND_RATIO = 1.3    # TTM EPS vs where the earlier trend would put it today
TREND_MAX = 0.25          # never assume a trend faster than 25% a year
PEAK_GROWTH_CAP = 0.10


def peak_earnings(eps_ttm: float | None, annual_eps: list[float | None]) -> tuple[float | None, float | None]:
    """(TTM EPS / average of the last five fiscal-year EPS, that average). Needs 4+ years; (None, None) otherwise."""
    vals = [e for e in annual_eps[-5:] if e is not None]
    if not eps_ttm or eps_ttm <= 0 or len(vals) < 4:
        return None, None
    avg = sum(vals) / len(vals)
    return (eps_ttm / avg, avg) if avg > 0 else (None, None)


def trend_ratio(eps_ttm: float | None, annual_eps: list[float | None]) -> float | None:
    """TTM EPS / the EPS the company's earlier trend predicts for today. The trend runs from the median of the
    first three of the last eleven years to the median of years -6..-4 (both before any recent spike), capped at TREND_MAX."""
    eps = [e for e in annual_eps if e is not None][-11:]   # the screen's ten-year view
    if not eps_ttm or eps_ttm <= 0 or len(eps) < 7:
        return None
    early, mid = [e for e in eps[:3] if e > 0], [e for e in eps[-6:-3] if e > 0]
    if len(early) < 2 or len(mid) < 2:
        return None
    a, b = sorted(early)[len(early) // 2], sorted(mid)[len(mid) // 2]
    g = min((b / a) ** (1 / (len(eps) - 6)) - 1, TREND_MAX)
    return eps_ttm / (b * (1 + g) ** 5)                # the middle window is about five years before TTM


def peak_test(eps_ttm: float | None, annual_eps: list[float | None], insurer: bool = False):
    """(ratio to the five-year average, that average, is_peak)."""
    ratio, avg = peak_earnings(eps_ttm, annual_eps)
    if ratio is None or ratio <= PEAK_RATIO:
        return ratio, avg, False
    if insurer:
        return ratio, avg, True
    tr = trend_ratio(eps_ttm, annual_eps)
    return ratio, avg, tr is not None and tr > PEAK_TREND_RATIO


def peak_rebase(g: float | None, eps: float | None, ratio: float | None, avg_eps: float | None, is_peak: bool = True):
    """(growth, eps, flag) for the Sticker: unchanged unless is_peak."""
    if not is_peak or ratio is None or ratio <= PEAK_RATIO or not avg_eps:
        return g, eps, ""
    return (min(g, PEAK_GROWTH_CAP) if g is not None else g, avg_eps,
            f"peak earnings: TTM EPS is {ratio:.1f}x its 5-year average, so the Sticker uses ${avg_eps:.2f} "
            f"and growth is capped at {PEAK_GROWTH_CAP:.0%}")


def historical_pe(eps_by_end: dict[str, float], price_at) -> dict:
    pes = []
    for end, eps in sorted(eps_by_end.items())[-10:]:
        p = price_at(end)
        if p and eps and eps > 0:
            pe = p / eps
            if 0 < pe < 200:
                pes.append(pe)
    if not pes:
        return {"avg": None, "median": None, "low": None, "high": None, "n": 0}
    return {"avg": mean(pes), "median": median(pes), "low": min(pes), "high": max(pes), "n": len(pes)}


# ---------------------------------------------------------------- WACC
@dataclass
class WACC:
    rf: float
    beta: float
    erp: float
    pre_tax_cost_of_debt: float
    tax_rate: float
    equity_value: float
    debt_value: float
    size_premium: float = 0.0

    @property
    def cost_of_equity(self) -> float:
        return self.rf + self.beta * self.erp + self.size_premium

    @property
    def after_tax_cost_of_debt(self) -> float:
        return self.pre_tax_cost_of_debt * (1 - self.tax_rate)

    @property
    def we(self) -> float:
        return self.equity_value / (self.equity_value + self.debt_value)

    @property
    def wd(self) -> float:
        return 1 - self.we

    @property
    def wacc(self) -> float:
        return self.we * self.cost_of_equity + self.wd * self.after_tax_cost_of_debt


# ---------------------------------------------------------------- DCF
@dataclass
class DCFInputs:
    revenue0: float
    growth: list[float]            # per-year revenue growth, len = horizon
    ebit_margin: list[float]       # per-year EBIT margin
    tax_rate: float
    da_pct: list[float]            # D&A as % revenue
    capex_pct: list[float]         # capex as % revenue
    nwc_pct_of_delta_rev: float    # change in NWC as % of change in revenue
    wacc: float
    terminal_growth: float
    exit_multiple: float           # EV / EBITDA in final year
    net_debt: float
    shares: float
    mid_year: bool = True


@dataclass
class DCFResult:
    rows: list[dict] = field(default_factory=list)
    pv_fcf: float = 0.0
    tv_perpetuity: float = 0.0
    tv_exit: float = 0.0
    pv_tv_perpetuity: float = 0.0
    pv_tv_exit: float = 0.0
    ev_perpetuity: float = 0.0
    ev_exit: float = 0.0
    per_share_perpetuity: float = 0.0
    per_share_exit: float = 0.0
    implied_exit_multiple_from_perp: float = 0.0
    implied_growth_from_exit: float = 0.0


def dcf(inp: DCFInputs) -> DCFResult:
    res = DCFResult()
    rev_prev = inp.revenue0
    n = len(inp.growth)
    for t in range(n):
        rev = rev_prev * (1 + inp.growth[t])
        ebit = rev * inp.ebit_margin[t]
        nopat = ebit * (1 - inp.tax_rate)
        da = rev * inp.da_pct[t]
        capex = rev * inp.capex_pct[t]
        dnwc = (rev - rev_prev) * inp.nwc_pct_of_delta_rev
        fcf = nopat + da - capex - dnwc
        disc_t = t + 0.5 if inp.mid_year else t + 1
        df = 1 / (1 + inp.wacc) ** disc_t
        res.rows.append({"year": t + 1, "revenue": rev, "growth": inp.growth[t], "ebit": ebit,
                         "margin": inp.ebit_margin[t], "nopat": nopat, "da": da, "capex": capex,
                         "dnwc": dnwc, "fcf": fcf, "df": df, "pv": fcf * df, "ebitda": ebit + da})
        res.pv_fcf += fcf * df
        rev_prev = rev
    last = res.rows[-1]
    df_n = 1 / (1 + inp.wacc) ** n
    res.tv_perpetuity = last["fcf"] * (1 + inp.terminal_growth) / (inp.wacc - inp.terminal_growth)
    res.tv_exit = last["ebitda"] * inp.exit_multiple
    res.pv_tv_perpetuity = res.tv_perpetuity * df_n
    res.pv_tv_exit = res.tv_exit * df_n
    res.ev_perpetuity = res.pv_fcf + res.pv_tv_perpetuity
    res.ev_exit = res.pv_fcf + res.pv_tv_exit
    res.per_share_perpetuity = (res.ev_perpetuity - inp.net_debt) / inp.shares
    res.per_share_exit = (res.ev_exit - inp.net_debt) / inp.shares
    res.implied_exit_multiple_from_perp = res.tv_perpetuity / last["ebitda"]
    # g such that perpetuity TV == exit TV
    res.implied_growth_from_exit = (res.tv_exit * inp.wacc - last["fcf"]) / (res.tv_exit + last["fcf"])
    return res


def dcf_sensitivity(inp: DCFInputs, waccs, tgs) -> list[list[float]]:
    out = []
    for w in waccs:
        row = []
        for g in tgs:
            i = DCFInputs(**{**inp.__dict__, "wacc": w, "terminal_growth": g})
            row.append(dcf(i).per_share_perpetuity)
        out.append(row)
    return out


# ---------------------------------------------------------------- DDM
def gordon(d0: float, g: float, r: float) -> float | None:
    if r <= g:
        return None
    return d0 * (1 + g) / (r - g)


def two_stage_ddm(d0: float, g1: float, years: int, g2: float, r: float) -> dict:
    pv, d = 0.0, d0
    for t in range(1, years + 1):
        d *= 1 + g1
        pv += d / (1 + r) ** t
    tv = d * (1 + g2) / (r - g2)
    return {"pv_stage1": pv, "tv": tv, "pv_tv": tv / (1 + r) ** years, "value": pv + tv / (1 + r) ** years}


def h_model(d0: float, g_short: float, g_long: float, half_life: float, r: float) -> float:
    """Fuller-Hsia H-model: linear fade from g_short to g_long over 2H years."""
    return d0 * (1 + g_long) / (r - g_long) + d0 * half_life * (g_short - g_long) / (r - g_long)
