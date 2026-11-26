import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config.ts";

// Two projects: `node` for shared, main, preload and the node-side suites; `dom` (jsdom)
// for the renderer. jsdom rather than happy-dom, for DOMPurify (06 §4).
export default mergeConfig(
  viteConfig({ mode: "test", command: "serve" }),
  defineConfig({
    root: ".",
    test: {
      projects: [
        {
          extends: true,
          test: {
            name: "node",
            environment: "node",
            include: [
              "src/{shared,main,preload}/**/*.test.ts",
              "tests/{contract,integration}/**/*.test.ts",
            ],
          },
        },
        {
          extends: true,
          test: {
            name: "dom",
            environment: "jsdom",
            setupFiles: ["tests/setup-dom.ts"],
            include: ["src/renderer/**/*.test.{ts,tsx}"],
          },
        },
      ],
    },
  }),
);
