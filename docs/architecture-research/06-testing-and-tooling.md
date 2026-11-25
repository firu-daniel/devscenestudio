# 06 — Testing and tooling
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

- **Build: Vite 8.3.8 for the renderer, plus a small esbuild 0.28.2 script for main and preload.** Keep electron-builder. Plain `vite --mode browser` is the browser-mode dev server, and the same config feeds Vitest. electron-vite 6.0.0 works (Vite 8 support, released 2026-10-14) but has one maintainer (354 of ~358 commits) and doesn't remove the need for a plain Vite config for browser mode. Electron Forge's Vite plugin is experimental and tied to Forge. Both fit 02's `src/{shared,main,preload,renderer}` tree unchanged, and 04's reviewer also favours Vite + esbuild; 07 makes the final pick. Plain `tsc` must go: a sandboxed preload can `require` only `electron`, so it has to be bundled as soon as it imports shared code [verified, 3, 4]. The bundler lands in the same change as 02's tsconfig split, because `tsc -b` then emits no JavaScript (02 §5).
- **TypeScript: stay on 6.0.3, and use 02's project references.** TS 7.0.2 is out, and Vite's own template uses it, but typescript-eslint 8.74.0 declares `typescript >=4.8.4 <6.1.0` [verified, 1]. One root solution file references `src/{shared,main,preload,renderer}/tsconfig.json`, `tests/tsconfig.json` and a tools project; `tsc -b` is typecheck only. `shared` is `composite` + `emitDeclarationOnly` with no DOM and no Node types; the process projects are `composite` + `noEmit`. Measured with TS 6.0.3: a `document` reference in shared fails (TS2584), and a renderer→main import fails (TS6307). Without `composite` that import compiles silently, so the flags are load-bearing [verified, 25].
- **Runner: Vitest 5.1.2 with two inline `test.projects`.** `node` covers shared, main, preload and the `tests/` suites; `dom` uses **jsdom 31.0.1** for renderer components. Pick jsdom over happy-dom so that component tests rendering `SafeMarkdown` never go green on a DOM DOMPurify calls "not considered safe" [verified, 9]. Security sign-off for sanitising comes only from 05's corpus in real Chromium. Neither DOM implements Trusted Types (measured), so Trusted Types and CSP are checked only in Chromium.
- **Colocate unit and component tests inside each layer** (`*.test.ts[x]`), unlike expause_web's `src/test/unit/<layer>/` mirror tree. The harness implementer must stay inside its layer's `path`, so a unit can only write its own tests if they sit in that path. Cross-layer suites (the IPC contract suite, stub-binary integration, Playwright) go under **one `tests/` root, 02's `tests` harness layer**.
- **IPC contract test: one `describeStudioApi(makeApi)` suite.** Day 1 runs it against the fixture adapter. Day 2 also runs it against the real preload factory `makeStudioApi(invoke)` wired to the real main handlers through a ~10-line `invoke` shim (`structuredClone` the arguments, call the handler `registerIpc` stored). No `vi.mock('electron')` and no fake IPC pair. Real Electron IPC is exercised only by 2–3 Playwright `_electron` smoke tests.
- **E2E:** Playwright 1.65.1. A `browser` project runs against `vite preview` of the browser-mode build, a real bundle where CSP can be enforced. An `electron` project uses `_electron.launch`, which is **still experimental** (Electron v21+) and needs the `nodeCliInspect` fuse not set to `false` [verified, 6]. So it runs against the unpackaged `dist/` build, never the fused release. On 1.65.1, unset `ELECTRON_RUN_AS_NODE` before launch (issue #44272, fixed on main for 1.66) [verified, 7].
- **Harness gates.** `commands.typecheck` = `bash devscene-scripts/typecheck.sh`, whose wrapper line is `npm run check` (`tsc -b` + ESLint, so 02's import rules are gated). `commands.test` = `bash devscene-scripts/test.sh`, wrapper line `npx vitest run "$@"`. `commands.devServer` = `bash devscene-scripts/start-dev-server.sh`, wrapper line `npm run dev:browser -- --port "$DEVSCENE_DEV_SERVER_PORT" --strictPort`. `commands.depInstall` stays raw: `npm ci --ignore-scripts` [verified, 20]. A unit runs the typecheck over the whole tree, so every unit pays `tsc -b` plus type-aware ESLint: a few seconds at this size [verified, 21]. **Playwright stays out of `commands.test`.** Its browsers aren't in `node_modules`, Electron E2E needs Xvfb, and gates run in a sandbox with a strict network allowlist [verified, 12].
- **Never import `electron` at runtime outside the main composition root and the preload entry.** In Electron 45 the npm package has no postinstall: `require('electron')` from plain Node returns a path string, not the API, and **downloads the binary at import time if it isn't there yet** (always the case after `npm ci --ignore-scripts` in a fresh run copy) [verified, 23]. A Vitest file that imports it breaks offline (gate sandbox) and gets no API online.
- **Lint and format:** ESLint 10.15.0 flat config + typescript-eslint 8.74.0 (`recommendedTypeChecked`, mainly for `no-floating-promises` and `switch-exhaustiveness-check`) + eslint-plugin-react-hooks 7.1.1 `flat.recommended` + 02's core `no-restricted-imports` blocks. Unused imports fail the per-unit gate through ESLint, by design. Prettier 3.10.1 with defaults. Biome and oxlint are rejected: neither has typescript-eslint's type-aware rules, and oxlint's JS plugins are alpha.
- **Fixtures, two kinds.** StudioApi scenarios (TS, typed against `src/shared/contract/`, with timed `snapshot`/`upsert`/`remove`/`status` events and `log:lines` batches per 03) live in 02's `src/renderer/studio/fixtures/` and feed browser mode (`?scenario=<name>`), component tests and Playwright. Harness `runs watch` NDJSON scripts (`snapshot`, `run_updated`, `heartbeat`…) live in `tests/stubs/` and feed the stub `devscene` binary and main's normaliser.

## Scope

Covered: build tooling, the TypeScript project layout and strictness, the test pyramid per layer, runners and environments, fixtures and scripted streams, lint and format, npm scripts and harness gate fit, how the QA agent drives browser mode, and what to reuse from expause_web.

Left to others: process model (01), the layers, folder names and the boundary-rule tool itself (02; paths below follow reviewed 02: `src/shared/{domain,contract}`, `src/{main,preload,renderer}`, one `tests/` root), store and stream design (03), perf measurement (04), the content of the security suites (XSS corpus, argv fuzz, hostile-repo fixture, fuse read-back) (05). Agent-drivable UI testing as a framework criterion is in `../product-startup-research/07-additional-criteria.md` §1; layer and gate mechanics are in `06-repo-topology-harness-fit.md` §2. Neither is repeated here.

## Findings

### 1. Versions checked live (npm registry, 2026-11-25)

| Tool | Latest | Released | Compatibility with this repo | Tag |
|---|---|---|---|---|
| vite | 8.3.8 | 2026-11-11 | Node ^20.19 \|\| >=22.12; esbuild is now an *optional peer* (^0.27 \|\| ^0.28), so add it explicitly | [verified, 1] |
| @vitejs/plugin-react | 6.3.0 | 2026-11-09 | Peer vite ^8 | [verified, 1] |
| esbuild | 0.28.2 | 2026-08-08 | Works under `npm ci --ignore-scripts` (measured) | [verified, 1, local] |
| electron-vite | 6.0.0 | 2026-10-14 | Peer vite ^6–^8; bundles rolldown ~1.2.10; maintainer bus factor 1 | [verified, 1, 2] |
| @electron-forge/plugin-vite | 8.0.1 | 2026-09-29 | "marked as experimental" since Forge 7.5; config lives in `forge.config.js` | [verified, 5] |
| vitest | 5.1.2 | 2026-11-25 (5.0.0: 2026-09-03) | Node ^22.12 \|\| ^24; vite ^6.4–^8 | [verified, 1, 10] |
| jsdom | 31.0.1 | 2026-11-13 | **Node ^22.22.2** \|\| ^24.15 (repo `engines` says >=22.12.0, so bump it) | [verified, 1] |
| happy-dom | 21.0.4 | 2026-10-20 | Node >=20 | [verified, 1] |
| @testing-library/react | 16.3.3 | 2026-08-27 | Peer react ^18 \|\| ^19 (React is 19.3.1) | [verified, 1] |
| @testing-library/jest-dom | 8.0.0 | 2026-11-19 | Peer `vitest >=5 <6` | [verified, 1] |
| @testing-library/user-event | 14.6.13 | 2026-11 | — | [verified, 1] |
| @playwright/test | 1.65.1 | 2026-11-13 | Chromium 158; `_electron` experimental | [verified, 1, 6, 8] |
| eslint | 10.15.0 | 2026-11-13 | Node ^20.19 \|\| ^22.13 \|\| >=24 | [verified, 1] |
| typescript-eslint | 8.74.0 | 2026-11-23 | **typescript <6.1.0**: rules out TS 7 | [verified, 1] |
| eslint-plugin-react-hooks | 7.1.1 | 2026-04-17 | ESLint ^10 OK; `configs.flat.recommended` includes the React Compiler rules | [verified, 1, 11] |
| eslint-plugin-react-refresh | 0.5.8 | 2026-11-15 | ESLint ^9 \|\| ^10 | [verified, 1] |
| prettier | 3.10.1 | 2026-11-12 | — | [verified, 1] |
| @biomejs/biome | 2.6.9 | 2026-11-24 | — | [verified, 1] |
| oxlint | 1.95.0 | 2026-11-23 | JS plugins "currently in alpha"; no type-aware rules in JS plugins | [verified, 1, 13] |
| typescript | 7.0.2 latest; repo pins 6.0.3 | — | Stay on 6.0.x (typescript-eslint peer) | [verified, 1] |
| electron | 45.5.0 | 2026-11-24 | Node 24.22.3, Chrome 156 | [verified, 14] |
| @playwright/mcp (harness QA) | 0.0.86 | 2026-11-18 | Pre-1.0 | [verified, 1] |

### 2. Build tooling

Today: `tsc -p tsconfig.json && node scripts/copy-renderer-assets.mjs` (`package.json:14`), one tsconfig with `lib: ["ES2023","DOM"]` for all three processes (`tsconfig.json:7`). The copy script already says "the Vite renderer build replaces this on Day 1" (`scripts/copy-renderer-assets.mjs:2`).

Why `tsc` alone stops working: with `sandbox: true` (`src/main/main.ts:13`), the preload's `require` "can only load the `electron` module". To split preload code "use a bundler" [verified, 3]. Sandboxed preloads also have no ESM [verified, 4]. The moment the preload imports channel names from `src/shared/contract/`, unbundled `tsc` output fails at runtime.

All options below fit 02's tree unchanged; 07 picks (02 §5).

| Option | Browser-mode dev server | Main/preload | Electron dev loop | Cost for this app | Verdict |
|---|---|---|---|---|---|
| **Vite (renderer) + esbuild script (main, preload)** | `vite --mode browser`: native | `esbuild --bundle --format=cjs --external:electron`, one CJS file each, easy to audit | ~50-line `scripts/dev.mjs`: Vite `createServer`, esbuild `context().watch()`, respawn Electron on main rebuild | We own ~80 lines of build scripts | **Pick** |
| electron-vite 6 | Needs a separate plain `vite.config.ts` anyway (the renderer section can import it). `dev --rendererOnly` still assumes the Electron flow [verified, 2] | Vite/rolldown; sandbox support through "isolated build" [verified, 2] | Built in (renderer HMR, main/preload hot reload) | One more config layer; bus factor 1 [verified, 1]; default `out/` dir | Fallback if `dev.mjs` grows past ~100 lines |
| Electron Forge + Vite plugin | Separate config | Forge-managed | Forge-managed | Experimental, may break in minors [verified, 5]; built around Forge's make/publish, while the repo uses electron-builder | Reject |
| Plain esbuild for all three | No HMR or dev server of note; we'd hand-write the HTML/CSS pipeline | Same as row 1 | Hand-written | Loses React Fast Refresh and Vite's ecosystem; Vitest wants a Vite config anyway | Reject |

The two build scripts, roughly:

```js
// scripts/build-main.mjs
import { build } from "esbuild";
const common = { bundle: true, format: "cjs", external: ["electron"], sourcemap: true, logLevel: "warning" };
await build({ ...common, entryPoints: { main: "src/main/main.ts" }, platform: "node", target: "node24", outdir: "dist/main" });
await build({ ...common, entryPoints: { preload: "src/preload/preload.ts" }, platform: "browser", target: "chrome156", outdir: "dist/preload" });
```

```ts
// vite.config.ts (renderer; also Vitest's root config)
export default defineConfig(({ mode }) => ({
  root: "src/renderer",
  base: "./",                                   // file:// or app:// in Electron (05 owns the protocol)
  plugins: [react()],
  build: { outDir: mode === "browser" ? "../../dist/browser" : "../../dist/renderer", emptyOutDir: true },
}));
```

The renderer composition root (`src/renderer/main.tsx`, 02 §2) installs the fixture adapter only in browser mode. Vite replaces `import.meta.env.MODE` statically, and a *dynamic* import behind it lets the production build drop the fixture code (a static import would rely on tree-shaking a side-effect-free module) [inferred]. A one-line test asserts `dist/renderer` contains no fixture marker string; 05 may want it in its suite.

```ts
const studio: StudioApi = import.meta.env.MODE === "browser"
  ? (await import("./studio/fixture")).createFixtureStudio(location.search) : window.studio;
```

Keep main as CJS. The package has no `"type": "module"`, `__dirname` is used (`src/main/main.ts:12`), and ESM in main needs awaited imports before `ready` [verified, 4] for no gain here [inferred].

**Answer to 02's open question (shared under `nodenext` vs `bundler`):** use `moduleResolution: "bundler"` everywhere. Main and preload are bundled by esbuild and the renderer by Vite, so no project's output is loaded by Node's own resolver and shared code needs no `.js` specifiers [inferred]. The one place plain Node loads files is the stub binaries in `tests/stubs/bin/`, and they import no TypeScript (§6).

### 3. TypeScript layout and strictness

02 §5 settled the layout: project references, so that the process boundary is a compile error. This section adds the flags.

```
tsconfig.json                  solution: { "files": [], "references": [shared, main, preload, renderer, tests, tools] }
tsconfig.base.json             shared flags, moduleResolution "bundler", module "esnext"
src/shared/tsconfig.json       composite, emitDeclarationOnly (outDir .tsbuild/); lib ES2024, types []    (purity check)
src/main/tsconfig.json         composite, noEmit; lib ES2024, types ["node"]; refs shared
src/preload/tsconfig.json      composite, noEmit; lib ES2024 + DOM, types []; refs shared
src/renderer/tsconfig.json     composite, noEmit; lib ES2024 + DOM, jsx react-jsx, types ["vite/client"]; refs shared
tests/tsconfig.json            NOT composite, noEmit; lib ES2024 + DOM, types ["node"]; refs shared
tsconfig.tools.json            noEmit; types ["node"]; include *.config.ts
```

- **Measured with TS 6.0.3 on this shape** [verified, 25]: `tsc -b` exits 0 and emits no `.js`. A `document` reference in shared fails with TS2584. A renderer file importing `../main/svc` fails with TS6307 ("not listed within the file list of project"). The review measured the earlier `noEmit`-only draft: there, the same import compiled with exit 0 (review M2). So **`composite` on the process projects is what enforces the boundary**; `noEmit` alone checks only `lib`/`types` purity.
- **The `tests` project is deliberately not `composite`.** Its suites import main, preload and renderer source, and a composite `tests` project fails each of those imports with TS6307 (measured). Non-composite, it pulls the imported files into its own program and builds with exit 0 [verified, 25]. Cost: those files are type-checked twice, once under `tests` settings; a second or so at this size [inferred]. The process projects still check them under their own strict `lib`.
- **Co-located tests sit inside their layer's project.** `src/renderer/**/*.test.tsx` is checked with DOM types, `src/main/**/*.test.ts` without. Import `describe`/`it` from `vitest` explicitly; no `globals` types needed.
- **TS 6 defaults that matter here:** `types` now defaults to `[]`, so list `"node"` where needed. `strict`, `noUncheckedSideEffectImports` and `module: esnext` are now defaults. `baseUrl` is deprecated, so use relative imports or `paths` without `baseUrl`. `moduleResolution node10` is deprecated [verified, 16].
- **Flags:** keep today's `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride` and `noFallthroughCasesInSwitch` (`tsconfig.json:8-12`). Add `verbatimModuleSyntax` and `erasableSyntaxOnly`: no enums or namespaces, so esbuild/Vite single-file transpiling can't diverge from `tsc`. That costs nothing and keeps a possible TS 7 move cheap [inferred]. Leave `noUnusedLocals`/`noUnusedParameters` off in tsconfig: `recommendedTypeChecked` already sets `@typescript-eslint/no-unused-vars: "error"`, and ESLint runs inside the typecheck gate, so unused code fails the per-unit gate once, through ESLint [verified, 26]. That is the intended policy: the harness implementer finishes each unit.
- Today's `lib: ["ES2023","DOM"]` for main gives main code `window` with no error. The split fixes that.
- Add `.tsbuild/` to `.gitignore` and to ESLint's `ignores`.

### 4. Test pyramid per layer

| Harness layer (02 §4) · what | Tests | Where | Runner / env | Doubles | Speed and count target |
|---|---|---|---|---|---|
| `shared` · domain (pure) | Reducers (`applyRunsEvent`), status/phase mapping, board column rules, trust rules, branch-name regex, `Result` | `src/shared/domain/**/*.test.ts` | Vitest `node` | None | ms each; the bulk of the tests |
| `shared` · contract | Payload validators; push-event types (03) | `src/shared/contract/**/*.test.ts` | Vitest `node` | None | A handful |
| `main` · unit | `ghCli`, `harnessCli` and its NDJSON normaliser, argv builder, log tailer, watcher, `Direct \| Wsl` transport, `app/` services. Spawn and fs injected as ports | `src/main/**/*.test.ts` | Vitest `node` + `vi.useFakeTimers()` | Fake spawner returning scripted stdout chunks; fake clock | Fast |
| `preload` (routes to `general`) | `makeStudioApi(invoke)` maps each verb to its channel; exposes no `ipcRenderer` | `src/preload/*.test.ts` | Vitest `node` | Fake `invoke` | 1 file |
| `renderer` · components | Board, detail, log tail, repo dropdown, doctor icons; hooks against the store (03) | `src/renderer/**/*.test.tsx` | Vitest `dom` (jsdom) + Testing Library + user-event | Fixture adapter injected through the same port the app uses | Query by role first; `data-testid` for things the QA agent must reach |
| `tests` · integration | Real `child_process.spawn` of **stub `gh`/`devscene`/`wsl.exe` scripts** (put first on `PATH`) that print fixture JSON/NDJSON, exit with a set code, or hang; every `tests/stubs/streams/*.ndjson` line passes main's normaliser | `tests/integration/`, stubs in `tests/stubs/bin/` | Vitest `node` | Stub binaries only | ~100 ms each; one per adapter plus failure modes (non-zero exit, partial line, kill on dispose) |
| `tests` · IPC contract | `describeStudioApi(makeApi)` against (a) the fixture adapter and, from Day 2, (b) `makeStudioApi(invoke)` + real `registerIpc` handlers with fake adapters, joined by a ~10-line `invoke` shim | `tests/contract/` | Vitest `node` | Fake ports in main; no `electron` mock | Same assertions both ways, so the fixture adapter can't drift from the real one (02 §6, LSP row) |
| `tests` · E2E browser | User flows across screens, live updates from a scripted stream, CSP/Trusted Types enforcement (05's corpus) | `tests/e2e/browser/` | Playwright `browser` project against `vite preview` of `dist/browser` | Fixture adapter | 10–20 specs |
| `tests` · E2E Electron | Launch, preload exposes only verbs, board renders from stub `gh`, one action round trip (native dialog stubbed in main via `electronApp.evaluate`) | `tests/e2e/electron/` | Playwright `electron` project, `_electron.launch` on `dist/main/main.js` | Stub binaries on `PATH` | 2–3 smoke specs; Linux needs Xvfb |

Notes:
- **Why jsdom over happy-dom.** expause_web picked happy-dom for "better ES module support" (`expause_web/vitest.config.ts:10`). Here the renderer runs DOMPurify. Its README "strongly recommend[s]" jsdom and says happy-dom "is not considered safe… will likely lead to XSS" [verified, 9]. That advice is about server-side sanitising, so the reason here is narrower: component tests that render `SafeMarkdown` must not go green on a DOM DOMPurify calls unsafe. **Security sign-off for sanitising comes only from 05's corpus in Playwright on `vite preview`** (05 "Tests"); jsdom also parses differently from Chromium, so a jsdom result is no mutation-XSS proof [inferred]. Measured with jsdom 31.0.1 vs happy-dom 21.0.4: neither has `trustedTypes`; jsdom lacks `ResizeObserver`, `IntersectionObserver` and `matchMedia`, which happy-dom has [verified, 25]. Cost of jsdom: about four one-line stubs in `tests/setup-dom.ts`, plus slower startup (happy-dom is "considered to be faster" [verified, 10]). Per-file `// @vitest-environment happy-dom` stays available if a test ever needs speed [verified, 10].
- **The contract suite's run (b) isn't Electron's IPC, and doesn't pretend to be.** It needs no `electron` mock because 02's composition roots already inject it: the preload entry is `contextBridge.exposeInMainWorld("studio", makeStudioApi((ch, ...a) => ipcRenderer.invoke(ch, ...a)))`, and main's `registerIpc(ipcMain, services)` takes `ipcMain` as an argument (02 §2). The shim is a `{ handle(ch, fn) }` object that stores handlers, plus an `invoke` that `structuredClone`s the arguments and calls the stored handler. It proves the two halves agree on channel names, argument validation and clone-ability. Push events (`webContents.send`), real `contextBridge` behaviour and sender-frame checks come only from the `_electron` smoke tests and 05's suites [inferred]. If even this proves more than it buys, drop (b) and keep (a); promote nothing further unless a preload/main mismatch escapes.
- **No runtime `electron` import in testable code.** Adapters receive `dialog`, `shell`, `BrowserWindow` and friends as constructor arguments from the composition root (02's term). Otherwise the import triggers a download in Node if the binary is missing, and returns a path string either way [verified, 23: `node_modules/electron/index.js:25-52`].
- **Electron E2E and fuses.** `_electron` needs `nodeCliInspect` not `false` [verified, 6]; the release fuse set (10 §6) turns it off. So the Electron project runs against the unpackaged build, and packaged-app fuses are verified by `@electron/fuses read` (05). That's correct, not a gap: the debug path must not exist in release. The first `_electron` launch in a fresh CI checkout triggers the same lazy Electron download, so the e2e job needs network or a cache of `node_modules/electron/dist` [verified, 23].
- **Native modal.** Playwright can't click an OS dialog. Playwright's Electron class doc has a "Mocking native dialogs" note that prescribes replacing `dialog.showMessageBox` in main through `electronApp.evaluate(({ dialog }) => …)` (it runs in the main process) [verified, 6]. For that stub to take effect, `adapters/electron/confirm.ts` must call `this.dialog.showMessageBox(…)` through the injected object at call time, not a function reference captured at startup [inferred]. Unit tests inject a fake `Confirm` port.

### 5. Vitest configuration

```ts
// vitest.config.ts
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";
export default mergeConfig(viteConfig({ mode: "test", command: "serve" }), defineConfig({
  test: {
    root: ".",                       // undo the renderer root for test discovery
    projects: [
      { test: { name: "node", environment: "node",
                include: ["src/{shared,main,preload}/**/*.test.ts", "tests/{contract,integration}/**/*.test.ts"] } },
      { test: { name: "dom", environment: "jsdom", setupFiles: ["tests/setup-dom.ts"],
                include: ["src/renderer/**/*.test.{ts,tsx}"] } },
    ],
  },
}));
```

- **Unmeasured** [inferred]: merging a function-form Vite config whose `root` is `src/renderer`, then resetting `test.root` with inline projects that inherit it. The first Day 1 check is that `npx vitest run` lists both projects and finds a test in each. Fallback: a separate `vitest.config.ts` that imports only the `react()` plugin.
- `test.projects` replaces the deprecated `workspace` file [verified, 17]. In Vitest 5, inline projects **extend the root config by default** and share one Vite server [verified, 18], so no `extends: true` is needed.
- Vitest 5 breaking changes that affect habits brought over from expause_web (Vitest 4): mocks are **cleared before each test by default**; an un-awaited async assertion fails the test; config files are no longer looked up in ancestor directories [verified, 18].
- `tests/setup-dom.ts`: `import "@testing-library/jest-dom/vitest"`, `afterEach(cleanup)`, plus stubs for `ResizeObserver` and `matchMedia`. This is expause_web's `src/test/setup.ts` minus the double `expect.extend`, which the `/vitest` entry already does. It sits in the `tests` layer per 02's tree, so a new DOM stub is a `tests` task.
- Playwright: `playwright.config.ts` with `testDir: "tests/e2e"` and two projects, `browser` (`testMatch: "browser/**"`, `webServer: npm run build:browser && vite preview`) and `electron` (`testMatch: "electron/**"`).

### 6. Fixtures and scripted live streams

Two fixture sets, because they sit on either side of main's read-model. 03 has main turn the harness's NDJSON and `gh` JSON into `snapshot`/`upsert`/`remove`/`status` pushes, so the renderer's fixture emits pushes, not fake NDJSON (03 §4).

```
src/renderer/studio/                         LAYER renderer (02 §3): browser mode ships these
  fixture.ts                                 createFixtureStudio(search): StudioApi from a Scenario + event player
  fixtures/
    empty.ts  busyBoard.ts  parkedRun.ts  remoteOnly.ts  doctorWarnings.ts   (typed against src/shared/contract/)
    index.ts                                 name → Scenario: initial snapshot + timed upsert/remove/status + log:lines batches
tests/stubs/                                 LAYER tests: wire-format data for main
  bin/gh, devscene, wsl.exe                  plain Node scripts (no TS imports); read STUB_DIR, print a file, exit/hang on cue
  gh/issues-busy.json  gh/runs-busy.json     `gh … --json` output as gh prints it
  streams/run-lifecycle.ndjson               `runs watch --json`: snapshot, run_updated, run_removed, log, heartbeat
  streams/stall.ndjson                       a gap longer than the heartbeat timeout
  streams/log-burst.ndjson                   for 04's 1–2k lines/s check
```

- **Scenarios: three consumers.** Browser mode, component tests and Playwright `browser` specs (`page.goto("/?scenario=parkedRun")`) all read `src/renderer/studio/fixtures/`. Typing them as TS against `src/shared/contract/` means a contract change breaks them at `tsc -b` [inferred]. A new browser-mode scenario plus its spec is two tasks, renderer then tests (02 §4).
- **Wire fixtures: plain JSON and NDJSON, so the stubs need no TypeScript.** Node's type stripping needs explicit `.ts` specifiers, which `moduleResolution: "bundler"` code doesn't have, so a stub that imported a TS scenario would fail at runtime where Vitest wouldn't notice [inferred, review S4]. Reading data files avoids that, and also avoids `tsx` or a generate step. Drift with the harness is caught by a `tests/integration` test that runs every `.ndjson` line and every `gh` JSON file through main's normaliser.
- **Select the scenario through the URL, not storage.** The harness QA agent clears `localStorage`/`sessionStorage` and reloads before each case [verified, 19]. An in-memory adapter keyed by `?scenario=` survives that and resets cleanly.
- **Timed events.** The fixture player emits each scenario event at its `t` offset through `setTimeout`. In Vitest, `vi.useFakeTimers()` + `await vi.advanceTimersByTimeAsync(1500)` steps it deterministically. In Playwright, use `page.clock` or a `?speed=0` query that flushes everything at once. Main's NDJSON reader tests feed `Readable.from([...])` chunks split **mid-line and mid-UTF-8 sequence**, because that's where NDJSON readers break [inferred].
- **Heartbeat and stall.** `stall.ndjson` drives main's watchdog in an integration test; a scenario with a `status` event drives the renderer's "reconnecting" badge (03 §5).
- **Windows.** On Windows the `PATH` stubs need `.cmd` shims (`gh.cmd` → `node "%~dp0gh" %*`), since `Direct | Wsl` is in scope. One line per stub [inferred].

### 7. Lint and format

```js
// eslint.config.js
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig } from "eslint/config";
export default defineConfig([
  { ignores: ["dist/**", "release/**", "coverage/**", ".tsbuild/**", ".vitest/**"] },
  tseslint.configs.recommendedTypeChecked,          // includes no-floating-promises and no-unused-vars as errors
  { languageOptions: { parserOptions: { projectService: true } } },
  { files: ["**/*.{js,mjs,cjs}"], extends: [tseslint.configs.disableTypeChecked] },   // eslint.config.js, scripts/*.mjs, stubs
  { files: ["src/renderer/**/*.{ts,tsx}"], extends: [reactHooks.configs.flat.recommended, reactRefresh.configs.vite] },
  { rules: { "@typescript-eslint/switch-exhaustiveness-check": "error" } },
  // + 02 §5's core no-restricted-imports blocks (rules inside each process; the process boundary is tsc -b)
]);
```

- **Type-aware linting earns its cost here.** Every IPC call is async, and a dropped promise is a silent lost action. Stream events are discriminated unions, where `switch-exhaustiveness-check` catches a new `run_updated` variant [inferred]. Cost: lint takes seconds instead of sub-second; acceptable at this size.
- **JS files.** `eslint .` also lints `eslint.config.js`, `scripts/*.mjs` (two exist today) and the stub scripts. None is in a tsconfig, so with `projectService` typescript-eslint would report them "not found by the project service"; `disableTypeChecked` on JS files avoids that [inferred, not run]. Root `*.config.ts` files are in `tsconfig.tools.json`; if the project service doesn't find them through the solution file, add them to `projectService.allowDefaultProject` (Day 1 check).
- expause_web's config (`eslint.config.js`) spreads raw `configs.recommended.rules` onto a hand-built plugin block and ignores `*.config.ts`. Reuse the plugin choice (react-hooks, react-refresh), not the shape: use `typescript-eslint`'s meta package and `defineConfig`. react-hooks 7's flat preset also brings the React Compiler rules [verified, 11].
- **Prettier 3.10.1 with defaults**, run as `prettier --check .` in CI and the pre-commit habit. Not part of `commands.typecheck`, so a formatting nit never fails a harness gate [inferred].
- **Rejected:** Biome 2.6.9 as linter (no typescript-eslint type-aware rules such as `no-floating-promises`, and one lint tool is enough) and oxlint 1.95.0 (JS plugins alpha, no type-aware rules in them [verified, 13]). Using Biome only as formatter would work but adds a second AST tool for no gain over Prettier at this size. Vite's own template switched to oxlint and TS 7 [verified, 15]; revisit both when typescript-eslint supports TS 7.

### 8. Harness gate fit

From the harness docs: `commands.typecheck` runs per implemented unit **and** whole-tree in every Run gates round. `commands.test` runs once per round after typecheck, never per unit [verified, 20]. Each wrapper forwards its arguments to the *last* command of its line, so that line should be a single command [verified, `expause/harness-scripts/test.sh`]. The config values are the wrapper invocations (`bash devscene-scripts/typecheck.sh`, `test.sh`, `start-dev-server.sh`), the form the permission profile allow-lists; a raw command line there is flagged by `init`, `config set` and `doctor` [verified, 20]. The npm scripts below are what the wrapper lines call. A unit runs `<typecheck_cmd>` with no path argument, over the whole tree, so each unit pays `tsc -b` plus type-aware ESLint (a few seconds here) [verified, 21]. The single-file test command comes from each layer's conventions document (`<test_file_cmd>`) [verified, 21]. Gate commands run inside Claude Code's sandbox with `network.strictAllowlist: true` and an empty domain list [verified, 12]. Remote runs skip the QA phase [verified, 22].

Proposed `package.json` scripts:

| Script | Command | Used by |
|---|---|---|
| `dev` | `node scripts/dev.mjs` | Human, Electron with HMR |
| `dev:browser` | `vite --mode browser` | Human; `start-dev-server.sh` wrapper line `npm run dev:browser -- --port "$DEVSCENE_DEV_SERVER_PORT" --strictPort` |
| `build` | `vite build && node scripts/build-main.mjs` | `start`, `dist:*`, `commands.build` |
| `build:browser` | `vite build --mode browser` | Playwright `browser` webServer |
| `typecheck` | `tsc -b` | Fast local check |
| `lint` | `eslint . --max-warnings 0` | — |
| `check` | `tsc -b && eslint . --max-warnings 0` | `typecheck.sh` wrapper line `npm run check` (**`commands.typecheck`**) |
| `test` | `vitest run` | Human, CI. `test.sh` wrapper line is `npx vitest run "$@"` (**`commands.test`**), so forwarded file arguments reach Vitest; `<test_file_cmd>` = `npx vitest run <file>` |
| `test:watch` | `vitest` | Human |
| `test:e2e` | `playwright test --project=browser` | CI job, local |
| `test:electron` | `playwright test --project=electron` | CI job (`xvfb-run` on Linux), local |
| `format` | `prettier --check .` | CI |

`commands.depInstall` stays raw and unwrapped [verified, 20]: `npm ci --ignore-scripts`, which matches 10 §6 item 9. Measured: esbuild and Vite 8 work without install scripts [verified, local]. Electron 45 has no postinstall at all [verified, local package.json].

**Should Playwright be in `commands.test`? No.**
1. Its browsers live outside `node_modules` (`~/.cache/ms-playwright` on Linux, `~/Library/Caches/ms-playwright` on macOS). They need `npx playwright install` (a network fetch) and, on a bare Linux, `--with-deps` system packages. The brief's bar is "no extra system packages", and the gate sandbox can't fetch [verified, 12].
2. Electron E2E needs a display (Xvfb). The repo's CI already apt-installs it for the smoke launch (`.github/workflows/linux-packaging.yml`, "Install launch dependencies").
3. Headless Chromium starting its own sandbox inside the gate sandbox (bubblewrap on Linux) is untested; see Risks.
4. What E2E would add to the gate is mostly covered elsewhere. Component tests plus the contract suite cover behaviour, and the harness QA phase drives browser mode with Playwright MCP locally.

Cost: an E2E regression can reach "ready for review" in an unattended run. Mitigation: a required GitHub check runs `test:e2e` and `test:electron` on every PR (Linux, ~2–3 min) [inferred].

**How the QA agent drives browser mode.** `commands.devServer` → `start-dev-server.sh` runs `npm run dev:browser -- --port "$DEVSCENE_DEV_SERVER_PORT" --strictPort` (expause's wrapper pattern: `expause/harness-scripts/start-dev-server.sh:90`, which exports the port as `DEVSCENE_DEV_SERVER_PORT`). The agent navigates to `base_url` [verified, 19], picks scenarios with `?scenario=`, and finds elements by `data-testid`, the locator convention the ui-tests-plan-reviewer checks [verified, 06-topology §2.5]. Keep `qa.portSeed` at its default (3001), already clear of Vite's 5173. Leave Vite's `strictPort` unset globally, as expause_web's `vite.config.ts` comments explain.

### 9. What to reuse from expause_web

| Item | Reuse? | Why |
|---|---|---|
| `vite.config.ts` port and `strictPort` policy plus comment | **Yes** | The same harness QA port contract |
| `start-dev-server.sh`, `test.sh` wrapper lines (`npx vitest run "$@"`) | **Yes**, pattern | Same harness |
| `src/test/setup.ts` | Yes, trimmed | Use the `jest-dom/vitest` entry; drop the duplicate `expect.extend` |
| Separate `vitest.config.ts` from `vite.config.ts` | Partly | Merge on top of the Vite config instead of duplicating the alias and plugin |
| `environment: 'happy-dom'` | **No** | jsdom, for DOMPurify (§4) |
| `src/test/unit/<layer>/` mirror tree | **No** | Implementers are confined to their layer path; colocate unit and component tests. A `tests` layer for cross-layer suites only: yes, as 02 §4 |
| `eslint.config.js` shape (raw rule spreads, ignoring config files) | **No** | Use the `typescript-eslint` meta config; lint `*.config.ts` via `tsconfig.tools.json` |
| `build.target: 'es2015'`, `define: {'process.env': {}}` | **No** | Electron 45 is Chrome 156; no `process` shim in a sandboxed renderer |
| `globals: true` | No | Explicit `import { describe, it } from "vitest"` keeps the `node` project's types clean [inferred] |
| No Playwright config exists there | — | New here |

## Recommendation for the spike

**Day 1 (renderer, browser mode, Playwright):**
1. Add devDependencies: `vite@8.3.8`, `@vitejs/plugin-react@6.3.0`, `esbuild@0.28.2`, `react@19.3.1`/`react-dom`, `@types/react`, `@types/react-dom`, `dompurify` (version per 05), `vitest@5.1.2`, `jsdom@31.0.1`, `@testing-library/{react,dom,user-event,jest-dom}`, `@playwright/test@1.65.1`, `eslint@10.15.0`, `typescript-eslint@8.74.0`, `eslint-plugin-react-hooks@7.1.1`, `eslint-plugin-react-refresh@0.5.8`, `prettier@3.10.1`, `@types/node`. Pin exact versions (10 §6 cooldown rule). Set `engines.node` to `^22.22.2 || ^24.15.0`, the intersection of jsdom 31.0.1 (`^22.22.2 || ^24.15.0 || >=26`) and Vitest 5 (`^22.12 || ^24`); `>=22.22.2` would admit Node 23.x and 24.0–24.14 [verified, 1].
2. In **one change** (02 §5): replace `tsconfig.json` with the solution file and the per-folder projects (§3), and move `build` to Vite + `scripts/build-main.mjs`. Delete `scripts/copy-renderer-assets.mjs`. Add `vite.config.ts`, `vitest.config.ts` (first check: both projects found, §5) and the scripts table (§8).
3. Write `src/renderer/studio/fixture.ts` with 3 scenarios in `studio/fixtures/` (timed `snapshot`/`upsert`/`status`/`log:lines` events, 03), and the `?scenario=` bootstrap behind `import.meta.env.MODE` in `main.tsx`.
4. Tests: `applyRunsEvent` and domain tests in `src/shared`, 3–5 component tests (board columns, badge, log tail append), `tests/contract/` against the fixture adapter, and 2 Playwright `browser` specs in `tests/e2e/browser/` (board renders; a timed update moves a card).
5. CI: add a `checks` job (`npm ci --ignore-scripts`, `npm run check`, `npm test`, `npm run format`) and an `e2e` job (`npx playwright install --with-deps chromium`, `npm run test:e2e`).

**Day 2 (main, gh, modal, preload):**
1. Adapters with injected `spawn`/`dialog`; the NDJSON reader with chunk-split tests. Stub `gh`/`devscene` scripts and wire fixtures in `tests/stubs/`, and one `tests/integration/` test each.
2. Preload bundled by esbuild, split into `makeStudioApi(invoke)` plus a 3-line entry. Add run (b) of the contract suite (§4): `makeStudioApi` + `registerIpc` with fake ports, joined by the ~10-line `invoke` shim.
3. Two `_electron` smoke specs in `tests/e2e/electron/` (launch + preload surface; board from stub `gh`, dialog stubbed in main), with `ELECTRON_RUN_AS_NODE` deleted from the launch env. Add `xvfb-run npm run test:electron` to the e2e CI job, with network for the first Electron download or a cache of `node_modules/electron/dist` (§4).
4. `scripts/dev.mjs`. If it passes ~100 lines, switch to electron-vite and keep `vite.config.ts` as its renderer section.

Effort: ≈ 0.5 O-d of tooling on Day 1 and ≈ 0.25 O-d on Day 2, beyond the feature code [inferred].

## Answers to the owner's questions

- **Q1 (what Electron provides vs. what we build), tooling slice.** Electron provides no build, test or dev-server tooling. We choose Vite (renderer), esbuild (main/preload bundles, required by the sandbox), Vitest and Playwright. Playwright's Electron support is experimental [verified, 6]. On the tooling side, the renderer really is "like React for the web": a normal Vite + React app, which is exactly why browser mode is cheap.
- **Q2 (start clean?).** Yes for tooling: 02's project references, colocated tests, one `tests/` root and the contract suite cost under a day and become the harness's gates. Skipping them means retrofitting tests across a layout the harness has already mapped.
- **Q5 (performance and security consequences), tooling slice.** jsdom over happy-dom (security of sanitiser tests, slower startup). Real-Chromium E2E for CSP and Trusted Types, since no Node DOM implements Trusted Types. Fixture code excluded from production bundles by a dynamic import behind `import.meta.env.MODE`, plus a bundle assertion. `_electron` tests only on unfused builds. Bundling main cuts the number of files loaded at startup; 04 measures it.
- **Q6 (expause_web as a model).** Reuse the harness wrappers, the port policy and the setup file. Don't reuse happy-dom, the `src/test/unit/<layer>/` mirror tree or the ESLint shape (§9).

## Risks and open questions

1. **Strict CSP vs. the Vite dev server.** `@vitejs/plugin-react` injects an inline Fast Refresh preamble in serve mode, which `script-src 'self'` blocks [inferred]. Plan: relax the CSP only in serve mode (a tiny Vite plugin), and run the CSP/Trusted Types E2E against `vite preview` of a built bundle. 05 owns the policy; confirm on Day 1.
2. **Chromium inside the gate sandbox.** If the owner later wants Playwright in `commands.test`, check whether headless Chromium starts under the harness's bubblewrap/Seatbelt sandbox and whether `~/.cache/ms-playwright` is readable there. Untested.
3. **`_electron` is experimental** and has a live env-var bug on 1.65.1 (#44272, fixed on main) [verified, 7]. Keep the Electron project to 2–3 smoke specs so a Playwright regression costs little.
4. **typescript-eslint pins TS <6.1** [verified, 1]. A TS 6.1 release would block a TS bump until typescript-eslint follows. Pin `typescript` exactly (already done).
5. **The QA agent against Electron itself** (CDP attach) stays unproven (07 §1, risk 1); this file relies on browser mode only.
6. **jsdom 31 needs Node `^22.22.2 || ^24.15.0`** here (with Vitest 5). Developers on older 22.x get an engines warning or failure; CI's `node-version: 22` resolves to the latest 22.x [inferred].
7. **Stub `PATH` on Windows** needs `.cmd` shims (§6); untested until the Windows item.
8. **`tests` project double-checks imported source** (§3). If that ever slows `tsc -b` noticeably, give the cross-layer suites narrower imports (the contract module and public factories only).

## Sources

1. https://registry.npmjs.org (`npm view <pkg> --json`: version, `time[version]`, `peerDependencies`, `engines`) for vite, @vitejs/plugin-react, esbuild, electron-vite, @electron-forge/plugin-vite, vitest, jsdom, happy-dom, @testing-library/*, @playwright/test, @playwright/mcp, eslint, typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh, prettier, @biomejs/biome, oxlint, typescript, electron. Accessed 2026-11-25.
2. https://electron-vite.org/guide/, /guide/cli, /guide/isolated-build; `gh api repos/alex8088/electron-vite` (5.6k stars, last push 2026-10-14) and `/contributors` (alex8088: 354 commits; next: 2). Config shape, `--rendererOnly`, isolated build as the sandbox prerequisite. Accessed 2026-11-25.
3. https://www.electronjs.org/docs/latest/tutorial/sandbox: sandboxed preload `require` loads only `electron`; "use a bundler". Accessed 2026-11-25.
4. https://www.electronjs.org/docs/latest/tutorial/esm: sandboxed preloads have no ESM context; main ESM needs awaited imports before `ready`. Accessed 2026-11-25.
5. https://www.electronforge.io/config/plugins/vite: Vite plugin "marked as experimental" since Forge 7.5. Accessed 2026-11-25.
6. https://playwright.dev/docs/api/class-electron: "experimental support", v21+, `nodeCliInspect` fuse must not be `false`, `evaluate` runs in main. Accessed 2026-11-25.
7. https://github.com/microsoft/playwright/issues/44272: `electron.launch()` fails when `ELECTRON_RUN_AS_NODE` is set; repro on 1.65.1 + Electron 45.4.1; fix on main (1.66.0-next); closed 2026-11-23. Accessed 2026-11-25.
8. https://github.com/microsoft/playwright/releases/tag/v1.65.0 (2026-11-05): Chromium 158. Accessed 2026-11-25.
9. https://github.com/cure53/DOMPurify README (via `gh api`): jsdom "strongly recommend[ed]"; happy-dom "not considered safe… will likely lead to XSS". Accessed 2026-11-25.
10. https://vitest.dev/guide/environment: happy-dom "considered to be faster than jsdom, but lacks some API"; `@vitest-environment` control comments. Accessed 2026-11-25.
11. https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/README.md: `configs.flat.recommended`, React Compiler rules. Accessed 2026-11-25.
12. `/Users/daniel/Work/devscene/docs/cli.md` lines 460, 524, 526: the unattended profile runs every Bash command in the sandbox; `network.strictAllowlist: true`; the domain list ships empty. Read 2026-11-25.
13. https://oxc.rs/docs/guide/usage/linter/js-plugins.html: JS plugins "currently in alpha"; no type-aware rules. Accessed 2026-11-25.
14. https://releases.electronjs.org/releases.json: Electron 45.5.0 (2026-11-24), Node 24.22.3, Chrome 156.0.8078.109. Accessed 2026-11-25.
15. https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts (via `gh api`): solution tsconfig with `noEmit` sub-projects and `tsc -b`; template now on `typescript ~7.0.2` and `oxlint`. Accessed 2026-11-25.
16. https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/ (2026-03-23): `types` defaults to `[]`, `strict` true by default, `baseUrl` and node10 deprecated, `noUncheckedSideEffectImports` default. Accessed 2026-11-25.
17. https://vitest.dev/guide/projects: `test.projects`; `workspace` deprecated since 3.2. Accessed 2026-11-25.
18. https://github.com/vitest-dev/vitest/releases/tag/v5.0.0 (via `gh api`): inline projects extend root by default, shared Vite server, mocks cleared by default, un-awaited async assertions fail, no ancestor config lookup, Node 22 / Vite 6.4 minimum. Accessed 2026-11-25.
19. `/Users/daniel/Work/devscene/plugin/agents/qa-tester.md` lines 63, 90–93: `base_url` per run; storage cleared and page reloaded before each case. Read 2026-11-25.
20. `/Users/daniel/Work/devscene/docs/config.md` lines 139–143: `commands.typecheck` (per unit + whole tree per round, `<none>` sentinel), `commands.test` (once per round), `commands.devServer`; all three hold the wrapper invocation `bash <scriptsDir>/<name>.sh`, while `commands.depInstall` is raw. Read 2026-11-25.
21. `/Users/daniel/Work/devscene/plugin/instructions/unit_loop_core.md` line 21: `<test_file_cmd>` comes from the layer's conventions document; line 162: a unit runs `<typecheck_cmd>` with no path argument, over the whole tree. Read 2026-11-25.
22. `/Users/daniel/Work/devscene/docs/remote-execution.md` line 242: remote runs skip the interactive-test phase. Read 2026-11-25.
23. Local repo: `package.json`, `tsconfig.json`, `scripts/copy-renderer-assets.mjs`, `src/main/main.ts`, `electron-builder.yml`, `.github/workflows/linux-packaging.yml`, `node_modules/electron/{index.js,package.json}` (no `scripts`; `index.js:25-52` `getElectronPath` downloads only when `path.txt` or the `dist/` binary is missing, and exports a path string). Read 2026-11-25.
24. `/Users/daniel/Work/expause/expause_web/{vitest.config.ts,vite.config.ts,eslint.config.js,package.json,src/test/setup.ts,src/test/README.md}`; `/Users/daniel/Work/expause/devscene.config.json`; `/Users/daniel/Work/expause/harness-scripts/{test.sh:57,typecheck.sh:57,start-dev-server.sh:90}`. Read 2026-11-25.
25. Local measurements (scratchpad, 2026-11-25): (a) `tsc -b` with TS 6.0.3 on a solution of `noEmit` projects; a DOM reference in the shared project fails with TS2584; (b) jsdom 31.0.1 vs happy-dom 21.0.4 on Node 22.23.2: neither has `trustedTypes`, and only happy-dom has `ResizeObserver`/`IntersectionObserver`/`matchMedia`; (c) `npm i --ignore-scripts esbuild@0.28.2 vite@8.3.8`: both run; (d) TS 6.0.3 on 02's layout (`scratchpad/fix06-ts/setup.sh`): shared `composite` + `emitDeclarationOnly`, process projects `composite` + `noEmit`, non-composite `tests` project importing main and renderer source → `tsc -b` exit 0, no `.js` emitted; renderer→main import → TS6307; `document` in shared → TS2584; the same `tests` project made `composite` → TS6307 on each cross-layer import.
26. `@typescript-eslint/eslint-plugin@8.74.0` `dist/configs/flat/recommended-type-checked.js:35,60` (`no-floating-promises` and `no-unused-vars` set to `error`), as checked by the review's `npm pack`. 2026-11-25.
27. Sibling research files (reviewed): `02-layered-architecture.md` §2–§5 and Risks (tree, `tests` row, project references, build in the same change, `nodenext` question); `03-reactive-data-flow.md` lines 11, 117, 289 (push protocol, fixture emits `snapshot`/`upsert`); `05-security-architecture.md` lines 204, 222 (XSS corpus in Playwright on `vite preview`). Read 2026-11-25.
