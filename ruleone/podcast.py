"""InvestED podcast ingest for the Professor agent.

Works through the show in episode order. Each run:

    python -m ruleone.podcast prepare --count 6   # download + transcribe the next episodes
    (Claude writes knowledge/invested/episodes/NNN.md from the transcripts)
    python -m ruleone.podcast record              # mark episodes whose notes exist as done

Transcripts and audio stay in .work/ (git-ignored). Only the Professor's own notes, with
short quotes, are committed, so the public repo never carries the show's full text.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

FEED = "https://feeds.megaphone.fm/investedpodcast"
ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge" / "invested"
PROGRESS = KNOW / "progress.json"
EPISODES = KNOW / "episodes"
WORK = ROOT / ".work" / "invested"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
UA = {"User-Agent": "RuleOne Professor (podcast notes for personal study)"}


def _seconds(text: str | None) -> int | None:
    if not text:
        return None
    total = 0
    for part in text.strip().split(":"):
        if not part.isdigit():
            return None
        total = total * 60 + int(part)
    return total


def _plain(text: str | None) -> str:
    text = re.sub(r"<br\s*/?>|</p>", "\n", text or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_feed(xml_text: str) -> list[dict]:
    """Episodes in show order (oldest first). Numbers come from the "NNN- Title" convention."""
    channel = ET.fromstring(xml_text).find("channel")
    out = []
    for item in channel.findall("item") if channel is not None else []:
        title = (item.findtext("title") or "").strip()
        m = re.match(r"\s*(\d+)\s*[-–:.]\s*(.*)", title)
        enclosure = item.find("enclosure")
        pub = item.findtext("pubDate")
        out.append({
            "number": int(m.group(1)) if m else None,
            "title": m.group(2).strip() if m else title,
            "date": parsedate_to_datetime(pub).date().isoformat() if pub else "",
            "duration": _seconds(item.findtext(f"{ITUNES}duration")),
            "audio": enclosure.get("url") if enclosure is not None else None,
            "guid": (item.findtext("guid") or "").strip(),
            "show_notes": _plain(item.findtext("description")),
        })
    # Unnumbered items (trailers, bonus drops) slot in by date after the numbered run.
    return sorted(out, key=lambda e: (e["number"] is None, e["number"] if e["number"] is not None else 0, e["date"]))


def episode_id(ep: dict) -> str:
    return f"{ep['number']:03d}" if ep["number"] is not None else f"x{ep['date'].replace('-', '')}"


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"feed": FEED, "done": [], "skipped": {}, "updated": ""}


def save_progress(state: dict) -> None:
    state["done"] = sorted(set(state["done"]))
    state["updated"] = time.strftime("%Y-%m-%d")
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(state, indent=2) + "\n")


def next_batch(episodes: list[dict], state: dict, count: int) -> list[dict]:
    seen = set(state["done"]) | set(state.get("skipped", {}))
    return [e for e in episodes if episode_id(e) not in seen and e["audio"]][:count]


def transcribe(audio: Path, model_name: str) -> str:
    from faster_whisper import WhisperModel  # installed only in the Professor workflow

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio), vad_filter=True, beam_size=1)
    lines, minute = [], -1
    for seg in segments:
        # A [mm:ss] marker roughly every minute lets notes cite where an idea came up.
        stamp = int(seg.start // 60)
        prefix = f"\n[{stamp:02d}:{int(seg.start % 60):02d}] " if stamp > minute else ""
        minute = max(minute, stamp)
        lines.append(prefix + seg.text.strip())
    return " ".join(lines).strip()


def audio_problem(text: str, duration: int | None) -> str | None:
    """Flag feed audio that is broken (silent, truncated, garbled): speech runs ~120-180 words a minute."""
    words = len(text.split())
    if not duration or duration < 120:
        return None if words else "no speech found"
    wpm = words / (duration / 60)
    if wpm < 50:
        return f"only {words} words transcribed for {duration // 60} min of audio"
    last = max((int(m) for m in re.findall(r"\[(\d+):\d\d\]", text)), default=0)
    if duration > 600 and last < 0.6 * duration / 60:
        return f"speech stops at about {last} min of a {duration // 60}-min episode"
    return None


def fetch_episodes() -> list[dict]:
    resp = requests.get(FEED, headers=UA, timeout=60)
    resp.raise_for_status()
    return parse_feed(resp.text)


def plan(count: int, shards: int) -> list[list[str]]:
    """Split the next `count` episodes into contiguous shards for parallel runners."""
    ids = [episode_id(e) for e in next_batch(fetch_episodes(), load_progress(), count)]
    size = -(-len(ids) // max(shards, 1)) if ids else 0
    return [ids[i:i + size] for i in range(0, len(ids), size)] if ids else []


def prepare(count: int, model_name: str, ids: list[str] | None = None) -> list[dict]:
    episodes = fetch_episodes()
    state = load_progress()
    if ids:
        wanted = set(ids)
        batch = [e for e in episodes if episode_id(e) in wanted]
    else:
        batch = next_batch(episodes, state, count)
    WORK.mkdir(parents=True, exist_ok=True)
    for f in WORK.glob("*"):
        f.unlink()
    done = []
    for ep in batch:
        eid = episode_id(ep)
        audio = WORK / f"{eid}.mp3"
        t0 = time.time()
        try:
            with requests.get(ep["audio"], headers=UA, timeout=300, stream=True) as r:
                r.raise_for_status()
                with audio.open("wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
        except Exception as exc:  # a failed download is retried next run
            print(f"{eid}: download failed, retry next run ({exc})", flush=True)
            audio.unlink(missing_ok=True)
            continue
        try:
            text = transcribe(audio, model_name)
        except Exception as exc:  # undecodable audio won't fix itself, so fall back to the show notes
            text, ep["audio_problem"] = "", f"audio could not be decoded ({type(exc).__name__})"
        finally:
            audio.unlink(missing_ok=True)
        if not ep.get("audio_problem") and (problem := audio_problem(text, ep["duration"])):
            ep["audio_problem"] = problem
        if ep.get("audio_problem"):
            print(f"{eid}: AUDIO PROBLEM: {ep['audio_problem']}", flush=True)
        (WORK / f"{eid}.txt").write_text(text + "\n")
        ep["id"] = eid
        ep["transcript"] = f".work/invested/{eid}.txt"
        ep["notes"] = f"knowledge/invested/episodes/{eid}.md"
        done.append(ep)
        print(f"{eid} {ep['title'][:60]}: {len(text.split())} words in {time.time() - t0:.0f}s", flush=True)
    (WORK / "batch.json").write_text(json.dumps({
        "episodes": done,
        "remaining": len([e for e in episodes if episode_id(e) not in set(state["done"])]) - len(done),
        "total": len(episodes),
    }, indent=2))
    return done


def record(ids: list[str] | None = None, total: int | None = None) -> list[str]:
    """Mark episodes done once the Professor has written their notes.

    Without ids, uses this runner's batch.json; with ids (the parallel workflow), checks those."""
    if ids is None:
        batch_file = WORK / "batch.json"
        if not batch_file.exists():
            return []
        batch = json.loads(batch_file.read_text())
        ids, total = [e["id"] for e in batch["episodes"]], batch.get("total")
    state = load_progress()
    added = []
    for eid in ids:
        if (EPISODES / f"{eid}.md").exists() and eid not in state["done"]:
            state["done"].append(eid)
            added.append(eid)
    if added:
        state["total"] = total or state.get("total")
        save_progress(state)
    return added


def _ids(text: str) -> list[str]:
    return [i for i in re.split(r"[,\s]+", text or "") if i]


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--count", type=int, default=6)
    p.add_argument("--model", default="base.en")
    p.add_argument("--ids", default="", help="comma list of episode ids (overrides --count)")
    pl = sub.add_parser("plan")
    pl.add_argument("--count", type=int, default=24)
    pl.add_argument("--shards", type=int, default=4)
    r = sub.add_parser("record")
    r.add_argument("--ids", default="")
    args = ap.parse_args()
    if args.cmd == "prepare":
        batch = prepare(args.count, args.model, _ids(args.ids))
        print(f"prepared {len(batch)} episode(s)")
    elif args.cmd == "plan":
        shards = plan(args.count, args.shards)
        print(json.dumps({"shards": [",".join(s) for s in shards], "ids": ",".join(i for s in shards for i in s)}))
    else:
        ids = _ids(args.ids)
        total = len(fetch_episodes()) if ids else None
        print("recorded:", ", ".join(record(ids or None, total)) or "none")


if __name__ == "__main__":
    main()
