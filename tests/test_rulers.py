from datetime import date

from ruleone.metrics import MARKER_LABELS
from ruleone.rulers import marker_gaps, parse_front, pick_names, tranche_plan


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


def test_split_and_memo(tmp_path, monkeypatch):
    import json
    from datetime import date
    from ruleone import rulers
    work, out = tmp_path / "work", tmp_path / "rulers"
    work.mkdir(); out.mkdir()
    monkeypatch.setattr(rulers, "WORK", work)
    monkeypatch.setattr(rulers, "OUT", out)
    monkeypatch.setattr(rulers, "ROOT", tmp_path)
    names = [{"ticker": t, "screen": {"methods_agree": 2}} for t in ("AAA", "BBB", "CCC", "DDD", "EEE")]
    (work / "inputs.json").write_text(json.dumps({"date": "2026-10-24", "names": names}))
    assert rulers.split(3) == ["s00", "s01"]
    s1 = json.loads((work / "shards" / "s01.json").read_text())
    assert [n["ticker"] for n in s1["names"]] == ["DDD", "EEE"] and s1["shards"] == 2
    (out / "index.json").write_text(json.dumps([
        {"ticker": "AAA", "verdict": "WATCH", "confidence": 3, "entry": [10.0], "updated": "2026-10-24", "price_at_update": 12.0, "summary": "ok"},
        {"ticker": "BBB", "verdict": "BUY", "confidence": 4, "entry": [5.0], "updated": "2026-10-10", "summary": "old"}]))
    (work / "memos").mkdir()
    (work / "memos" / "s00.md").write_text("### AAA · WATCH\n- **For the owner:** fine")
    text = rulers.memo(date(2026, 10, 24)).read_text()
    assert "5 names queued, 1 dossiers updated" in text and "BBB, CCC, DDD, EEE" in text
    assert "| [AAA](../../research/rulers/AAA.md) | WATCH | 3/5 | $12.00 | $10.00 | 2 | ok |" in text
    assert "### AAA · WATCH" in text


def test_marker_gaps_flags_dossier_without_per_marker_lines():
    # METHOD.md proposal 2026-10-09: a dossier needs one line per marker
    full = "\n".join(f"- ✔ `{k}`: ok" for k in MARKER_LABELS)
    assert marker_gaps(full) == []
    partial = full.replace("- ✔ `margin_stable`: ok", "margin_stable is fine")
    assert marker_gaps(partial) == ["margin_stable"]
    assert marker_gaps("## Markers\nAll good.") == list(MARKER_LABELS)


def test_marker_gaps_accepts_unquoted_keys_and_ignores_stray_question_marks():
    from ruleone.rulers import marker_gaps
    gaps = marker_gaps("- ✔ roic_consistent: confirmed.\n- ✘ `low_debt`: 5 years.\n- is fcf_margin fine?\n")
    assert "roic_consistent" not in gaps and "low_debt" not in gaps and "fcf_margin" in gaps
