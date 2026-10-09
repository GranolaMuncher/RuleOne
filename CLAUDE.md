# RuleOne: instructions for every Claude session

Start by reading `docs/HANDOFF.md` (the owner's standing rules and how the project fits together) and `knowledge/MAP.md` (how the agents share knowledge).

## Keep a session log and the handoff current (owner's standing request)
The owner wants every chat to be continuable in a new or forked chat **before the context window fills**.
- **Automatic:** before each context compaction, the `PreCompact` hook in `.claude/settings.json` runs `node tools/session_log.mjs`, which writes `.work/session-log/session-log.html`. After compaction a `SessionStart` hook prints `tools/after_compact.md`. Follow it: publish the log as a private artifact (one per session, listed in `docs/SESSIONS.md`), update `docs/HANDOFF.md`, then commit and push.
- **By hand:** also do this when the owner asks, and after any large milestone (a new agent, workflow or page). Run `node tools/session_log.mjs`, then publish and update as above.
- **Never commit the log HTML or raw transcripts.** The repo is public; the log lives only as a private artifact.

## Rules (details in docs/HANDOFF.md)
- Push only to `claude/dazzling-knuth-dmucvz`. Never put model IDs in commits.
- Not investment advice. No options strategies. No private holdings in the repo. No push or email notifications.
- Never commit book text or podcast transcripts.
- Before pushing, run `python -m pytest -q tests`, `actionlint -shellcheck= .github/workflows/*.yml`, and `cd site && npm run build` if `site/` changed.
