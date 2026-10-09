"""Knowledge index: makes the 498 InvestED notes searchable by company and by concept, so every
agent can find what Phil and Danielle said about a business or a situation.

    python -m ruleone.knowledge build   # -> knowledge/index/companies.json, concepts.json
    python -m ruleone.knowledge find NFLX   # quick lookup from the command line

Company matching is deliberately conservative: distinctive brand words and full names only, plus a
hand-kept alias file (knowledge/index/aliases.json) for nicknames like Google -> GOOGL.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "knowledge" / "invested" / "episodes"
INDEX = ROOT / "knowledge" / "index"
UNIVERSE = ROOT / "lists" / "latest" / "universe.csv"
SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|holdings?|group|ltd|limited|plc|sa|nv|ag|"
                    r"the|class [a-c]|common stock|lp|llc|trust|international|global)\b\.?", re.I)
# Brand words that are also everyday words or too generic to match on their own.
GENERIC = {"american", "general", "united", "first", "national", "global", "international", "energy", "capital",
           "financial", "bank", "royal", "new", "big", "great", "best", "target", "gap", "visa", "ford", "match",
           "public", "service", "data", "health", "home", "life", "power", "real", "southern", "western", "eastern",
           "northern", "central", "pacific", "atlantic", "community", "standard", "applied", "advanced", "digital",
           "texas", "california", "florida", "boston", "chicago", "york", "republic", "liberty", "freedom", "progress",
           "carter", "dollar", "smart", "simply", "rule", "value", "market", "markets", "fair", "clear", "core", "key",
           "main", "summit", "pioneer", "frontier", "alpha", "beta", "delta", "omega", "prime", "select", "evolution",
           "invest", "investor", "investors", "fortune", "focus", "rent", "box", "zoom", "snap", "block", "square",
           "shift", "wealth", "money", "edge", "insight", "vision", "wave", "sun", "oil", "gold", "silver", "sky",
           "warren", "buffett", "munger", "town", "phil", "danielle", "charlie", "graham", "jacobs",
           "intelligent", "invested", "moat", "price", "cash", "safety", "event", "story", "love", "radar",
           # places and first names that are also single-word company names
           "burlington", "taylor", "america", "japan", "china", "india", "europe", "bridgewater", "kelly", "harvard",
           "grand", "howard", "williams", "michael", "david", "james", "robert", "john", "mary", "jackson", "jordan",
           "morgan", "lincoln", "washington", "madison", "hamilton", "franklin", "omaha", "boulder", "atlanta",
           "denver", "dallas", "houston", "phoenix", "austin", "nashville", "portland", "seattle", "vermont", "valley"}


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", re.sub(r"[,.&'()]", " ", name))).strip()


def aliases(universe: list[dict], lower_words: Counter | None = None) -> dict[str, str]:
    """{alias: ticker}. Full cleaned names, plus a distinctive first word when no other company shares it
    and it isn't an ordinary English word (one the notes also use in lower case, like "check" or "circle")."""
    lower_words = lower_words or Counter()
    firsts = Counter(_clean(r["name"]).split(" ")[0].lower() for r in universe if r.get("name"))
    out: dict[str, str] = {}
    by_cap = sorted(universe, key=lambda r: -(float(r.get("market_cap") or 0)))
    for r in by_cap:
        clean = _clean(r.get("name") or "")
        if not clean:
            continue
        words = clean.split()
        if len(words) >= 2 and len(clean) >= 8 and not all(lower_words[w.lower()] >= 2 for w in words):
            out.setdefault(clean, r["ticker"])
        first = clean.split(" ")[0]
        if len(first) >= 5 and firsts[first.lower()] == 1 and first.lower() not in GENERIC and first[0].isupper() \
                and lower_words[first.lower()] < 2:
            out.setdefault(first, r["ticker"])
    manual = INDEX / "aliases.json"
    if manual.exists():
        out.update(json.loads(manual.read_text()))
    return out


def _episodes() -> list[dict]:
    eps = []
    for p in sorted(EPISODES.glob("*.md")):
        text = p.read_text()
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', text, re.M)
        concepts = re.search(r"^concepts:\s*\[(.*?)\]", text, re.M)
        one = re.search(r"\*\*In one sentence:\*\*\s*(.+)", text)
        eps.append({"id": p.stem, "title": title.group(1) if title else p.stem, "text": text,
                    "concepts": [c.strip() for c in concepts.group(1).split(",") if c.strip()] if concepts else [],
                    "sentence": one.group(1).strip()[:300] if one else ""})
    return eps


def build() -> dict:
    with UNIVERSE.open() as fh:
        universe = list(csv.DictReader(fh))
    names = {r["ticker"]: r["name"] for r in universe}
    eps = _episodes()
    lower = Counter(w for ep in eps for w in re.findall(r"\b[a-z][a-z']+\b", re.sub(r"^---.*?---", "", ep["text"], flags=re.S)))
    al = aliases(universe, lower)
    pattern = re.compile(r"\b(" + "|".join(sorted((re.escape(a) for a in al), key=len, reverse=True)) + r")\b")
    companies: dict[str, dict] = {}
    concepts: dict[str, list] = {}
    for ep in eps:
        body = re.sub(r"^---.*?---", "", ep["text"], flags=re.S)
        hits = Counter(al[m] for m in pattern.findall(body))
        for t, n in hits.items():
            c = companies.setdefault(t, {"name": names.get(t, ""), "episodes": []})
            c["episodes"].append({"id": ep["id"], "title": ep["title"], "mentions": n, "sentence": ep["sentence"]})
        for c in ep["concepts"]:
            concepts.setdefault(c, []).append(ep["id"])
    for c in companies.values():
        c["episodes"].sort(key=lambda e: (-e["mentions"], e["id"]))
        c["total_mentions"] = sum(e["mentions"] for e in c["episodes"])
    companies = dict(sorted(companies.items(), key=lambda kv: -kv[1]["total_mentions"]))
    INDEX.mkdir(parents=True, exist_ok=True)
    (INDEX / "companies.json").write_text(json.dumps(companies, indent=1) + "\n")
    (INDEX / "concepts.json").write_text(json.dumps(dict(sorted(concepts.items(), key=lambda kv: -len(kv[1]))), indent=1) + "\n")
    return {"companies": len(companies), "concepts": len(concepts)}


def lookup(ticker: str, limit: int = 8) -> list[dict]:
    f = INDEX / "companies.json"
    if not f.exists():
        return []
    return (json.loads(f.read_text()).get(ticker) or {}).get("episodes", [])[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "find"])
    ap.add_argument("ticker", nargs="?")
    a = ap.parse_args()
    if a.cmd == "build":
        print(build())
    else:
        for e in lookup(a.ticker.upper(), 20):
            print(e["id"], e["mentions"], e["title"])


if __name__ == "__main__":
    main()
