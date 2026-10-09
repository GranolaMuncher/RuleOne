import type { APIRoute } from "astro";
import { loadDossiers, loadGurus, loadRadar, loadStreet } from "../../lib/data";

// Latest Radar verdict, guru holdings, dossier and analyst consensus per ticker, for the browser-only Holdings page.
export const GET: APIRoute = () => {
  const { history, latest } = loadRadar();
  const gurus = loadGurus().by_ticker;
  const radar = Object.fromEntries(Object.entries(history).map(([t, items]) => [t, items[0]]));
  const held = Object.fromEntries(Object.entries(gurus).map(([t, ps]) => [t, ps.map((p) => ({ g: p.guru, w: p.weight, c: p.change }))]));
  const rulers = Object.fromEntries(loadDossiers().map((d) => [d.ticker,
    { v: d.verdict, c: d.confidence, entry: d.entry, trim: d.trim, updated: d.updated, summary: d.summary }]));
  const street = Object.fromEntries([...loadStreet()].map(([t, a]) => [t,
    { d: a.asOf, l: a.low, m: a.mean, h: a.high, n: a.n, r: a.rec, v: a.revision, s: a.signal }]));
  return new Response(JSON.stringify({ date: latest?.date ?? null, radar, gurus: held, rulers, street }), { headers: { "Content-Type": "application/json" } });
};
