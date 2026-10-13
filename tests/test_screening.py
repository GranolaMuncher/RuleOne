"""Known-answer tests for the code that decides which companies reach the lists: the stage-1
screen, quality tiers, the historical P/E behind every Sticker Price, events and the
last-fiscal-year valuation used for the whole-market table."""
import math
from datetime import date

from ruleone.events import _form4_purchases, event_score, event_summary, load_events
from ruleone.marketwide import fy_valuation
from ruleone.metrics import big_five, bvps, fcf
from ruleone.prices import beta, price_near
from ruleone.screener import quality_tier, stage1_pass
from ruleone.valuation import (DCFInputs, dcf, dcf_sensitivity, gordon, historical_pe, payback_price,
                               sticker_price, h_model)

TODAY = date(2026, 10, 13)


class FakeFetcher:
    def __init__(self, json=None, text=None):
        self.json, self.text, self.urls = json, text, []

    def get_json(self, url, ttl_hours=24.0):
        self.urls.append(url)
        return self.json

    def get_text_cached(self, url):
        self.urls.append(url)
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


# ---------------------------------------------------------------- screener
def _b5(**kw):
    b = {"tests_total": 15, "tests_passed": 12, "big5_score": 0.8, "revenue": 100e6, "net_income": 10e6,
         "eps": 1.0, "fy_end": "2025-12-31", "roic10": 0.12, "roic5": 0.11, "roic1": 0.13,
         "debt_payoff_years": 2.0}
    return {**b, **kw}


def test_stage1_pass_thresholds():
    ok = lambda **kw: stage1_pass(_b5(**kw), 0.6, 50e6, TODAY)
    assert ok()
    assert ok(big5_score=0.6) and not ok(big5_score=0.59)        # score is >= min_score
    assert not stage1_pass({}, 0.6, 50e6, TODAY)
    assert not ok(tests_total=7)                                 # too little data to judge
    assert not ok(revenue=49e6)
    assert not ok(net_income=0) and not ok(eps=-0.5)             # must be profitable
    assert ok(fy_end="2025-05-01") and not ok(fy_end="2024-12-31")   # 530 vs 651 days: over 550 is stale
    # needs a 10y or 5y ROIC of at least 10%; the 1y ROIC alone is not enough
    assert ok(roic10=None, roic5=0.10)
    assert not ok(roic10=0.09, roic5=None, roic1=0.30)


def test_quality_tiers():
    assert quality_tier(_b5(debt_payoff_years=3.0)) == "A"       # boundary: 3 years is allowed
    assert quality_tier(_b5(debt_payoff_years=3.1)) == "B"
    assert quality_tier(_b5(debt_payoff_years=None)) == "B"      # unknown debt payoff is not A
    assert quality_tier(_b5(roic1=None)) == "A"                  # a missing ROIC window is skipped
    assert quality_tier(_b5(roic1=0.09, big5_score=0.95)) == "C"  # any ROIC window under 10% drops to C
    assert quality_tier(_b5(big5_score=0.79)) == "B"
    assert quality_tier(_b5(big5_score=0.67)) == "B" and quality_tier(_b5(big5_score=0.66)) == "C"


# ---------------------------------------------------------------- valuation
def test_historical_pe_uses_last_ten_years_and_drops_bad_points():
    eps = {f"{y}-12-31": 1.0 for y in range(2014, 2026)}
    eps["2020-12-31"] = -1.0                                     # loss year: skipped
    prices = {"2014-12-31": 5, "2015-12-31": 5,                  # older than the last 10 years
              "2016-12-31": 10, "2017-12-31": 12, "2018-12-31": 14, "2019-12-31": None,
              "2020-12-31": 30, "2021-12-31": 250,               # P/E of 250 is an outlier: skipped
              "2022-12-31": 16, "2023-12-31": 18, "2024-12-31": 20, "2025-12-31": 22}
    h = historical_pe(eps, prices.get)
    assert h["n"] == 7 and h["low"] == 10 and h["high"] == 22
    assert h["median"] == 16 and math.isclose(h["avg"], 16)
    assert historical_pe({}, prices.get) == {"avg": None, "median": None, "low": None, "high": None, "n": 0}


def test_sticker_future_pe_takes_lower_of_history_and_cap():
    assert sticker_price(1.0, 0.15, 16)["future_pe"] == 16       # history below 2 x 15 = 30
    assert math.isclose(sticker_price(1.0, 0.15, None)["future_pe"], 30)   # no history: 2 x growth
    assert sticker_price(1.0, 0.30, 80)["future_pe"] == 50       # capped at 50
    assert sticker_price(1.0, 0.0, 16) is None


def test_h_model_and_dcf_sensitivity():
    # H-model: 1.04/0.05 + 5 x 0.06/0.05 = 20.8 + 6.0
    assert math.isclose(h_model(1.0, 0.10, 0.04, 5, 0.09), 26.8)
    assert math.isclose(h_model(1.0, 0.04, 0.04, 5, 0.09), gordon(1.0, 0.04, 0.09))
    n = 5
    inp = DCFInputs(revenue0=1000, growth=[0.0] * n, ebit_margin=[0.2] * n, tax_rate=0.25, da_pct=[0.05] * n,
                    capex_pct=[0.05] * n, nwc_pct_of_delta_rev=0.0, wacc=0.10, terminal_growth=0.0,
                    exit_multiple=6.0, net_debt=0, shares=1, mid_year=False)
    grid = dcf_sensitivity(inp, [0.08, 0.10, 0.12], [0.0, 0.02])
    # flat FCF of 150 with no growth is worth 150 / WACC
    assert all(math.isclose(row[0], 150 / w) for row, w in zip(grid, (0.08, 0.10, 0.12)))
    assert all(row[1] > row[0] for row in grid)                  # more terminal growth, more value
    assert math.isclose(grid[1][1], dcf(DCFInputs(**{**inp.__dict__, "terminal_growth": 0.02})).per_share_perpetuity)
    assert inp.wacc == 0.10 and inp.terminal_growth == 0.0       # the input is not changed


# ---------------------------------------------------------------- metrics
def test_bvps_and_fcf():
    assert bvps({"equity": 500, "shares": 100}) == 5
    assert bvps({"equity": 500, "shares": 0}) is None and bvps({"shares": 100}) is None
    assert fcf({"ocf": 100, "capex": -30}) == 70 and fcf({"ocf": 100, "capex": 30}) == 70   # either sign
    assert fcf({"ocf": 100}) == 100 and fcf({"capex": 30}) is None


# ---------------------------------------------------------------- events
FORM4 = """<ownershipDocument>
<nonDerivativeTransaction>
  <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
  <transactionAmounts>
    <transactionShares>
      <value>100</value>
    </transactionShares>
    <transactionPricePerShare><value>50.50</value></transactionPricePerShare>
  </transactionAmounts>
</nonDerivativeTransaction>
<nonDerivativeTransaction>
  <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
  <transactionAmounts><transactionShares><value>200</value></transactionShares>
  <transactionPricePerShare><value>60</value></transactionPricePerShare></transactionAmounts>
</nonDerivativeTransaction>
<nonDerivativeTransaction>
  <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
  <transactionAmounts><transactionShares><value>10</value></transactionShares></transactionAmounts>
</nonDerivativeTransaction>
</ownershipDocument>"""


def test_form4_counts_only_open_market_purchases():
    f = {"accessionNumber": "0000320193-26-000001", "primaryDocument": "xslF345X05/form4.xml"}
    fx = FakeFetcher(text=FORM4)
    assert _form4_purchases(fx, 320193, f) == (5050.0, 110)     # the sale is ignored; no price adds no dollars
    assert fx.urls == ["https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/form4.xml"]
    assert _form4_purchases(FakeFetcher(text=OSError("down")), 320193, f) == (0.0, 0)


def test_event_score():
    assert event_score({}) == 0.0
    assert event_score({"drawdown_52w": -0.10}) == 0.0           # first 10% of a drawdown counts for nothing
    assert math.isclose(event_score({"drawdown_52w": -0.30}), 0.8)
    assert event_score({"drawdown_52w": -0.90}) == 2.0           # capped at +2
    assert event_score({"insider_buys": 2, "insider_buy_usd": 2.5e6}) == 1.5
    assert event_score({"insider_buys": 1, "insider_buy_usd": 50e6}) == 2.0
    assert event_score({"activist_13d": ["x"], "negative_8k": ["y"]}) == 1.0


def test_load_events_from_submissions():
    cik = 320193
    filings = [  # EDGAR lists the newest first
        ("8-K", "2026-10-01", "0000320193-26-000009", "a.htm", "2.05,9.01"),
        ("4", "2026-09-01", "0000320193-26-000008", "xslF345X05/form4.xml", ""),
        ("10-Q", "2026-08-01", "0000320193-26-000007", "q.htm", ""),
        ("SC 13D", "2026-07-01", "0000999999-26-000001", "d.htm", ""),     # an outside activist
        ("SC 13D", "2026-07-01", "0000320193-26-000006", "e.htm", ""),     # filed by the company itself
        ("8-K", "2026-06-01", "0000320193-26-000005", "b.htm", "2.06"),    # older than 60 days
    ]
    keys = ["form", "filingDate", "accessionNumber", "primaryDocument", "items"]
    sub = {"sicDescription": "Electronic Computers",
           "filings": {"recent": {k: [f[i] for f in filings] for i, k in enumerate(keys)}}}
    ev = load_events(FakeFetcher(json=sub, text=FORM4), cik, {"price": 70, "high52": 100}, TODAY)
    assert ev["8k"] == ["2026-10-01: 2.05 Restructuring/exit costs"]       # exhibits item 9.01 left out
    assert ev["negative_8k"] == ["2026-10-01: Restructuring/exit costs"]
    assert ev["insider_buys"] == 1 and ev["insider_buy_usd"] == 5050.0
    assert ev["activist_13d"] == ["SC 13D 2026-07-01"]
    assert ev["last_periodic"] == "10-Q 2026-08-01" and ev["next_earnings_est"] == "2026-10-31"
    assert math.isclose(ev["drawdown_52w"], -0.30) and ev["sic"] == "Electronic Computers"
    assert math.isclose(event_score(ev), 2.8)
    s = event_summary(ev)
    assert "-30% off 52w high" in s and "neg 8-K" in s and "13D" in s


# ---------------------------------------------------------------- prices
def test_price_near():
    series = [("2025-01-31", 10.0, 10.0), ("2025-02-28", 11.0, 11.0), ("2025-06-30", 12.0, 12.0)]
    assert price_near(series, "2025-02-20") == 11.0
    assert price_near(series, "2025-04-30") is None             # nearest bar is over 45 days away
    assert price_near([], "2025-02-20") is None


def test_beta_is_ols_slope_of_monthly_returns():
    dates = [f"{2021 + i // 12}-{i % 12 + 1:02d}-01" for i in range(37)]
    rm = [0.01 * ((i % 5) - 2) for i in range(36)]
    market, stock = [100.0], [50.0]
    for r in rm:
        market.append(market[-1] * (1 + r))
        stock.append(stock[-1] * (1 + 0.005 + 1.5 * r))         # alpha does not change beta
    ms = [(d, p, p) for d, p in zip(dates, market)]
    ss = [(d, p, p) for d, p in zip(dates, stock)]
    assert math.isclose(beta(ss, ms), 1.5, rel_tol=1e-9)
    assert beta(ss[:20], ms[:20]) is None                       # under 24 months of overlap
    flat = [(d, 100.0, 100.0) for d in dates]
    assert beta(ss, flat) is None                               # market never moves


# ---------------------------------------------------------------- whole-market table
def test_fy_valuation_restates_a_split_after_the_last_10k():
    years = {}
    for i, y in enumerate(range(2015, 2026)):
        k = 1.12 ** i
        years[y] = {"end": f"{y}-12-31", "revenue": 100e6 * k, "eps": 1 * k, "shares": 10e6,
                    "equity": 50e6 * k, "ocf": 20e6 * k, "capex": 5e6 * k, "op_income": 30e6 * k,
                    "pretax": 30e6 * k, "tax": 6e6 * k, "net_income": 10e6 * k, "lt_debt": 10e6}
    b5 = big_five(years)
    # a 10:1 split after the last 10-K; history traded at 15x (split-adjusted) earnings
    monthly = [(f"{y}-12-31", 15 * years[y]["eps"] / 10, 0) for y in years]
    out = fy_valuation(years, b5, 10.0, monthly, 100e6)
    k = 1.12 ** 10
    eps = k / 10
    assert out["split_after_fy"] == 10.0 and math.isclose(out["eps"], eps)
    assert out["market_cap"] == 10.0 * 100e6 and math.isclose(out["pe"], 10.0 / eps)
    assert math.isclose(out["hist_pe_median"], 15) and math.isclose(out["windage_growth"], 0.12)
    assert math.isclose(out["sticker"], eps * 1.12 ** 10 * 15 / 1.15 ** 10)
    # Ten Cap: owner earnings = OCF 20 - half of capex 5 + tax 6 = 23.5 (x k), less gross long-term debt
    assert math.isclose(out["ten_cap_price"], (10 * 23.5e6 * k - 10e6) / 100e6)
    assert math.isclose(out["payback_price"], payback_price(15e6 * k, 100e6, 0.12))
    assert math.isclose(out["fcf_yield"], 15e6 * k / (10.0 * 100e6))
    empty = fy_valuation({}, {}, 10.0, [], None)
    assert empty["sticker"] is None and empty["split_after_fy"] == 1.0
