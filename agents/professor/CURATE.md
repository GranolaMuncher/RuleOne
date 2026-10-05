# Professor: fold new episode notes into the course

Parallel runners have just written study notes for the InvestED episodes listed in `.work/invested/new.txt` (one id per line, in episode order). Their notes are in `knowledge/invested/episodes/<id>.md`. You don't have transcripts. Work only from the notes.

1. Read `knowledge/invested/course.json` and every new note, in order.
2. **Check each note's format** against `episodes/001.md`. Fix only clear problems: a missing front-matter field, a `module` id that doesn't exist in course.json, or a quote longer than 25 words (shorten it). Don't rewrite notes otherwise.
3. **Update `course.json`**, following step 4 of `agents/professor/PROMPT.md`:
   - Append each id to its module's `episodes` in numeric order, without duplicates.
   - Revise each touched module's `lesson` (at most ~250 words; a tight numbered synthesis of everything taught so far; note where later episodes refine or contradict earlier ones).
   - Add glossary terms (at most 3 per episode) and append episode ids to existing terms.
   - Set `updated` to today's date.
4. Don't edit `progress.json` or any transcript.

Finish with a short summary: the episodes added, the modules revised and the single most useful new idea.
