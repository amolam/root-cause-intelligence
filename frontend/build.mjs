import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const publicDirectory = path.join(root, "public");
const outputDirectory = path.join(root, "dist");
const configuredApiUrl = process.env.API_BASE_URL?.trim();

if (!configuredApiUrl) {
  throw new Error("API_BASE_URL must be set for the Vercel build");
}

let apiUrl;
try {
  apiUrl = new URL(configuredApiUrl);
} catch {
  throw new Error("API_BASE_URL must be a valid absolute URL");
}
if (!new Set(["http:", "https:"]).has(apiUrl.protocol) || apiUrl.pathname !== "/" || apiUrl.search || apiUrl.hash) {
  throw new Error("API_BASE_URL must be an http(s) origin without a path, query, or fragment");
}

await rm(outputDirectory, { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });
await cp(publicDirectory, outputDirectory, { recursive: true });
await writeFile(
  path.join(outputDirectory, "runtime-config.js"),
  `window.DHAGA_CONFIG = Object.freeze({ apiBaseUrl: ${JSON.stringify(apiUrl.origin)} });\n`,
  "utf8",
);
console.log(`Built dashboard for API origin ${apiUrl.origin}`);
