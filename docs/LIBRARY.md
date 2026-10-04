# Getting *The Intelligent Investor* into the Professor, without its text in the repo

*The Intelligent Investor* (Graham, 1949; revised 1973; Zweig commentary 2003) is still under copyright. Works first published in 1930 or earlier are in the US public domain as of 2026, and this book isn't. The repo and site are public. So the rule is: **the book's text lives somewhere private, and only the Professor's own-words notes (with very short quotes and chapter citations) go in `knowledge/intelligent_investor/`.**

The options below run from fastest to most faithful. They can be combined.

| # | Option | What you do | What the agent does | Fidelity | Time to useful |
|---|---|---|---|---|---|
| A | **Study guide from the model's own knowledge** | Nothing | Writes chapter-by-chapter notes on Graham's ideas (Mr. Market, margin of safety, defensive vs enterprising investor, the 7 defensive criteria, net-nets, investor vs speculator), each clearly labelled "from general knowledge, verify against your copy" | Medium. Good on the big ideas, weak on exact wording and figures | One run |
| B | **Kindle or e-reader highlights** | Export your highlights (Kindle: `My Clippings.txt`, or the notebook export at read.amazon.com) to a **private** repo | Turns each highlight into notes by chapter, linking them to Rule #1 and to the RuleOne screen | High for what *you* found important | As soon as you've read |
| C | **Your own copy, read privately** (recommended for completeness) | Put your purchased, DRM-free ebook (or your own scans or photos run through OCR) in a **private** GitHub repo, e.g. `ruleone-library` | A workflow checks out the private repo with a read-only token. The Professor reads one or two chapters per run and writes notes in its own words, with at most two short quotes per chapter, and a combined Graham + Town + Buffett checklist. The text never touches the public repo | Highest | About a week (20 chapters + postscript, 2 per run) |
| D | **Read it yourself, talk to the Professor** | Record voice memos after each chapter (phone) into the private repo, or a Drive folder | Transcribes them with the same Whisper step as the podcast, then writes structured notes and quiz questions from **your** understanding, flagging anything that conflicts with Graham | Personal; best for learning | At your reading pace |
| E | **Graham's public material** | Nothing | Studies sources anyone can read for free (below) and writes notes cross-referenced to the book's chapters | High for Graham's core ideas; not the book itself | One or two runs |

**Free and public sources for option E:**
- Graham's 1955 testimony to the Senate Banking and Currency Committee ("Stock Market Study"). It's a US government record, so it's public domain, and it covers Mr. Market-style speculation and value in Graham's own words.
- *A Conversation with Benjamin Graham*, Financial Analysts Journal (1976). His late-career view, including the simple screens he favoured.
- Buffett, *The Superinvestors of Graham-and-Doddsville* (Hermes, Columbia Business School, 1984), widely reprinted online.
- Berkshire Hathaway shareholder letters, 1977 onward (free at berkshirehathaway.com). Graham's ideas run throughout, especially Mr. Market (1987) and margin of safety.
- *Security Analysis* (1934 first edition) enters the US public domain on 1 Jan 2030. The Professor can ingest it in full then.

## Chosen path: you read your own copy and record it (built)

You own the revised edition (2006). For each chapter, record yourself reading it aloud, record your own takeaways afterwards, or do both. The Professor writes study notes from the recordings. If you include takeaways, it also checks your understanding against Graham's argument. Until a chapter is recorded, its page on **Learn → The Intelligent Investor** shows a short "what to listen for" preview from general knowledge.

**One-time setup (about 10 minutes):**
1. On GitHub, go to **New repository**, name it `ruleone-library` and choose **Private**. Tick *Add a README* so it isn't empty.
2. Create a token at **Settings → Developer settings → Fine-grained tokens → Generate new token**:
   - Repository access: *Only select repositories* → `ruleone-library`.
   - Permissions: **Contents: Read-only**.
   - Expiry: up to a year (you'll renew it then).
3. In **RuleOne → Settings → Secrets and variables → Actions**:
   - Secret `LIBRARY_TOKEN` = the token.
   - Variable `LIBRARY_REPO` = `granolamuncher/ruleone-library`.

**Each chapter:**
1. Record it on your phone (Voice Memos or any recorder; m4a, mp3 and wav all work). Name the file by chapter:
   - `ch08.m4a`, or for several parts `ch08-part1.m4a`, `ch08-part2.m4a`, `ch08-commentary.m4a`.
   - Use `intro` and `postscript` for those sections.
   - A typed memo works too: `ch08.txt`.
2. In `ruleone-library`, open **Add file → Upload files** (this works from a phone browser) and drop the files in. No folder is needed. GitHub's web upload limit is 25 MB per file, which is about 45–60 minutes of voice memo. Split longer chapters into parts.
3. Notes appear by the next morning ([`professor-book.yml`](../.github/workflows/professor-book.yml) runs daily at 03:23 UTC). For notes sooner, go to **Actions → Professor (The Intelligent Investor) → Run workflow**. Adding another part later updates that chapter's notes.

Your recordings and their transcripts stay in the private repo and on the temporary runner. They are never committed to the public repo.

## Other options (if you change your mind)

Start **A + E now**. They need nothing from you and give a cited Graham module within a day. Then add **C** (or **B** if you'd rather only use what you highlighted) to replace the general-knowledge notes with chapter-accurate ones. **D** is optional, but it's the best way to really *learn* the book rather than just have it summarised.

## What setting up C involves (about 10 minutes)

1. Create a **private** repository, e.g. `granolamuncher/ruleone-library`, and upload the book file (EPUB, PDF or text) under `intelligent-investor/`.
2. Create a fine-grained GitHub token with **read-only Contents** access to that one repo. Save it in RuleOne as the secret `LIBRARY_TOKEN`, and set the variable `LIBRARY_REPO=granolamuncher/ruleone-library`.
3. Claude adds a `book` mode to the Professor workflow:
   - It checks out the private repo into `.work/library/`, which is git-ignored and never committed.
   - It converts the book to plain text per chapter (`ebooklib`/`pdftotext`).
   - It processes the next unread chapter and records progress in `knowledge/intelligent_investor/progress.json`.
   - The notes appear on the site under **Learn → The Intelligent Investor**, in the same format as the podcast notes: key ideas, a RuleOne mapping, an exercise and a quiz.

Nothing in this setup makes the book itself public. The only things published are the Professor's notes.
