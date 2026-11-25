# Review — 07-recommendation.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

07 is a faithful synthesis. I spot-checked about 45 numbers, versions and paths against the final text of 01–06 and their review resolutions, and found no wrong number. That covers Vite 8.3.8, esbuild 0.28.2, Zustand 5.1.0, Query 5.108.4, TypeBox 1.4.7, DOMPurify 3.5.0, fuses 2.1.3, Playwright 1.65.1, `engines.node`, ≈ 56 MB, < 0.1 ms, 20–60 vs 2,000, 0.6 vs 36 ms, ≈ 53 KB, 550–700 lines, TS6307/TS2584, `layer-implementer.md:48`, devscene 0.7.1 `flat:fallback` and the drift list. Every open item the area files handed to 07 is settled in §2: 04 (a)–(e), 05 Risks 8–9, 03 Risk 8, 02's path and build questions. Rows 6 and 8 are new decisions, but they are reasoned and have triggers. The layers JSON is valid against the schema and identical to 02's. The `/devscene:analyze` rename is correct. The effort arithmetic adds up.

The fixes needed:
- One internal contradiction: the "runtime `electron` only in `main.ts`/`window/**`/preload" rule cannot be met by the placement the same document gives for `scheduler.ts` and `register.ts`.
- A few silent overrides of area files.
- A wrong Issue #1 target for the F-1 asks.
- A spike total that ignores the owner's Day 4 move.
- Some spike-scope trimming.

The architecture itself is still "basic: four folders plus `tests/`, placement rules, lint". The weight sits in the security bar, which 10 §6 mandates, and in the Day 2 plan.

## Must fix

**M1. The runtime-`electron` rule contradicts the placement of `scheduler.ts` and `register.ts`.**
- **Location:** §2 row 12, §3.2 rows 4–5 ("Runtime `electron` only in `main.ts`, `window/**`, `preload.ts`"; "`main/app` sees only `ports/` and `shared`"), §3.1 tree, §4.2 steps 2, 4 and 7.
- **Problem:**
  - (a) Day 2 step 7 puts `powerMonitor` in `app/scheduler.ts`, but `main/app` may import neither `electron` nor `window/`, and no port carries activity signals.
  - (b) `APP_ORIGINS` lives in `window/hardening.ts` and depends on `app.isPackaged` (05 §4 table, line 186: consumed by `ipc/register.ts`). `register.ts` therefore imports a module that imports `electron` at runtime. That defeats row 12's stated reason ("makes those modules unit-testable in Vitest with no Electron", 06 TL;DR line 13: a runtime import in Node returns a path and may download the binary).
  - (c) Step 2 still says "`hardening.ts` (four exports)", but 07's tree moved `CSP` out into `window/csp.ts`, which leaves three exports.
- **Evidence:** `05-security-architecture.md:182-190`; `06-testing-and-tooling.md:13`; 07 §3.1 lines 101–103, §4.2 step 7.
- **Fix:**
  - In §2 row 12, add: "`main.ts` subscribes to `powerMonitor` and window `show`/`hide`/`minimize` and calls `scheduler.setActivity(…)`. `scheduler.ts` imports no Electron. `main.ts` computes `APP_ORIGINS` once (`app.isPackaged`, dev URL) and injects it into `registerIpc` and `appProtocol`. `hardening.ts` exports `secureWebPreferences` and `applySessionPolicy`; `csp.ts` holds `CSP` with no imports, so `vite.config.ts` can import it without pulling in Electron."
  - In §4.2 step 2, change "(four exports)" to "(`secureWebPreferences`, `applySessionPolicy`; `APP_ORIGINS` built in `main.ts`)".
  - Add the `csp.ts` split to §2 row 9 or 12 as a stated deviation from 05 §1 row 1, which puts `CSP` in `hardening.ts`.

## Should fix

**S1. Silent overrides of area files.** Each should become a §2 row or a one-line note tagged [inferred]:
- (a) `studio/studio.ts` with `installStudio`/`getStudio` as a module-level singleton. 02 §2 line 50 says the renderer receives `StudioApi` "from a React context". 01 line 195 says "React context, or the store layer". No area file names `installStudio`. The module getter is the right call, because Zustand subscriptions and `queryFn` run outside React and 03 already calls `getStudio()` directly. But it is a decision, so state it.
- (b) `window/csp.ts` split out of `hardening.ts` (see M1).
- (c) Renderer log rings: "one per mounted log tail, dropped on unmount" overrides 04 §7's "keep at most N (e.g. 3), LRU" (`04-performance.md:206`). The reason given in row 7 is fine. Name the override in the Positions column.
- (d) The `node:fs` rule (§3.2: "only in `adapters/fs/` (and `perf/`)") conflicts with 02's logger, which writes a file in the app logs dir (`02-layered-architecture.md:85`). It also conflicts with the `KnownExe` `PATH` probe in `process/runner.ts`, which needs `fs.access` or equivalent. Either add `log/` to the exception, or say the logger and the probe go through `adapters/fs/`.

**S2. The F-1 asks target the wrong Issue #1 item.**
- **Location:** §5, Issue #1 "Item 21 (F-1): add the asks in §6".
- **Problem:** In Issue #1, F-1 is **item 7** ("A JSON read/act interface in the harness: a dependency (harness follow-up F-1)"). Item 21 only says "File the feature rows (F-1 onwards) when Studio work needs them". The F-1 row itself is `../product-startup-research/10-recommendation.md:382`, which already asks for "ISO-8601 timestamps with an offset" and "a JSON Schema in `schemas/`".
- **Evidence:** `gh issue view 1` lines 58 and 98; `10-recommendation.md:382`.
- **Fix:** "Item 7 (F-1): append the §6 asks (per-event `ts`, documented heartbeat interval, which runs' `log` events `runs watch` carries plus a per-run filter). Item 21: carry them into the F-1 issue when it is filed (devscene #170 mapping)." In §6, change the JSON Schema row's status to "Already in F-1 (10 §8 row F-1)".

**S3. The spike total ignores the owner's Day 4 move.**
- **Location:** §4.3, "The spike moves from 7–8 to ≈ 9–10.5 O-d".
- **Problem:** 7–8 is 10 §5's plan, which includes Day 4 (Windows + WSL2). Issue #4's Setup section records the owner's decision of 2026-11-25: Day 4 moves to Issue #1 item 4 and is "not part of the go/no-go". The spike baseline is now about 1 O-d lower. Spike plus v1 is unaffected, because the work moves into v1.
- **Evidence:** `gh issue view 4`, Setup and "Day 4: Windows + WSL2 (moved to Issue #1 item 4)"; `10-recommendation.md:282-290`.
- **Fix:** "The spike moves from 7–8 O-d (10 §5; ≈ 6–7 now that Day 4 has moved to Issue #1 item 4) to ≈ 8–9.5 O-d."

**S4. The effort table's sources do not match the area files.**
- **Location:** §4.3 table.
- **Problem:**
  - "Security structure" is allotted 0.25 + 0.25–0.5 = 0.5–0.75 O-d, but 05 says 0.5–1 O-d (`05-security-architecture.md:299`). The upper bound is silently dropped by 0.25.
  - "Layer wiring … 02 §1": 02 §1 says "about half a day of tsconfig and wiring on Day 1" (line 35), not 0.25 + 0.25 split across days.
  - "Reactive core … 03 §4": 03 gives ≈ 550–700 lines (line 132), not O-d. The 0.25–0.5 figure is 07's own estimate.
- **Fix:**
  - Tag the reactive-core and layer-wiring rows [inferred, 07].
  - Either use 05's 0.5–1 (Days 1–2 total ≈ 5–5.75) or say "05's upper end absorbed by the overlap with tooling".
  - Keep the "1.5 O-d pulled forward" sentence, but give its composition: "tooling 0.75 + security structure 0.5–0.75 ≈ 1.5; both sit inside 10 §7's v1 items 2 and the 5.5 O-d security bar". The arithmetic itself checks out: 7–8 + 2–2.5 = 9–10.5, and (9–10.5) + 32.5 − (4 + 1.5) = 36–37.5 against 10's ≈ 36, so +0.5–1.

**S5. Day 2 ordering: the main lint bans land after the code they police.**
- **Location:** §4.2 step 9.
- **Problem:** Steps 1–8 write `child_process`, `ipcMain`, `dialog`, `node:fs` and `BrowserWindow` code. The bans that confine them arrive only at step 9, so violations are found after the fact. Day 1 puts the renderer bans in step 2, before the code.
- **Fix:** Move "Main lint bans (05 §1)" into step 1 (the main skeleton). Keep `scripts/dev.mjs` as a separate late step.

**S6. Proportion: trim the spike's Day 2 to what the go/no-go and the skeleton need.**
- **Location:** §4.2 steps 6–7, §4 "Can slip" list.
- **Problem:** Several v1 mechanisms are scheduled into the spike with no spike-time payoff:
  - (a) The **Suspended** state with `powerMonitor` and reconnect-on-resume. Issue #4's Day 2 target is "≈ 0% CPU with the window hidden". Sleep/resume was a Day 4 item, now moved.
  - (b) The **main-ring LRU cap of 10**. The spike tails one stub stream.
  - (c) **`WatchAdapter` backoff** beyond one reconnect.
  - (d) The `Settings` port in the tree. It has one implementation and no spike use, against 02 §1's own rule "add a port only where a second implementation or a test fake exists today".
- **Fix:**
  - Add (a)–(c) to the "Can slip" list.
  - In the tree, mark `Settings` and `confinedReader.ts` as post-spike. `confinedReader.ts` is already marked.
  - Add one line to §4: "The go/no-go needs only steps 1–6, 8, 10 (fuses, debug port), 13 and 14; everything else is skeleton work that may move to Issue #1 item 2."

## Nice to have

**N1. §2 row 14's Positions column is slightly wrong.**
- 02 §2 (line 60) also uses `import.meta.env.MODE`.
- `__BROWSER_MODE__` appears only in 05, which wrongly attributes it to "01/02/06" (`05-security-architecture.md:27,216,256,266`).
- Fix: "01, 02, 06: `import.meta.env.MODE`; 05 says `__BROWSER_MODE__` (mis-attributed to 01/02/06)". The marker assertion is unaffected.

**N2. §2 row 4 does not answer 01's `did-navigate` alternative.**
- 01 offers "`did-start-navigation` with `isMainFrame`, **or `did-navigate`**" (`01-electron-process-model.md:207`). `did-navigate` fires after commit, so the cancelled-navigation argument does not apply to it.
- Fix: add "and `did-navigate` would still race the new page's first `subscribe`, which `hello` cannot, because it rides the same ordered pipe".

**N3. Tag the untagged derived figures.**
- Q5 "State held twice (a few hundred KB)": no area file gives this. It is consistent with 04's 110 KB snapshot; tag [inferred].
- Row 6 "≈ 60 KB" per 500 lines: tag [inferred, 04's 120 chars/line].
- `?speed=0` and `process.crash()` in §4.1 step 4 and §4.2 step 12: these are 07's additions and not in 06 §6 or 03.

**N4. §4.2 step 3 omits the branch-validation call.**
- Issue #4's Day 2 item is "argv builder with branch validation". Step 3 names the `BranchName` brand, but not `adapters/git` `check-ref-format` or 02's pure regex in `shared/domain`.
- Fix: add "`adapters/git` `check-ref-format` mints `BranchName`".

**N5. Perf mark transport.**
- 04's sketch uses `ipcMain.on('perf:mark', …)` (`04-performance.md:242`). That breaks §3.2's "`ipcMain` only reaches `ipc/register.ts`" and needs a preload verb.
- Fix: say that §4.1 step 10's mark is read by Playwright/`_electron` from `window.__perf`, or that it goes through `register` as a perf-only verb present only under `STUDIO_PERF=1`.

**N6. Issue #1 item 3 edit: mention `/devscene:analyze`'s own `layers` target.**
- `plugin/commands/analyze.md` step 5 proposes its own `layers` array, which is applied only on an explicit yes or `--apply-layers`, and it records a `detection.review` verdict.
- Fix: add to the item 3 edit: "Run `config set layers` with the 07 §3.3 JSON **before** `/devscene:analyze`, and decline any layers proposal it makes."
- Item 10's title and button text ("Harness-analyze recommendation", "run harness analyze") could also drop "harness". Optional.
- I verified the rename: `plugin/commands/analyze.md` exists, and there are no `harness-analyze` hits in `plugin/`, `docs/` or `cli/src/` of `/Users/daniel/Work/devscene` (0.7.1, `ba16c19a`).

**N7. README.**
- The file table, summaries and all six verdict lines are accurate: every review is "PASS WITH FIXES", every area file is `Status: reviewed`, and every review has a `## Review resolution` section.
- "How to read it" names §1–§5 only. Add "§6 harness asks, §7 deferred mechanisms with triggers, §8 risks".
- Update the 07 row and the header status after this review is resolved.

## Checks run

- **Layers JSON:** parsed from 07 and checked against the `layers` subschema of `/Users/daniel/Work/devscene/schemas/devscene.config.schema.json`. All names match `^[a-z][a-z0-9-]*$`, all three keys are present with no extras, one `path: "."` row exists, and it is byte-identical to 02 §4's JSON (which 02's reviewer applied with `config set layers` on devscene 0.7.1). No `npx devscene` re-run was needed.
- **Issue #4** (`gh issue view 4`): every Day 1 and Day 2 checklist item maps to a §4 step. I checked the ANSI parser, frame-batched appends, Intel x64, the signed update round trip, `gh --version`/`git --version`, the four measurements, and fuses plus debug port.
- **`10-recommendation.md`** §5 and §7: 1.5 + 1.5 days; spike 7–8; v1 32.5; ≈ 4 O-d of carry-over; spike plus v1 ≈ 36.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1** Applied. Re-checked: 05 §4 puts `APP_ORIGINS` (reads `app.isPackaged`) in `hardening.ts` and has `register.ts` consume it, and step 7 put `powerMonitor` in `app/`. §2 row 12 now has `main.ts` build `APP_ORIGINS` and feed window events into an Electron-free `scheduler.setActivity`; `hardening.ts` keeps two exports; tree, §3.2 and Day 2 steps 2 and 7 updated; the `csp.ts` split is §2 row 21.
- **S1** Applied. (a) new §2 row 20 (module singleton `installStudio`/`getStudio`, why not context); (b) §2 row 21; (c) row 7 names the 04 §7 renderer LRU override; (d) new §2 row 22: `node:fs` also in `log/` and `perf/` (own files only), the `PATH` probe moves to `adapters/fs/exeProbe.ts` so 05's choke point holds.
- **S2** Applied. Confirmed in `gh issue view 1`: F-1 is item 7, item 21 only files rows. §5 now targets item 7 and carries to item 21; §6 JSON Schema row reads "Already in F-1 (10 §8 row F-1)".
- **S3** Applied. Issue #4 Setup confirms the Day 4 move (≈ 1 O-d in 10 §5). Spike now 7–8 (≈ 6–7 without Day 4) → ≈ 8–9.5 O-d; spike plus v1 unchanged.
- **S4** Applied. Security row uses 05's full 0.5–1 (Day 2 +0.25–0.75); wiring and reactive rows tagged [inferred, 07] with 02's half-day and 03's line count named; the 1.5 O-d pulled forward is broken down. Day totals unchanged because S6's deferrals save ≈ 0.25 on Day 2.
- **S5** Applied. Main lint bans moved into Day 2 step 1; step 9 keeps only `scripts/dev.mjs`.
- **S6** Partially applied. Suspended/`powerMonitor`, the main-ring LRU cap, `WatchAdapter` backoff and the `Settings` port moved to §7 with triggers (not deleted); `Settings` marked post-spike in the tree; go/no-go line added. Deviation: step 7 stays in the go/no-go set in its Visible/Hidden form, because the hidden-CPU measurement should reflect the real polling policy.
- **N1** Applied. Row 14 Positions corrected (01, 02, 06 use `import.meta.env.MODE`; 05's attribution noted).
- **N2** Applied. Row 4 now answers `did-navigate` (fires after commit but still races the first `subscribe`).
- **N3** Applied. Q5 "a few hundred KB" and row 6 "≈ 60 KB" tagged [inferred]; `?speed=0` and `process.crash()` marked as 07's additions.
- **N4** Applied. Day 2 step 3 names `adapters/git` `check-ref-format` minting `BranchName` after 02's pure regex; Issue #4 item text includes branch validation.
- **N5** Applied. Day 1 step 10: marks stay on `window.__perf` and are read by Playwright; no `perf:mark` IPC channel.
- **N6** Applied. Issue #1 item 3 edit says to run `config set layers` before `/devscene:analyze` and decline its proposal; item 10 rename of the title and button text noted as optional.
- **N7** Applied. README "How to read it" names §6–§8; 07 row and header status updated to reviewed; TL;DR cost line updated.
