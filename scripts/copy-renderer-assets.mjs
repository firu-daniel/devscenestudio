// Copies the renderer's static files next to the compiled scripts.
// Temporary: the Vite renderer build replaces this on Day 1.
import { cpSync, mkdirSync } from "node:fs";

const assets = ["index.html", "styles.css"];
mkdirSync("dist/renderer", { recursive: true });
for (const asset of assets) {
  cpSync(`src/renderer/${asset}`, `dist/renderer/${asset}`);
}
