"""Radar: the daily news-and-filings sweep for the watch list.

    python -m ruleone.radar prepare   # gather facts -> .work/radar/inputs.json (+ lists/latest/gurus.json)
    (Claude reads them, judges EVENT / PROBLEM / NOISE / WATCH per knowledge/rule1/METHOD.md,
     and writes research/radar/<date>.md + research/radar/latest.json)
    python -m ruleone.radar record    # fold latest.json into research/radar/history.json

Radar supplies names and facts, never decisions (InvestED 077, 190, 423). The judgement step follows
the event rules in METHOD.md section 7.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from .events import ITEM_NAMES, NEGATIVE_ITEMS, SUBMISSIONS_URL, _form4_purchases, _recent
from .http import Fetcher
from .marketwide import load_spark

ROOT = Path(__file__).resolve().parent.parent
LISTS = ROOT / "lists"
OUT = ROOT / "research" / "radar"
WORK = ROOT / ".work" / "radar"
CUSIP_CACHE = LISTS / "reference" / "cusip.csv"
NEWS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"

# Value investors whose 13Fs are worth cloning as Radar (InvestED 138, 292, 293, 423). Names, never decisions.
GURUS = {
    1067983: "Berkshire Hathaway (Buffett)",
    1549575: "Dalal Street (Mohnish Pabrai)",
    1709323: "Himalaya Capital (Li Lu)",
    1112520: "Akre Capital",
    1336528: "Pershing Square (Bill Ackman)",
    1061768: "Baupost (Seth Klarman)",
    1056831: "Fairholme (Bruce Berkowitz)",
    1096343: "Markel (Tom Gayner)",
}
MAX_WATCH = 150


# ---------------------------------------------------------------- guru 13Fs
def _num(x: str | None) -> float:
    try:
        return float((x or "0").replace(",", ""))
    except ValueError:
        return 0.0


def parse_13f(xml: str) -> dict[str, dict]:
    """{cusip: {name, value, shares}} for common-stock rows (option rows are skipped)."""
    out: dict[str, dict] = {}
    for row in re.findall(r"<(?:\w+:)?infoTable>(.*?)</(?:\w+:)?infoTable>", xml, re.S):
        def tag(name):
            m = re.search(rf"<(?:\w+:)?{name}>\s*([^<]*?)\s*</(?:\w+:)?{name}>", row)
            return html.unescape(m.group(1)) if m else None
        if tag("putCall"):
            continue
        cusip = (tag("cusip") or "").upper()
        if not cusip:
            continue
        cur = out.setdefault(cusip, {"name": tag("nameOfIssuer") or "", "value": 0.0, "shares": 0.0})
        cur["value"] += _num(tag("value"))
        cur["shares"] += _num(tag("sshPrnamt"))
    return out


def _latest_13fs(fetcher: Fetcher, cik: int, n: int = 2) -> list[dict]:
    sub = fetcher.get_json(SUBMISSIONS_URL.format(cik=cik), ttl_hours=24) or {}
    r = sub.get("filings", {}).get("recent", {})
    out = []
    for form, acc, rep, filed in zip(r.get("form", []), r.get("accessionNumber", []), r.get("reportDate", []),
                                     r.get("filingDate", [])):
        if form == "13F-HR" and all(x["report"] != rep for x in out):
            out.append({"acc": acc, "report": rep, "filed": filed})
        if len(out) == n:
            break
    for f in out:
        base = ARCHIVE.format(cik=cik, acc=f["acc"].replace("-", ""))
        idx = fetcher.get_json(base + "index.json", ttl_hours=24 * 365) or {}
        xmls = [i["name"] for i in idx.get("directory", {}).get("item", [])
                if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
        f["holdings"] = parse_13f(fetcher.get_text_cached(base + xmls[0]) or "") if xmls else {}
    return out


def _load_cusips() -> dict[str, str]:
    if not CUSIP_CACHE.exists():
        return {}
    with CUSIP_CACHE.open() as fh:
        return {r["cusip"]: r["ticker"] for r in csv.DictReader(fh)}


def map_cusips(cusips: set[str], log=print) -> dict[str, str]:
    """CUSIP -> ticker via OpenFIGI (free, no key: 10 ids per call, ~25 calls/min), cached on disk."""
    known = _load_cusips()
    todo = sorted(c for c in cusips if c not in known)
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        try:
            resp = requests.post("https://api.openfigi.com/v3/mapping", timeout=30,
                                 json=[{"idType": "ID_CUSIP", "idValue": c} for c in batch])
            if resp.status_code == 429:
                time.sleep(30)
                resp = requests.post("https://api.openfigi.com/v3/mapping", timeout=30,
                                     json=[{"idType": "ID_CUSIP", "idValue": c} for c in batch])
            resp.raise_for_status()
            for c, res in zip(batch, resp.json()):
                data = [d for d in res.get("data") or [] if d.get("exchCode") == "US"] or res.get("data") or []
                known[c] = (data[0].get("ticker") or "").replace("/", "-") if data else ""
        except Exception as e:  # mapping is best-effort; unmapped names still show by issuer name
            log(f"[openfigi] {e!r}")
            break
        time.sleep(2.6)
    CUSIP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CUSIP_CACHE.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cusip", "ticker"])
        w.writerows(sorted(known.items()))
    return known


def guru_holdings(fetcher: Fetcher, log=print) -> dict:
    filings = {}
    for cik, name in GURUS.items():
        try:
            filings[cik] = _latest_13fs(fetcher, cik)
        except Exception as e:
            log(f"[13F] {name}: {e!r}")
    cusips = {c for fs in filings.values() for f in fs for c in f.get("holdings", {})}
    tick = map_cusips(cusips, log)
    by_ticker: dict[str, list] = {}
    moves, as_of = [], {}
    for cik, fs in filings.items():
        if not fs:
            continue
        name, cur = GURUS[cik], fs[0]
        prev = fs[1]["holdings"] if len(fs) > 1 else {}
        total = sum(h["value"] for h in cur["holdings"].values()) or 1.0
        as_of[name] = cur["report"]
        for c, h in cur["holdings"].items():
            t = tick.get(c) or ""
            p = prev.get(c)
            change = ("new" if not p else "added" if h["shares"] > p["shares"] * 1.2
                      else "cut" if h["shares"] < p["shares"] * 0.8 else "held")
            pos = {"guru": name, "ticker": t, "issuer": h["name"], "weight": round(h["value"] / total, 4),
                   "change": change, "report": cur["report"], "filed": cur["filed"]}
            if t:
                by_ticker.setdefault(t, []).append(pos)
            if change in ("new", "added") and pos["weight"] >= 0.01:
                moves.append(pos)
        for c, p in prev.items():
            if c not in cur["holdings"]:
                moves.append({"guru": name, "ticker": tick.get(c) or "", "issuer": p["name"], "weight": 0.0,
                              "change": "sold", "report": cur["report"], "filed": cur["filed"]})
    for v in by_ticker.values():
        v.sort(key=lambda p: -p["weight"])
    moves.sort(key=lambda m: (m["change"] == "sold", -m["weight"]))
    return {"as_of": as_of, "by_ticker": by_ticker, "moves": moves}


# ---------------------------------------------------------------- watch list
def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def dossier_story(ticker: str) -> dict | None:
    """The RULERS dossier's verdict, ladder and story checks, so Radar can tell when news trips a trigger."""
    p = ROOT / "research" / "rulers" / f"{ticker}.md"
    if not p.exists():
        return None
    text = p.read_text()
    meta = dict(re.findall(r"^(verdict|confidence|trim|updated):\s*(.+)$", text.split("\n---", 1)[0], re.M))
    entry = re.search(r"^entry:\s*\[(.*?)\]", text, re.M)
    def grab(label):
        m = re.search(rf"\*\*{label}[^*]*\*\*(.*?)(?=\n- \*\*|\n## |\Z)", text, re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip(" :.-")[:600] if m else ""
    return {"verdict": meta.get("verdict", "").strip(), "updated": meta.get("updated", "").strip(),
            "entry": entry.group(1) if entry else "", "trim": meta.get("trim", "").strip(),
            "must_stay_true": grab("Three things that must stay true"), "sell_triggers": grab("Sell triggers")}


def watch_list(universe: list[dict], gurus: dict, dossiers: set[str] | None = None) -> list[dict]:
    """Dossier names first (Radar guards their stories), then buy range / on deck, tier A, guru-held quality."""
    dossiers = dossiers or set()
    def prio(r):
        if r["ticker"] in dossiers:
            return -1
        if r["quality_pass"] == "yes" and r["status"] in ("BUY", "BUY*"):
            return 0
        if r["quality_pass"] == "yes" and r["status"] == "ON DECK":
            return 1
        if r["tier"] == "A":
            return 2
        held = gurus["by_ticker"].get(r["ticker"]) or []
        if r["tier"] in ("A", "B") and any(p["weight"] >= 0.04 for p in held):
            return 3
        return None
    picked = [(prio(r), r) for r in universe]
    picked = sorted(((p, r) for p, r in picked if p is not None), key=lambda x: (x[0], -(_f(x[1]["market_cap"]) or 0)))
    return [r for _, r in picked[:MAX_WATCH]]


def filings_since(fetcher: Fetcher, cik: int, since: date) -> list[dict]:
    sub = fetcher.get_json(SUBMISSIONS_URL.format(cik=cik), ttl_hours=4) or {}
    out = []
    for f in _recent(sub):
        fd = date.fromisoformat(f["filingDate"])
        if fd < since:
            break
        form = f["form"]
        if form in ("8-K", "8-K/A"):
            items = [i.strip() for i in (f.get("items") or "").split(",") if i.strip()]
            named = [f"{i} {ITEM_NAMES.get(i, '')}".strip() for i in items if i not in ("9.01",)]
            out.append({"date": f["filingDate"], "form": form, "items": named,
                        "negative": any(i in NEGATIVE_ITEMS for i in items)})
        elif form == "4":
            usd, sh = _form4_purchases(fetcher, cik, f)
            if sh:
                out.append({"date": f["filingDate"], "form": "4", "insider_buy_usd": round(usd)})
        elif form.startswith(("SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G")):
            out.append({"date": f["filingDate"], "form": form})
        elif form in ("10-K", "10-Q", "20-F", "6-K", "DEF 14A"):
            out.append({"date": f["filingDate"], "form": form})
    return out


def news_since(ticker: str, since: date, limit: int = 6) -> list[dict]:
    try:
        resp = requests.get(NEWS_URL.format(t=ticker), timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception:
        return []
    items = []
    for it in re.findall(r"<item>(.*?)</item>", resp.text, re.S):
        def tag(n):
            m = re.search(rf"<{n}>(.*?)</{n}>", it, re.S)
            return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""
        try:
            when = parsedate_to_datetime(tag("pubDate")).astimezone(timezone.utc).date()
        except (TypeError, ValueError):
            continue
        if when >= since:
            items.append({"date": when.isoformat(), "title": tag("title"), "link": tag("link")})
    return items[:limit]


def _chg(series: list, days: int) -> float | None:
    if len(series) <= days:
        return None
    a, b = series[-1 - days][1], series[-1][1]
    return b / a - 1 if a else None


KEEP = ["ticker", "name", "sector", "industry", "status", "tier", "price", "sticker", "mos_price", "payback_price",
        "ten_cap_price", "methods_agree", "marker_score", "markers", "price_to_sticker", "pe", "off_high", "big5_score",
        "roic5", "flags", "events"]


def prepare(fetcher: Fetcher, today: date, log=print) -> dict:
    with (LISTS / "latest" / "universe.csv").open() as fh:
        universe = list(csv.DictReader(fh))
    gurus = guru_holdings(fetcher, log)
    (LISTS / "latest" / "gurus.json").write_text(json.dumps(gurus, indent=1) + "\n")
    state_file = OUT / "state.json"
    last = json.loads(state_file.read_text()).get("last_run") if state_file.exists() else None
    since = max(date.fromisoformat(last) - timedelta(days=1), today - timedelta(days=7)) if last else today - timedelta(days=3)
    dossiers = {p.stem for p in (ROOT / "research" / "rulers").glob("*.md")}
    watch = watch_list(universe, gurus, dossiers)
    mentions = json.loads((ROOT / "knowledge" / "index" / "companies.json").read_text()) \
        if (ROOT / "knowledge" / "index" / "companies.json").exists() else {}
    daily = load_spark(fetcher, [r["ticker"] for r in watch], "1mo", "1d", log=lambda *_: None)
    entries = []
    for i, r in enumerate(watch):
        t = r["ticker"]
        series = (daily.get(t) or {}).get("series") or []
        e = {k: r.get(k) for k in KEEP}
        e.update({"dossier": dossier_story(t) if t in dossiers else None,
                  "invested_episodes": [x["id"] for x in (mentions.get(t) or {}).get("episodes", [])[:5]],
                  "chg_1d": _chg(series, 1), "chg_5d": _chg(series, 5),
                  "filings": filings_since(fetcher, int(r["cik"]), since) if r.get("cik") else [],
                  "news": news_since(t, since),
                  "gurus": [{k: p[k] for k in ("guru", "weight", "change", "report", "filed")}
                            for p in gurus["by_ticker"].get(t, [])]})
        sig = []
        if e["chg_1d"] is not None and e["chg_1d"] <= -0.05:
            sig.append(f"fell {e['chg_1d']:.0%} in a day")
        if e["chg_5d"] is not None and e["chg_5d"] <= -0.08:
            sig.append(f"fell {e['chg_5d']:.0%} in 5 days")
        for f in e["filings"]:
            if f.get("negative"):
                sig.append(f"negative 8-K {f['date']}: {', '.join(f['items'])}")
            elif f["form"].startswith("8-K") and any(x.startswith("2.02") for x in f["items"]):
                sig.append(f"earnings release {f['date']}")
            elif f["form"].startswith("8-K") and any(x.startswith("5.02") for x in f["items"]):
                sig.append(f"director/officer change {f['date']}")
            elif f.get("insider_buy_usd", 0) >= 100_000:
                sig.append(f"insider bought ${f['insider_buy_usd']:,} {f['date']}")
            elif f["form"].startswith(("SC 13D", "SCHEDULE 13D")):
                sig.append(f"13D filed {f['date']}")
        for g in e["gurus"]:
            # A 13F is news only when it is filed; afterwards it stays visible as context in "gurus".
            if g["change"] in ("new", "added") and g["weight"] >= 0.01 and g["filed"] >= since.isoformat():
                sig.append(f"{g['guru']} {g['change']} ({g['weight']:.1%} of 13F, {g['report']})")
        e["signals"] = sig
        entries.append(e)
        if i % 25 == 0:
            log(f"[radar] {i + 1}/{len(watch)}")
    payload = {"date": today.isoformat(), "since": since.isoformat(), "watch": entries,
               "guru_moves": gurus["moves"][:40], "guru_as_of": gurus["as_of"]}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "inputs.json").write_text(json.dumps(payload, indent=1, default=str))
    log(f"[radar] {len(entries)} names, {sum(1 for e in entries if e['signals'])} with signals, since {since}")
    return payload


def record(today: date) -> int:
    """Merge latest.json into history.json (last 12 verdicts per ticker) and advance the state."""
    latest = OUT / "latest.json"
    if not latest.exists():
        return 0
    data = json.loads(latest.read_text())
    hist_file = OUT / "history.json"
    hist = json.loads(hist_file.read_text()) if hist_file.exists() else {}
    n = 0
    for it in data.get("items", []):
        t = it.get("ticker")
        if not t:
            continue
        row = {"date": data.get("date"), **{k: it.get(k) for k in ("verdict", "headline", "why", "sources")}}
        lst = [x for x in hist.get(t, []) if not (x["date"] == row["date"] and x.get("headline") == row["headline"])]
        hist[t] = ([row] + lst)[:12]
        n += 1
    hist_file.write_text(json.dumps(dict(sorted(hist.items())), indent=1) + "\n")
    if data.get("date") == today.isoformat():   # only advance when today's judgement was written
        (OUT / "state.json").write_text(json.dumps({"last_run": today.isoformat()}) + "\n")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "record"])
    args = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    if args.cmd == "prepare":
        prepare(Fetcher(ROOT / ".cache"), today)
    else:
        print(f"recorded {record(today)} radar item(s)")


if __name__ == "__main__":
    main()
