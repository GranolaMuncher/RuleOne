#!/usr/bin/env node
// Session log: turns this Claude Code session's transcript into a readable HTML page that a new or
// forked chat can reference. Runs automatically before every context compaction (.claude/settings.json,
// PreCompact hook) and can be run by hand:
//   node tools/session_log.mjs [--transcript path.jsonl] [--out .work/session-log/session-log.html]
// Only your messages and Claude's replies are kept (no tool output); token-like strings are redacted.
// The page is published as a private artifact by Claude (see CLAUDE.md), never committed: the repo is public.
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const arg = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };

let hookInput = {};
if (args.includes("--hook")) { try { hookInput = JSON.parse(fs.readFileSync(0, "utf8") || "{}"); } catch { hookInput = {}; } }

function findTranscript() {
  if (arg("--transcript")) return arg("--transcript");
  if (hookInput.transcript_path) return hookInput.transcript_path;
  const id = hookInput.session_id || process.env.CLAUDE_CODE_SESSION_ID;
  const bases = [path.join(os.homedir(), ".claude", "projects"), "/root/.claude/projects"];
  const all = [];
  for (const b of bases) {
    if (!fs.existsSync(b)) continue;
    for (const d of fs.readdirSync(b)) {
      const dir = path.join(b, d);
      if (!fs.statSync(dir).isDirectory()) continue;
      for (const f of fs.readdirSync(dir)) if (f.endsWith(".jsonl")) all.push(path.join(dir, f));
    }
  }
  const byId = all.find((f) => id && path.basename(f) === `${id}.jsonl`);
  return byId ?? all.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
}

const transcript = findTranscript();
if (!transcript || !fs.existsSync(transcript)) { console.error("session_log: no transcript found"); process.exit(0); }
const OUT = arg("--out") ?? path.join(ROOT, ".work", "session-log", "session-log.html");

// ---- extract the conversation
const SECRET = /(sk-ant-[A-Za-z0-9_\-]{10,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[abp]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})/g;
const redact = (s) => s.replace(SECRET, "[redacted]");
const conv = [];
for (const line of fs.readFileSync(transcript, "utf8").split("\n")) {
  let d; try { d = JSON.parse(line); } catch { continue; }
  if (d.isMeta || d.isSidechain) continue;
  const m = d.message || {}, c = m.content, ts = (d.timestamp || "").slice(0, 16).replace("T", " ");
  if (d.type === "user") {
    let t = typeof c === "string" ? c : Array.isArray(c) ? c.filter((x) => x && x.type === "text").map((x) => x.text).join("\n") : "";
    t = t.trim();
    if (!t || /^<(system-reminder|local-command|command-|task-notification)/.test(t)) continue;
    conv.push([d.isCompactSummary || t.startsWith("This session is being continued") ? "summary" : "user", ts, redact(t)]);
  } else if (d.type === "assistant" && Array.isArray(c)) {
    const t = c.filter((x) => x.type === "text").map((x) => x.text).join("\n").trim();
    if (t) conv.push(["assistant", ts, redact(t)]);
  }
}

// ---- markdown: the site's copy of marked when installed, else a plain fallback
let marked = null;
try { ({ marked } = await import(path.join(ROOT, "site", "node_modules", "marked", "lib", "marked.esm.js"))); } catch { marked = null; }
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const md = (s, user) => marked ? marked.parse(user ? s.replace(/</g, "&lt;") : s, { gfm: true, breaks: !!user })
  : s.split(/\n{2,}/).map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`).join("");

// ---- links
const remote = process.env.CLAUDE_CODE_REMOTE_SESSION_ID || "";
const SESSION = remote ? `https://claude.ai/code/${remote.replace(/^cse_/, "session_")}` : `local session ${path.basename(transcript, ".jsonl")}`;
const sessionsMd = path.join(ROOT, "docs", "SESSIONS.md");
const known = fs.existsSync(sessionsMd) ? fs.readFileSync(sessionsMd, "utf8").split("\n").find((l) => remote && l.includes(remote.replace(/^cse_/, "session_"))) : null;
const ARTIFACT = (known?.match(/https:\/\/claude\.ai\/artifact\/[A-Za-z0-9]+/) || [])[0] ?? "(this page's link)";
const HANDOFF = "docs/HANDOFF.md";
const days = new Map();
let n = 0;
for (const [k, ts, t] of conv) {
  const d = ts.slice(0, 10);
  if (!days.has(d)) days.set(d, []);
  if (k === "user") n++;
  days.get(d).push({ k, ts, t, n });
}
const fmtDay = (d) => new Date(d + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
let body = "";
for (const [d, items] of days) {
  body += `<section class="day" id="d${d}"><h2 class="dayhead"><span>${fmtDay(d)}</span><span class="count">${items.filter((i) => i.k === "user").length} requests</span></h2>`;
  for (const it of items) {
    const time = `<time>${it.ts.slice(11)} UTC</time>`;
    if (it.k === "user") body += `<article class="msg you" id="m${it.n}"><header><span class="who">You</span><span class="num">#${it.n}</span>${time}</header><div class="prose">${md(it.t, true)}</div></article>`;
    else if (it.k === "assistant") body += `<article class="msg claude"><header><span class="who">Claude</span>${time}</header><div class="prose">${md(it.t)}</div></article>`;
    else body += `<details class="summary"><summary><span class="who">Context summary</span> written when the conversation was compacted · ${time}</summary><div class="prose">${md(it.t)}</div></details>`;
  }
  body += `</section>`;
}
const toc = [...days].map(([d, items]) => `<a href="#d${d}">${fmtDay(d).replace(/, \d{4}$/, "")}<span>${items.filter((i) => i.k === "user").length}</span></a>`).join("");
const prompt = `Continue the RuleOne project (GranolaMuncher/RuleOne, branch claude/dazzling-knuth-dmucvz). Read docs/HANDOFF.md first, then knowledge/MAP.md. The full earlier conversation is the "RuleOne Session Log" artifact: $"https://claude.ai/artifact/VM51Nue4ALW6Ehprz1PowN"`;
const html = `<title>RuleOne Session Log</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap">
<style>
/* Layout: a reading column of the conversation with a sticky day index on wide screens. */
:root {
  --bg: #f6f7f5; --panel: #ffffff; --ink: #1c2220; --muted: #5d6763; --line: #dfe3e0;
  --accent: #1f6f5c; --you: #e8f1ed; --code: #eef1ef;
  --display: "IBM Plex Serif", Georgia, serif; --body: "IBM Plex Sans", system-ui, sans-serif; --mono: "IBM Plex Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111513; --panel: #181d1b; --ink: #e4e9e6; --muted: #98a39e; --line: #2a312e; --accent: #5cc0a2; --you: #1b2a25; --code: #1f2523; color-scheme: dark } }
:root[data-theme="dark"] { --bg: #111513; --panel: #181d1b; --ink: #e4e9e6; --muted: #98a39e; --line: #2a312e; --accent: #5cc0a2; --you: #1b2a25; --code: #1f2523; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 15px/1.6 var(--body); }
.wrap { max-width: 1120px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 64px; display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 40px; }
@media (max-width: 820px) { .wrap { grid-template-columns: minmax(0, 1fr); gap: 20px; } nav.toc { position: static !important; flex-direction: row !important; flex-wrap: wrap; } }
nav.toc { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 20px); align-self: start; display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
nav.toc .label { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; width: 100%; }
nav.toc a { color: var(--ink); text-decoration: none; padding: 4px 8px; border-radius: 6px; display: flex; justify-content: space-between; gap: 12px; }
nav.toc a span { color: var(--muted); font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; }
nav.toc a:hover, nav.toc a:focus-visible { background: var(--you); outline: none; }
main { min-width: 0; }
h1 { font: 600 34px/1.15 var(--display); margin: 0 0 6px; text-wrap: balance; }
.lede { color: var(--muted); margin: 0 0 22px; max-width: 65ch; }
.fork { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; display: grid; gap: 10px; margin-bottom: 34px; }
.fork h2 { font: 600 16px/1.3 var(--body); margin: 0; }
.fork p { margin: 0; max-width: 70ch; overflow-wrap: anywhere; }
.fork { min-width: 0; }
.fork .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-start; }
.fork code.p { flex: 1 1 320px; min-width: 0; display: block; background: var(--code); border-radius: 6px; padding: 10px 12px; font: 12.5px/1.5 var(--mono); white-space: pre-wrap; word-break: break-word; }
button { font: 500 13px var(--body); color: var(--accent); background: transparent; border: 1px solid var(--accent); border-radius: 6px; padding: 7px 12px; cursor: pointer; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
a { color: var(--accent); }
.dayhead { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 1; background: var(--bg); display: flex; justify-content: space-between; align-items: baseline; font: 600 20px/1.3 var(--display); padding: 10px 0; margin: 26px 0 8px; border-bottom: 1px solid var(--line); }
.dayhead .count { font: 12px var(--mono); color: var(--muted); }
.msg { padding: 14px 0; display: grid; gap: 4px; }
.msg header { display: flex; gap: 10px; align-items: baseline; font-size: 12px; color: var(--muted); }
.who { font-weight: 600; letter-spacing: .06em; text-transform: uppercase; font-size: 11px; color: var(--ink); }
.num { font-family: var(--mono); }
time { font-family: var(--mono); margin-left: auto; }
.msg.you { background: var(--you); border-radius: 10px; padding: 12px 16px; margin: 10px 0; }
.msg.you .who { color: var(--accent); }
.prose { min-width: 0; max-width: 72ch; overflow-wrap: anywhere; }
.prose > :first-child { margin-top: 0; } .prose > :last-child { margin-bottom: 0; }
.prose h1, .prose h2, .prose h3 { font: 600 16px/1.35 var(--body); margin: 16px 0 6px; }
.prose ul, .prose ol { padding-left: 22px; }
.prose code { font: 0.9em var(--mono); background: var(--code); border-radius: 4px; padding: 1px 4px; }
.prose pre { background: var(--code); border-radius: 8px; padding: 10px 12px; overflow-x: auto; }
.prose pre code { background: none; padding: 0; }
.prose table { border-collapse: collapse; font-size: 13.5px; display: block; overflow-x: auto; max-width: 100%; }
.prose th, .prose td { border-bottom: 1px solid var(--line); padding: 5px 10px 5px 0; text-align: left; vertical-align: top; }
.summary { border: 1px dashed var(--line); border-radius: 10px; padding: 10px 14px; margin: 12px 0; font-size: 13.5px; }
.summary summary { cursor: pointer; color: var(--muted); }
.summary .prose { margin-top: 10px; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
</style>
<div class="wrap">
  <nav class="toc" aria-label="Days"><div class="label">Days</div>${toc}</nav>
  <main>
    <h1>RuleOne Session Log</h1>
    <p class="lede">The full conversation that built RuleOne: the Rule #1 screener, the site at ruleone.pages.dev and the agent stack (Professor, Radar, RULERS, Editor, Engineer, analyst consensus). Your ${n} requests and Claude's replies, in order. Tool output is left out. The two context summaries hold the key technical details.</p>
    <section class="fork" aria-labelledby="forkh">
      <h2 id="forkh">Starting a forked chat</h2>
      <p>Paste this into the new session. It points the new chat at the handoff file in the repo, which a new session can read directly, and at this log.</p>
      <div class="row"><code class="p" id="prompt">${esc(prompt)}</code><button type="button" id="copy">Copy</button></div>
      <p class="small">Handoff file: <code>${HANDOFF}</code> in the repo · Original session: ${SESSION.startsWith("https") ? `<a href="${SESSION}">${SESSION.replace("https://", "")}</a>` : esc(SESSION)} · Log updated ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC</p>
    </section>
    ${body}
  </main>
</div>
<script>
document.getElementById("copy").addEventListener("click", (e) => {
  const el = document.getElementById("prompt"), b = e.currentTarget;
  navigator.clipboard.writeText(el.textContent).then(() => { b.textContent = "Copied"; }, () => {
    const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = "Selected: press Ctrl+C";
  });
});
</script>`;
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, html);
console.log(`session_log: ${n} requests, ${conv.length} messages -> ${path.relative(ROOT, OUT)} (${Math.round(html.length / 1024)} KB)`);
