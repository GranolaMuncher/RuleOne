// Build-time data access: reads the screener's CSV/JSON output and the
// markdown reports straight from the repository (no runtime API).
import fs from "node:fs";
import path from "node:path";

const ROOT = process.env.REPO_ROOT ?? path.resolve(process.cwd(), "..");
const LISTS = path.join(ROOT, "lists");
const REPORTS = path.join(ROOT, "reports");

export type Row = Record<string, string>;

export interface Stock {
  ticker: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  status: string;
  tier: string;
  price: number | null;
  priceDate: string;
  marketCap: number | null;
  sticker: number | null;
  mos: number | null;
  payback: number | null;
  tenCap: number | null;
  priceToSticker: number | null;
  buySignals: string;
  growth: number | null;
  futurePe: number | null;
  histPe: number | null;
  pe: number | null;
  eps: number | null;
  fcfYield: number | null;
  divYield: number | null;
  divGrowth5y: number | null;
  tr10y: number | null;
  debtPayoff: number | null;
  big5Score: number | null;
  big5Tests: string;
  roic10: number | null;
  roic5: number | null;
  roic1: number | null;
  growthTable: Record<string, (number | null)[]>;
  drawdown: number | null;
  chg1m: number | null;
  eventScore: number | null;
  events: string;
  nextReport: string;
  flags: string;
  rank: number | null;
}

/** RFC-4180-ish CSV parser (quoted fields, embedded commas/quotes/newlines). */
export function parseCsv(text: string): Row[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') inQuotes = false;
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  const [head, ...body] = rows.filter((r) => r.length > 1 || r[0]);
  if (!head) return [];
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

const num = (v: string | undefined): number | null => {
  if (v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export function toStock(r: Row): Stock {
  const g = (k: string) => [num(r[`${k}_g10`]), num(r[`${k}_g5`]), num(r[`${k}_g1`])];
  return {
    ticker: r.ticker,
    name: r.name,
    exchange: r.exchange,
    sector: r.sector,
    industry: r.industry ?? "",
    status: r.status,
    tier: r.tier,
    price: num(r.price),
    priceDate: r.price_date,
    marketCap: num(r.market_cap),
    sticker: num(r.sticker),
    mos: num(r.mos_price),
    payback: num(r.payback_price),
    tenCap: num(r.ten_cap_price),
    priceToSticker: num(r.price_to_sticker),
    buySignals: r.buy_signals,
    growth: num(r.windage_growth),
    futurePe: num(r.future_pe),
    histPe: num(r.hist_pe_median ?? r.hist_pe_avg),
    pe: num(r.pe_ttm),
    eps: num(r.eps_ttm),
    fcfYield: num(r.fcf_yield),
    divYield: num(r.div_yield),
    divGrowth5y: num(r.div_growth_5y),
    tr10y: num(r.tr_10y),
    debtPayoff: num(r.debt_payoff_years),
    big5Score: num(r.big5_score),
    big5Tests: r.big5_tests,
    roic10: num(r.roic10),
    roic5: num(r.roic5),
    roic1: num(r.roic1),
    growthTable: { Sales: g("sales"), EPS: g("eps"), BVPS: g("bvps"), OCF: g("ocf") },
    drawdown: num(r.drawdown_52w),
    chg1m: num(r.chg_1m),
    eventScore: num(r.event_score),
    events: r.events,
    nextReport: r.next_report_est,
    flags: r.flags ?? "",
    rank: num(r.rank_score),
  };
}

const readCsv = (file: string): Row[] => (fs.existsSync(file) ? parseCsv(fs.readFileSync(file, "utf8")) : []);

export const LIST_KEYS = [
  "buy_range",
  "buy_range_alt_methods",
  "on_deck",
  "event_watch",
  "wonderful_companies",
  "all_candidates",
] as const;
export type ListKey = (typeof LIST_KEYS)[number];

export function loadRun(dir = path.join(LISTS, "latest")) {
  const lists = Object.fromEntries(
    LIST_KEYS.map((k) => [k, readCsv(path.join(dir, `${k}.csv`)).map(toStock)]),
  ) as Record<ListKey, Stock[]>;
  const metaFile = path.join(dir, "meta.json");
  const meta = fs.existsSync(metaFile) ? JSON.parse(fs.readFileSync(metaFile, "utf8")) : {};
  return { lists, meta };
}

export function archiveDates(): string[] {
  const dir = path.join(LISTS, "archive");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d))
    .sort()
    .reverse();
}

export const archiveDir = (date: string) => path.join(LISTS, "archive", date);

export interface HistoryPoint {
  date: string;
  status: string;
  price: number | null;
  sticker: number | null;
  mos: number | null;
}

/** history.csv rows grouped by ticker, one point per run date (last write wins). */
export function loadHistory(): Map<string, HistoryPoint[]> {
  const out = new Map<string, Map<string, HistoryPoint>>();
  for (const r of readCsv(path.join(LISTS, "history.csv"))) {
    const m = out.get(r.ticker) ?? new Map();
    m.set(r.run_date, {
      date: r.run_date,
      status: r.status,
      price: num(r.price),
      sticker: num(r.sticker),
      mos: num(r.mos_price),
    });
    out.set(r.ticker, m);
  }
  return new Map([...out].map(([t, m]) => [t, [...m.values()].sort((a, b) => a.date.localeCompare(b.date))]));
}

export interface Report {
  slug: string;
  title: string;
  kind: "deep-dive" | "weekly" | "model";
  date: string;
  body: string;
  tickers: string[];
}

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : e.name.endsWith(".md") ? [p] : [];
  });
}

export function loadReports(): Report[] {
  return walk(REPORTS)
    .map((file) => {
      const rel = path.relative(REPORTS, file).replace(/\\/g, "/");
      const body = fs.readFileSync(file, "utf8");
      const slug = rel.replace(/\.md$/, "");
      const kind: Report["kind"] = rel.startsWith("weekly/") ? "weekly" : rel.startsWith("model/") ? "model" : "deep-dive";
      const heading = body.match(/^#{1,3}\s+(.+)$/m)?.[1] ?? slug;
      const date = rel.match(/(\d{4}-\d{2}-\d{2})/)?.[1] ?? "";
      const tickers = [...new Set([...body.matchAll(/\b(?:NYSE|Nasdaq|NASDAQ)[:]\s*([A-Z.-]{1,6})\b|\(([A-Z]{1,5})\)/g)]
        .map((m) => m[1] ?? m[2]))];
      return { slug, title: heading.replace(/[*_`]/g, ""), kind, date, body, tickers };
    })
    .sort((a, b) => b.date.localeCompare(a.date) || a.slug.localeCompare(b.slug));
}

/** Rewrite links between markdown files (e.g. ../lists/latest/README.md) to site routes. */
export function rewriteLinks(html: string, slug: string): string {
  const base = slug.split("/").slice(0, -1);
  return html.replace(/href="([^"#:]+?)\.md(#[^"]*)?"/g, (_m, target: string, hash = "") => {
    const parts = [...base];
    for (const seg of target.split("/")) {
      if (seg === "..") parts.pop();
      else if (seg !== ".") parts.push(seg);
    }
    const joined = parts.join("/");
    if (joined.startsWith("../lists") || joined.startsWith("lists")) return `href="/"`;
    const dossier = joined.match(/(?:^|\/)research\/rulers\/([A-Z0-9.-]+)$/);
    if (dossier) return `href="/rulers/${dossier[1]}/${hash}"`;
    const radar = joined.match(/(?:^|\/)research\/radar\/(\d{4}-\d{2}-\d{2})$/);
    if (radar) return `href="/radar/${radar[1]}/${hash}"`;
    if (/(?:^|\/)knowledge\/rule1\/(METHOD|CHECKLIST)$/.test(joined)) return `href="/rule1/${hash}"`;
    return `href="/reports/${joined}/${hash}"`;
  });
}

// ---------------------------------------------------------------- all stocks
export interface UniverseRow {
  ticker: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  detail: string; // "ttm" = detailed stage-2 analysis, "fy" = last-fiscal-year screen
  status: string;
  tier: string;
  qualityPass: boolean;
  price: number | null;
  priceDate: string;
  marketCap: number | null;
  chg: { w1: number | null; m1: number | null; m3: number | null; m6: number | null; ytd: number | null; y1: number | null };
  offHigh: number | null;
  aboveLow: number | null;
  high52: number | null;
  low52: number | null;
  eps: number | null;
  epsBasis: string;
  pe: number | null;
  histPe: number | null;
  growth: number | null;
  sticker: number | null;
  mos: number | null;
  priceToSticker: number | null;
  payback: number | null;
  tenCap: number | null;
  methodsAgree: number;
  markerScore: number | null;
  markers: { key: string; pass: boolean | null }[];
  fcfYield: number | null;
  divTtm: number | null;
  divYield: number | null;
  divGrowth5y: number | null;
  tr5y: number | null;
  tr10y: number | null;
  big5Score: number | null;
  big5Tests: string;
  roic: (number | null)[];
  growthTable: Record<string, (number | null)[]>;
  revenue: number | null;
  netIncome: number | null;
  debtPayoff: number | null;
  fy: string;
  events: string;
  flags: string;
  spark: number[];
}

export function toUniverseRow(r: Row): UniverseRow {
  const g = (k: string) => [num(r[`${k}_g10`]), num(r[`${k}_g5`]), num(r[`${k}_g1`])];
  const px = num(r.price);
  // How many of the three Rule #1 prices the stock is under (computed here too for older runs).
  const agree = num(r.methods_agree) ?? (px == null ? 0 :
    [num(r.mos_price), num(r.payback_price), num(r.ten_cap_price)].filter((v) => v != null && px <= v).length);
  return {
    methodsAgree: agree,
    markerScore: num(r.marker_score),
    markers: (r.markers || "").split("|").filter(Boolean).map((kv) => {
      const [key, v] = kv.split("=");
      return { key, pass: v === "1" ? true : v === "0" ? false : null };
    }),
    ticker: r.ticker, name: r.name, exchange: r.exchange, sector: r.sector, industry: r.industry ?? "", detail: r.detail,
    status: r.status, tier: r.tier, qualityPass: r.quality_pass === "yes",
    price: num(r.price), priceDate: r.price_date, marketCap: num(r.market_cap),
    chg: { w1: num(r.chg_1w), m1: num(r.chg_1m), m3: num(r.chg_3m), m6: num(r.chg_6m), ytd: num(r.chg_ytd), y1: num(r.chg_1y) },
    offHigh: num(r.off_high), aboveLow: num(r.above_low), high52: num(r.high52), low52: num(r.low52),
    eps: num(r.eps), epsBasis: r.eps_basis, pe: num(r.pe), histPe: num(r.hist_pe_median), growth: num(r.windage_growth),
    sticker: num(r.sticker), mos: num(r.mos_price), priceToSticker: num(r.price_to_sticker),
    payback: num(r.payback_price), tenCap: num(r.ten_cap_price), fcfYield: num(r.fcf_yield),
    divTtm: num(r.div_ttm), divYield: num(r.div_yield), divGrowth5y: num(r.div_growth_5y), tr5y: num(r.tr_5y), tr10y: num(r.tr_10y),
    big5Score: num(r.big5_score), big5Tests: r.big5_tests,
    roic: [num(r.roic10), num(r.roic5), num(r.roic1)],
    growthTable: { Sales: g("sales"), EPS: g("eps"), BVPS: g("bvps"), OCF: g("ocf") },
    revenue: num(r.revenue), netIncome: num(r.net_income), debtPayoff: num(r.debt_payoff_years),
    fy: r.fy_end || r.fy, events: r.events, flags: r.flags ?? "",
    spark: (r.spark_1y || "").split(" ").filter(Boolean).map(Number),
  };
}

let _universe: UniverseRow[] | null = null;
export function loadUniverse(): UniverseRow[] {
  if (!_universe) _universe = readCsv(path.join(LISTS, "latest", "universe.csv")).map(toUniverseRow);
  return _universe;
}

/** {ticker: [{date, price, sticker, mos, status}]} from each run's compact snapshot. */
export function loadSnapshots(): Map<string, { date: string; price: number | null; sticker: number | null; mos: number | null; status: string }[]> {
  const out = new Map<string, { date: string; price: number | null; sticker: number | null; mos: number | null; status: string }[]>();
  for (const date of archiveDates().slice().reverse()) {
    for (const r of readCsv(path.join(archiveDir(date), "universe_snapshot.csv"))) {
      const list = out.get(r.ticker) ?? [];
      list.push({ date, price: num(r.price), sticker: num(r.sticker), mos: num(r.mos_price), status: r.status });
      out.set(r.ticker, list);
    }
  }
  return out;
}

// ---------------------------------------------------------------- price history
export interface PriceSeries { dates: string[]; closes: number[]; adj?: number[] }

function monthAdd(ym: string, n: number): string {
  const [y, m] = ym.split("-").map(Number);
  const t = y * 12 + (m - 1) + n;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, "0")}`;
}

let _monthly: Map<string, PriceSeries> | null = null;
/** 10-year monthly closes per ticker; the final point is the live quote. */
export function loadMonthly(): Map<string, PriceSeries> {
  if (_monthly) return _monthly;
  _monthly = new Map();
  for (const r of readCsv(path.join(LISTS, "latest", "prices_monthly.csv"))) {
    const closes = r.closes.split(" ").map(Number);
    const months = r.start.includes(" ")
      ? r.start.split(" ")
      : Array.from({ length: closes.length - 1 }, (_, i) => monthAdd(r.start, i));
    const adj = r.adj ? r.adj.split(" ").map(Number) : undefined;
    _monthly.set(r.ticker, { dates: [...months.map((m) => `${m}-01`), r.live], closes, adj: adj?.length === closes.length ? adj : undefined });
  }
  return _monthly;
}

// ---------------------------------------------------------------- learn (InvestED course)
const KNOW = path.join(ROOT, "knowledge", "invested");

export interface Module { id: string; title: string; goal: string; lesson: string; episodes: string[] }
export interface Course {
  title: string; source: string; updated: string; modules: Module[];
  glossary: { term: string; definition: string; episodes: string[] }[];
}
export interface Episode {
  id: string; number: number; title: string; date: string; minutes: number | null;
  guests: string[]; module: string; concepts: string[]; rulers: string[]; body: string; audio: string;
}

export function loadCourse(): Course | null {
  const f = path.join(KNOW, "course.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

export function loadProgress(): { done: string[]; total: number | null; updated: string } {
  const f = path.join(KNOW, "progress.json");
  if (!fs.existsSync(f)) return { done: [], total: null, updated: "" };
  const p = JSON.parse(fs.readFileSync(f, "utf8"));
  return { done: p.done ?? [], total: p.total ?? null, updated: p.updated ?? "" };
}

/** Minimal front-matter reader for the Professor's notes (scalars and [a, b] lists only). */
function frontMatter(text: string): [Record<string, string | string[]>, string] {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return [{}, text];
  const meta: Record<string, string | string[]> = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (!kv) continue;
    const v = kv[2].trim();
    meta[kv[1]] = v.startsWith("[")
      ? v.slice(1, -1).split(",").map((s) => s.trim().replace(/^["']|["']$/g, "")).filter(Boolean)
      : v.replace(/^["']|["']$/g, "");
  }
  return [meta, text.slice(m[0].length)];
}

export function loadEpisodes(): Episode[] {
  const dir = path.join(KNOW, "episodes");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".md")).sort().map((f) => {
    const [meta, body] = frontMatter(fs.readFileSync(path.join(dir, f), "utf8"));
    const s = (k: string) => (typeof meta[k] === "string" ? (meta[k] as string) : "");
    const l = (k: string) => (Array.isArray(meta[k]) ? (meta[k] as string[]) : []);
    const id = f.replace(/\.md$/, "");
    return {
      id, number: Number(s("episode") || id), title: s("title") || id, date: s("date"),
      minutes: s("minutes") ? Number(s("minutes")) : null, guests: l("guests"), module: s("module"),
      concepts: l("concepts"), rulers: l("rulers"), body: body.replace(/^#\s+.*\n/, ""), audio: s("audio"),
    };
  });
}

// ---------------------------------------------------------------- learn (The Intelligent Investor)
export interface BookChapter {
  key: string; title: string; status: "preview" | "notes"; sources: string[];
  concepts: string[]; rulers: string[]; body: string;
}

export function loadBook(): BookChapter[] {
  const dir = path.join(ROOT, "knowledge", "intelligent_investor", "chapters");
  if (!fs.existsSync(dir)) return [];
  const rank = (k: string) => (k === "intro" ? -1 : k === "postscript" ? 99 : Number(k.slice(2)));
  return fs.readdirSync(dir).filter((f) => f.endsWith(".md")).map((f) => {
    const [meta, body] = frontMatter(fs.readFileSync(path.join(dir, f), "utf8"));
    const l = (k: string) => (Array.isArray(meta[k]) ? (meta[k] as string[]) : []);
    const key = f.replace(/\.md$/, "");
    return {
      key, title: String(meta.title ?? key), status: meta.status === "notes" ? "notes" : "preview",
      sources: l("sources"), concepts: l("concepts"), rulers: l("rulers"), body: body.replace(/^#\s+.*\n/, ""),
    } as BookChapter;
  }).sort((a, b) => rank(a.key) - rank(b.key));
}

/** Glossary/source ids: "001" is a podcast episode, "ii-ch08" a book chapter. */
export const learnHref = (id: string) => (id.startsWith("ii-") ? `/learn/graham/${id.slice(3)}/` : `/learn/${id}/`);
export const chapterLabel = (k: string) => (k === "intro" ? "Introduction" : k === "postscript" ? "Postscript" : `Chapter ${Number(k.slice(2))}`);

// ---------------------------------------------------------------- radar + gurus
const RADAR = path.join(ROOT, "research", "radar");
export interface RadarItem { ticker: string; verdict: string; headline: string; why: string; sources: string[]; date?: string }
export interface GuruPos { guru: string; ticker: string; issuer: string; weight: number; change: string; report: string; filed?: string }
export interface RadarData {
  latest: { date: string; summary: string; items: RadarItem[]; guru_moves: GuruPos[] } | null;
  history: Record<string, RadarItem[]>;
  digests: { date: string; body: string }[];
}

export function loadRadar(): RadarData {
  const read = (f: string) => (fs.existsSync(path.join(RADAR, f)) ? JSON.parse(fs.readFileSync(path.join(RADAR, f), "utf8")) : null);
  const digests = fs.existsSync(RADAR)
    ? fs.readdirSync(RADAR).filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f)).sort().reverse()
        .map((f) => ({ date: f.slice(0, 10), body: fs.readFileSync(path.join(RADAR, f), "utf8") }))
    : [];
  return { latest: read("latest.json"), history: read("history.json") ?? {}, digests };
}

export function loadGurus(): { as_of: Record<string, string>; by_ticker: Record<string, GuruPos[]>; moves: GuruPos[] } {
  const f = path.join(LISTS, "latest", "gurus.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : { as_of: {}, by_ticker: {}, moves: [] };
}

export function loadMethodDocs(): { method: string; checklist: string; markers: string; lessons: string; map: string } {
  const d = path.join(ROOT, "knowledge", "rule1");
  const r = (f: string) => (fs.existsSync(path.join(d, f)) ? fs.readFileSync(path.join(d, f), "utf8") : "");
  const mapF = path.join(ROOT, "knowledge", "MAP.md");
  return { method: r("METHOD.md"), checklist: r("CHECKLIST.md"), markers: r("MARKERS.md"), lessons: r("LESSONS.md"),
    map: fs.existsSync(mapF) ? fs.readFileSync(mapF, "utf8") : "" };
}

export const MARKER_LABELS: Record<string, string> = {
  roic_consistent: "ROIC ≥10% in 8 of 10 years", roic_not_falling: "ROIC not falling",
  growth_coherent: "Sales, profit and cash flow growing together", margin_stable: "Stable margins (pricing power)",
  fcf_margin: "FCF ≥10% of revenue", cash_real: "Cash is real (owner earnings ≥75% of profit)",
  low_debt: "Debt ≤2 years of FCF", no_dilution: "No share dilution", predictable: "Revenue up in 8 of 10 years",
  recession_tested: "Held up in 2020",
};

export function loadInvestedIndex(): Record<string, { name: string; total_mentions: number; episodes: { id: string; title: string; mentions: number; sentence: string }[] }> {
  const f = path.join(ROOT, "knowledge", "index", "companies.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : {};
}

export function loadScorecard(): { date: string; calls: number; graded: number; by_verdict: Record<string, { calls: number; avg_excess: number; beat_spy: number }>; recent: { date: string; agent: string; ticker: string; verdict: string; price: string; return: number; excess: number | null; age_days: number }[] } | null {
  const f = path.join(ROOT, "research", "scorecard", "latest.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

// ---------------------------------------------------------------- RULERS dossiers
const RULERS_DIR = path.join(ROOT, "research", "rulers");
export interface Dossier {
  ticker: string; name: string; verdict: string; confidence: number | null; entry: number[];
  trim: number | null; updated: string; priceAtUpdate: number | null; summary: string; body: string;
}

export function loadDossiers(): Dossier[] {
  if (!fs.existsSync(RULERS_DIR)) return [];
  const order = ["BUY", "ACCUMULATE", "WATCH", "AVOID", "TOO HARD"];
  return fs.readdirSync(RULERS_DIR).filter((f) => f.endsWith(".md")).map((f) => {
    const [meta, body] = frontMatter(fs.readFileSync(path.join(RULERS_DIR, f), "utf8"));
    const s = (k: string) => (typeof meta[k] === "string" ? (meta[k] as string) : "");
    const n = (k: string) => (s(k) && !Number.isNaN(Number(s(k))) ? Number(s(k)) : null);
    return {
      ticker: s("ticker") || f.replace(/\.md$/, ""), name: s("name"), verdict: s("verdict").toUpperCase(),
      confidence: n("confidence"), trim: n("trim"), updated: s("updated"), priceAtUpdate: n("price_at_update"),
      entry: (Array.isArray(meta.entry) ? meta.entry : []).map(Number).filter((x) => !Number.isNaN(x)),
      summary: s("summary"), body: body.replace(/^#\s+.*\n/, ""),
    };
  }).sort((a, b) => (order.indexOf(a.verdict) + 1 || 9) - (order.indexOf(b.verdict) + 1 || 9) || a.ticker.localeCompare(b.ticker));
}

// ---------------------------------------------------------------- editor
export interface Decisions {
  date: string; summary: string;
  decisions: { ticker: string; question: string; why: string; link?: string }[];
  actions: { ticker: string; action: string; reason: string }[];
}
export function loadDecisions(): Decisions | null {
  const f = path.join(ROOT, "research", "editor", "decisions.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

// ---------------------------------------------------------------- ops (Engineer)
export function loadOps(): { health: { date: string; body: string } | null; incidents: { slug: string; date: string; status: string; title: string; body: string }[] } {
  const hdir = path.join(ROOT, "ops", "health");
  const reports = fs.existsSync(hdir) ? fs.readdirSync(hdir).filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f)).sort() : [];
  const last = reports.at(-1);
  const idir = path.join(ROOT, "ops", "incidents");
  const incidents = fs.existsSync(idir) ? fs.readdirSync(idir).filter((f) => f.endsWith(".md")).sort().reverse().map((f) => {
    const [meta, body] = frontMatter(fs.readFileSync(path.join(idir, f), "utf8"));
    return { slug: f.replace(/\.md$/, ""), date: String(meta.date ?? ""), status: String(meta.status ?? ""),
      title: body.match(/^#\s+(.+)$/m)?.[1] ?? f, body: body.replace(/^#\s+.*\n/, "") };
  }) : [];
  return { health: last ? { date: last.slice(0, 10), body: fs.readFileSync(path.join(hdir, last), "utf8") } : null, incidents };
}

// ---------------------------------------------------------------- analyst consensus (the street)
export interface StreetRow {
  ticker: string; asOf: string; price: number | null; low: number | null; mean: number | null; median: number | null; high: number | null;
  n: number | null; rec: number | null; recKey: string; counts: { label: string; n: number }[];
  epsGrowthCy: number | null; epsGrowthNy: number | null; upside: number | null; revision: number | null;
  signal: string; actions: string[];
}
export interface StreetBrief {
  ticker: string; name: string | null; tier: string | null; status: string | null; price: number | null; mos_price: number | null;
  sticker: number | null; target_low: number | null; target_mean: number | null; target_high: number | null;
  n_analysts: number | null; rec_mean: number | null; upside_mean: number | null; revision_30d: number | null; signal: string; recent_actions: string;
}
export interface StreetFocus {
  date: string; covered: number; signals: Record<string, number>; signal_text: Record<string, string>;
  focus: Record<"agree" | "contrarian" | "crowded" | "revisions" | "most_watched" | "dossiers", StreetBrief[]>;
}

let _street: Map<string, StreetRow> | null = null;
export function loadStreet(): Map<string, StreetRow> {
  if (_street) return _street;
  _street = new Map();
  for (const r of readCsv(path.join(LISTS, "latest", "analysts.csv"))) {
    _street.set(r.ticker, {
      ticker: r.ticker, asOf: r.as_of, price: num(r.price), low: num(r.target_low), mean: num(r.target_mean), median: num(r.target_median),
      high: num(r.target_high), n: num(r.n_analysts), rec: num(r.rec_mean), recKey: r.rec_key ?? "",
      counts: [["Strong buy", r.strong_buy], ["Buy", r.buy], ["Hold", r.hold], ["Sell", r.sell], ["Strong sell", r.strong_sell]]
        .map(([label, v]) => ({ label: label as string, n: num(v as string) ?? 0 })),
      epsGrowthCy: num(r.eps_growth_cy), epsGrowthNy: num(r.eps_growth_ny), upside: num(r.upside_mean), revision: num(r.revision_30d),
      signal: r.street_signal ?? "", actions: (r.recent_actions ?? "").split("; ").filter(Boolean),
    });
  }
  return _street;
}

export function loadStreetFocus(): StreetFocus | null {
  const f = path.join(ROOT, "research", "analysts", "latest.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

export const STREET_LABEL: Record<string, string> = {
  agree: "Street agrees", contrarian: "Contrarian", crowded: "Crowded", "both cautious": "Both cautious",
  "thin coverage": "Thin coverage", mixed: "Mixed",
};
export const STREET_CLASS: Record<string, string> = {
  agree: "BUY", contrarian: "ONDECK", crowded: "warn", "both cautious": "info", "thin coverage": "info", mixed: "",
};
