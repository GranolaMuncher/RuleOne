export const usd = (v: number | null | undefined, digits = 2) =>
  v == null ? "–" : `$${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

export const pct = (v: number | null | undefined, digits = 0) => (v == null ? "–" : `${(v * 100).toFixed(digits)}%`);

export const mult = (v: number | null | undefined) => (v == null ? "–" : `${v.toFixed(1)}×`);

export const big = (v: number | null | undefined) => {
  if (v == null) return "–";
  if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
};

/** Upside (+) / downside (−) from price to a target price. */
export const upside = (price: number | null, target: number | null) =>
  price && target ? target / price - 1 : null;

export const STATUS_LABEL: Record<string, string> = {
  BUY: "Buy range",
  "BUY*": "Buy (Payback/Ten Cap)",
  "ON DECK": "On deck",
  "ABOVE STICKER": "Above Sticker",
  "NO STICKER": "No Sticker",
  "BELOW MOS": "Below buy price (fails quality screen)",
  "BELOW STICKER": "Below Sticker (fails quality screen)",
};

/** Flags that question the numbers are warnings; basis notes (currency, ADR, EPS source) are info. */
export const flagClass = (f: string) => (/check|micro-cap|less meaningful/i.test(f) ? "warn" : "info");
