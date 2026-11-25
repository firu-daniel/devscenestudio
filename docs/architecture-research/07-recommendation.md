# 07 — Recommendation: Studio application architecture
> Status: reviewed · Date: 2026-11-25 · Synthesis

This is the decision document for the application architecture, written before spike Day 1 (Issue #4). It synthesises the six reviewed area files 01–06 and the "Review resolution" sections in [`reviews/`](reviews/). It adds no new primary research: every conflict below was settled from the final text of the area files. "See 03 §5.1" means section 5.1 of `03-reactive-data-flow.md`. O-d means owner-days, as in `../product-startup-research/10-recommendation.md` (10). Tags: **[verified]** (an area file or its review checked a primary source), **[inferred]** (reasoning, here or in the area file).

## TL;DR

- **Layout: one folder per Electron process plus one pure shared folder:** `src/shared/{domain,contract}`, `src/main`, `src/preload`, `src/renderer`, and one `tests/` root for cross-layer suites. This replaces Issue #1's `app/` + `app/main/` + `contract/` (02 §3).
- **Harness layers: five rows,** `shared`, `main`, `renderer`, `tests` and the catch-all `general` (which also takes the one-file preload). `devscene init` will not detect this tree; set it once with `devscene config set layers` (§3.3; 02 §4).
- **Boundaries are enforced by tools, not prose.** TS project references (`tsc -b`) make a cross-process import a compile error. ESLint core `no-restricted-imports`/`-syntax`/`-properties` enforce the rules inside each process and the nine security choke points (02 §5, 05 §1).
- **Build: Vite 8 for the renderer and a small esbuild script for main and preload** (CommonJS), landing in the same change as the tsconfig split. electron-vite 6 is the fallback (06 §2).
- **Patterns kept:** ports and adapters with hand-wired composition roots, Strategy for `Direct | Wsl`, one argv-builder function, a read-model in main, a fixture/IPC Adapter behind `StudioApi`, the preload Facade, intents as data, `Result` over IPC, branded types at the choke points. No DI container, no use-case classes, no event bus, no IPC library (02 §6, 05 §1).
- **Typed IPC is hand-written:** one `StudioApi` interface in `src/shared/contract/`, implemented by the preload, by main's handlers and by the browser-mode fixture. The renderer reaches it only through `getStudio()`, picked at build time; a missing preload throws, never falls back to fixtures (01 §4–§5).
- **Live data flows one way:** sources in main → pure normaliser → read-model in main → `snapshot` then one-entity `upsert`/`remove` pushes → a **Zustand** mirror in the renderer. Logs go through **ring buffers** on both sides. On-demand reads and commands use **TanStack Query** over `invoke`. Electron supplies the pipes; we write ≈ 550–700 lines of glue, not an observable framework (03).
- **Performance:** batch logs in main, virtualise only the log tail, memoise cards by id, never block main (no `*Sync`, no backtracking regex), and slow main's own polling when the window is hidden. No `utilityProcess` in v1 (04).
- **Security:** each item of the v1 bar has one owning module, a compile-time or lint guard and a test. IPC is validated in main only (TypeBox 1.x). DOMPurify goes to **≥ 3.5.0**, and the XSS gate becomes **0 Trusted Types violations and 0 executions** (05).
- **Cost:** spike Days 1–2 grow from 3 to ≈ 5–5.5 O-d; the whole spike goes from ≈ 6–7 O-d (10 §5 without Day 4, which the owner moved to Issue #1 item 4) to ≈ 8–9.5. About 1.5 O-d of the addition is v1 work pulled forward, so spike plus v1 grows by ≈ 0.5–1 O-d (§4.3) [inferred].

## 1. Answers to the owner's questions

| # | Question | Answer | Detail |
|---|---|---|---|
| 1 | How do Electron's parts fit, and is it "like React for the web"? | See the plain-language answer below. | 01 §1–§3, Q1 |
| 2 | Start on a clean layered architecture? What is the smallest clean one? | **Yes.** The Day 1 folders become the harness layer map, and browser mode needs a port with two adapters from the first screen. The smallest clean version: one folder per process plus `shared`, a small hexagon inside main, and the `StudioApi` port with two adapters in the renderer. Add a port only where a second implementation or a test fake exists today. | 02 §1, §3 |
| 3 | Clean architecture, SOLID, patterns, concretely? | The pattern table in §3.4 names each kept pattern and its file. Skip DI containers, use-case-per-file classes, a global event bus, Repository CRUD, Redux-style action layers and barrel files. | 02 §6, 05 Q3 |
| 4 | How do live updates reach a component? | Child stdout → `readline` async iterator → pure normaliser → read-model reducer in main → IPC push (`snapshot`, then `upsert`/`remove`) → preload `onRunsUpdated` → pure `applyRunsEvent` into Zustand → selector hooks via `useSyncExternalStore`. Logs take a parallel ring-buffer path. Electron gives the pipes (`webContents.send`, proxied callbacks); React gives `useSyncExternalStore`. No RxJS, no observables. | §3.5; 03 §4, Q4 |
| 5 | Performance and security consequences? | The table below. | 04 Q5, 05 Q5 |
| 6 | Can expause_web be the model? | **Partly.** Carry over: domain types kept apart from wire DTOs, remappers (harness/`gh` JSON → domain, inside main's adapters), feature folders, subscribe functions returning an `Unsubscribe`, "global state only for shared data", TanStack Query for request/response data, and a validated data boundary. Leave behind: its top-down dependency direction (domain imports data; Studio points dependencies *at* the domain), use-case-per-file (186 files, some pure pass-throughs), the global event bus, RTK slices and thunks, Firebase, Dexie, barrels, happy-dom and the `src/test/unit/<layer>/` mirror tree. | 02 §8, 03 §9, 06 §9 |

**Q1 in plain language (for a React web developer).** Think of an Electron app as a website and its backend server packaged together and running on one machine.

- The **renderer** is the website: a Chromium tab running your React app. Components, hooks, Vite, Testing Library all work as on the web. It cannot touch files or start processes.
- The **main process** is the "server": a Node program that opens the window and does everything privileged. For Studio, that is running `gh`, `git`, `devscene` and `wsl.exe`, watching folders and showing native dialogs.
- **IPC** replaces HTTP. `invoke` is like `fetch` to an API route and returns a promise. `webContents.send` is like a WebSocket push from server to page.
- The **preload** is a small script that decides which API functions the page gets (`window.studio.startRun(…)` and nothing else). It plays the role of a typed API client that the page cannot bypass.
- **Electron provides** the browser, Node, the IPC pipes and a handful of native OS calls (dialogs, menus, `shell`). It provides **no UI components, no store and no reactivity**. We build the React UI, the API contract, the sources and the glue.

So the UI half is "React for the web". The other half is a small Node backend you also own, and the seam between them is the security boundary.

**Q5: consequences of each choice.**

| Choice | Performance | Security |
|---|---|---|
| Logic in main, no `utilityProcess` | Saves ≈ 56 MB and a hop; every measured task ≤ 1 ms. Risk: a sync call or bad regex blocks every window (lint bans `*Sync`) | One privileged process to harden |
| Named intent verbs, hand-written preload | ≈ 0.1 ms per `invoke` | The renderer-reachable surface is one reviewable file; no generic `exec`/`readFile` |
| Sender check + schema + byte cap in `ipc/register.ts` | Negligible | A forged or sub-frame sender is refused; every argument is validated in main |
| Ids in, facts re-derived in main | One extra `gh` call per act (acts are rare) | An XSS can request an act but cannot write the text the human confirms |
| Read-model and trust rules in main | State held twice (a few hundred KB [inferred, from 04's ≈ 110 KB snapshot]) | Untrusted GitHub/branch data is classified before it crosses IPC |
| Batched log pushes, rings on both sides | ≈ 10× less transport, 20–60 instead of 2,000 renderer callbacks/s; bounded memory | Secrets masked in main before IPC |
| Zustand + per-id selectors, virtualised log | One-card update re-renders one card; log at 0.6 ms vs 36 ms per frame (under load; the ratio is the finding) | — |
| Sanitise at the sink (`SafeMarkdown`) under Trusted Types | markdown-it + DOMPurify ≈ 53 KB gz, lazy-loaded with the detail screen | Any other HTML sink throws at runtime and fails lint |
| Browser mode as a build-time fork | No cost in the packaged app | No runtime switch to fixtures; a release assertion checks the fixture marker is absent |
| Bundling (Vite + esbuild) | One file each for main and preload; no `node_modules` in the asar | Makes the sandboxed preload loadable; `dependencies` stays empty |

## 2. Resolved disagreements

Each row was checked against the final text of the files named.

| # | Issue | Positions (file) | Decision | Reason |
|---|---|---|---|---|
| 1 | **IPC contract location** | 01 §4 and 03 §8 sketch a top-level `contract/`; 02 §2, 05 §2 and 06 use `src/shared/contract/` | **`src/shared/contract/`**: `studio-api.ts`, `studio-live.ts`, `channels.ts`, `intents.ts`, `schemas.ts` | It is pure TS that every process imports; one `shared` layer keeps a new verb to one shared task. 01/03 used placeholder paths (03 Scope says so) |
| 2 | **Generated harness types** | Issue #1 item 2 and the first 05 draft: `contract/`; 02 §2: `src/main/adapters/harness/schema/` | **`src/main/adapters/harness/schema/`** (generated, never hand-edited) | Only main parses harness output; the renderer must never see raw harness shapes (02 §3) |
| 3 | **Build tool** | 04 (first draft): electron-vite 6; 06 §2: Vite + esbuild; 04 final defers to 06; 02 leaves it to 07 | **Vite 8.3.8 (renderer) + `scripts/build-main.mjs` with esbuild 0.28.2 (main, preload; CJS)**. Fallback: electron-vite 6 if `scripts/dev.mjs` grows past ≈ 100 lines | Browser mode needs a plain Vite config anyway; electron-vite has a bus factor of 1; performance does not discriminate (04 §5) |
| 4 | **Reload detection** | 01 §6 and 04 §7: drop subscriptions on `did-start-navigation`; 03 §5.1: preload sends `hello` | **Preload `hello`**, plus `render-process-gone` and `destroyed` | `did-start-navigation` fires before commit, so a cancelled navigation would drop live subscriptions. `hello` travels on the same ordered IPC pipe as the `subscribe` calls that follow it, so there is no race. 01's other option, `did-navigate`, fires after commit but would still race the new page's first `subscribe`, which `hello` cannot. `hello` is preload-internal (not on `window.studio`) and goes through the same sender check. Rule: main's `hello` and `subscribe` handlers update the registry synchronously before any `await` [inferred] |
| 5 | **Hidden-window polling** | 03 §6: focused vs hidden cadence (60 s / 5 min for Issues); 04 §4: three activity states, first draft "stop when hidden" | **04's three states with 03's intervals.** Visible: focused cadence, refresh at once if stale. Hidden (window events or the renderer's `setVisible`): ≈ 5 min, PRs off. Suspended (`powerMonitor` `suspend`/`lock-screen`): stopped; on resume, reconnect and expect a fresh `snapshot`. The spike builds Visible and Hidden only and polls Issues only (60 s / 5 min); Suspended is v1 (§7) | Main's timers are never throttled, so main must slow itself; the renderer's `visibilitychange` is the only signal that covers macOS occlusion and Wayland. 03 and 04 agree once 04 dropped "stop" |
| 6 | **Log backfill (`reset`) message size** | 04 §2: a ≈ 1.2 MB `reset` exempt from the 1 MB guideline; 03 §5.3 final: no `reset` message, the first message after subscribe is the ring contents | **No `reset` type.** The backfill is sent as ordinary `log:lines` batches of ≤ 500 lines, back to back | The existing 500-line cap already bounds every message (≈ 60 KB [inferred, 04's ≈ 120 chars/line]), so no exemption and no extra message type are needed. The renderer starts each subscription with an empty ring |
| 7 | **Main-side log ring caps** | 03: a 10k-line `LogRing` per run in main, no cap stated; 04 §7: cap and drop rule in main, and in the renderer "keep at most N (e.g. 3) rings, LRU" (overridden here) | **10k lines per run; at most 10 rings, LRU; a ring is dropped when its run has finished and no renderer subscribes.** Renderer: one ring per mounted log tail, dropped on unmount (main backfills on remount). The spike tails one stub stream and builds neither the LRU cap nor the drop rule (§7) | Bounds main at ≈ 30–50 MB worst case [inferred, 04 §7]; the renderer needs no LRU cache of its own (04 §7's N = 3) because main backfills on remount |
| 8 | **Log forwarding while hidden** | 04 §4: stop forwarding, `reset` on show; 03: silent | **Keep forwarding while hidden, but flush every 1 s instead of 50 ms** (still ≤ 500 lines per message) | The renderer ingests on arrival into a bounded ring and renders nothing while hidden (rAF stops), so memory stays bounded. A slower flush cuts wake-ups 20× with no protocol change and no show/hide coordination. With no run producing output, nothing is sent, so the ≈ 0% idle target is unaffected. Trigger to switch to 04's stop-and-backfill: Day 2's hidden measurement with an active log stream misses the target |
| 9 | **Dev origin and dev CSP** | 05 Risk 8: dev origin trusted only when `!app.isPackaged`, plus a release assertion; 06 Risk 1: relax the CSP only in `vite serve` for the React Refresh preamble | **Both, stated once.** `APP_ORIGINS = ['app://studio']`, built once in `main.ts` (row 12), plus `http://127.0.0.1:<port>` only when `!app.isPackaged` and `scripts/dev.mjs` set the dev URL. Vite binds `127.0.0.1`, `strictPort`, never `--host`, Vite ≥ 8.3.7. A small Vite plugin relaxes the CSP in serve mode only (inline preamble, HMR websocket). `vite preview` and `app://` serve the unmodified `CSP` constant. All security gates run on `vite preview` or packaged builds | The two files agree in substance; neither referenced the other's half. The release assertion (packaged origin list is `app://studio` alone) keeps the dev path out of releases |
| 10 | **Test placement and the `tests` layer** | 06 (first draft): no `tests` layer, mirror tree rejected; 02: a `tests` row. Settled in 02's and 06's review resolutions | **Unit and component tests co-located** (`*.test.ts[x]` inside each layer). **One `tests/` root, its own `tests` layer**, for cross-layer suites only: `contract/`, `integration/`, `e2e/{browser,electron}/`, `stubs/`, `setup-dom.ts` | A harness implementer may write only inside its layer path (`layer-implementer.md:48`). The harness gives detected presets a `tests` row for the same reason |
| 11 | **TanStack Query's role** | 02 §8: "No (03 decides)"; 03 §3.1 final: yes for on-demand reads and commands, not for live state | **03 §3.1.** Query for `invoke`-backed reads (run detail and analytics, Issue/PR detail, doctor, repo list) and `useMutation` for commands. `networkMode: 'always'`, `retry: 1`, `staleTime: 30_000`. Never for pushed data | Main is already the poller and cache for live data; Query adds loading, error, dedupe and race handling for the ≈ 5 reads that a hand-written hook would get wrong. The one bridge is in §3.5 |
| 12 | **Where `electron` may be imported** | 02 §5: `electron` only in `adapters/electron`; 05: `dialog`/`shell` only there; 06 §4: no runtime `electron` import outside the composition root and the preload entry (an import in Node returns a path and may download the binary) | **Runtime `import … from 'electron'` only in `src/main/main.ts`, `src/main/window/**` and `src/preload/preload.ts`.** Everywhere else `import type` only (`allowTypeImports`); `dialog`, `shell` and `ipcMain` are injected by the composition root into `adapters/electron/` and `ipc/register.ts`. `main.ts` subscribes to window `show`/`hide`/`minimize` (and, in v1, `powerMonitor`) and calls `scheduler.setActivity(…)`; `scheduler.ts` imports no Electron. `main.ts` computes `APP_ORIGINS` once (`app.isPackaged`, dev URL) and injects it into `registerIpc` and `appProtocol`. `hardening.ts` exports `secureWebPreferences` and `applySessionPolicy` only; the logger's directory (`app.getPath('logs')`) is injected the same way | Keeps 05's choke points and makes those modules unit-testable in Vitest with no Electron (06). Overrides 05 §4, which puts `APP_ORIGINS` (which reads `app.isPackaged`) in `hardening.ts` and has `register.ts` import it: that import would pull runtime `electron` into `register.ts` [inferred] |
| 13 | **Preload: hand-written or built from the channel table** | 02 §4: generate verbs from the table if bundled; 05 §1: hand-written literal list; 06 §4: `makeStudioApi(invoke)` + a 3-line entry | **Bundled, hand-written:** `src/preload/api.ts` exports `makeStudioApi({invoke, on, off})`, an explicit object literal `satisfies StudioApi`; `preload.ts` is the 3-line `contextBridge` entry that also sends `hello`. Channel names are imported from `channels.ts` (fine once bundled) | A literal list is the most reviewable form of the security-critical file (05); the factory makes it testable without Electron (06). The contract test checks preload keys against the channel table |
| 14 | **Browser-mode switch** | 01, 02 and 06: `import.meta.env.MODE === 'browser'`; 05: a `__BROWSER_MODE__` define (which 05 mis-attributes to 01/02/06) | **`import.meta.env.MODE === 'browser'`**, with a *dynamic* import of `studio/fixture.ts` in `main.tsx` only | Vite already replaces it statically; no custom define to maintain. The fixture-marker release assertion is unchanged |
| 15 | **`app://` implementation** | 01 Risk 4: prefer `protocol.handle` unless 05 decides; 05 §4: `protocol.registerSource` | **`protocol.registerSource`** (CSP in route `headers`, Electron-side confinement, off the main thread); fallback `protocol.handle` with decode-then-`path.relative` confinement (01 §6). The traversal e2e runs either way | 05 decided; the fallback is ≈ 15 lines in one file if the Experimental API changes |
| 16 | **Push vocabulary and first board load** | 04: `patch`, `reset`, a `getBoard()` verb awaiting a cached promise; 03 final: `snapshot`/`upsert`/`remove`/`status`, snapshot on subscribe | **03's vocabulary.** Main starts the `gh` fetch at `ready`; the first `subscribe` snapshot awaits that in-flight fetch. No `getBoard` verb | 04 wrote against an earlier 03 draft; the intent (start `gh` early, in parallel with window creation) is kept |
| 17 | **Log flush window** | 03: 50 ms or 500 lines; 04: 16–50 ms or 500 lines | **50 ms or 500 lines** visible, **1 s** hidden | Inside 04's range; 03's value |
| 18 | **`moduleResolution`** | 02 Risk: shared under `nodenext` needs `.js` specifiers; 06 §2: `bundler` everywhere | **`bundler` everywhere** | No project's output is loaded by Node's resolver; stub binaries import no TS (06 §6) |
| 19 | **Validation library** | 05: TypeBox 1.x, conditional on F-1 shipping a JSON Schema; zod 4 close second | **TypeBox 1.4.7**, in main only; switch to zod 4 if the harness publishes TS/zod types instead | The `register(verb, schema, fn)` signature hides the choice, so a switch costs one file per schema (05 Risk 3) |
| 20 | **How the renderer reaches `StudioApi`** | 02 §2: "received from a React context"; 01 §5: "React context, or the store layer"; 03 calls `getStudio()` directly | **A module-level singleton:** `studio/studio.ts` exports `installStudio(api)`, called once by `main.tsx`, and `getStudio()`. No React context | Zustand subscriptions and Query's `queryFn` run outside React, where a context is unreachable; one module getter serves both. Tests call `installStudio(fake)` [inferred] |
| 21 | **Where the `CSP` constant lives** | 05 §1 row 1 and §4: in `window/hardening.ts` | **`src/main/window/csp.ts`**, a string constant with no imports | `vite.config.ts` imports it for `vite preview`; importing `hardening.ts` would pull runtime `electron` into the Vite config [inferred] |
| 22 | **Where `node:fs` may be imported** | 05 §1 row 4: only in `main/adapters/fs/`; 02 §2: the logger in `log/` writes a file; 05 §1 row 3: `KnownExe` resolved at startup (a `PATH` probe) | **`adapters/fs/`, plus `log/` and `perf/`**, which only append to Studio's own files under an injected directory, never a repo path. The `PATH` probe lives in `adapters/fs/exeProbe.ts`; `main.ts` injects the resolved paths into `process/runner.ts` | Keeps every read of repo or run files behind 05's choke point; a logger behind a port would break 02's "plain module" rule for no gain [inferred] |

## 3. Reference architecture

### 3.1 Folder tree

```
devscenestudio/
├── src/
│   ├── shared/                   LAYER shared: pure TS, no electron / node:* / DOM / React (composite, emitDeclarationOnly, types [])
│   │   ├── domain/               Run, Issue, RunPhase, columnOf, trust.ts, text.ts (maskSecrets, revealInvisible), brand types, branch shape, Result, LogRing<T>
│   │   └── contract/             studio-api.ts (StudioApi), studio-live.ts (LiveEvent, LogLine), channels.ts, intents.ts, schemas.ts (TypeBox; runtime use in main only)
│   ├── main/                     LAYER main: Node + Electron main; main.ts = composition root (wiring, single-instance lock, ProcessRegistry, quit cleanup, APP_ORIGINS, window/power events → scheduler)
│   │   ├── app/                  services per area: runs.ts (read-model, mergeRun), intents.ts (ActPreview, Confirmed), repos.ts (TrustedRepo), scheduler.ts (activity state; no Electron import)
│   │   ├── ports/                GhClient, GitClient, HarnessClient, Transport, FileWatcher, Confirm; Settings post-spike
│   │   ├── adapters/
│   │   │   ├── gh/               `gh api -i` client (ETag, parsed 304), gh JSON → domain
│   │   │   ├── git/              check-ref-format, branch and merge state
│   │   │   ├── harness/          `devscene … --json` client, NDJSON reader + normaliser, WatchAdapter; schema/ = generated types
│   │   │   ├── transport/        direct.ts, wsl.ts: the only `child_process` importers
│   │   │   ├── fs/               log tail, watcher, exeProbe.ts (`PATH` probe); settings.ts and confinedReader.ts post-spike
│   │   │   └── electron/         confirm.ts, externalLinks.ts (dialog/shell injected)
│   │   ├── process/              argv.ts (pure builders), runner.ts (env allowlist, KnownExe, cwd = $HOME)
│   │   ├── ipc/                  register.ts (sender check, schema, byte cap, closed error codes), subscriptions.ts (registry + publisher + log flush)
│   │   ├── window/               csp.ts (CSP string, no imports), hardening.ts (secureWebPreferences, applySessionPolicy), appProtocol.ts, window creation
│   │   ├── log/                  logger (plain module, not a port; log dir injected by main.ts)
│   │   └── perf/                 sampler.ts, active only with STUDIO_PERF=1
│   ├── preload/                  no harness row (routes to `general`); bundled CJS: preload.ts (entry + hello), api.ts (makeStudioApi)
│   └── renderer/                 LAYER renderer: React 19; main.tsx = composition root (installs the StudioApi adapter, providers)
│       ├── studio/               studio.ts (installStudio/getStudio), ipc.ts (window.studio, throws if missing), fixture.ts + fixtures/ (browser mode only)
│       ├── state/                boardStore (Zustand vanilla), applyRunsEvent/applyIssuesEvent, useBoardLive, useLogTail, queryClient
│       ├── features/             board/, run-detail/, log-tail/, repo-picker/, doctor/: screens and their hooks
│       ├── ui/                   presentational components (no StudioApi, no state/)
│       └── markdown/             SafeMarkdown.tsx, policy.ts (the only createPolicy calls), ansi.ts
├── tests/                        LAYER tests: contract/, integration/, e2e/{browser,electron}/, stubs/{bin,gh,streams}/, setup-dom.ts
├── scripts/                      build-main.mjs, dev.mjs, signing helpers (exist)
├── build/                        electron-builder resources, entitlements (exists)
├── vm/                           Linux VM tooling (exists)
├── docs/                         research and design docs
└── .claude/context/              shared.md, main.md, renderer.md, tests.md, conventions.md (with a "Preload" section)
```

Root files: `tsconfig.json` (solution), `tsconfig.base.json`, `tsconfig.tools.json`, `vite.config.ts`, `vitest.config.ts`, `playwright.config.ts`, `eslint.config.js`, `.npmrc` (`ignore-scripts=true`), `electron-builder.yml` (adds `electronFuses`). Avoid a top-level `src/api/` or `src/handlers/`: `init` would pick the `api-service` preset (02 §4).

### 3.2 Dependency rules and how each is enforced

| Rule | Enforced by |
|---|---|
| main, preload and renderer never import each other; all may import `shared` | TS project references with `composite` on every process project: a cross-process import fails with TS6307 (06 §3, measured) |
| `shared` has no DOM, Node, Electron or React | `src/shared/tsconfig.json` `types: []`, no DOM lib (TS2584, measured) + lint |
| `shared/domain` imports nothing; `shared/contract` imports only domain and `typebox` (in `schemas.ts`) | Lint (`no-restricted-imports`) |
| `main/app` sees only `ports/` and `shared` | Lint |
| `child_process` only in `adapters/transport/`; only `process/runner.ts` imports `adapters/transport/`; no `process.getBuiltinModule` | Lint (`no-restricted-imports`, `no-restricted-properties`) |
| Runtime `electron` only in `main.ts`, `window/**`, `preload.ts`; `import type` elsewhere; `ipc/`, `app/` and `adapters/` never import `window/` except `csp.ts` | Lint with `allowTypeImports` (§2 row 12) |
| `new BrowserWindow` only in `window/`; `ipcMain` only reaches `ipc/register.ts`; `ipcRenderer` only in the preload; no `setAsDefaultProtocolClient` | Lint (`no-restricted-syntax`, `no-restricted-imports`) |
| `node:fs` only in `adapters/fs/`, `log/` and `perf/` (§2 row 22); no `*Sync` calls in main after bootstrap | Lint |
| Every IPC handler goes through `register(verb, schema, service)`; every verb has a schema; preload keys equal the channel table; `answer`/`resume` absent until H1 + H1′ | IPC contract test (`tests/contract/`) |
| Act services take a `Confirmed<ActPreview>`; argv repo slots take `TrustedRepo`/`BranchName`; no argv slot takes `FreeText` | Branded types (compile error) |
| Renderer `features/`, `state/`, `ui/` never import `studio/ipc` or `studio/fixture*`; only `main.tsx` imports `studio/fixture*`; `ui/` never imports `state/` | Lint |
| `dangerouslySetInnerHTML` only in `SafeMarkdown.tsx`; `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` banned; `createPolicy` only in `markdown/policy.ts` | Lint + Trusted Types CSP at runtime (any other sink throws) |
| No fixture code in the packaged renderer; packaged `APP_ORIGINS` is `app://studio` alone; fuses as set; no debug port; CSP header present | Release assertions after `electron-builder` (05 §7) |
| Pushed DTOs are never mutated | `Readonly` types; `contextBridge` freezes them at runtime (01 §3) |
| Query never holds pushed data; Zustand never holds request/response data; no barrel files | `renderer.md` / `conventions.md` + review (no mechanical check) |

Cost: ≈ 6 import-rule blocks (02) plus ≈ 16 security entries (05) in one `eslint.config.js`, most overlapping. Lint is not a boundary (dynamic `require`, dependencies); the fuzz and hostile-repo suites are the backstop (05 Risk 4).

### 3.3 Harness layer map

```json
[
  { "name": "shared",   "path": "src/shared",   "conventions": ".claude/context/shared.md" },
  { "name": "main",     "path": "src/main",     "conventions": ".claude/context/main.md" },
  { "name": "renderer", "path": "src/renderer", "conventions": ".claude/context/renderer.md" },
  { "name": "tests",    "path": "tests",        "conventions": ".claude/context/tests.md" },
  { "name": "general",  "path": ".",            "conventions": ".claude/context/conventions.md" }
]
```

Order is the bottom-up ship order, catch-all last. Verified on devscene 0.7.1: `init --dry-run` gives `flat:fallback`; this JSON is accepted; `doctor` then reports `layer-profile` PASS and a permanent `layer-drift` WARN for `build, scripts, vm, src/preload` (02 §4). `shared.md` must say that a new verb leaves the whole-tree typecheck red until the main, renderer and preload tasks land (accepted evidence downgrades; 02 §4).

Harness commands (06 §8): `commands.typecheck` = `bash devscene-scripts/typecheck.sh` → `npm run check` (`tsc -b && eslint . --max-warnings 0`); `commands.test` = `bash devscene-scripts/test.sh` → `npx vitest run "$@"`; `commands.devServer` = `bash devscene-scripts/start-dev-server.sh` → `npm run dev:browser -- --port "$DEVSCENE_DEV_SERVER_PORT" --strictPort`; `commands.depInstall` = `npm ci --ignore-scripts`. Playwright stays out of `commands.test` and runs as a required GitHub check.

### 3.4 Patterns kept

| Pattern | Where | File(s) | Payoff here |
|---|---|---|---|
| Ports and adapters | main services depend on ports; the renderer depends on `StudioApi` | `src/main/ports/*`, `src/shared/contract/studio-api.ts` | F-1 churn stays in `adapters/harness/`; services unit-test with fakes; browser mode works |
| Composition root, hand-wired | one per process | `src/main/main.ts`, `src/renderer/main.tsx`, `src/preload/preload.ts` | ≈ 30 visible lines of wiring; tests wire fakes the same way |
| Strategy | `Transport = Direct \| Wsl` | `src/main/adapters/transport/{direct,wsl}.ts` | Everything above spawn is OS-agnostic; Windows is one file |
| One argv builder (typed functions) | all spawns | `src/main/process/argv.ts`, `runner.ts` | One place for `--end-of-options`, `--repo`, env allowlist, cwd `$HOME`; one fuzz target |
| Read-model | runs merged from gh + local under the trust rules | `src/main/app/runs.ts`, `src/shared/domain/trust.ts` | Survives renderer reloads; the UI never sees unclassified input |
| Adapter | `StudioApi` via IPC or fixtures | `src/renderer/studio/{ipc,fixture}.ts` | The same React code runs in Electron, Playwright and the QA agent |
| Facade | preload exposes verbs only | `src/preload/api.ts` | The renderer-reachable surface is one file |
| Command as data | intents are a typed union; main builds the argv and shows it in the native modal | `src/shared/contract/intents.ts`, `src/main/app/intents.ts` | The human confirms exactly what runs |
| Result | expected failures as values over IPC | `src/shared/domain/result.ts` | `invoke` loses thrown error fields; ≈ 15 lines, no library |
| Choke point / gateway | the nine security modules | 05 §1 | Every bypass is a lint or type error |
| Branded types | `Confirmed`, `TrustedRepo`, `BranchName`, `FreeText` | types in `shared/domain`, minted in main | Unsafe calls fail to compile |
| Observer as `subscribe → unsubscribe` | preload `on*` verbs, source adapters | `src/preload/api.ts`, `src/main/ipc/subscriptions.ts` | The only leak-free shape across `contextBridge` |
| Ring buffer | logs in main and renderer | `src/shared/domain/` (`LogRing<T>`) | Bounded memory, hidden or not |

### 3.5 Data flow: source to component

```
 MAIN                                                                                  RENDERER
 runs watch --json ─ spawn → readline → ndjson ──┐
 gh api poll (ETag, 304) ── scheduler ───────────┼─→ normaliser (pure) → read-model reduce + mergeRun (pure)
 log tail / `log` events ────────────────────────┘          │                         
                                                             ├─ runs:updated / issues:updated ─→ preload on* ─→ applyRunsEvent ─→ Zustand ─→ useRunCard(id), useColumn(c)
                                                             │     snapshot on subscribe, then upsert/remove/status                        └─ invalidates ['runDetail', repo, branch]
                                                             └─ per-run LogRing ─ log:lines (≤ 500 lines; 50 ms visible, 1 s hidden) ─→ LogRing (ingest now, render on rAF) ─→ useLogTail
 ipc/register.ts handlers ◀──────────── invoke (reads, commands) ◀──────────── TanStack Query: useRunDetail, useMutation(startRun …) ─→ getStudio()
```

| Data | Tool | Rule |
|---|---|---|
| Board: runs, Issues, connection status | **Zustand 5.1.0** vanilla store, per-id selectors, normalised by id | Pushed by main. `snapshot` replaces the mirror; `upsert`/`remove` replace one entity, so other cards keep their identity |
| Log tail | **`LogRing`** (10k lines, `{seq, spans}`; ANSI parsed at ingest) + TanStack Virtual | Ingest on arrival, render at most once per rAF via a version counter |
| Run detail and analytics, Issue/PR detail, doctor, repo list | **TanStack Query 5.108.4** over `invoke` | Read when a screen opens; `queryFn` unwraps `Result` and throws on error |
| Commands (start, pause, …) | **`useMutation`** | Main shows the native confirm; `onSuccess` invalidates the affected detail |

**The rule between them:** pushed data lives only in Zustand; requested data lives only in Query. The one bridge: when `applyRunsEvent` upserts or removes run X, invalidate X's `runDetail` query. Main stays the only poller. Lifecycle: subscriptions are keyed `(webContents.id, topic, key)`, `subscribe` is idempotent, a source runs while it has a subscriber, and `hello`, `render-process-gone` and `destroyed` drop a webContents' subscriptions. Wire log lines carry main's `seq`, so keys stay stable across backfill and appends [inferred].

## 4. Spike plan: revised Day 1 and Day 2 (Issue #4)

### 4.1 Day 1: web UI and browser mode (≈ 2.5 O-d, was 1.5)

| # | Step | Issue #4 item |
|---|---|---|
| 1 | **Scaffolding, one change:** pinned devDependencies (06 Day 1 list, DOMPurify 3.5.0, Vite ≥ 8.3.7, `zustand@5.1.0`, `@tanstack/react-query@5.108.4`, `@tanstack/react-virtual`, `markdown-it@15.0.3`, `typebox@1.4.7`); `engines.node` → `^22.22.2 \|\| ^24.15.0`; `.npmrc` `ignore-scripts`; tsconfig solution + base + `src/{shared,main,preload,renderer}` + `tests` + tools projects (06 §3); `vite.config.ts` + `scripts/build-main.mjs` replace `tsc` + `copy-renderer-assets.mjs`; `.tsbuild/` ignored; the scripts table (06 §8). Check: `npm run build` produces `dist/{main,preload,renderer}` and the window still opens (owner-run) | **New** (precondition for all) |
| 2 | ESLint 10 flat config (`recommendedTypeChecked`, react-hooks, react-refresh) + Prettier; the `shared` and renderer import rules and renderer security bans; `vitest.config.ts` with `node` and `dom` (jsdom) projects. First check: `vitest run` finds a test in each project | **New** |
| 3 | `src/shared`: domain types, `Result`, `LogRing`; contract: `StudioApi` (Day 1 reads + `onRunsUpdated`, `onIssuesUpdated`, `onLogLines`, `setVisible`), `studio-live.ts`, `channels.ts` | Browser mode |
| 4 | **The `getStudio` seam:** `studio/studio.ts` (`installStudio`/`getStudio`), `ipc.ts` (throws if `window.studio` is missing), `fixture.ts` + 3–5 scenarios (timed `snapshot`/`upsert`/`remove`/`status` + `log:lines`), `?scenario=` and `?speed=0` (07's addition, not in 06 or 03: events fire at once, for tests); `main.tsx` picks by `import.meta.env.MODE` with a dynamic fixture import | Browser mode with fixture-backed IPC |
| 5 | State: Zustand board store + `applyRunsEvent`/`applyIssuesEvent` (unit tests: snapshot replaces, upsert keeps identities, remove), `useBoardLive`, `useRunCard`, `useColumn`, `useLogTail`; one `QueryClient` with 03's defaults | Board / log tail |
| 6 | Features: board (300 cards, `memo` cards by id, `contain: content`, a column-move case asserting only two column lists change identity), detail screen (`useRunDetail`), log tail (10k ring, TanStack Virtual, fixed 16 px rows, keyed by `seq`, follow toggle) | Board with 300 fixture cards… |
| 7 | `markdown/`: markdown-it `html: false` → DOMPurify 3.5.0 (fixed `ALLOWED_TAGS`/`ALLOWED_ATTR`, `ALLOWED_URI_REGEXP`, module-private `studio-purify` policy) → `studio-html` policy; `ansi.ts`; lazy detail chunk. `CSP` constant in `src/main/window/csp.ts`, served as a header by `vite preview`; dev-only relaxed CSP plugin for `vite serve` | Rendering pipeline |
| 8 | Tests: co-located unit/component tests; `tests/contract/` run (a) against the fixture; Playwright `browser` project on `vite preview`: every screen, a timed update moves a card | Playwright drives every screen |
| 9 | 50-string XSS corpus on `vite preview` with the CSP header: **0 Trusted Types violations, 0 executions/dialogs, 0 off-origin requests, 0 `javascript:` hrefs**; `*-src-attr` reports recorded only | XSS corpus (wording changes) |
| 10 | `perf.mark('board-populated')` and a log-tail frame counter on `window.__perf`, read by Playwright (`page.evaluate`, or `_electron`'s window on Day 2); no `perf:mark` IPC channel, unlike 04 §8's sketch, so `ipcMain` stays in `register.ts` | New (feeds Day 2/3 measurements) |
| 11 | CI: `checks` job (`npm ci --ignore-scripts`, `npm run check`, `npm test`, `npm run format`) and `e2e` job (Playwright Chromium) | New |

### 4.2 Day 2: Electron shell on macOS (≈ 2.5–3 O-d, was 1.5)

| # | Step | Issue #4 item |
|---|---|---|
| 1 | Main skeleton: ports, composition root, logger; single-instance lock; `ProcessRegistry` + `before-quit` cleanup with a hard timeout; `app.enableSandbox()`; **main lint bans (05 §1, §3.2)** before the code they police | TS main process |
| 2 | `window/`: `hardening.ts` (`secureWebPreferences`, `applySessionPolicy`; `APP_ORIGINS` built in `main.ts`), `appProtocol.ts` on `registerSource` with the CSP header; drop `loadFile` and the meta CSP; traversal e2e | Preload… confined `app://` handler |
| 3 | `process/argv.ts`, `runner.ts` (env allowlist, `KnownExe` resolved at startup = the `PATH` probe, cwd `$HOME`), `adapters/transport/{direct,wsl}.ts`; `adapters/fs/exeProbe.ts`; `adapters/git` `check-ref-format` mints `BranchName` (after 02's pure regex in `shared/domain`); brands `TrustedRepo` (type), `FreeText`; argv fuzz (Direct + pure Wsl wrapper) | Argv builder with branch validation, `PATH` probe, `Direct \| Wsl` |
| 4 | `ipc/register.ts` (origin + main frame + null check, TypeBox schema, byte cap, closed error codes) and `ipc/subscriptions.ts` (keyed registry, `hello`, `render-process-gone`, `destroyed`, log flush 50 ms / 1 s hidden); contract suite run (b) via the `invoke` shim | Preload with intent verbs only |
| 5 | Preload bundled: `api.ts` (`makeStudioApi`, explicit verb list) + `preload.ts` entry sending `hello` | Preload with intent verbs only |
| 6 | Adapters: `GhPollAdapter` for open Issues (`gh api -i`, ETag, only a parsed 304 is "unchanged", drop PRs, `per_page=100`); `WatchAdapter` against a stub `runs watch` (heartbeat watchdog, per-attempt abort, one reconnect; backoff is v1, §7); log tail from a child into main's `LogRing`; normaliser + `reduce` + `mergeRun` stub with Issue #1's three trust rules as tests; `tests/stubs/` + one integration test per adapter | A `gh` read call; a log-tail stream |
| 7 | `app/scheduler.ts`: Visible / Hidden (no Electron import); `main.ts` feeds window `show`/`hide`/`minimize` and the `setVisible` verb into `scheduler.setActivity`. Suspended and `powerMonitor` are v1 (§7) | ≈ 0% CPU hidden |
| 8 | `adapters/electron/confirm.ts` + `Confirmed` brand; `startRun` re-fetches the Issue and shows provenance and exact text | Native start modal |
| 9 | `scripts/dev.mjs` with the guarded dev origin (the main lint bans moved to step 1) | New |
| 10 | `electronFuses` in `electron-builder.yml`; release assertions: fuses via `npx @electron/fuses@2.1.3 read`, no debug port, no fixture marker, CSP header, packaged `APP_ORIGINS` | Fuses read back… (wording extends) |
| 11 | Two `_electron` smoke specs on the unpackaged `dist/` (launch + preload surface; board from stub `gh`, dialog stubbed in main); unset `ELECTRON_RUN_AS_NODE` | New |
| 12 | Subscription check: reload and forced crash (`process.crash()`, 07's addition) return the subscription count to its previous value; killing the stub stream shows "reconnecting", then a fresh snapshot, with no orphan child | New |
| 13 | `perf/sampler.ts` behind `STUDIO_PERF=1`; record installer size, idle RSS, board ≤ 1.5 s (median of 10 launches), hidden CPU on an **idle** machine | The four measurement items (unchanged) |
| 14 | Unchanged: electron-builder + electron-updater, Intel x64 build, signed update round trip, signed app spawns `gh --version`/`git --version` | Unchanged |

The go/no-go needs only steps 1–6, 7 (Visible/Hidden, so the hidden-CPU number reflects the real policy), 8, 10 (fuses, debug port), 13 and 14. Everything else is skeleton work that may move to Issue #1 item 2.

Can slip past the spike without touching the go/no-go: contract run (b), the `_electron` specs, `scripts/dev.mjs`, step 10's release assertions other than fuses and debug port, step 12. Moved out of the spike to §7 with their triggers: the Suspended state with `powerMonitor` and reconnect-on-resume, the main-side ring LRU cap, `WatchAdapter` backoff beyond one reconnect, and the `Settings` port.

### 4.3 Effort

| Addition | Day 1 | Day 2 | Source |
|---|---|---|---|
| Tooling (bundler, tsconfig split, ESLint, Vitest, Playwright, CI) | +0.5 | +0.25 | 06 Day 1–2 |
| Layer wiring, ports, `getStudio` seam (overlaps tooling) | +0.25 | +0.25 | [inferred, 07]; 02 §1 says "about half a day of tsconfig and wiring on Day 1", split here across both days |
| Security structure (lint block, brands, `register`, contract test, release assertions) | +0.25 | +0.25–0.75 | 05 Effort (0.5–1 O-d) |
| Reactive core beyond the checklist (registry, one reconnect, Visible/Hidden scheduler, Query) | — | +0.25 | [inferred, 07]; 03 §4 gives ≈ 550–700 lines, not days. Suspended, ring LRU and backoff moved to §7 |
| Perf hooks and sampler | small | small | 04 §8 |
| **Total** | **≈ +1 (1.5 → 2.5)** | **≈ +1–1.5 (1.5 → 2.5–3)** | |

Honest delta: **Days 1–2 go from 3 to ≈ 5–5.5 O-d (+2 to +2.5).** The spike moves from 7–8 O-d (10 §5; ≈ 6–7 now that Day 4 has moved to Issue #1 item 4, Issue #4 Setup) to **≈ 8–9.5 O-d**. About 1.5 O-d of the addition is v1 work done earlier: tooling 0.75 + security structure 0.5–1 ≈ 1.5, both inside 10 §7's v1 item 2 and the 5.5 O-d security bar. So spike plus v1 (≈ 36 O-d in 10 §7, unchanged by the Day 4 move because that work moves into v1) grows by ≈ 0.5–1 O-d [inferred]. Deferring Suspended, the ring LRU and backoff to v1 saves ≈ 0.25 O-d on Day 2, which offsets taking 05's full 0.5–1 O-d for security, so Day 2 stays at 2.5–3; the deferred work lands in v1, so the total is unchanged. Every figure is an estimate.

## 5. Proposed edits to the Issues (text only; not applied)

**Issue #4:**
- Header: add "Architecture: [`docs/architecture-research/07-recommendation.md`](…) §4".
- Day 1 title: "(≈ 1.5 days)" → "(≈ 2.5 days)". Add, first: "Scaffolding in one change: tsconfig project references + Vite/esbuild build, ESLint/Prettier/Vitest, `engines.node` `^22.22.2 || ^24.15.0` (07 §4.1 steps 1–2)" and "`getStudio()` seam with fixture scenarios selected by `?scenario=` (step 4)".
- Rendering item: "DOMPurify ≥ 3.4.17" → "**DOMPurify ≥ 3.5.0** (3.4.x line ended; two new advisories)"; "Trusted Types" → "Trusted Types (`studio-html`, module-private `studio-purify`)".
- XSS item: "0 dialogs, 0 off-origin requests, 0 CSP violations" → "**0 Trusted Types violations, 0 executions/dialogs, 0 off-origin requests, 0 `javascript:` hrefs**, on `vite preview` with the CSP header (`*-src-attr` reports recorded, not failed)".
- Day 2 title: "(≈ 1.5 days)" → "(≈ 2.5–3 days)". Preload item: append "IPC sender check (origin + main frame + null), TypeBox schema per verb; `app://` via `protocol.registerSource` (fallback `protocol.handle`) with the CSP as a header; meta CSP and `loadFile` removed".
- Fuses item: append "plus release assertions: no fixture marker, CSP header present, packaged `APP_ORIGINS` = `app://studio`".
- Add Day 2: "Reload and forced crash leave the main-side subscription count unchanged; killing the stream stub shows reconnecting, then a fresh snapshot, with no orphan".
- Hidden-CPU item: append "(main's three-state activity policy, 07 §2 row 5; measured on an idle machine)".
- Day 5: "`tsc` and the tests pass" → "`npm run check` (`tsc -b` + ESLint) and `npx vitest run` pass"; "layers set by hand" → "layers set with the 07 §3.3 JSON".

**Issue #1:**
- Decisions taken, add: "**Architecture:** `src/{shared,main,preload,renderer}` + `tests/`; ports and adapters in main; a hand-written `StudioApi` contract; Zustand for pushed state, TanStack Query for on-demand reads (architecture research 07)."
- Item 2: replace the layout with "`src/shared/{domain,contract}`, `src/main`, `src/preload`, `src/renderer`, `tests/`; generated harness types in `src/main/adapters/harness/schema/` (07 §3)".
- Item 3: "`/devscene:harness-analyze`" → "`/devscene:analyze`"; "`commands.typecheck` is `tsc`" → "`commands.typecheck` runs `npm run check` (`tsc -b` + ESLint) and `commands.test` runs `npx vitest run`, both through `devscene-scripts/` wrappers; Playwright runs as a required GitHub check"; add "Expect a permanent `layer-drift` warning for `build, scripts, vm, src/preload`" and "Run `config set layers` with the 07 §3.3 JSON **before** `/devscene:analyze`, and decline any layers proposal it makes (it applies one only on an explicit yes or `--apply-layers`)".
- Item 10: "`/devscene:harness-analyze`" → "`/devscene:analyze`" (optionally also drop "harness" from its title and button text).
- Item 7 (F-1): append the §6 asks (per-event `ts`, documented heartbeat interval, which runs' `log` events `runs watch` carries plus a per-run filter).
- Item 21: carry them into the F-1 issue when it is filed (devscene #170 mapping).

## 6. Harness asks

| Ask | For | Status |
|---|---|---|
| A `ts` (ISO-8601 with offset) on every `runs watch` event | gh-vs-watch precedence in `mergeRun` (03 §5.3) | **Add to F-1 now** |
| Document the heartbeat interval in the contract | The watchdog fires at 3× the interval (03 Risk 3) | **Add to F-1 now** |
| A JSON Schema for the `--json` output in `schemas/` | TypeBox validates it as-is; otherwise switch to zod (05 §2) | Already in F-1 (10 §8 row F-1) |
| Say which runs' `log` events `runs watch` carries, and allow a per-run filter | On `Wsl`, logs arrive only on the stream; a filter keeps main's rings bounded [inferred] | **Add to F-1 now** (question) |
| `seq` on `runs watch` events | Only if the stream becomes lossy (relay) | Deferred (03 §5.4) |
| An `electron` detection preset for `src/{main,preload,renderer}` + `src/shared` | `init` falls to `flat` today | Deferred: one `config set layers` suffices |
| A way to acknowledge catch-all-routed directories so `layer-drift` stops warning | Permanent WARN for `build, scripts, vm, src/preload` | Deferred, nice to have |
| How a path matching two `layers[]` rows is resolved | Only the catch-all overlaps here (02 Risks) | Question; check at Day 5 |
| Chromium under the gate sandbox (bubblewrap/Seatbelt) | Only if Playwright ever joins `commands.test` | Deferred (06 Risk 2) |

## 7. Deferred mechanisms and their triggers

| Mechanism | Add when | From |
|---|---|---|
| `epoch` + gapless `seq` on pushes | A transport that can drop or reorder (MessagePort relay, utilityProcess, network), or measured mirror divergence | 03 §5.4 |
| Grace period before stopping a source | A costly `runs watch` respawn on a quick repo toggle or reload is measured | 03 §5.4 |
| Coalescing board patches (≈ 100 ms) | Profiling shows `run_updated` bursts causing jank | 03, 04 §2 |
| One source shared by several windows | A detail pop-out window (not v1) | 03 |
| Full `mergeRun` precedence table; workflow-run and PR polling | Issue #1 item 5; remote runs and the Done column after the spike | 03 §5.4 |
| RxJS 9 | Stable, and three or more sources need time-based composition | 03 §2 |
| Stop log forwarding while hidden + backfill on show | Hidden measurement with an active stream misses the target (§2 row 8) | 04 §4 |
| `utilityProcess` / `MessagePort` log stream | A source adapter crashes or blocks main in practice, or WSL stream handling is heavy | 01, 04 §1 |
| `worker_threads` | A single CPU job over ≈ 16 ms shows in a trace | 04 §1 |
| Board virtualisation | Above ≈ 2,000 cards | 04 §3.1 |
| React Compiler | The component count grows | 04 §3.1 |
| `module.enableCompileCache()`, more code splitting | Main grows well past 1 MB; parse time shows in traces | 04 §5 |
| Doubling poll intervals on battery | Optional, any time | 04 §4 |
| electron-trpc 1.x | Verb count passes ≈ 40, or per-procedure validation is wanted | 01 §4 |
| electron-vite 6 | `scripts/dev.mjs` passes ≈ 100 lines | 06 §2 |
| zod 4 instead of TypeBox | F-1 ships TS/zod types, not a JSON Schema | 05 §2 |
| `protocol.handle` instead of `registerSource` | The Experimental API changes or misbehaves | 05 §4 |
| eslint-plugin-import-x / boundaries / dependency-cruiser | Specifier matching proves leaky / rules exceed ≈ 10 patterns | 02 §5 |
| A `preload` layer row or a dedicated security reviewer | The preload outgrows one file | 02 §4, 05 §8 |
| New ports (logger and others) | A second implementation or a test fake appears | 02 §1 |
| `safeStorage` | Studio ever stores a token | 05 §6 |
| Playwright in `commands.test` | The owner wants it and Chromium starts in the gate sandbox | 06 §8 |
| TS 7, oxlint | typescript-eslint supports TS 7 | 06 §7 |
| Drop contract run (b) | It costs more than it catches | 06 §4 |
| Suspended activity state (`powerMonitor` `suspend`/`lock-screen`, reconnect on resume) | v1 (Issue #1 item 2), or earlier if sleep/resume leaves a dead stream in the spike; it was a Day 4 item, now in Issue #1 item 4 | 04 §4, §2 row 5 |
| Main-side log ring LRU cap (10 rings) and drop-on-finish rule | Studio tails more than one run's log; v1 | 04 §7, §2 row 7 |
| `WatchAdapter` backoff beyond one reconnect | v1, or a stub that flaps shows reconnect storms | 03 §5 |
| `Settings` port and `adapters/fs/settings.ts` | The first persisted setting (v1 settings store, 05 Post-spike) | 02 §1, 05 |

## 8. Risks and what remains unverified

**Day 1 checks:**
1. `vitest run` lists both projects and finds a test in each (merged function-form Vite config; fallback: a separate `vitest.config.ts`) (06 §5).
2. typescript-eslint's `projectService` finds the root `*.config.ts` files through the solution, or needs `allowDefaultProject` (06 §7).
3. The dev-only CSP relaxation lets React Refresh and HMR run, and Vite's error overlay coexists with enforced Trusted Types (else disable the overlay) [inferred].
4. DOMPurify 3.5.0 with the module-private `studio-purify` policy renders cleanly in the real build; the corpus re-checks it (05 Risk 2).
5. A card moving between columns changes only the two affected column lists' identity (04 §3.1).
6. `moduleResolution: bundler` with project references builds cleanly across all projects (06 §2, inferred).

**Day 2 checks:**
7. `hello` ordering: subscription count after reload and forced crash (§2 row 4) [inferred].
8. `registerSource` (Experimental) serves `app://studio` with the CSP header and refuses traversal (05 Risk 1).
9. Quit cleanup never hangs Cmd+Q (hard timeout) (01 Risk 6).
10. `_electron` on Playwright 1.65.1 with `ELECTRON_RUN_AS_NODE` unset (06 Risk 3).
11. Every absolute performance number: 04's figures were taken under heavy concurrent load; only same-run ratios hold. Re-measure on an idle machine, and on the Linux VMs on Day 3 (04 §0).

**Standing risks:**
- **F-1 does not exist.** `adapters/harness/` and the schema location may move inside main; the spike runs against a stub (02, 03).
- **gh 304 handling** relies on CLI behaviour (exit 1 for any status ≥ 300); pin it with an adapter test (03 Risk 2).
- **TypeScript is pinned at 6.0.3** by typescript-eslint's `<6.1.0` peer (02, 06).
- **Young or single-maintainer dependencies:** Zustand 5.1.0 (19 days), TypeBox 1.x, electron-vite (fallback only). Pin exact versions (03, 05).
- **Two state tools** must be kept apart by `renderer.md`, or agents will mix them (03 Risk 6).
- **Killing `wsl.exe`** may orphan the Linux side; prefer harness stop verbs (01 Risk 2; Issue #1 item 4).
- **Out of this file's scope but security-relevant:** the AppImage runs with `--no-sandbox` on Ubuntu 24.04 (Issue #4 early Day 3 finding); Day 3 must decide the Linux formats with the 10 §6 bar in mind.

## Sources

No new external checks were needed: every conflict was settled from the area files' final text.

1. `01-electron-process-model.md` — TL;DR, §1–§6 (processes, IPC, typed IPC, browser-mode seam, lifecycle), Risks; review and resolution in `reviews/01-electron-process-model.md`.
2. `02-layered-architecture.md` — §1–§8 (layering decision, tree, layer map, dependency rules, patterns, expause_web); review resolution incl. the cross-file test-placement decision.
3. `03-reactive-data-flow.md` — §3.1 (TanStack Query), §4 (pipeline), §5 (lifecycle, `hello`, log batching), §5.4 (deferred), §6 (polling); review resolution.
4. `04-performance.md` — §0 (measurement caveat), §1–§8, Risks open items (a)–(e); review resolution.
5. `05-security-architecture.md` — §1 (choke points), §2 (trust seam, TypeBox), §3 (DOMPurify policy), §4 (hardening), §5 (browser mode), §7 (CI suites), Risks 8–9; review resolution.
6. `06-testing-and-tooling.md` — §2 (build), §3 (tsconfig), §4–§8 (tests, fixtures, lint, gates); review resolution.
7. `../product-startup-research/10-recommendation.md` — §5 (spike), §6 (security bar), §7 (costs).
8. GitHub Issue #4 (Day 1 / Day 2 checklist, early Day 3 findings comment) and Issue #1 (items 2, 3, 10, 21), via `gh issue view`, 2026-11-25.
9. `package.json` (`engines.node >=22.12.0`, `tsc`-only build) — local, read 2026-11-25.
