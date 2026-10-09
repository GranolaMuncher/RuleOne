import math

from ruleone.companyfacts import annual_series, ttm
from ruleone.metrics import big_five, growth, normalize_splits, roic, windage_growth
from ruleone.universe import _is_common
from ruleone.valuation import (DCFInputs, dcf, gordon, payback_price, sticker_price, ten_cap_price,
                               two_stage_ddm)


def test_growth():
    assert math.isclose(growth(100, 200, 1), 1.0)
    assert math.isclose(growth(100, 259.37424601, 10), 0.10, rel_tol=1e-6)
    assert growth(-1, 5, 5) is None and growth(5, None, 5) is None


def test_sticker_price_matches_rule_one_book_example():
    # EPS 1, g 10%: future EPS 2.594, PE min(20, 25)=20 -> 51.87 / 1.15^10 = 12.82
    s = sticker_price(1.0, 0.10, 25)
    assert math.isclose(s["future_pe"], 20)
    assert math.isclose(s["sticker"], 2.5937424601 * 20 / 1.15 ** 10, rel_tol=1e-9)
    assert math.isclose(s["mos_price"], s["sticker"] / 2)
    assert sticker_price(-1, 0.1, 20) is None


def test_payback_and_ten_cap():
    assert math.isclose(payback_price(100, 100, 0.0), 8.0)
    assert math.isclose(ten_cap_price(50, 100), 5.0)


def test_dcf_perpetuity_and_exit_consistency():
    n = 5
    inp = DCFInputs(revenue0=1000, growth=[0.0] * n, ebit_margin=[0.2] * n, tax_rate=0.25, da_pct=[0.05] * n,
                    capex_pct=[0.05] * n, nwc_pct_of_delta_rev=0.0, wacc=0.10, terminal_growth=0.0,
                    exit_multiple=6.0, net_debt=0, shares=1, mid_year=False)
    r = dcf(inp)
    # flat FCF of 150 forever at 10% = 1500
    assert math.isclose(r.ev_perpetuity, 1500, rel_tol=1e-9)
    assert math.isclose(r.implied_exit_multiple_from_perp, 1500 / 250)
    assert math.isclose(r.implied_growth_from_exit, 0.0, abs_tol=1e-9)


def test_ddm():
    assert math.isclose(gordon(1.0, 0.04, 0.09), 1.04 / 0.05)
    two = two_stage_ddm(1.0, 0.04, 5, 0.04, 0.09)["value"]
    assert math.isclose(two, gordon(1.0, 0.04, 0.09), rel_tol=1e-9)


def test_split_normalization():
    years = {2019: {"shares": 100, "eps": 10.0, "net_income": 1000},
             2020: {"shares": 98, "eps": 11.0, "net_income": 1078},
             2021: {"shares": 1960, "eps": 0.6, "net_income": 1176}}   # 20:1 split
    out = normalize_splits(years)
    assert math.isclose(out[2019]["eps"], 0.5) and math.isclose(out[2020]["eps"], 0.55)
    assert out[2021]["eps"] == 0.6


def test_big_five_and_windage():
    years = {}
    for i, y in enumerate(range(2015, 2026)):
        k = 1.12 ** i
        years[y] = {"end": f"{y}-12-31", "revenue": 100 * k, "eps": 1 * k, "shares": 10, "equity": 50 * k,
                    "ocf": 20 * k, "capex": 5 * k, "op_income": 30 * k, "pretax": 30 * k, "tax": 6 * k,
                    "net_income": 24 * k, "lt_debt": 10}
    b = big_five(years)
    assert b["tests_passed"] == b["tests_total"] == 15
    assert math.isclose(windage_growth(b), 0.12, rel_tol=1e-9)
    assert roic({"equity": 100, "lt_debt": 0, "op_income": 10, "pretax": 10, "tax": 2}) == 0.08


def test_ttm_and_annual():
    ents = [{"start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2025-02-01"},
            {"start": "2024-01-01", "end": "2024-06-30", "val": 45, "filed": "2024-08-01"},
            {"start": "2025-01-01", "end": "2025-06-30", "val": 60, "filed": "2025-08-01"},
            {"start": "2023-01-01", "end": "2023-12-31", "val": 90, "filed": "2024-02-01"}]
    assert ttm(ents) == (115, "2025-06-30")
    assert annual_series(ents) == {"2023-12-31": 90, "2024-12-31": 100}


def test_ticker_filter():
    assert _is_common("BRK-B") and _is_common("AAPL")
    assert not _is_common("BAC-PL") and not _is_common("ETI-P") and not _is_common("ABCDW")


def test_post_filing_split():
    from ruleone.metrics import post_filing_split
    assert post_filing_split(32e6, 800e6) == 25.0
    assert post_filing_split(100e6, 97e6) == 1.0
    assert post_filing_split(None, 5) == 1.0


def test_reporting_currency_ignores_convenience_usd():
    from ruleone.companyfacts import reporting_currency
    gaap = {"NetIncomeLoss": {"units": {"CNY": [{}] * 9, "USD": [{}] * 2}},
            "Revenues": {"units": {"CNY": [{}] * 9, "USD": [{}] * 2}}}
    assert reporting_currency(gaap) == "CNY"
    assert reporting_currency({"NetIncomeLoss": {"units": {"USD": [{}]}}}) == "USD"
    assert reporting_currency({}) == "USD"


def test_convert_to_usd_per_ads():
    from ruleone.normalize import convert
    # HKD filer, 1 ADS = 8 ordinary shares -> share factor 1/8
    row = {"revenue": 7.8e9, "eps": 10.0, "shares": 1e9, "end": "2025-12-31"}
    out = convert(row, fx=7.8, per_share_factor=1 / 8)
    assert math.isclose(out["revenue"], 1e9)
    assert math.isclose(out["eps"], 10.0 / 7.8 * 8)
    assert out["shares"] == 1e9 and out["end"] == "2025-12-31"


def test_ads_ratio_detected_as_fractional_split():
    from ruleone.metrics import post_filing_split
    assert post_filing_split(1.12e9, 140e6) == 1 / 8


def test_marketwide_labels_and_price_stats():
    from ruleone.marketwide import price_stats, status_of, valuation_label
    assert status_of(50, 60, None, None, 120) == "BUY"
    assert status_of(100, 60, 110, None, 120) == "BUY*"
    assert valuation_label(50, 60, 120) == "BELOW MOS"
    assert valuation_label(100, 60, 120) == "BELOW STICKER"
    assert valuation_label(130, 60, 120) == "ABOVE STICKER"
    assert valuation_label(130, None, None) == "NO STICKER"
    weekly = [(f"2026-{m:02d}-01", float(m), float(m)) for m in range(1, 11)]
    ps = price_stats({"regularMarketPrice": 10.0, "fiftyTwoWeekHigh": 20.0, "fiftyTwoWeekLow": 5.0}, weekly)
    assert ps["off_high"] == -0.5 and ps["above_low"] == 1.0
    assert abs(ps["chg_1w"] - (10 / 9 - 1)) < 1e-9


def test_normalize_keeps_negative_eps(monkeypatch):
    from datetime import date
    from types import SimpleNamespace
    import ruleone.normalize as nz
    monkeypatch.setattr(nz, "load_fx", lambda f, c: {"price": 1.0, "series": []})
    monkeypatch.setattr(nz, "load_share_fallback", lambda f, t: {})
    cf = {"currency": "USD", "annual": {},
          "ttm": {"_end": "2026-06-28", "eps": -0.05, "net_income": 154000},
          "latest": {"diluted_shares": 43e6, "diluted_shares_date": "2026-06-28"}}
    out = nz.normalize(None, SimpleNamespace(ticker="X"), cf, date(2026, 10, 4))
    assert out["eps"] == -0.05


def test_sic_to_sector():
    from ruleone.sectors import sic_to_sector
    assert sic_to_sector("7372") == "Information Technology"     # prepackaged software
    assert sic_to_sector(2834) == "Health Care"                  # pharma
    assert sic_to_sector(2800) == "Materials"                    # chemicals
    assert sic_to_sector(6331) == "Financials"                   # P&C insurance
    assert sic_to_sector(6798) == "Real Estate"                  # REITs
    assert sic_to_sector(3711) == "Consumer Discretionary"       # motor vehicles
    assert sic_to_sector(4911) == "Utilities"
    assert sic_to_sector(1311) == "Energy"
    assert sic_to_sector("") == ""


def test_contiguous_months():
    from ruleone.marketwide import _contiguous_months
    assert _contiguous_months(["2025-11", "2025-12", "2026-01"])
    assert not _contiguous_months(["2025-11", "2026-01"])


def test_dividend_stats():
    from ruleone.marketwide import dividend_stats
    series = [(f"{2016 + i // 12}-{i % 12 + 1:02d}-01", 100.0, 50.0 + i * 0.5) for i in range(121)]
    divs = [("2025-12-15", 1.0), ("2025-06-15", 1.0), ("2020-03-15", 0.5), ("2020-09-15", 0.5)]
    out = dividend_stats({"series": series, "dividends": divs}, 100.0)
    assert out["div_ttm"] == 2.0 and abs(out["div_yield"] - 0.02) < 1e-12
    assert abs(out["div_growth_5y"] - ((2.0 / 1.0) ** 0.2 - 1)) < 1e-9
    assert out["tr_10y"] is not None and out["tr_5y"] is not None
    assert dividend_stats(None, 10)["div_yield"] is None


def test_owner_earnings_and_ten_cap_follow_the_refined_method():
    from ruleone.metrics import owner_earnings
    from ruleone.valuation import methods_agree
    # OCF 100, capex 40, D&A 25 -> maintenance capex 25; tax 15 added back -> 90
    assert math.isclose(owner_earnings({"ocf": 100, "capex": -40, "da": 25, "tax": 15}), 90)
    # no D&A: maintenance defaults to half of capex; a tax benefit is not added
    assert math.isclose(owner_earnings({"ocf": 100, "capex": 40, "tax": -5}), 80)
    assert owner_earnings({"capex": 10}) is None
    # Ten Cap subtracts net debt but never adds net cash
    assert math.isclose(ten_cap_price(50, 100, net_debt=100), 4.0)
    assert math.isclose(ten_cap_price(50, 100, net_debt=-300), 5.0)
    assert ten_cap_price(10, 100, net_debt=500) is None
    assert methods_agree(10, 12, 9, 11) == 2
    assert methods_agree(None, 12, 9, 11) == 0


def test_sane_shares_fixes_scale_errors_only():
    from ruleone.metrics import sane_shares
    assert math.isclose(sane_shares(32_800, 259_223_000, 7.96), 259_223_000 / 7.96)
    assert sane_shares(30_000_000, 259_223_000, 7.96) == 30_000_000      # within range: untouched
    assert sane_shares(32_800, -5, 7.96) == 32_800                     # losses can't be used


def test_wonderful_markers_separate_steady_compounders_from_weak_businesses():
    from ruleone.metrics import marker_summary, wonderful_markers
    def year(y, k):  # steady compounder: 12%/yr growth, 25% ROIC, stable margins, no debt, shrinking shares
        g = 1.12 ** k
        return {"end": f"{y}-12-31", "revenue": 1000 * g, "gross_profit": 600 * g, "op_income": 250 * g,
                "pretax": 250 * g, "tax": 50 * g, "net_income": 200 * g, "eps": 2 * g * 1.01 ** k,
                "shares": 100 / 1.01 ** k, "ocf": 230 * g, "capex": -30 * g, "da": 20 * g,
                "equity": 800 * g, "lt_debt": 0.0}
    good = {2015 + k: year(2015 + k, k) for k in range(11)}
    m = wonderful_markers(good, good[2025])
    score, s = marker_summary(m)
    assert score == 1.0 and "growth_coherent=1" in s and "recession_tested=1" in s
    bad = {y: {**r, "net_income": -50.0, "op_income": -40.0, "ocf": -10.0, "shares": r["shares"] * (1.1 ** (y - 2015) * 1.02 ** (y - 2015)),
               "lt_debt": 5000.0} for y, r in good.items()}
    mb = wonderful_markers(bad, bad[2025])
    assert mb["roic_consistent"]["pass"] is False and mb["no_dilution"]["pass"] is False
    assert marker_summary(mb)[0] < 0.5
