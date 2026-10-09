"""Street consensus: analysts' price targets (low / mean / median / high), ratings and recent actions.

    python -m ruleone.analysts refresh                  # daily: the names Rule #1 cares about (~350)
    python -m ruleone.analysts refresh --scope broad    # weekly: also every listing above $2B (~1,700)
    python -m ruleone.analysts refresh --tickers ADBE KNSL

Source: Yahoo Finance's quoteSummary (financialData, recommendationTrend, earningsTrend,
upgradeDowngradeHistory). These are the same sell-side targets that TipRanks and MarketBeat
aggregate; those sites forbid scraping, Yahoo's JSON is public and already used for prices.

Outputs:
    lists/latest/analysts.csv          one row per ticker (rows not refreshed this run are kept, with as_of)
    research/analysts/history.json     per ticker, the mean/low/high target over time (for revisions)
    research/analysts/latest.json      the focus lists: where the street and Rule #1 agree or disagree

How Rule #1 reads the street (InvestED 077, 093, 122, 249, 440):
  * A price target is a 12-month price opinion, not a valuation. A broker's call is a lead, never a
    decision (077). Our value still comes from Ten Cap, Payback Time and Sticker.
  * Analysts lean optimistic (their banks want the business), so their growth rate is a ceiling (093, 122).
  * Fear is the opportunity. When analysts downgrade a wonderful business, managers dump it (249):
    that is how an event creates a price. "Contrarian" names are the ones to research first.
  * Little coverage means more room for mispricing (440). "Crowded" names are priced for good news.
Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists" / "latest"
OUT = ROOT / "research" / "analysts"
CSV_PATH = LISTS / "analysts.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
QS_URL = ("https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
          "?modules=financialData,recommendationTrend,earningsTrend,upgradeDowngradeHistory&crumb={crumb}")
FIELDS = ["ticker", "as_of", "price", "target_low", "target_mean", "target_median", "target_high", "n_analysts",
          "rec_mean", "rec_key", "strong_buy", "buy", "hold", "sell", "strong_sell", "eps_growth_cy", "eps_growth_ny",
          "upside_mean", "upside_low", "spread", "mean_vs_sticker", "revision_30d", "street_signal", "recent_actions"]
HISTORY_KEEP = 40
MIN_COVERAGE = 3
SIGNAL_TEXT = {
    "agree": "Rule #1 price and the street both say cheap",
    "contrarian": "Rule #1 price says cheap, the street is cautious: find out what they fear (possible event)",
    "crowded": "the street loves it but the price is above Sticker: good news is priced in",
    "both cautious": "above Sticker and the street is cautious",
    "thin coverage": "fewer than 3 analysts: more room for mispricing, less help checking the numbers",
    "mixed": "",
}


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _raw(d: dict, k: str):
    v = (d or {}).get(k)
    return _f(v.get("raw")) if isinstance(v, dict) else _f(v)


# ---------------------------------------------------------------- fetch
class Yahoo:
    """Cookie + crumb session for quoteSummary. Throttled; re-crumbs once on 401."""

    def __init__(self, interval: float = 0.35):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.interval, self.last, self.crumb = interval, 0.0, ""

    def _crumb(self) -> str:
        try:
            self.s.get("https://fc.yahoo.com", timeout=20)
        except requests.RequestException:
            pass
        r = self.s.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=20)
        self.crumb = r.text.strip() if r.status_code == 200 and "<" not in r.text else ""
        return self.crumb

    def summary(self, ticker: str) -> dict | None:
        if not self.crumb and not self._crumb():
            raise RuntimeError("Yahoo gave no crumb")
        sym = ticker.replace(".", "-")
        for attempt in range(4):
            wait = self.last + self.interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            try:
                r = self.s.get(QS_URL.format(sym=sym, crumb=self.crumb), timeout=20)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 401 and attempt == 0:
                self._crumb()
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * 2 ** attempt)
                continue
            if r.status_code != 200:
                return None
            res = (r.json().get("quoteSummary") or {}).get("result") or []
            return res[0] if res else None
        return None


def parse(ticker: str, res: dict, today: date) -> dict | None:
    """quoteSummary result -> one flat row (None when no analyst covers the stock)."""
    fd = res.get("financialData") or {}
    row = {"ticker": ticker, "as_of": today.isoformat(), "price": _raw(fd, "currentPrice"),
           "target_low": _raw(fd, "targetLowPrice"), "target_mean": _raw(fd, "targetMeanPrice"),
           "target_median": _raw(fd, "targetMedianPrice"), "target_high": _raw(fd, "targetHighPrice"),
           "n_analysts": _raw(fd, "numberOfAnalystOpinions"), "rec_mean": _raw(fd, "recommendationMean"),
           "rec_key": fd.get("recommendationKey") if fd.get("recommendationKey") not in (None, "none") else None}
    trend = ((res.get("recommendationTrend") or {}).get("trend") or [{}])
    now = next((t for t in trend if t.get("period") == "0m"), trend[0] if trend else {})
    for k in ("strongBuy", "buy", "hold", "sell", "strongSell"):
        row[{"strongBuy": "strong_buy", "strongSell": "strong_sell"}.get(k, k)] = _f(now.get(k))
    growth = {t.get("period"): _raw(t, "growth") for t in (res.get("earningsTrend") or {}).get("trend", [])}
    row["eps_growth_cy"], row["eps_growth_ny"] = growth.get("0y"), growth.get("+1y")
    row["actions"] = [{
        "date": datetime.fromtimestamp(a["epochGradeDate"], tz=timezone.utc).date().isoformat(),
        "firm": a.get("firm"), "action": a.get("action"), "from": a.get("fromGrade"), "to": a.get("toGrade"),
        "target": _f(a.get("currentPriceTarget")) or None, "prior": _f(a.get("priorPriceTarget")) or None,
    } for a in ((res.get("upgradeDowngradeHistory") or {}).get("history") or [])[:25] if a.get("epochGradeDate")]
    if row["target_mean"] is None and not row["n_analysts"]:
        return None
    return row


# ---------------------------------------------------------------- Rule #1 reading
def street_view(a: dict, u: dict | None) -> dict:
    """Compare the consensus with the screen's Rule #1 prices. `u` is the universe row (or None)."""
    u = u or {}
    px = _f(u.get("price")) or _f(a.get("price"))
    mean, low, high = _f(a.get("target_mean")), _f(a.get("target_low")), _f(a.get("target_high"))
    sticker, n, rec = _f(u.get("sticker")), _f(a.get("n_analysts")) or 0, _f(a.get("rec_mean"))
    out = {"upside_mean": mean / px - 1 if mean and px else None,
           "upside_low": low / px - 1 if low and px else None,
           "spread": (high - low) / mean if high and low and mean else None,
           "mean_vs_sticker": mean / sticker if mean and sticker and sticker > 0 else None}
    if n < MIN_COVERAGE:
        out["street_signal"] = "thin coverage"
        return out
    up = out["upside_mean"]
    bull = rec is not None and rec <= 2.2 and up is not None and up >= 0.10
    bear = (rec is not None and rec >= 2.8) or (up is not None and up <= 0.0)
    cheap = u.get("status") in ("BUY", "BUY*", "ON DECK")
    rich = sticker is not None and px is not None and (sticker <= 0 or px > sticker)
    out["street_signal"] = ("agree" if cheap and bull else "contrarian" if cheap and bear else
                            "crowded" if rich and bull else "both cautious" if rich and bear else "mixed")
    return out


def revision(hist: list[dict], mean: float | None, today: date, days: int = 30) -> float | None:
    """Change in the mean target versus the newest snapshot at least `days - 2` days old."""
    cut = (today - timedelta(days=days - 2)).isoformat()
    old = [h for h in hist if h["date"] <= cut and h.get("mean")]
    return mean / old[-1]["mean"] - 1 if old and mean else None


def recent_actions(actions: list[dict], since: str) -> list[dict]:
    return [a for a in actions if a["date"] >= since]


def action_text(a: dict) -> str:
    verb = {"up": "upgraded", "down": "downgraded", "init": "initiated", "main": "kept", "reit": "kept"}.get(a.get("action"), a.get("action") or "")
    tgt = ""
    if a.get("target"):
        tgt = f", target ${a['prior']:,.0f}→${a['target']:,.0f}" if a.get("prior") and a["prior"] != a["target"] else f", target ${a['target']:,.0f}"
    return f"{a['date']} {a.get('firm')} {verb} {a.get('to') or ''}{tgt}".strip()


# ---------------------------------------------------------------- scope
def _read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def scope(universe: list[dict], broad: bool = False) -> list[str]:
    """Daily: dossiers, the watch list, the buy range and on deck, quality tiers. Broad adds every name above $2B."""
    keep: list[str] = []
    seen: set[str] = set()

    def add(t):
        if t and t not in seen:
            seen.add(t)
            keep.append(t)
    for p in sorted((ROOT / "research" / "rulers").glob("*.md")):
        add(p.stem)
    wl = ROOT / "research" / "watchlist.txt"
    for line in (wl.read_text().splitlines() if wl.exists() else []):
        if line.strip() and not line.startswith("#"):
            add(line.strip().upper())
    by_cap = sorted(universe, key=lambda r: -(_f(r.get("market_cap")) or 0))
    for r in by_cap:
        if r.get("status") in ("BUY", "BUY*", "ON DECK") or r.get("quality_pass") == "yes" or r.get("tier") in ("A", "B"):
            add(r["ticker"])
    if broad:
        for r in by_cap:
            if (_f(r.get("market_cap")) or 0) >= 2e9:
                add(r["ticker"])
    return keep


# ---------------------------------------------------------------- focus lists
def _brief(row: dict, u: dict) -> dict:
    return {"ticker": row["ticker"], "name": u.get("name"), "tier": u.get("tier"), "status": u.get("status"),
            "price": _f(u.get("price")) or _f(row.get("price")), "mos_price": _f(u.get("mos_price")),
            "ten_cap_price": _f(u.get("ten_cap_price")), "sticker": _f(u.get("sticker")),
            "target_low": _f(row.get("target_low")), "target_mean": _f(row.get("target_mean")),
            "target_high": _f(row.get("target_high")), "n_analysts": _f(row.get("n_analysts")),
            "rec_mean": _f(row.get("rec_mean")), "rec_key": row.get("rec_key"),
            "upside_mean": _f(row.get("upside_mean")), "revision_30d": _f(row.get("revision_30d")),
            "signal": row.get("street_signal"), "recent_actions": row.get("recent_actions") or ""}


def focus(rows: list[dict], universe: dict[str, dict], dossiers: set[str]) -> dict:
    """Where to look first: Rule #1 and the street side by side. Only quality names (tier A/B, quality pass, dossiers)."""
    def q(r):
        u = universe.get(r["ticker"], {})
        return r["ticker"] in dossiers or u.get("quality_pass") == "yes" or u.get("tier") in ("A", "B")
    good = [r for r in rows if q(r)]
    up = lambda r: _f(r.get("upside_mean")) or 0
    n = lambda r: _f(r.get("n_analysts")) or 0
    pick = lambda sig: [_brief(r, universe.get(r["ticker"], {})) for r in sorted(
        (r for r in good if r.get("street_signal") == sig), key=lambda r: -up(r))][:15]
    revs = sorted((r for r in good if abs(_f(r.get("revision_30d")) or 0) >= 0.10), key=lambda r: _f(r["revision_30d"]))
    return {
        "agree": pick("agree"),
        "contrarian": pick("contrarian"),
        "crowded": sorted(pick("crowded"), key=lambda b: -(b["price"] or 0) / (b["sticker"] or 1))[:10],
        "revisions": [_brief(r, universe.get(r["ticker"], {})) for r in revs][:15],
        "most_watched": [_brief(r, universe.get(r["ticker"], {})) for r in sorted(good, key=lambda r: -n(r))][:15],
        "dossiers": [_brief(r, universe.get(r["ticker"], {})) for r in rows if r["ticker"] in dossiers],
    }


# ---------------------------------------------------------------- refresh
def refresh(today: date, broad: bool = False, tickers: list[str] | None = None, client: Yahoo | None = None,
            log=print) -> dict:
    universe_rows = _read_csv(LISTS / "universe.csv")
    universe = {r["ticker"]: r for r in universe_rows}
    names = tickers or scope(universe_rows, broad)
    old = {r["ticker"]: r for r in _read_csv(CSV_PATH)}
    hist_path = OUT / "history.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else {}
    client = client or Yahoo()
    since = (today - timedelta(days=7)).isoformat()
    got = failed = 0
    for i, t in enumerate(names):
        try:
            res = client.summary(t)
        except Exception as exc:          # no crumb or the network is down: keep yesterday's file
            log(f"[analysts] stopped at {t}: {exc}")
            break
        row = parse(t, res, today) if res else None
        if not row:
            failed += 1
            continue
        h = [x for x in history.get(t, []) if x["date"] != today.isoformat()]
        row.update(street_view(row, universe.get(t)))
        row["revision_30d"] = revision(h, row["target_mean"], today)
        row["recent_actions"] = "; ".join(action_text(a) for a in recent_actions(row.pop("actions"), since)[:4])
        snap = {"date": today.isoformat(), "mean": row["target_mean"], "low": row["target_low"],
                "high": row["target_high"], "n": row["n_analysts"], "rec": row["rec_mean"]}
        if not h or {k: h[-1].get(k) for k in snap if k != "date"} != {k: snap[k] for k in snap if k != "date"} \
                or h[-1]["date"] <= (today - timedelta(days=7)).isoformat():
            h.append(snap)
        history[t] = h[-HISTORY_KEEP:]
        old[t] = row
        got += 1
        if i % 50 == 0:
            log(f"[analysts] {i + 1}/{len(names)} {t}")
    if not got:
        log("[analysts] nothing fetched; files unchanged")
        return {"fetched": 0}
    rows = sorted(old.values(), key=lambda r: r["ticker"])
    LISTS.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    OUT.mkdir(parents=True, exist_ok=True)
    hist_path.write_text(json.dumps(history, separators=(",", ":")) + "\n")
    dossiers = {p.stem for p in (ROOT / "research" / "rulers").glob("*.md")}
    signals: dict[str, int] = {}
    for r in rows:
        signals[r.get("street_signal") or "mixed"] = signals.get(r.get("street_signal") or "mixed", 0) + 1
    latest = {"date": today.isoformat(), "source": "Yahoo Finance analyst consensus", "covered": len(rows),
              "refreshed": got, "no_coverage": failed, "signals": signals, "signal_text": SIGNAL_TEXT,
              "focus": focus(rows, universe, dossiers)}
    (OUT / "latest.json").write_text(json.dumps(latest, indent=1, default=str) + "\n")
    log(f"[analysts] {got} refreshed, {failed} without coverage, {len(rows)} in file")
    return latest


def load() -> dict[str, dict]:
    """analysts.csv keyed by ticker, for the other agents."""
    return {r["ticker"]: r for r in _read_csv(CSV_PATH)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--scope", choices=["daily", "broad"], default="daily")
    r.add_argument("--tickers", nargs="*")
    a = ap.parse_args()
    if a.cmd == "refresh":
        refresh(date.today(), broad=a.scope == "broad", tickers=[t.upper() for t in a.tickers] if a.tickers else None)


if __name__ == "__main__":
    main()
