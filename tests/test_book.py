from pathlib import Path

from ruleone import book


def test_chapter_key_accepts_common_names():
    assert book.chapter_key("ch8.m4a") == "ch08"
    assert book.chapter_key("Chapter 08 - part 2.mp3") == "ch08"
    assert book.chapter_key("ch20-commentary.m4a") == "ch20"
    assert book.chapter_key("Intro.txt") == "intro"
    assert book.chapter_key("postscript.wav") == "postscript"
    assert book.chapter_key("ch21.m4a") is None
    assert book.chapter_key("notes.m4a") is None


def test_pending_tracks_new_and_changed_recordings(tmp_path: Path):
    lib = tmp_path / "intelligent-investor"
    lib.mkdir()
    (lib / "ch08.txt").write_text("Mr. Market")
    (lib / "intro.txt").write_text("hello")
    (lib / "readme.md").write_text("ignored")
    found = book.scan(lib)
    assert set(found) == {"intro", "ch08"}
    state = {"chapters": {"intro": {"files": book.fingerprint(found["intro"])}}}
    assert book.pending(found, state) == ["ch08"]
    (lib / "intro-part2.txt").write_text("more")
    assert book.pending(book.scan(lib), state) == ["intro", "ch08"]
