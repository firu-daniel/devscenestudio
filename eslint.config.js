// Lint config. Which process may import which is enforced by `tsc -b` (project references);
// these rules cover what lives inside a process and the security choke points.
// Sources: docs/architecture-research/07-recommendation.md §3.2, 02 §5, 05 §1, 06 §7.
// Main's rules arrive with the Day 2 main-process work.
//
// Note on flat config: when several blocks set the same rule for a file, the LAST one wins
// (options are replaced, not merged). So each renderer block below repeats the shared bans.
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const NO_ELECTRON_OR_NODE = [
  {
    group: ["electron", "electron/*"],
    message: "Only main and the preload may import electron.",
  },
  { group: ["node:*"], message: "No Node built-ins outside main." },
];

const renderer = {
  fixtures: {
    group: ["**/studio/fixture*", "**/studio/fixtures/**"],
    message: "Only main.tsx loads fixtures.",
  },
  ipc: {
    group: ["**/studio/ipc", "**/studio/ipc.*"],
    message: "Reach StudioApi through getStudio(), never the IPC adapter.",
  },
  state: {
    group: ["**/state", "**/state/**"],
    message: "ui/ is presentational: it never imports state/.",
  },
};

const rendererImports = (...extra) => [
  "error",
  { patterns: [...NO_ELECTRON_OR_NODE, ...extra] },
];

const HTML_SINKS = [
  {
    property: "innerHTML",
    message: "Render text through React; HTML only through SafeMarkdown.",
  },
  {
    property: "outerHTML",
    message: "Render text through React; HTML only through SafeMarkdown.",
  },
  {
    property: "insertAdjacentHTML",
    message: "Render text through React; HTML only through SafeMarkdown.",
  },
  {
    object: "document",
    property: "write",
    message: "document.write is banned.",
  },
  {
    object: "document",
    property: "writeln",
    message: "document.writeln is banned.",
  },
];
const CREATE_POLICY = {
  property: "createPolicy",
  message:
    "Trusted Types policies are created only in src/renderer/markdown/policy.ts.",
};

export default defineConfig([
  {
    ignores: [
      "dist/**",
      "release/**",
      "coverage/**",
      ".tsbuild/**",
      "test-results/**",
      "playwright-report/**",
    ],
  },

  tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  // Plain JS (this file, scripts/) is in no tsconfig: lint it without type information.
  {
    files: ["**/*.{js,mjs,cjs}"],
    extends: [tseslint.configs.disableTypeChecked],
  },
  {
    files: ["**/*.{ts,tsx}"],
    rules: { "@typescript-eslint/switch-exhaustiveness-check": "error" },
  },

  // --- shared: pure TypeScript -------------------------------------------------------
  {
    files: ["src/shared/**/*.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            ...NO_ELECTRON_OR_NODE,
            { group: ["react", "react-dom", "react/*", "react-dom/*"] },
          ],
        },
      ],
    },
  },
  {
    // domain imports nothing outside domain.
    files: ["src/shared/domain/**/*.ts"],
    ignores: ["**/*.test.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^(?!\\./)",
              message: "shared/domain imports nothing outside shared/domain.",
            },
          ],
        },
      ],
    },
  },
  {
    // contract imports only domain (and typebox, in schemas.ts alone).
    files: ["src/shared/contract/**/*.ts"],
    ignores: ["**/*.test.ts", "src/shared/contract/schemas.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^(?!\\./|\\.\\./domain/)",
              message: "shared/contract imports only shared/domain.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/shared/contract/schemas.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^(?!\\./|\\.\\./domain/|typebox$)",
              message: "schemas.ts imports only shared/domain and typebox.",
            },
          ],
        },
      ],
    },
  },

  // --- renderer ----------------------------------------------------------------------
  {
    files: ["src/renderer/**/*.{ts,tsx}"],
    extends: [reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
    rules: {
      "no-restricted-imports": rendererImports(renderer.fixtures),
      "no-restricted-properties": ["error", ...HTML_SINKS, CREATE_POLICY],
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message:
            "dangerouslySetInnerHTML is allowed only in src/renderer/markdown/SafeMarkdown.tsx.",
        },
      ],
    },
  },
  // The composition root and the studio/ adapters may load fixtures.
  {
    files: ["src/renderer/main.tsx", "src/renderer/studio/**"],
    rules: { "no-restricted-imports": rendererImports() },
  },
  {
    files: ["src/renderer/features/**", "src/renderer/state/**"],
    rules: {
      "no-restricted-imports": rendererImports(renderer.fixtures, renderer.ipc),
    },
  },
  {
    files: ["src/renderer/ui/**"],
    rules: {
      "no-restricted-imports": rendererImports(
        renderer.fixtures,
        renderer.ipc,
        renderer.state,
      ),
    },
  },
  // The two security choke points.
  {
    files: ["src/renderer/markdown/SafeMarkdown.tsx"],
    rules: { "no-restricted-syntax": "off" },
  },
  {
    files: ["src/renderer/markdown/policy.ts"],
    rules: { "no-restricted-properties": ["error", ...HTML_SINKS] },
  },
  // Tests render components and export nothing: Fast Refresh rules don't apply.
  {
    files: ["src/renderer/**/*.test.{ts,tsx}"],
    rules: { "react-refresh/only-export-components": "off" },
  },
]);
