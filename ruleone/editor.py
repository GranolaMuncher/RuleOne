"""Editor: the last step on Saturday. Reconciles the agents' *outputs* (screen, Radar, RULERS
dossiers) into one weekly brief and a short list of decisions only the owner can make.

    python -m ruleone.editor prepare   # week's changes + mechanical conflicts -> .work/editor/inputs.json
    (Claude writes reports/weekly/<date>_brief.md + research/editor/decisions.json per agents/editor/PROMPT.md)
    python -m ruleone.editor record    # snapshot this week's state for next week's comparison
    python -m ruleone.editor issues    # optional: mirror decisions to one GitHub issue (EDITOR_ISSUES=true)

The Editor never runs or edits the other agents. It works on what they wrote (docs/AGENT_PLAN.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
RADAR = ROOT / "research" / "radar"
RULERS = ROOT / "research" / "rulers"
OUT = ROOT / "research" / "editor"
WORK = ROOT / ".work" / "editor"
ACTIONABLE = ("BUY", "BUY*", "ON DECK")


def _read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def _json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def screen_changes(cur: list[dict], prev: list[dict]) -> dict:
    """Names entering/leaving buy range and on deck since the previous run."""
    c = {r["ticker"]: r for r in cur}
    p = {r["ticker"]: r for r in prev}
    def bucket(r):
        return r["status"] if r and r.get("status") in ACTIONABLE else None
    entered, left, moved = [], [], []
    for t in sorted(set(c) | set(p)):
        a, b = bucket(p.get(t)), bucket(c.get(t))
        if a == b:
            continue
        row = {"ticker": t, "from": a, "to": b, "tier": (c.get(t) or p.get(t) or {}).get("tier"),
               "price": _f((c.get(t) or {}).get("price"))}
        (entered if a is None else left if b is None else moved).append(row)
    return {"entered": entered, "left": left, "moved": moved}


def conflicts(dossiers: list[dict], radar_hist: dict, screen: dict, today: date) -> list[dict]:
    """Disagreements between agents that the Editor must resolve or hand to the owner."""
    out = []
    cut14 = (today - timedelta(days=14)).isoformat()
    cut21 = (today - timedelta(days=21)).isoformat()
    covered = {d["ticker"] for d in dossiers}
    for d in dossiers:
        t, v = d["ticker"], d.get("verdict")
        s = screen.get(t)
        problems = [it for it in radar_hist.get(t, []) if it.get("verdict") == "PROBLEM" and (it.get("date") or "") >= cut14]
        if v in ("BUY", "ACCUMULATE") and problems:
            out.append({"ticker": t, "kind": "verdict vs Radar",
                        "detail": f"RULERS says {v} but Radar flagged PROBLEM on {problems[0]['date']}: {problems[0].get('headline')}"})
        if v in ("BUY", "ACCUMULATE") and s and s.get("status") not in ("BUY", "BUY*"):
            out.append({"ticker": t, "kind": "verdict vs screen",
                        "detail": f"RULERS says {v} but the screen now has it {s.get('status')}"})
        if v in ("WATCH", "AVOID", "TOO HARD") and s and s.get("status") in ("BUY", "BUY*"):
            out.append({"ticker": t, "kind": "screen buy vs analyst",
                        "detail": f"The screen lists {t} as {s.get('status')} but the dossier says {v}: explain which numbers the analyst corrected"})
        px, t1 = _f((s or {}).get("price")), (d.get("entry") or [None])[0]
        if v == "WATCH" and px is not None and t1 and px <= t1:
            out.append({"ticker": t, "kind": "price reached tranche 1",
                        "detail": f"Price ${px:,.2f} is at or below the dossier's tranche 1 (${t1:,.2f}) but the verdict is WATCH"})
        trim = d.get("trim")
        if px is not None and trim and px > trim:
            out.append({"ticker": t, "kind": "above trim level", "detail": f"Price ${px:,.2f} is above the trim level ${trim:,.2f}"})
        serious = [f for f in ((s or {}).get("flags") or "").split(";")
                   if any(k in f for k in ("cash not real", "debt > 3 years", "ROIC falling"))]
        if v in ("BUY", "ACCUMULATE") and serious:
            out.append({"ticker": t, "kind": "verdict vs screen flags", "detail": f"RULERS says {v} but the screen flags: {'; '.join(serious)}"})
        if (d.get("updated") or "") < cut21:
            out.append({"ticker": t, "kind": "stale dossier", "detail": f"Dossier last updated {d.get('updated') or 'never'}"})
    for t, items in radar_hist.items():
        recent = [it for it in items if it.get("verdict") == "EVENT" and (it.get("date") or "") >= cut14]
        s = screen.get(t)
        if recent and t not in covered and s and s.get("tier") in ("A", "B"):
            out.append({"ticker": t, "kind": "event without a dossier",
                        "detail": f"Radar EVENT {recent[0]['date']} on a tier {s.get('tier')} name with no RULERS dossier"})
    return out


def review_conflicts() -> list[dict]:
    """The Professor's 'major' findings: a dossier whose verdict or levels break a Rule #1 rule."""
    rv = _json(ROOT / "research" / "reviews" / "latest.json", {})
    return [{"ticker": r["ticker"], "kind": "Professor review: major",
             "detail": "; ".join(r.get("issues", []))[:400]} for r in rv.get("reviews", []) if r.get("severity") == "major"]


def upcoming_reports(rows: list[dict], names: set[str], today: date, days: int = 21) -> list[dict]:
    out = []
    for r in rows:
        d = r.get("next_report_est") or ""
        if r["ticker"] in names and d and today.isoformat() <= d <= (today + timedelta(days=days)).isoformat():
            out.append({"ticker": r["ticker"], "date": d, "status": r.get("status")})
    return sorted(out, key=lambda x: x["date"])


def prepare(today: date) -> dict:
    cands = _read_csv(LISTS / "latest" / "all_candidates.csv")
    runs = sorted(p.name for p in (LISTS / "archive").glob("*") if p.is_dir())
    prev_run = next((r for r in reversed(runs) if r < (_json(LISTS / "latest" / "meta.json", {}).get("run_date") or "9999")), None)
    prev = _read_csv(LISTS / "archive" / prev_run / "all_candidates.csv") if prev_run else []
    screen = {r["ticker"]: r for r in cands}
    radar_hist = _json(RADAR / "history.json", {})
    dossiers = _json(RULERS / "index.json", [])
    last = _json(OUT / "state.json", {})
    prev_verdicts = last.get("verdicts", {})
    verdict_changes = [{"ticker": d["ticker"], "from": prev_verdicts.get(d["ticker"]), "to": d["verdict"]}
                       for d in dossiers if prev_verdicts.get(d["ticker"]) != d["verdict"]]
    cut7 = (today - timedelta(days=7)).isoformat()
    radar_week = [{"ticker": t, **it} for t, items in radar_hist.items() for it in items
                  if (it.get("date") or "") >= cut7 and it.get("verdict") in ("EVENT", "PROBLEM", "WATCH")]
    names = {d["ticker"] for d in dossiers} | {t for t, r in screen.items() if r.get("status") in ACTIONABLE}
    payload = {
        "date": today.isoformat(), "screen_run": _json(LISTS / "latest" / "meta.json", {}).get("run_date"),
        "previous_run": prev_run,
        "counts": {s: sum(1 for r in cands if r.get("status") == s) for s in ACTIONABLE},
        "screen_changes": screen_changes(cands, prev),
        "top_ranked": [{k: r.get(k) for k in ("ticker", "name", "status", "tier", "price", "mos_price", "ten_cap_price",
                                                "payback_price", "sticker", "rank_score", "flags")}
                       for r in sorted((r for r in cands if r.get("status") in ("BUY", "BUY*")),
                                       key=lambda r: -(_f(r.get("rank_score")) or 0))[:12]],
        "dossiers": dossiers, "verdict_changes": verdict_changes,
        "radar_week": sorted(radar_week, key=lambda x: (x["verdict"] != "PROBLEM", x["verdict"] != "EVENT", x["ticker"])),
        "guru_moves": _json(LISTS / "latest" / "gurus.json", {}).get("moves", [])[:15],
        "upcoming_reports": upcoming_reports(cands, names, today),
        "conflicts": conflicts(dossiers, radar_hist, screen, today) + review_conflicts(),
        "review": _json(ROOT / "research" / "reviews" / "latest.json", {}),
        "scorecard": {k: v for k, v in _json(ROOT / "research" / "scorecard" / "latest.json", {}).items()
                      if k in ("date", "calls", "graded", "by_verdict", "review_candidates")},
        "last_brief": last.get("brief"),
    }
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "inputs.json").write_text(json.dumps(payload, indent=1, default=str))
    return payload


def record(today: date) -> None:
    dossiers = _json(RULERS / "index.json", [])
    brief = ROOT / "reports" / "weekly" / f"{today.isoformat()}_brief.md"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps({
        "date": today.isoformat(), "verdicts": {d["ticker"]: d["verdict"] for d in dossiers},
        "brief": str(brief.relative_to(ROOT)) if brief.exists() else _json(OUT / "state.json", {}).get("brief"),
    }, indent=1) + "\n")


def issues(today: date) -> str:
    """Mirror decisions.json to one open issue labelled 'editor' (opt-in: repo variable EDITOR_ISSUES=true).
    Off by default because GitHub emails watchers about new issues and the owner asked for no email."""
    if os.environ.get("EDITOR_ISSUES", "").lower() != "true":
        return "issues disabled (set the EDITOR_ISSUES variable to true to enable)"
    dec = _json(OUT / "decisions.json", {})
    items = dec.get("decisions", [])
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo and items):
        return "nothing to post"
    api = f"https://api.github.com/repos/{repo}/issues"
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    body = f"Decisions from the weekly brief ({dec.get('date')}). Research, not advice.\n\n" + "\n".join(
        f"- [ ] **{d.get('ticker', '')}**: {d.get('question')} ({d.get('why', '')})" for d in items)
    existing = requests.get(api, headers=hdr, params={"labels": "editor", "state": "open"}, timeout=30).json()
    title = f"Weekly decisions: {dec.get('date')}"
    if existing:
        requests.patch(f"{api}/{existing[0]['number']}", headers=hdr, json={"title": title, "body": body}, timeout=30)
        return f"updated issue #{existing[0]['number']}"
    r = requests.post(api, headers=hdr, json={"title": title, "body": body, "labels": ["editor"]}, timeout=30)
    return f"opened issue #{r.json().get('number')}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "record", "issues"])
    args = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    if args.cmd == "prepare":
        p = prepare(today)
        print(f"prepared: {len(p['dossiers'])} dossiers, {len(p['conflicts'])} conflicts, "
              f"{len(p['radar_week'])} Radar items, {len(p['upcoming_reports'])} upcoming reports")
    elif args.cmd == "record":
        record(today)
        print("recorded")
    else:
        print(issues(today))


if __name__ == "__main__":
    main()
