import type { APIRoute } from "astro";
import { loadGurus, loadRadar } from "../../lib/data";

// Latest Radar verdict and guru holdings per ticker, for the browser-only Holdings page.
export const GET: APIRoute = () => {
  const { history, latest } = loadRadar();
  const gurus = loadGurus().by_ticker;
  const radar = Object.fromEntries(Object.entries(history).map(([t, items]) => [t, items[0]]));
  const held = Object.fromEntries(Object.entries(gurus).map(([t, ps]) => [t, ps.map((p) => ({ g: p.guru, w: p.weight, c: p.change }))]));
  return new Response(JSON.stringify({ date: latest?.date ?? null, radar, gurus: held }), { headers: { "Content-Type": "application/json" } });
};
