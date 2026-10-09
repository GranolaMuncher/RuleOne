import type { APIRoute } from "astro";
import { loadUniverse } from "../../lib/data";

// Compact column-oriented feed for the All stocks page (gzip/brotli on Cloudflare keeps it small).
export const COLS = [
  "ticker", "name", "exchange", "sector", "industry", "status", "tier", "price", "marketCap",
  "w1", "m1", "m3", "ytd", "y1", "offHigh", "pe", "sticker", "mos", "pts", "payback", "tenCap", "methodsAgree",
  "growth", "roic5", "big5", "big5Tests", "fcfYield", "divYield", "divGrowth5y", "tr10y", "detail", "flags", "events",
] as const;

const r4 = (v: number | null) => (v == null ? null : Math.round(v * 10000) / 10000);

export const GET: APIRoute = () => {
  const rows = loadUniverse().map((u) => [
    u.ticker, u.name, u.exchange, u.sector, u.industry, u.status, u.tier, r4(u.price), u.marketCap == null ? null : Math.round(u.marketCap),
    r4(u.chg.w1), r4(u.chg.m1), r4(u.chg.m3), r4(u.chg.ytd), r4(u.chg.y1), r4(u.offHigh), r4(u.pe),
    r4(u.sticker), r4(u.mos), r4(u.priceToSticker), r4(u.payback), r4(u.tenCap), u.methodsAgree,
    r4(u.growth), r4(u.roic[1]), r4(u.big5Score), u.big5Tests, r4(u.fcfYield), r4(u.divYield), r4(u.divGrowth5y), r4(u.tr10y),
    u.detail, u.flags, u.events,
  ]);
  return new Response(JSON.stringify({ cols: COLS, rows }), { headers: { "Content-Type": "application/json" } });
};
