from datetime import date

from ruleone.analysts import action_text, parse, revision, street_view
from ruleone.radar import street_signals

RES = {
    "financialData": {"currentPrice": {"raw": 241.05}, "targetHighPrice": {"raw": 373.0}, "targetLowPrice": {"raw": 195.0},
                      "targetMeanPrice": {"raw": 275.06}, "targetMedianPrice": {"raw": 265.5},
                      "numberOfAnalystOpinions": {"raw": 32}, "recommendationMean": {"raw": 2.77}, "recommendationKey": "hold"},
    "recommendationTrend": {"trend": [{"period": "0m", "strongBuy": 4, "buy": 7, "hold": 23, "sell": 4, "strongSell": 1}]},
    "earningsTrend": {"trend": [{"period": "0y", "growth": {"raw": 0.169}}, {"period": "+1y", "growth": {"raw": 0.13}}]},
    "upgradeDowngradeHistory": {"history": [
        {"epochGradeDate": 1791000000, "firm": "UBS", "toGrade": "Neutral", "fromGrade": "Buy", "action": "down",
         "currentPriceTarget": 250.0, "priorPriceTarget": 300.0}]},
}


def test_parse_flattens_consensus():
    r = parse("ADBE", RES, date(2026, 10, 9))
    assert (r["target_low"], r["target_mean"], r["target_high"]) == (195.0, 275.06, 373.0)
    assert r["n_analysts"] == 32 and r["rec_key"] == "hold" and r["hold"] == 23
    assert r["eps_growth_ny"] == 0.13
    a = r["actions"][0]
    assert a["action"] == "down" and a["target"] == 250.0
    assert "downgraded Neutral, target $300→$250" in action_text(a)


def test_parse_no_coverage():
    assert parse("TINY", {"financialData": {"currentPrice": {"raw": 3.0}}}, date(2026, 10, 9)) is None


def test_street_signal_labels():
    bull = {"target_mean": 150, "target_low": 120, "target_high": 180, "n_analysts": 12, "rec_mean": 1.8}
    bear = {"target_mean": 95, "target_low": 70, "target_high": 120, "n_analysts": 12, "rec_mean": 3.1}
    cheap = {"price": 100, "sticker": 200, "status": "BUY"}
    rich = {"price": 100, "sticker": 80, "status": "WAIT"}
    assert street_view(bull, cheap)["street_signal"] == "agree"
    assert street_view(bear, cheap)["street_signal"] == "contrarian"
    assert street_view(bull, rich)["street_signal"] == "crowded"
    assert street_view(bear, rich)["street_signal"] == "both cautious"
    v = street_view({**bull, "n_analysts": 2}, cheap)
    assert v["street_signal"] == "thin coverage" and round(v["upside_mean"], 2) == 0.5


def test_revision_uses_snapshot_a_month_old():
    hist = [{"date": "2026-08-20", "mean": 100.0}, {"date": "2026-09-08", "mean": 110.0}, {"date": "2026-10-01", "mean": 90.0}]
    assert round(revision(hist, 88.0, date(2026, 10, 9)), 3) == -0.2
    assert revision(hist[-1:], 88.0, date(2026, 10, 9)) is None


def test_radar_street_signals_only_fear():
    row = {"recent_actions": "2026-10-07 UBS downgraded Neutral, target $300→$250; 2026-10-06 MS upgraded Buy",
           "revision_30d": "-0.12"}
    sig = street_signals(row, date(2026, 10, 6))
    assert any("UBS downgraded" in s for s in sig) and not any("upgraded" in s for s in sig)
    assert any("cut 12%" in s for s in sig)
    assert street_signals(None, date(2026, 10, 6)) == []
