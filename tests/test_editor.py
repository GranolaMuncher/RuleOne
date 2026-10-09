from datetime import date

from ruleone.editor import conflicts, screen_changes, upcoming_reports

TODAY = date(2026, 10, 10)


def test_screen_changes_buckets():
    prev = [{"ticker": "A", "status": "BUY"}, {"ticker": "B", "status": "ON DECK"}, {"ticker": "C", "status": "ABOVE STICKER"}]
    cur = [{"ticker": "A", "status": "BUY"}, {"ticker": "B", "status": "BUY*"}, {"ticker": "C", "status": "BUY"},
           {"ticker": "D", "status": "ABOVE STICKER"}]
    ch = screen_changes(cur, prev)
    assert [r["ticker"] for r in ch["entered"]] == ["C"]
    assert [r["ticker"] for r in ch["moved"]] == ["B"] and ch["left"] == []
    assert [r["ticker"] for r in screen_changes(prev[:1], cur[:1] + [{"ticker": "Z", "status": "BUY"}])["left"]] == ["Z"]


def test_conflicts_between_agents():
    dossiers = [
        {"ticker": "BUYP", "verdict": "BUY", "entry": [100], "trim": 300, "updated": "2026-10-09"},
        {"ticker": "WAT", "verdict": "WATCH", "entry": [50], "trim": 90, "updated": "2026-09-01"},
    ]
    radar = {"BUYP": [{"verdict": "PROBLEM", "date": "2026-10-08", "headline": "auditor resigns"}],
             "EVT": [{"verdict": "EVENT", "date": "2026-10-07"}]}
    screen = {"BUYP": {"status": "ON DECK", "price": "120", "flags": "debt > 3 years of FCF"},
              "WAT": {"status": "BUY", "price": "45", "flags": ""},
              "EVT": {"status": "BUY*", "tier": "A", "price": "10"}}
    kinds = {(c["ticker"], c["kind"]) for c in conflicts(dossiers, radar, screen, TODAY)}
    assert kinds == {("BUYP", "verdict vs Radar"), ("BUYP", "verdict vs screen"), ("BUYP", "verdict vs screen flags"),
                     ("WAT", "price reached tranche 1"), ("WAT", "stale dossier"), ("WAT", "screen buy vs analyst"),
                     ("EVT", "event without a dossier")}


def test_upcoming_reports_window():
    rows = [{"ticker": "A", "next_report_est": "2026-10-20"}, {"ticker": "B", "next_report_est": "2026-12-20"},
            {"ticker": "C", "next_report_est": "2026-10-12"}]
    assert [r["ticker"] for r in upcoming_reports(rows, {"A", "B"}, TODAY)] == ["A"]
