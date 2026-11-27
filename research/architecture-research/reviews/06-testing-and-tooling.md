# Review — 06-testing-and-tooling.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

The facts are strong. I re-checked every version, date, peer range and engine in §1 against the npm registry today, and all of them match: Vite 8.3.8, esbuild 0.28.2, electron-vite 6.0.0, TS 7.0.2, typescript-eslint 8.74.0 (`typescript >=4.8.4 <6.1.0`), Vitest 5.1.2, jsdom 31.0.1 (`^22.22.2 || ^24.15.0 || >=26`), Playwright 1.65.1, ESLint 10.15.0, react-hooks 7.1.1 and Prettier 3.10.1. The DOMPurify quote, the Playwright `nodeCliInspect` note, issue #44272, the Vitest 5 release notes, the electron-vite bus factor, Forge's "experimental" label and the local `node_modules/electron/index.js` behaviour all hold.

The problems are in consistency with 02 and in one internal contradiction:
- 06 drops 02's `tests` layer and renames its folder.
- 06's TypeScript layout is not the one 02 relies on, and I measured that it lets the renderer import main code without an error.
- The "unused imports won't fail typecheck" rationale is false under 06's own ESLint config.

The contract suite's second run, (b), is more machinery than its payoff justifies on Day 2.

## Must fix

**M1. The cross-layer test location and the `tests` layer contradict 02 without saying so.**
- **Location:** TL;DR bullet 4 ("Cross-layer suites … go in `test/` and `e2e/`"), §4 and §6 (`test/stubs/bin`, `test/setup-dom.ts`), and the §9 row "`src/test/unit/<layer>/` mirror tree and a `tests` harness layer | **No**".
- **Problem:** 02 §3 and §4 propose one top-level `tests/` directory as its own harness layer, `{ "name": "tests", "path": "tests", … }`, and that layer holds the Playwright E2E and the cross-process tests. 06 uses two directories with different names (`test/`, `e2e/`). Its §9 also reads as a rejection of a `tests` layer altogether, so those suites would fall to the catch-all `general` layer.
- **What both files agree on:** the colocation premise itself is right and matches 02. `plugin/agents/layer-implementer.md:48` says "Implement only inside the dispatched `layers[].path` … stop and tell the orchestrator", so unit tests must sit in the layer they test. The disagreement is only about where the cross-layer suites live.
- **Evidence:** `02-layered-architecture.md` lines 95 and 126; `/Users/daniel/Work/devscene/plugin/agents/layer-implementer.md:48`.
- **Fix:**
  - Use 02's single `tests/` directory: `tests/e2e/`, `tests/contract/`, `tests/integration/`, `tests/stubs/bin/`, `tests/setup-dom.ts`.
  - Reword the §9 row to "`src/test/unit/<layer>/` mirror tree: **No**, colocate unit tests. A `tests` layer for cross-layer suites only: yes, as 02 §4."
  - Update the Vitest `include` globs, the `tsconfig.tools.json` include and the Playwright `testDir` to match.
  - If 06 really wants these suites in the catch-all layer, it has to argue that against 02's row explicitly, so 07 can choose.

**M2. The §3 TypeScript layout is not 02's, and as written it loses 02's cross-process check.**
- **Location:** §3 ("Overlapping `include`s are fine with `noEmit`, so there's no `composite` or declaration emit to manage") and TL;DR bullet 2.
- **What 02 does:** it builds its main boundary enforcement on project references with `composite` + `emitDeclarationOnly`. In that setup, a renderer→main import fails with TS6307 (02 §5, the "TS project references" row). 02 also says `commands.typecheck` becomes `tsc -b`.
- **What 06 does:** sub-projects use `noEmit` with no `composite`, and their `include`s overlap. In that setup, a file a project imports is simply pulled into that project.
- **Evidence:** I measured it with TS 6.0.3 in a scratch dir. First, a solution of two `noEmit` projects: `tsc -b` exits 0, and adding `document` to the shared folder gives TS2584 (exit 2). That confirms 06's claim. Then I added `r/bad.ts` importing `../m/svc` (a file in no project's `include`): `tsc -b` **exits 0**. Under 06's layout a renderer→main import compiles unless the main file happens to use Node globals.
- **Fix:** pick one layout and state the trade.
  - Option 1: adopt 02's `composite` + `emitDeclarationOnly` + references.
  - Option 2: keep `noEmit` and say outright that cross-process imports are caught only by 02's ESLint `no-restricted-imports` blocks, which then have to include a renderer→`src/main/**` and a main→`src/renderer/**` pattern.

  Either way, edit 06's sentence "domain purity is enforced at compile time for free" so it claims only the `lib`/`types` purity check, not the process boundary.

**M3. The rationale "let ESLint report unused locals so a half-finished unit doesn't fail typecheck" contradicts 06's own gate.**
- **Location:** §3 Flags ("Skip `noUnusedLocals`/`noUnusedParameters` … so a half-finished unit doesn't fail typecheck on an unused import") together with §8 (`commands.typecheck` = `tsc -b && eslint . --max-warnings 0`).
- **Problem:** `recommendedTypeChecked` sets `@typescript-eslint/no-unused-vars: 'error'`, and ESLint is inside `commands.typecheck`, which runs per unit. An unused import therefore fails the gate anyway.
- **Evidence:** `@typescript-eslint/eslint-plugin@8.74.0` `dist/configs/flat/recommended-type-checked.js:60`.
- **Fix:** choose one.
  - Option 1: keep the gate strict and delete the rationale. "Unused code fails the per-unit gate, through ESLint" is a fine policy.
  - Option 2: downgrade the rule to `warn` and drop `--max-warnings 0` from `check`.

  I recommend option 1, because the harness implementer finishes each unit.

## Should fix

**S1. The TL;DR says `commands.typecheck → npm run check`. The config value has to be the wrapper invocation.**
- **Problem:** `docs/config.md:139-142` says `commands.typecheck`, `commands.test` and `commands.devServer` hold `bash <scriptsDir>/typecheck.sh` (or `test.sh`, `start-dev-server.sh`), "the form the permission profile allow-lists". A raw command line is stored, but `init`, `config set` and `doctor`'s `command-wrappers` check flag it. §8's table already says "(via `typecheck.sh`)", but the TL;DR and the prose read as if the raw command is the value.
- **Evidence:** `/Users/daniel/Work/devscene/docs/config.md:139-143`; `/Users/daniel/Work/expause/harness-scripts/test.sh:57` (wrapper line `cd expause_web && npx vitest run "$@"`).
- **Fix:** replace the TL;DR bullet with this text:
  > `commands.typecheck` = `bash devscene-scripts/typecheck.sh`, whose wrapper line is `npm run check`. `commands.test` = `bash devscene-scripts/test.sh`, wrapper line `npx vitest run "$@"`. `commands.devServer` = `bash devscene-scripts/start-dev-server.sh`, wrapper line `npm run dev:browser -- --port "$PORT" --strictPort`. `commands.depInstall` stays raw: `npm ci --ignore-scripts`.

  Also add that a unit runs `<typecheck_cmd>` "with no path argument: the whole tree" (`plugin/instructions/unit_loop_core.md:162`). The per-unit cost is therefore whole-tree `tsc -b` plus type-aware ESLint every time, which is a few seconds at this size. Say so.

**S2. Proportion: running the IPC contract suite twice costs more than it buys on Day 2.**
- **Location:** TL;DR bullet 5, the §4 "IPC contract" row, Day 2 step 2, and Risk 7.
- **What run (b) needs:** a hand-written in-memory IPC pair, `vi.mock('electron')` for both `contextBridge`/`ipcRenderer` and `ipcMain`, and `structuredClone` on every hop.
- **Why it adds little:** channel names and payload types already come from one shared contract module, so `tsc -b` catches most preload/main drift. Clone-ability and sender checks are exactly what (b) can't prove faithfully, and the `_electron` smoke tests cover them anyway. Risk 7 itself warns that the pair can become "the framework the brief warns against".
- **Fix:**
  - Day 1: run the suite against the fixture adapter only. That is the high-value LSP check 02 asks for.
  - Day 2: make the preload a thin `makeStudioApi(invoke)` factory, so it unit-tests with a fake `invoke` and needs no `electron` mock. Test the main handlers directly, by calling the registered handler with `structuredClone`d arguments.
  - Promote to the full twin-run only if a preload/main mismatch actually escapes.

  This drops the in-memory pair, Risk 7 and the `vi.mock('electron')` row.

**S3. The jsdom rationale overstates what the unit DOM proves, and 05 already runs the corpus in Chromium.**
- **Location:** TL;DR bullet 3 ("05's sanitiser tests must run on a DOM that doesn't lie") and the §4 note.
- **What checks out:** the DOMPurify quote is verbatim and current. README: happy-dom "**are not considered safe** at this point … will likely lead to XSS"; jsdom is "**strongly recommend**[ed]".
- **The problem:** the quote is about *server-side* sanitising. And 05 §"Tests" places the XSS corpus in **Playwright on `vite preview`** (05 lines 204 and 222), not in Vitest. Even jsdom parses differently from Chromium, so mutation-XSS results from jsdom are not a security sign-off.
- **Evidence:** `gh api repos/cure53/DOMPurify/readme`, lines 98–102; `05-security-architecture.md:204,222`.
- **Fix:** keep jsdom, but restate the reason:
  > Component tests that render `SafeMarkdown` must not go green on a DOM DOMPurify calls unsafe. Security sign-off for sanitising comes only from 05's Chromium corpus.

  Drop "05's sanitiser tests must run on" jsdom.

**S4. The fixtures location and the stream format disagree with 02 and 03.**
- **Location:** §6, the tree with top-level `fixtures/` and `{"t":…,"line":{"type":"snapshot"|"run_updated"}}`.
- **The conflicts:**
  - 02 §3 puts the fixtures in `src/renderer/studio/fixtures/` (inside the renderer layer).
  - 03 (lines 198 and 241) describes `FixtureLive` replaying "`snapshot` + timed `patch` + log `append` events".
  - A top-level `fixtures/` sits in no tsconfig `include` in §3 and in the catch-all layer.
- **A related runtime gap:** the stub binaries are meant to read the same TS scenarios under plain Node. Node's type stripping needs explicit `.ts` import specifiers, but `moduleResolution: "bundler"` code is extensionless, so a scenario that imports `contract/` won't load in a stub. The unit tests can't catch this, because Vitest resolves the imports.
- **Fix:**
  - Follow 02's placement, or argue for a shared fixtures location (it is cross-layer by nature, so the `tests` layer is a candidate).
  - Align the event vocabulary with 03.
  - Have the stubs read a JSON export that a build step generates (or `tsx`), or require `.ts` extensions with `allowImportingTsExtensions` in the files they load.
  - This also answers 02's open question at its line 246 (shared under `nodenext` vs `bundler`). Since main is bundled by esbuild, `bundler` everywhere is fine, but say it explicitly as the answer to 02.

**S5. The type-aware ESLint config will error on JS and config files as written.**
- **Problem:** `projectService: true` with `recommendedTypeChecked` over `eslint .` will lint `eslint.config.js`, `scripts/*.mjs` (two exist today: `copy-renderer-assets.mjs`, `require-signing-env.mjs`) and the stub scripts. None of them is in a tsconfig (`tsconfig.tools.json` has no `allowJs`), so typescript-eslint reports "was not found by the project service". [inferred from typescript-eslint behaviour; not run]
- **Fix:** add `{ files: ["**/*.{js,mjs,cjs}"], extends: [tseslint.configs.disableTypeChecked] }`, or `parserOptions.projectService.allowDefaultProject: ["*.js", "scripts/*.mjs"]`.
- **Also:**
  - The explicit `no-floating-promises: "error"` is already in `recommendedTypeChecked` (`recommended-type-checked.js:35`), so it is redundant but harmless.
  - The sketch's comment "02's boundary config (eslint-plugin-boundaries 7.4.4 or dependency-cruiser 18.9.0)" names the two tools 02 *rejected*. 02 picked core `no-restricted-imports` (02 §5). Fix the comment.
  - Fix the Biome rejection reason in the same way: there is no "boundary plugin". The real reasons are typescript-eslint's type-aware rules and keeping one lint tool.

**S6. The `electron` import claim is right, but it omits the "if missing" condition.**
- **What holds:** `node_modules/electron/index.js` exports `getElectronPath()`, a string. It calls `downloadElectron()` only when `path.txt` or the binary under `dist/` is missing. `package.json` has no `scripts` (verified locally, 45.5.0).
- **Fix:** write "downloads the binary on first import *if it isn't there yet* (always the case after `npm ci --ignore-scripts` in a fresh run copy)". Add one consequence the file misses: the Playwright `electron` CI job and `npm start` trigger that same lazy download, so the e2e job needs network on its first Electron launch, or a cache of `node_modules/electron/dist`.

## Nice to have

- **N1.** Write `engines.node` as `^22.22.2 || >=24.15.0`, not `>=22.22.2`. The latter admits Node 23.x and 24.0–24.14, which jsdom 31.0.1 rejects (npm `engines`, checked today).
- **N2.** §8: "Set `qa.portSeed` (default 3001) away from Vite's 5173." The default is already away from it, so either drop the sentence or say "keep the default".
- **N3.** §8 point 1: the Playwright cache path is `~/.cache/ms-playwright` on Linux only. On macOS it is `~/Library/Caches/ms-playwright`.
- **N4.** Native modal: cite Playwright's own "Mocking native dialogs" note in the Electron class doc, which prescribes exactly the `electronApp.evaluate(({ dialog }) => …)` pattern. Also note that adapters must call `this.dialog.showMessageBox(…)` through the injected object, not a captured function reference, or the E2E stub won't take effect.
- **N5.** The §5 Vitest sketch (merging a function-form Vite config with `root: "src/renderer"`, then `test.root: "."` with inline projects that now inherit the root config) is unmeasured. Tag it [inferred] and make "Vitest discovers both projects" the first Day 1 check.
- **N6.** The Day 1 dependency list omits `@types/react-dom` and `dompurify` (05's).
- **N7.** §8 point 3 and Risk 1: on Windows, `wsl.exe`/`gh` stubs on `PATH` need `.cmd` shims. Worth one line, since `Direct | Wsl` is in scope.

## Checks performed (2026-11-25)

- **npm registry:** `npm view` for vite, esbuild, electron-vite, typescript, vitest, jsdom, happy-dom, @playwright/test, eslint, eslint-plugin-react-hooks, prettier, @testing-library/jest-dom, @testing-library/react, @vitejs/plugin-react, @electron-forge/plugin-vite, oxlint, @biomejs/biome and typescript-eslint@8.74.0 (peers). Every value in §1 matched.
- **Packages and repos via `gh`:**
  - `npm pack` of eslint-plugin-react-hooks 7.1.1 (README shows `configs.flat.recommended`), eslint-plugin-react-refresh 0.5.8 (`configs.vite`) and @typescript-eslint/eslint-plugin 8.74.0 (recommended-type-checked rules).
  - `gh api` for the DOMPurify README; vitest v5.0.0 release notes; Playwright issue #44272 (closed 2026-11-23, PR #44273, reproduced on 1.66.0-next) and v1.65.0 notes (Chromium 158.0.8127.18); `alex8088/electron-vite` contributors (354/2/1/1, last push 2026-10-14); Vite `template-react-ts` (TS ~7.0.2, oxlint, `noEmit` app tsconfig).
- **Web pages:** playwright.dev/docs/api/class-electron (v21+, `nodeCliInspect` known issue, dialog mocking); electronforge.io Vite plugin page (experimental since 7.5.0); releases.electronjs.org (45.5.0, 2026-11-24, Node 24.22.3, Chrome 156.0.8078.109).
- **Local:**
  - devscenestudio: `node_modules/electron/{index.js,package.json}`, `package.json:14`, `tsconfig.json:7-12`, `.github/workflows/linux-packaging.yml:30,42-43`.
  - devscene: `docs/config.md:139-143`, `plugin/agents/layer-implementer.md:48`, `plugin/instructions/unit_loop_core.md:20-21,161-162`, `docs/cli.md:460,524,526`, `plugin/agents/qa-tester.md:63,90-93`, `docs/remote-execution.md:242`.
  - expause: `harness-scripts/test.sh`, `start-dev-server.sh`, `expause_web/vite.config.ts`, `expause_web/vitest.config.ts:10`.
- **Scratch experiment** (TS 6.0.3, in the session scratchpad):
  - `noEmit` solution builds (exit 0).
  - A DOM reference in shared fails with TS2584 (exit 2).
  - A renderer file importing an un-included "main" file builds with exit 0 (the M2 finding).

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1 — Applied.** Re-checked `layer-implementer.md:48` and reviewed 02 §3–§4. All cross-layer suites now sit under one `tests/` root (`contract/`, `integration/`, `e2e/{browser,electron}/`, `stubs/`, `setup-dom.ts`), 02's `tests` layer. The §9 row is reworded, and the Vitest globs, `tests/tsconfig.json` and Playwright `testDir` are updated.
- **M2 — Applied (option 1, 02's layout).** Reproduced on TS 6.0.3: process projects with `composite` + `noEmit`, shared with `emitDeclarationOnly` → renderer→main gives TS6307 and `document` in shared gives TS2584, with no `.js` emitted. New finding: the `tests` project must *not* be composite (composite gives TS6307 on its cross-layer imports, measured). §3 says this and no longer claims process-boundary checks from `noEmit` alone.
- **M3 — Applied (option 1).** The "half-finished unit" rationale is removed. Unused code now fails the per-unit gate through ESLint, by design. The redundant explicit `no-floating-promises` is dropped.
- **S1 — Applied.** Verified `config.md:139-142` and `unit_loop_core.md:162`. The TL;DR and §8 give the wrapper invocations and their wrapper lines, and state the whole-tree cost per unit. The dev-server line uses `DEVSCENE_DEV_SERVER_PORT`, as expause's wrapper exports it (`start-dev-server.sh:90`), not `$PORT`.
- **S2 — Partially applied.** The `vi.mock('electron')` row, the in-memory IPC pair and Risk 7 are gone. Day 1 runs the suite against the fixture adapter only. Run (b) is kept on Day 2 in a smaller form: `makeStudioApi(invoke)` plus 02's injected `registerIpc(ipcMain, …)`, joined by a ~10-line `invoke` shim. That keeps 02 §6's LSP row at almost no cost. The file also says to drop (b) if it isn't worth it.
- **S3 — Applied.** The jsdom reason is restated: component tests must not go green on a DOM DOMPurify calls unsafe. Sanitiser sign-off comes only from 05's Chromium corpus (05:204,222).
- **S4 — Applied.** There are now two fixture sets. StudioApi scenarios with 03's `snapshot`/`upsert`/`remove`/`status` + `log:lines` events live in 02's `src/renderer/studio/fixtures/`. Wire-format `gh` JSON and harness NDJSON live in `tests/stubs/` as plain data files, so the stubs never load TS. §2 answers 02's open question: `bundler` resolution everywhere.
- **S5 — Applied.** Added `disableTypeChecked` for JS files and an `allowDefaultProject` fallback (still [inferred], not run). The boundary comment now points to 02's core `no-restricted-imports`. Biome is rejected for the real reason: no type-aware rules, and one lint tool is enough.
- **S6 — Applied.** Re-read `index.js:25-52`. The file now says "downloads if missing", and the e2e CI job needs network or a cached `node_modules/electron/dist`.
- **N1 — Applied, tightened.** `engines.node` is `^22.22.2 || ^24.15.0`: jsdom also excludes 25.x, and Vitest 5 allows only `^22.12 || ^24`.
- **N2 — Applied.** "Keep the default".
- **N3 — Applied.** Linux and macOS cache paths are both listed.
- **N4 — Applied.** Cites Playwright's dialog-mocking note and adds the call-through-the-injected-object caveat.
- **N5 — Applied.** The §5 sketch is tagged [inferred], and "both projects found" is the first Day 1 check, with a fallback.
- **N6 — Applied.** Added `@types/react-dom` and `dompurify` (version per 05).
- **N7 — Applied.** Added the `.cmd` shims line in §6 and as Risk 7.
