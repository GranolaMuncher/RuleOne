# Professor: fold new episode notes into the course

> **Shared knowledge:** read `knowledge/MAP.md` first. It shows what every other agent writes and where. The Rule #1 method (`knowledge/rule1/METHOD.md`), the markers (`MARKERS.md`) and the lessons (`LESSONS.md`) apply to every decision you make.

`.work/invested/new.txt` lists InvestED episodes (one id per line, in episode order) whose notes are not yet part of the course: this run's new notes, plus any an earlier run failed to curate. If the list is long, work through it in order, saving `course.json` after every few episodes, so progress isn't lost if you run out of turns. Their notes are in `knowledge/invested/episodes/<id>.md`. You don't have transcripts. Work only from the notes.

1. Read `knowledge/invested/course.json` and every new note, in order.
2. **Check each note's format** against `episodes/001.md`. Fix only clear problems: a missing front-matter field, a `module` id that doesn't exist in course.json, or a quote longer than 25 words (shorten it). Don't rewrite notes otherwise.
3. **Update `course.json`**, following step 4 of `agents/professor/PROMPT.md`:
   - Append each id to its module's `episodes` in numeric order, without duplicates.
   - Revise each touched module's `lesson` (at most ~250 words; a tight numbered synthesis of everything taught so far; note where later episodes refine or contradict earlier ones).
   - Add glossary terms (at most 3 per episode) and append episode ids to existing terms.
   - Set `updated` to today's date (`date -u +%F`).
   - Keep `course.json` valid JSON. Check it with `python3 -m json.tool knowledge/invested/course.json > /dev/null` after editing.
4. **Keep the method current.** New episodes are the main source of new rules: check each new note against `METHOD.md` and `MARKERS.md`. If a new episode adds or refines a rule (a new test, a changed threshold, a later version of an earlier rule), update `knowledge/rule1/METHOD.md` and `knowledge/rule1/CHECKLIST.md`: edit the rule in place, cite the episode, and say "refined in [NNN]". Never paste transcript text. If the change affects what the screener computes, add a line under `## Proposed app changes` at the end of METHOD.md, so the Engineer (or the owner) can implement it.
5. Don't edit `progress.json` or any transcript.

Finish with a short summary: the episodes added, the modules revised and the single most useful new idea.
