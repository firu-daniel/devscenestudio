import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type Plugin } from "vite";
import { CSP } from "./src/main/window/csp.ts";

// Adds the CSP <meta> to built HTML only. `vite serve` injects inline scripts and styles
// (React Refresh, CSS HMR) that this CSP would block; a dev-only CSP comes with Day 1 step 7.
function cspMeta(): Plugin {
  return {
    name: "studio-csp-meta",
    apply: "build",
    transformIndexHtml: () => [
      {
        tag: "meta",
        attrs: { "http-equiv": "Content-Security-Policy", content: CSP },
        injectTo: "head-prepend",
      },
    ],
  };
}

// Renderer build; also the base of vitest.config.ts. `--mode browser` is browser mode
// (fixture-backed, for Playwright and the harness QA agent), built into its own folder.
// strictPort stays unset here: the harness passes `--port … --strictPort` itself.
export default defineConfig(({ mode }) => ({
  root: "src/renderer",
  base: "./", // loaded from file:// (and app:// from Day 2) in Electron
  plugins: [react(), tailwindcss(), cspMeta()],
  build: {
    outDir: mode === "browser" ? "../../dist/browser" : "../../dist/renderer",
    emptyOutDir: true,
    target: "chrome156", // Electron 45
  },
}));
