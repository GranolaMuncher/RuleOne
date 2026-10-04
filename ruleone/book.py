"""The Intelligent Investor, from the owner's own recordings.

The owner reads their copy (revised edition, 2006) and records each chapter, either read aloud
or as their own takeaways, into a PRIVATE repo checked out at .work/library/ (any folder). Each run:

    python -m ruleone.book prepare --count 2   # transcribe chapters with new or changed recordings
    (Claude rewrites knowledge/intelligent_investor/chapters/<key>.md as study notes)
    python -m ruleone.book record              # remember which recordings were turned into notes

Recordings and transcripts never leave .work/ (git-ignored). Only the notes are committed.

Name files by chapter: intro.m4a, ch08.m4a, ch08-part2.m4a, ch08-commentary.mp3, postscript.txt.
Typed memos (.txt/.md) are read as-is.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from .podcast import transcribe

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge" / "intelligent_investor"
CHAPTERS = KNOW / "chapters"
PROGRESS = KNOW / "progress.json"
WORK = ROOT / ".work" / "book"
LIBRARY = Path(os.environ.get("LIBRARY_DIR", ROOT / ".work" / "library"))

AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".oga", ".webm", ".aac", ".flac", ".mp4"}
TEXT = {".txt", ".md"}
NAME = re.compile(r"^(intro|introduction|postscript|ch(?:apter)?[\s_-]*(\d{1,2}))(?:[\s_-].*)?$", re.I)

# Chapter titles of the revised edition (Graham's 1973 text with Zweig's commentary).
TITLES = {
    "intro": "Introduction: What This Book Expects to Accomplish",
    "ch01": "Investment versus Speculation: Results to Be Expected by the Intelligent Investor",
    "ch02": "The Investor and Inflation",
    "ch03": "A Century of Stock-Market History: The Level of Stock Prices in Early 1972",
    "ch04": "General Portfolio Policy: The Defensive Investor",
    "ch05": "The Defensive Investor and Common Stocks",
    "ch06": "Portfolio Policy for the Enterprising Investor: Negative Approach",
    "ch07": "Portfolio Policy for the Enterprising Investor: The Positive Side",
    "ch08": "The Investor and Market Fluctuations",
    "ch09": "Investing in Investment Funds",
    "ch10": "The Investor and His Advisers",
    "ch11": "Security Analysis for the Lay Investor: General Approach",
    "ch12": "Things to Consider About Per-Share Earnings",
    "ch13": "A Comparison of Four Listed Companies",
    "ch14": "Stock Selection for the Defensive Investor",
    "ch15": "Stock Selection for the Enterprising Investor",
    "ch16": "Convertible Issues and Warrants",
    "ch17": "Four Extremely Instructive Case Histories",
    "ch18": "A Comparison of Eight Pairs of Companies",
    "ch19": "Shareholders and Managements: Dividend Policy",
    "ch20": "“Margin of Safety” as the Central Concept of Investment",
    "postscript": "Postscript",
}


def chapter_key(filename: str) -> str | None:
    m = NAME.match(Path(filename).stem.strip())
    if not m:
        return None
    if m.group(2):
        key = f"ch{int(m.group(2)):02d}"
        return key if key in TITLES else None
    return "intro" if m.group(1).lower().startswith("intro") else "postscript"


def scan(library: Path = LIBRARY) -> dict[str, list[Path]]:
    """Chapter files anywhere in the library repo (top level or any folder)."""
    found: dict[str, list[Path]] = {}
    if not library.exists():
        return found
    for f in sorted(library.rglob("*")):
        if ".git" in f.parts:
            continue
        if f.is_file() and f.suffix.lower() in AUDIO | TEXT and (key := chapter_key(f.name)):
            found.setdefault(key, []).append(f)
    return found


def fingerprint(files: list[Path]) -> list[str]:
    return [f"{f.name}:{f.stat().st_size}" for f in files]


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"edition": "Revised edition (2006), Graham with commentary by Jason Zweig", "chapters": {}, "updated": ""}


def pending(found: dict[str, list[Path]], state: dict) -> list[str]:
    """Chapters whose recordings are new or changed since their notes were written, in book order."""
    order = list(TITLES)
    return [k for k in order if k in found and state["chapters"].get(k, {}).get("files") != fingerprint(found[k])]


def prepare(count: int, model_name: str) -> list[dict]:
    found, state = scan(), load_progress()
    WORK.mkdir(parents=True, exist_ok=True)
    for f in WORK.glob("*"):
        f.unlink()
    batch = []
    for key in pending(found, state)[:count]:
        parts, t0 = [], time.time()
        for f in found[key]:
            text = f.read_text(errors="replace") if f.suffix.lower() in TEXT else transcribe(f, model_name)
            parts.append(f"=== {f.name} ===\n{text.strip()}\n")
        (WORK / f"{key}.txt").write_text("\n".join(parts))
        batch.append({
            "key": key, "title": TITLES[key], "files": fingerprint(found[key]),
            "transcript": f".work/book/{key}.txt", "notes": f"knowledge/intelligent_investor/chapters/{key}.md",
        })
        print(f"{key}: {len(found[key])} file(s), {sum(len(p.split()) for p in parts)} words in {time.time() - t0:.0f}s", flush=True)
    (WORK / "batch.json").write_text(json.dumps({"chapters": batch}, indent=2))
    return batch


def record() -> list[str]:
    """Remember recordings whose chapter notes the Professor rewrote (status: notes)."""
    batch_file = WORK / "batch.json"
    if not batch_file.exists():
        return []
    state, added = load_progress(), []
    for ch in json.loads(batch_file.read_text())["chapters"]:
        notes = ROOT / ch["notes"]
        if notes.exists() and re.search(r"^status:\s*notes\s*$", notes.read_text(), re.M):
            state["chapters"][ch["key"]] = {"files": ch["files"], "updated": time.strftime("%Y-%m-%d")}
            added.append(ch["key"])
    if added:
        state["updated"] = time.strftime("%Y-%m-%d")
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(state, indent=2) + "\n")
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--count", type=int, default=2)
    p.add_argument("--model", default="base.en")
    sub.add_parser("record")
    args = ap.parse_args()
    if args.cmd == "prepare":
        print(f"prepared {len(prepare(args.count, args.model))} chapter(s)")
    else:
        print("recorded:", ", ".join(record()) or "none")


if __name__ == "__main__":
    main()
