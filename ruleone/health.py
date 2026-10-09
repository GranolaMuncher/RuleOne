"""Engineer's weekly health check: data coverage, anomalies, site size, live pages, workflow status.

    python -m ruleone.health [--dist site/dist] [--build-seconds N] [--site URL]
      -> ops/health/<date>.md and ops/health/latest.json

Deterministic on purpose: the Engineer agent only gets involved when something is new, recurring or broken.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
OUT = ROOT / "ops" / "health"
CF_FILE_LIMIT = 20_000          # Cloudflare Pages: max files per deployment
WORKFLOWS = ["weekly.yml", "radar.yml", "rulers.yml", "editor.yml", "professor.yml", "professor-book.yml", "deploy-site.yml"]


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def anomalies(rows: list[dict], prev_snapshot: list[dict]) -> dict[str, list[str]]:
    """{kind: [tickers]} of data patterns that usually mean an extraction bug, not a bargain."""
    prev = {r["ticker"]: r for r in prev_snapshot}
    out: dict[str, list[str]] = {k: [] for k in (
        "pe_below_4", "yield_above_25pct", "total_return_above_100pct", "sticker_jump_50pct", "missing_price",
        "share_scale_suspect", "ten_cap_over_20x_price")}
    for r in rows:
        t, price = r["ticker"], _f(r.get("price"))
        pe, dy = _f(r.get("pe")), _f(r.get("div_yield"))
        if price is None:
            out["missing_price"].append(t)
            continue
        if pe is not None and 0 < pe < 4:
            out["pe_below_4"].append(t)
        if dy is not None and dy > 0.25:
            out["yield_above_25pct"].append(t)
        if any((_f(r.get(k)) or 0) > 1.0 for k in ("tr_5y", "tr_10y")):
            out["total_return_above_100pct"].append(t)
        st, pst = _f(r.get("sticker")), _f((prev.get(t) or {}).get("sticker"))
        if st and pst and pst > 0 and abs(st / pst - 1) > 0.5:
            out["sticker_jump_50pct"].append(t)
        mcap = _f(r.get("market_cap"))
        rev = _f(r.get("revenue")) or 0
        if mcap is not None and rev > 5e7 and mcap < 0.02 * rev:
            out["share_scale_suspect"].append(t)      # market cap < 2% of sales: shares likely mis-scaled (Nova 2026)
        tc = _f(r.get("ten_cap_price"))
        if tc and tc > 20 * price:
            out["ten_cap_over_20x_price"].append(t)
    return out


def coverage(rows: list[dict]) -> dict:
    n = len(rows) or 1
    share = lambda k: round(sum(1 for r in rows if r.get(k) not in (None, "")) / n, 4)
    return {"rows": len(rows), "with_price": share("price"), "with_sticker": share("sticker"),
            "with_sector": share("sector"), "detailed_ttm": sum(1 for r in rows if r.get("detail") == "ttm"),
            "buy": sum(1 for r in rows if r.get("status") == "BUY"),
            "buy_alt": sum(1 for r in rows if r.get("status") == "BUY*"),
            "on_deck": sum(1 for r in rows if r.get("status") == "ON DECK")}


def site_checks(base: str, tickers: list[str]) -> list[dict]:
    out = []
    for path in ["/", "/stocks/", "/radar/", "/rulers/", "/learn/", "/rule1/", "/holdings/", "/data/universe.json"] + \
                [f"/stock/{t}/" for t in tickers]:
        t0 = time.time()
        try:
            r = requests.get(base.rstrip("/") + path, timeout=30)
            out.append({"path": path, "status": r.status_code, "ms": round((time.time() - t0) * 1000)})
        except Exception as e:
            out.append({"path": path, "status": 0, "error": type(e).__name__})
    return out


def workflow_status(repo: str | None) -> list[dict]:
    if not repo:
        return []
    out = []
    hdr = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        hdr["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    for wf in WORKFLOWS:
        try:
            runs = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/runs",
                                params={"per_page": 5}, headers=hdr, timeout=30).json().get("workflow_runs", [])
        except Exception:
            runs = []
        done = [r for r in runs if r.get("status") == "completed"]
        out.append({"workflow": wf, "last": done[0]["conclusion"] if done else None,
                    "last_at": done[0]["created_at"] if done else None,
                    "failures_of_last_5": sum(1 for r in done if r.get("conclusion") == "failure")})
    return out


def dist_stats(dist: Path) -> dict:
    if not dist.exists():
        return {}
    files = [p for p in dist.rglob("*") if p.is_file()]
    return {"files": len(files), "bytes": sum(p.stat().st_size for p in files),
            "pages": sum(1 for p in files if p.name == "index.html"), "cf_file_limit": CF_FILE_LIMIT}


def repo_stats() -> dict:
    def du(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
    return {"git_bytes": du(ROOT / ".git"), "lists_archive_bytes": du(LISTS / "archive"),
            "archive_runs": len([p for p in (LISTS / "archive").glob("*") if p.is_dir()])}


def run(dist: Path | None, build_seconds: float | None, site: str | None, repo: str | None) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    rows = _rows(LISTS / "latest" / "universe.csv")
    runs = sorted(p.name for p in (LISTS / "archive").glob("*") if p.is_dir())
    prev_snap = _rows(LISTS / "archive" / runs[-2] / "universe_snapshot.csv") if len(runs) >= 2 else []
    an = anomalies(rows, prev_snap)
    prev = json.loads((OUT / "latest.json").read_text()) if (OUT / "latest.json").exists() else {}
    prev_an = prev.get("anomalies", {})
    flagged = {k: {"count": len(v), "sample": v[:12],
                   "new": sorted(set(v) - set(prev_an.get(k, {}).get("all", []))),
                   "recurring": sorted(set(v) & set(prev_an.get(k, {}).get("all", []))), "all": v}
               for k, v in an.items()}
    sample = [r["ticker"] for r in sorted(rows, key=lambda r: -(_f(r.get("market_cap")) or 0))[:3]]
    report = {
        "date": today, "screen_run": json.loads((LISTS / "latest" / "meta.json").read_text()).get("run_date")
        if (LISTS / "latest" / "meta.json").exists() else None,
        "coverage": coverage(rows), "anomalies": flagged,
        "site": {**(dist_stats(dist) if dist else {}), "build_seconds": build_seconds,
                 "checks": site_checks(site, sample) if site else []},
        "workflows": workflow_status(repo), "repo": repo_stats(),
    }
    problems = []
    cov = report["coverage"]
    if cov["rows"] < 5000:
        problems.append(f"universe has only {cov['rows']} rows (expected ~5,800)")
    if cov["with_price"] < 0.9:
        problems.append(f"only {cov['with_price']:.0%} of rows have a price")
    for c in report["site"].get("checks", []):
        if c["status"] != 200:
            problems.append(f"site {c['path']} returned {c['status']}")
    if report["site"].get("files", 0) > 0.8 * CF_FILE_LIMIT:
        problems.append(f"site has {report['site']['files']} files, near Cloudflare's {CF_FILE_LIMIT} limit")
    for w in report["workflows"]:
        if w["last"] == "failure":
            problems.append(f"{w['workflow']} last run failed")
    for k, v in flagged.items():
        if v["recurring"] and k in ("share_scale_suspect", "ten_cap_over_20x_price", "total_return_above_100pct"):
            problems.append(f"recurring anomaly {k}: {', '.join(v['recurring'][:6])}")
    report["problems"] = problems
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(report, indent=1) + "\n")
    (OUT / f"{today}.md").write_text(markdown(report))
    return report


def markdown(r: dict) -> str:
    c, s = r["coverage"], r["site"]
    lines = [f"# Health check: {r['date']}", "",
             f"Screen run {r['screen_run']}. " + ("**Problems:** " + "; ".join(r["problems"]) if r["problems"] else "No problems found."), "",
             "## Data coverage", "",
             f"- Universe rows: {c['rows']:,} · with price {c['with_price']:.1%} · with Sticker {c['with_sticker']:.1%} · with sector {c['with_sector']:.1%}",
             f"- Detailed (TTM) analyses: {c['detailed_ttm']} · BUY {c['buy']} · BUY* {c['buy_alt']} · ON DECK {c['on_deck']}", "",
             "## Anomalies", "", "| Check | Count | New | Recurring | Sample |", "|---|---:|---|---|---|"]
    for k, v in r["anomalies"].items():
        lines.append(f"| {k.replace('_', ' ')} | {v['count']} | {', '.join(v['new'][:5]) or '–'} | "
                     f"{', '.join(v['recurring'][:5]) or '–'} | {', '.join(v['sample'][:6]) or '–'} |")
    lines += ["", "## Site", ""]
    if s.get("files"):
        lines.append(f"- {s['pages']:,} pages, {s['files']:,} files ({s['files'] / s['cf_file_limit']:.0%} of Cloudflare's "
                     f"{s['cf_file_limit']:,}-file limit), {s['bytes'] / 1e6:,.0f} MB"
                     + (f", built in {s['build_seconds']:.0f}s" if s.get("build_seconds") else ""))
    for ch in s.get("checks", []):
        lines.append(f"- `{ch['path']}` → {ch['status']}" + (f" in {ch['ms']} ms" if "ms" in ch else f" ({ch.get('error')})"))
    lines += ["", "## Workflows", "", "| Workflow | Last | When | Failures in last 5 |", "|---|---|---|---:|"]
    for w in r["workflows"]:
        lines.append(f"| {w['workflow']} | {w['last'] or '–'} | {(w['last_at'] or '')[:16]} | {w['failures_of_last_5']} |")
    rp = r["repo"]
    lines += ["", "## Repository", "",
              f"- .git {rp['git_bytes'] / 1e6:,.0f} MB · lists/archive {rp['lists_archive_bytes'] / 1e6:,.1f} MB "
              f"across {rp['archive_runs']} runs", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="")
    ap.add_argument("--build-seconds", type=float, default=None)
    ap.add_argument("--site", default=os.environ.get("SITE_URL", ""))
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    a = ap.parse_args()
    r = run(Path(a.dist) if a.dist else None, a.build_seconds, a.site or None, a.repo or None)
    print(f"health {r['date']}: {len(r['problems'])} problem(s)")
    for p in r["problems"]:
        print(" -", p)


if __name__ == "__main__":
    main()
