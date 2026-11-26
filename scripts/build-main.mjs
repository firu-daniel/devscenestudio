// Bundles the main process and the preload, one CommonJS file each (Vite builds the renderer).
// The preload must be bundled: a sandboxed preload can `require` only "electron".
import { build } from "esbuild";

const common = {
  bundle: true,
  format: "cjs",
  external: ["electron"],
  sourcemap: true,
  logLevel: "warning",
  // .cjs: package.json is "type": "module" (for the TS/config files), but Electron's main
  // process and the sandboxed preload stay CommonJS.
  outExtension: { ".js": ".cjs" },
};

await Promise.all([
  build({
    ...common,
    entryPoints: { main: "src/main/main.ts" },
    platform: "node",
    target: "node24",
    outdir: "dist/main",
  }),
  build({
    ...common,
    entryPoints: { preload: "src/preload/preload.ts" },
    platform: "browser",
    target: "chrome156",
    outdir: "dist/preload",
  }),
]);
