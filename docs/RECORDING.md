# How to record *The Intelligent Investor* (quick reference)

Setup is done: the `ruleone-library` private repo exists, and RuleOne has the `LIBRARY_TOKEN` secret and `LIBRARY_REPO` variable (tested 2026-10-04).

## Each chapter
1. **Read and record** on your phone. Read the chapter aloud, or record your own takeaways afterwards (2–5 min), or both. Zweig's commentary can be part of the same recording or a separate one.
2. **Name the recording** after the chapter: in Voice Memos, tap the title and rename it.
   - `intro`, `ch01` … `ch20`, `postscript`
   - several parts: `ch08-part1`, `ch08-part2`, `ch08-commentary`
   - a typed memo works too: `ch08.txt`
3. **Save it to Files:** in Voice Memos tap **⋯ → Save to Files**.
4. **Upload it:** open **github.com/GranolaMuncher/ruleone-library** in Safari or Chrome (not the GitHub app).
   - First upload (empty repo): tap **"uploading an existing file"**.
   - After that: **Add file → Upload files**.
   - Pick the recording, then tap **Commit changes**.
   - The limit is 25 MB per file (about 45–60 min). Split longer chapters into parts.
5. **Wait, or run it now.** Notes appear on **Learn → The Intelligent Investor** by the next morning (daily run at 03:23 UTC). For notes sooner: **RuleOne → Actions → Professor (The Intelligent Investor) → Run workflow**. It takes about 5–10 minutes, and the chapter's label changes from *preview* to *notes*.

Adding another part later updates that chapter's notes. Recordings and transcripts never go into the public repo; only the Professor's notes do.

**If it stops working:** the access key (`LIBRARY_TOKEN`) has probably expired. Make a new fine-grained token with *Contents: Read-only* on `ruleone-library`, then paste it into **RuleOne → Settings → Secrets and variables → Actions → LIBRARY_TOKEN → Update**.
