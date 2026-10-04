import { defineConfig } from "astro/config";

// Static site: every page is rendered at build time from ../lists and ../reports.
export default defineConfig({
  output: "static",
  site: process.env.SITE_URL || undefined,
  build: { format: "directory" },
});
