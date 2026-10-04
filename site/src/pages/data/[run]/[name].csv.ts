import fs from "node:fs";
import path from "node:path";
import type { APIRoute } from "astro";
import { LIST_KEYS, archiveDates, archiveDir } from "../../../lib/data";

const ROOT = process.env.REPO_ROOT ?? path.resolve(process.cwd(), "..");

export function getStaticPaths() {
  const runs = ["latest", ...archiveDates()];
  return runs.flatMap((run) => LIST_KEYS.map((name) => ({ params: { run, name } })));
}

export const GET: APIRoute = ({ params }) => {
  const dir = params.run === "latest" ? path.join(ROOT, "lists", "latest") : archiveDir(params.run!);
  const file = path.join(dir, `${params.name}.csv`);
  const body = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  return new Response(body, { headers: { "Content-Type": "text/csv; charset=utf-8" } });
};
