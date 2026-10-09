from datetime import date

from ruleone.rulers import parse_front, pick_names, tranche_plan


def test_tranche_plan_three_levels_capped_at_sticker():
    p = tranche_plan(price=95, mos=80, payback=100, ten_cap=150, sticker=120)
    assert [t["price"] for t in p["tranches"]] == [120, 100, 80]     # ten cap capped at sticker
    assert p["stop_buying_above"] == 120 and p["trim_above"] == 120
    assert p["tranches_triggered"] == 2


def test_tranche_plan_single_level_steps_down():
    p = tranche_plan(price=None, mos=None, payback=None, ten_cap=50, sticker=None)
    assert [t["price"] for t in p["tranches"]] == [50, 42.5, 35]
    assert tranche_plan(10, None, None, None, 20) is None


def test_pick_names_orders_scope():
    cands = [{"ticker": "A", "status": "BUY", "tier": "B", "rank_score": "3", "flags": ""},
             {"ticker": "M", "status": "BUY", "tier": "C", "rank_score": "9", "flags": "micro-cap"},
             {"ticker": "B", "status": "BUY*", "tier": "A", "rank_score": "5", "flags": ""},
             {"ticker": "Z", "status": "ON DECK", "tier": "A", "rank_score": "9", "flags": ""}]
    radar = {"E": [{"verdict": "EVENT", "date": "2026-10-08"}], "N": [{"verdict": "NOISE", "date": "2026-10-08"}]}
    picks = pick_names(cands, radar, ["W"], {"OLD": "2026-09-01", "NEW": "2026-10-05"}, date(2026, 10, 10), ["F"])
    assert [t for t, _ in picks] == ["F", "W", "B", "A", "E", "OLD", "NEW"]


def test_parse_front():
    meta = parse_front('---\nticker: ADBE\nverdict: WATCH\nentry: [262.9, 230]\nsummary: "A, b"\n---\n# x')
    assert meta == {"ticker": "ADBE", "verdict": "WATCH", "entry": ["262.9", "230"], "summary": "A, b"}
