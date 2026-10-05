from ruleone.podcast import episode_id, next_batch, parse_feed

FEED = """<?xml version="1.0"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
<item><title>2- Part Two</title><pubDate>Wed, 17 Jun 2015 10:00:00 -0000</pubDate><itunes:duration>2737</itunes:duration>
<enclosure url="https://x/2.mp3"/><description><![CDATA[<p>Notes &amp; links</p>]]></description></item>
<item><title>00- Welcome</title><pubDate>Wed, 17 Jun 2015 09:00:00 -0000</pubDate><itunes:duration>17:43</itunes:duration>
<enclosure url="https://x/0.mp3"/></item>
<item><title>Bonus trailer</title><pubDate>Mon, 01 Jun 2015 09:00:00 -0000</pubDate><enclosure url="https://x/t.mp3"/></item>
<item><title>1- Part One</title><pubDate>Wed, 17 Jun 2015 09:30:00 -0000</pubDate><enclosure url="https://x/1.mp3"/></item>
</channel></rss>"""


def test_parse_feed_orders_by_episode_number():
    eps = parse_feed(FEED)
    assert [episode_id(e) for e in eps] == ["000", "001", "002", "x20150601"]
    assert eps[0]["duration"] == 17 * 60 + 43 and eps[2]["duration"] == 2737
    assert eps[2]["title"] == "Part Two" and eps[2]["show_notes"] == "Notes & links"


def test_next_batch_skips_done_and_skipped():
    eps = parse_feed(FEED)
    state = {"done": ["000"], "skipped": {"001": "broken audio"}}
    assert [episode_id(e) for e in next_batch(eps, state, 2)] == ["002", "x20150601"]


def test_audio_problem_flags_silent_or_truncated_audio():
    from ruleone.podcast import audio_problem
    normal = " ".join(f"[{m:02d}:00] " + "word " * 150 for m in range(40))
    assert audio_problem(normal, 40 * 60) is None
    assert "only" in audio_problem("hello there", 40 * 60)
    cut = " ".join(f"[{m:02d}:00] " + "word " * 300 for m in range(10))  # plenty of words, stops at 9 min
    assert "stops" in audio_problem(cut, 40 * 60)
    assert audio_problem("Happy holidays everyone", 78) is None
