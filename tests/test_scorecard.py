from datetime import date

from ruleone import scorecard


def test_new_calls_logs_changes_only():
    existing = [{"agent": "rulers", "ticker": "A", "verdict": "WATCH", "date": "2026-10-01"},
                {"agent": "radar", "ticker": "B", "verdict": "EVENT", "date": "2026-10-02"}]
    dossiers = [{"ticker": "A", "verdict": "WATCH", "updated": "2026-10-09", "price_at_update": 10, "entry": [9]},
                {"ticker": "C", "verdict": "BUY", "updated": "2026-10-09", "price_at_update": 20, "entry": [21]}]
    radar = {"B": [{"verdict": "EVENT", "date": "2026-10-02"}, {"verdict": "PROBLEM", "date": "2026-10-08", "headline": "x"}]}
    rows = scorecard.new_calls(date(2026, 10, 9), existing, dossiers, radar, {"B": 5.0}, 500.0)
    assert [(r["agent"], r["ticker"], r["verdict"]) for r in rows] == [("rulers", "C", "BUY"), ("radar", "B", "PROBLEM")]


def test_evaluate_grades_against_spy(tmp_path, monkeypatch):
    monkeypatch.setattr(scorecard, "OUT", tmp_path)
    monkeypatch.setattr(scorecard, "CALLS", tmp_path / "calls.csv")
    (tmp_path / "calls.csv").write_text("date,agent,ticker,verdict,price,spy,tranche1,note\n"
                                        "2026-08-01,rulers,X,BUY,100,500,,\n2026-10-01,rulers,Y,BUY,100,500,,\n")
    r = scorecard.evaluate(date(2026, 10, 9), spy_now=550.0, px={"X": 70.0, "Y": 120.0})
    assert r["graded"] == 2
    assert r["by_verdict"]["BUY"]["calls"] == 1                     # Y is too recent to grade
    assert round(r["by_verdict"]["BUY"]["avg_excess"], 2) == -0.40   # -30% vs +10%
    assert [c["ticker"] for c in r["review_candidates"]] == ["X"]
