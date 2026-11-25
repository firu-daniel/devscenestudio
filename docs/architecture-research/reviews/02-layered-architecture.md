# Review — 02-layered-architecture.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

The file is well scoped and decision-oriented, and most of its load-bearing claims hold up when re-run. I re-ran harness detection with the devscene 0.7.1 CLI (`cli/dist/cli.js init --dry-run`) on a scratch copy of the proposed tree. It picks `flat:fallback`, and `src/api/` or `src/handlers/` each select `api-service`. The proposed 6-row `layers` JSON is accepted by `config set layers` (schema: `name` pattern `^[a-z][a-z0-9-]*$`, `contains path "."`). After applying it, `doctor` gives `layer-profile` PASS and `layer-drift` WARN for exactly `build, scripts, vm`. TS6307 and TS6310 reproduce on TS 6.0.3. ESLint 10.15.0 `no-restricted-imports` flags `../adapters/ipc.js`. All npm versions and peer ranges match, and so do the 186 use-case files and the `fetchFeedUseCase` behaviour.

There are two must-fix problems. The expause_web "dependency direction" claim is the opposite of what that repo does. And the proposed TS setup quietly breaks the current `tsc`-only build. The should-fix items cover the cost of a one-file `preload` layer, the red-tree problem when a cross-layer contract changes, a wrong `layer-drift` remedy, and some trimming of the pattern table.

## Must fix

**M1 — expause_web's dependency direction is misdescribed (TL;DR bullet "expause_web", §8 row 1, Q6 answer).**
- **Problem:** The file says expause_web has "Three layers, dependencies pointing inward" and that Studio should "carry over the direction of dependencies". expause_web's own rule is the reverse.
- **Evidence:** `ARCHITECTURE.md:180-192` draws `Presentation → Domain → Data` and lists the rules "Presentation can import from Domain and Data" (`:189`), "Domain can import from Data" (`:190`) and "Data should NOT import from Presentation or Domain" (`:191`). The code follows this: 193 files under `src/domain/` import `@/data` (`grep -rl "from '@/data" src/domain | wc -l`).
- **Why it matters:** That is classic top-down layering, with the domain depending on data. Studio's proposal is dependency-inverted: `shared/domain` imports nothing, and main's `app/` sees only `ports/`. So the one thing the file says carries over is the thing that does not. This is an answer to owner question 6.
- **Fix:** Row 1 should read: "Three layers, top-down (`Presentation → Domain → Data`; domain imports data, `:180-191`) | **No — inverted here.** | Studio points dependencies *at* the domain (ports in main, `StudioApi` in the renderer), so adapters depend on domain types, not the reverse. What carries over is the *idea* of named layers with written import rules." Then update the TL;DR bullet ("carry over … domain types kept apart from wire DTOs, and remappers") and the Q6 answer ("Its feature folders and DTO→domain remapping carry over; its dependency direction does not") to match.

**M2 — The project-references setup breaks today's `tsc`-only build (§5 TS row, Day 1 step 4, Risks).**
- **Problem:** The file recommends `emitDeclarationOnly` with an outDir cache and `typecheck: tsc -b`, and turns the root `tsconfig.json` into a solution file. It never says what produces the JavaScript afterwards.
- **Evidence:** In a scratch test with the same shape (TS 6.0.3), `tsc -b` emitted only `.d.ts` and `.tsbuildinfo`, with zero `.js` files. `tsc -p tsconfig.json` on the solution file (`files: []` plus `references`) exits 0 and emits nothing. Today's `package.json` runs `"build": "tsc -p tsconfig.json && …"` and `"main": "dist/main/main.js"`. Following Day 1 step 4 literally therefore makes `npm run build` / `npm start` / `dist:mac` silently ship a stale or empty `dist/`.
- **A second problem:** main's runtime imports of `src/shared/**` need emitted JS laid out so that the relative `../shared/…js` specifiers still resolve.
- **Fix:** Add this to §5 and to Day 1 step 4: "`tsc -b` becomes the **typecheck only**. On the same day, the build must move to a bundler: electron-vite or esbuild/Vite, per 01 Risk 1 and 06, which also bundles the preload. The alternative is that every project emits JS into `dist/{shared,main,preload,renderer}` with `rootDir`/`outDir` mirroring `src/`. Do not merge the tsconfig split before the build change."

## Should fix

**S1 — Is a one-file `preload` worth its own harness layer? (§4 "Why these units", JSON)**
- **What the file argues:** The preload is one ~30-line file that "changes only when a verb is added (one line)". As its own layer, it adds a task to every new IPC verb: shared → main → **preload** → renderer.
- **Where the payoff is overstated:** The claimed payoff is a dedicated reviewer. But per-unit `layer-reviewer` runs only in the semi-autonomous flows and the autonomous user-review flow, never in the autonomous plan flow or supervised flows (devscene `plugin/agents/layer-reviewer.md` description). The end-of-branch `branch-reviewer` reviews the whole diff against every conventions doc anyway. A catch-all (`.`) dispatch already reads **every** conventions document and has the whole map in scope (`plugin/agents/layer-implementer.md:17,82`).
- **Fix:** Weigh the two options explicitly and pick one.
  - (a) **Drop the `preload` row.** Preload work routes to `general`, and `conventions.md` gets a short "Preload (sandboxed facade)" section. You accept one `layer-drift` warning for `src/preload` (it is a sibling under `src/`, which `doctor` inspects, `cli.md` §7). Each new verb then costs 3 typed tasks plus a trivial catch-all edit, or the main task's plan folds the one-liner into a `general` follow-up.
  - (b) **Keep it,** and say plainly that the reason is security focus (the whole renderer-reachable surface reviewed against `preload.md`), not reviewer independence.
- **My recommendation:** (a) is the proportionate default at this size. If 01/06 bundle the preload, a facade generated from the contract's channel table removes the per-verb preload edit entirely, which strengthens (a).

**S2 — Cross-layer contract changes leave the tree red between tasks (§4 "A typical feature … three tasks").**
- **Problem:** `StudioApi` lives in `shared`, but it is implemented in three other layers:
  - preload (`satisfies StudioApi`, §6 Facade)
  - main (handlers checked with `satisfies`, 01 TL;DR)
  - renderer (`studio/fixture.ts`)
- **Consequence:** A shared task that adds a verb makes `tsc -b` fail in up to three other projects until their tasks land. Every unit runs the whole-tree `commands.typecheck` (`docs/config.md` `commands.typecheck` row; 10-recommendation:190). The implementer records such failures "outside this unit's change" as an evidence downgrade (`layer-implementer.md:154,181`). So every new verb produces a run of downgraded units.
- **The example also undercounts:** a new *verb* is four tasks, not three.
- **Fix:** Add a bullet to §4 that states the 4-task count and the expected intermediate red typecheck. Name the mitigation chosen: accept the downgrades, or have the plan writer order the shared task's contract edit last among the producers. The latter is impossible under bottom-up order, so in practice the choice is "accept, and say so in `shared.md`".

**S3 — The `layer-drift` remedy is wrong, and the claim is marked "not run" (§4 last bullet; Risks bullet 5).**
- **Problem:** The file says "Accept it or record a `detection.review` verdict." But `cli.md` §7 (line 660) says `layer-drift` reads `detection.review` "for reporting, never as a gate: a recorded verdict does not silence it". The review record clears `layer-profile`, not `layer-drift`.
- **Evidence:** I ran it. In a scratch repo, `init` followed by `config set layers '<§4 json>'` and then `doctor` gave:
  - `layer-profile` PASS
  - `layer-drift` WARN: `build, scripts, vm`
  - `setup-analysis` WARN: the five new conventions docs are missing until `/devscene:analyze` writes them
- **Fix:** "`doctor` will warn (`layer-drift`) that `build/`, `scripts/`, `vm/` route to the catch-all, and that warning is permanent. Add them as layers or accept the warning; a `detection.review` verdict does not clear it. `setup-analysis` warns until `/devscene:analyze` writes the five new conventions docs. [verified: scratch `init` + `config set layers` + `doctor`, devscene 0.7.1]". Drop Risks bullet 5.

**S4 — TS6310 is overstated (§5 TS row, TL;DR).**
- **Problem:** "`composite` + `noEmit` fails (TS6310)" is true only for a **referenced** project.
- **Evidence:** In a scratch test on TS 6.0.3, a leaf composite `noEmit` project referencing an emitting `shared` built with exit 0. A `noEmit` `shared` referenced by `main` gave "TS6310: Referenced project … may not disable emit".
- **Fix:** "Only `shared` (the referenced project) needs `emitDeclarationOnly` with an outDir cache. The leaf projects `main`, `preload` and `renderer` may stay `noEmit` if a bundler builds them (M2)."

**S5 — The pattern table is mostly proportionate but carries padding and one unstated cost (§6).**
- **Remove filler:** The rows "OCP | — | — | Only via the Strategy above" and "Observer | … | see 03 | —" carry no content. Fold them into one line under the table.
- **State the LSP cost:** "LSP, checked by tests: shared contract test suite" means running the same suite against the IPC adapter, which needs a running Electron (or a mocked `window.studio`, which then tests nothing). Name the cost, or restate it as "the fixture adapter and the preload both `satisfies StudioApi`; behavioural parity is checked by the Electron-mode Playwright smoke in 06".
- **Apply the file's own rule to ports:** "add a port only where a second implementation or a test fake exists **today**". `Logger` and `GitClient` in §3's `ports/` list have no named second implementation. Either name the fake, or say they are plain modules until one exists.
- **Simplify the builder:** A fluent builder (`gh(...).repo(r).json(fields)`) is more API than one argv builder needs. A typed function (`ghArgv({ cmd, repo, json })`) gives the same single enforcement point.

## Nice to have

**N1 — Citation line drift.**
- devscene `task-plan-writer.md:104` should be `:105`; the bottom-up/catch-all-last sentence is on 105.
- expause_web `ARCHITECTURE.md:184` should be `:189`, and `:176-189` should be `:180-192`.
- `presets.ts:620-626` is the `layered-clean-arch`/`api-service` switch, not the flat result. Cite `cli.md` §4 row 17 plus `PRESET_TEST_ROOTS` (`presets.ts:~559`, no `flat` entry, hence no `tests` row).

**N2 — Dates and the TypeScript 7 line.**
- Source 4 / §5: ESLint 10.15.0 was **published** 2026-11-13. The 2026-11-16 date is the registry `modified` time.
- Risks bullet 1: npm's `latest` tag for TypeScript is now 7.0.2, so 6.0.3 is a deliberate pin behind `latest` and should be stated as one. 7.1.0-beta (2026-10-20) exists, and dependency-cruiser already admits `>=7.1.0 <8`. typescript-eslint 8.74.0 still caps at `<6.1.0`, which is the binding constraint.

**N3 — `eslint-plugin-import-x` is not considered.** It is at 4.18.1 and active, last modified 2026-11-09. Its `no-restricted-paths` matches **resolved** paths by zone, which removes §5's caveat that `no-restricted-imports` "matches the specifier string". One line in the tools table would close the comparison. Skipping it is still fine at this size.

**N4 — fetchFeedUseCase wording.** The use case *logs* the error (`appLogger.error`, line 34) before returning `{ medias: [], hasMore: false }`. Write "logs it and returns an empty list, so callers cannot tell a failure from an empty feed" rather than "swallows".

**N5 — Cross-file path naming.** 01 (`contract/studio-api.ts`) and 03 (`contract/studio-live.ts`) sketch a top-level `contract/`, while this file places the IPC contract at `src/shared/contract/`. Flag it for 07 so the synthesis uses one path.

**N6 — Fixtures sit in the renderer layer, e2e tests in the tests layer.** Fixture scenarios live in `src/renderer/studio/fixtures/` and Playwright specs in `tests/`. A new browser-mode scenario is therefore two tasks. That is acceptable, but worth one sentence in §4.

**N7 — Verified claims can be upgraded.** The `init`/`flat`, `api-service`, layer JSON validity and `layer-drift` claims are now reproducible. Cite "scratch `init --dry-run` on the proposed tree, devscene 0.7.1" alongside the source line numbers.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1 — Applied.** Re-checked: `ARCHITECTURE.md:183-191` is top-down and 193 `src/domain` files import `@/data`. §8 row 1, TL;DR and Q6 now say the direction is inverted here; only named layers with written rules carry over.
- **M2 — Applied.** Reproduced: `tsc -b` emits zero `.js`. §5 adds a "Build dependency" note, Day 1 step 4 lands the tsconfig split and the bundler in one change, and Risks names it. Tool pick left to 07.
- **S1 — Applied (option a).** Verified the `layer-reviewer` flow scope, that the catch-all reads every conventions doc (`layer-implementer.md:17,82`), and that `layer-drift` reaches `src/preload`. The `preload` row is dropped, preload rules go into `conventions.md`, and a generated facade removes the per-verb edit if the preload is bundled. Reconsider if 05 wants a dedicated reviewer.
- **S2 — Applied.** Verified `layer-implementer.md:154`. §4 adds a bullet: a new verb leaves the typecheck red between tasks, so accept the evidence downgrades and say so in `shared.md`.
- **S3 — Applied.** Re-ran `init` + `config set layers` (5-row JSON) + `doctor` on devscene 0.7.1: `layer-drift` WARN `build, scripts, vm, src/preload`, `setup-analysis` WARN, `layer-profile` PASS. Remedy corrected, Risks bullet removed.
- **S4 — Applied.** Reproduced: TS6310 fires only for a referenced `noEmit` project, and a leaf `noEmit` project builds.
- **S5 — Partially applied.** OCP/Observer rows folded into one line. Builder changed to a typed function. Logger is now a plain module, not a port. `GitClient` stays a port: §1 already names its fake (`app/` unit tests). LSP cost restated with a correction: 06's suite runs preload + main handlers over an in-memory IPC pair, so it needs no Electron and is not "a mocked `window.studio` that tests nothing".
- **N1 — Applied.** Citations corrected to `task-plan-writer.md:105`, `ARCHITECTURE.md:183-191`/`:189`, and `cli.md` §4 row 17 + `presets.ts:556-567`.
- **N2 — Applied.** ESLint shown as published 2026-11-13. TS 6.0.3 stated as a deliberate pin behind `latest` 7.0.2, with typescript-eslint `<6.1.0` as the binding constraint.
- **N3 — Applied.** eslint-plugin-import-x 4.18.1 added to the tools table and skipped at this size (version verified on npm).
- **N4 — Applied.** "Swallows" became "logs and returns an empty list" (verified at :34).
- **N5 — Applied.** §2 and Risks name the files `src/shared/contract/{studio-api,studio-live}.ts` and flag the top-level `contract/` paths used in 01, 03, 05 and 06 for 07.
- **N6 — Applied.** §4 says a new browser-mode scenario takes two tasks.
- **N7 — Applied.** The detection, layer-JSON and doctor claims now cite the scratch run (Source 9).
- **Cross-file 1 (test placement) — Decided.** Both files are partly right. Unit and component tests are co-located (06 holds: `layer-implementer.md:48`, `task-plan-writer.md:129`). 02 keeps a `tests` row for the cross-layer suites only (contract suite, stub binaries, Playwright), with one `tests/` root. That is not the mirror tree 06 rejects, and it matches the harness's own `tests` row convention (`cli.md` §4).
- **Cross-file 2 (build) — Noted, not decided.** The tsconfig split needs a bundler in the same change. electron-vite 6 (04) and Vite + esbuild (06) both fit the `src/{main,preload,renderer}` tree unchanged, so the pick is left to 07.
