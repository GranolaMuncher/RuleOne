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
  return {
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
