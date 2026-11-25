# 02 — Layered architecture
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

- **Yes, start the spike on a layered layout, and keep it small.** Two facts settle it. The folders chosen on Day 1 become the harness's layer map (one implementer and reviewer per layer). And browser mode (a v1 requirement) needs the renderer to talk to a *port* with two adapters from the first screen. The smallest clean version is **one folder per Electron process, plus one shared pure-TS folder**. No use-case classes, no DI container, no event bus. [inferred]
- **Tree:** keep the existing `src/main`, `src/preload`, `src/renderer` (the electron-vite convention [1]) and add `src/shared/{domain,contract}`. Hexagonal ports and adapters live **inside main** (`ports/`, `adapters/`, `app/`). In the renderer, the `studio` port is the contract's `StudioApi` type, with `studio/ipc.ts` and `studio/fixture.ts` as its two adapters. [inferred]
- **Issue #1's `app/` + `app/main/` + `contract/` layout should not be used as written.** `app/main/` nested inside the renderer's `app/` makes two layer paths overlap. It puts the sandboxed preload under Node main's rules. And it puts the generated harness types where the renderer can import them. §3 gives the details. [inferred]
- **Harness layers (5 rows):** `shared`, `main`, `renderer`, `tests`, and the catch-all `general` (`.`). The one-file preload routes to `general`, with a "Preload" section in `conventions.md` (§4). **`devscene init` will not detect this tree:** it falls to `flat` (only `general`). Set the layers by hand with one `devscene config set layers '<json>'`, as Issue #1 item 3 already expects. [verified: scratch `init` + `config set layers` + `doctor`, devscene 0.7.1 [9]]
- **Tests:** unit and component tests sit next to their code, because a harness implementer may write only inside its own layer path. `tests/` holds only the cross-layer suites (IPC contract suite, stub binaries, Playwright). [verified: devscene `layer-implementer.md:48`, `task-plan-writer.md:129`]
- **Dependency rules:** `shared/domain` imports nothing. `shared/contract` imports only domain. main, preload and renderer each import `shared` and never each other. Inside main, `app/` sees only `ports/` and `shared/`, never `electron`, `node:child_process` or `adapters/`.
- **Enforcement, cheapest that works:** (1) **TS project references**, one tsconfig per process plus shared. These are needed anyway for the different `lib`/`types` settings, and a cross-process import fails with TS6307 (tested on TS 6.0.3). `tsc -b` then becomes **typecheck only**: it emits no JavaScript, so the same change must move the build to a bundler (tool: 04/06, settled in 07). (2) **ESLint core `no-restricted-imports`** in flat-config `files` blocks for the few rules inside a process (tested on ESLint 10.15.0). Skip eslint-plugin-boundaries, eslint-plugin-import-x and dependency-cruiser for now. [verified: local tests §5]
- **Patterns worth it:** ports/adapters, a hand-wired composition root in each process, Strategy (`Transport` Direct|Wsl), one typed argv-builder function, a read-model (runs from gh + registry), Adapter (fixture vs IPC), Facade (preload), Command-as-data (intents shown in the native confirm), and a hand-rolled `Result` over IPC. **Skip** DI containers, use-case-per-file classes, a global event bus, Repository-with-CRUD, Redux-style action layers and barrel files.
- **expause_web:** carry over domain types kept apart from wire DTOs, remappers (here, harness JSON → domain inside main's harness adapter) and feature folders. **Not** its dependency direction: expause is top-down (`Presentation → Domain → Data`, domain imports data), while Studio points dependencies *at* the domain. Leave behind Firebase, Redux, Dexie, barrels and **use-case-per-file** (186 files, including pass-throughs such as `fetchFeedUseCase.ts`). [verified: local files §8]
- **Errors:** expected failures are typed `Result` values that cross IPC as data. Electron rejects `invoke` with a *different* `Error` object than the one main threw [2]. Logging happens in main adapters and at the IPC boundary. The renderer uses error boundaries per feature.

## Scope

This file covers the layers and the folder tree; where the domain, ports, adapters and IPC contract live; the harness `layers[]` map and whether `init` detects it; dependency rules and the tool that enforces them; SOLID and patterns with file placement; the expause_web comparison; and where errors and logs are handled.

It leaves to the other files: IPC primitives and the preload build (01), stores, streams and subscription lifecycle (03), performance and the bundler (04), security controls and their placement (05; this file only names the folders they land in), and test runners, the build tool and the browser-mode harness (06).

## Findings

### 1. Owner question 2: layered from Day 1?

| Argument | For layering now | Against |
|---|---|---|
| Throwaway risk | The owner expects Electron to stay, so spike code becomes the skeleton (Issue #1 item 2). Moving files later means rewriting every conventions doc and `layers[]`. | The spike's job is a go/no-go (10 §5). If Electron flips, the layers die with it. |
| Browser mode | It needs a renderer that talks only to a `StudioApi` port, with fixture and IPC adapters. That is a layer split you pay for on Day 1 anyway. | — |
| Security bar | One argv builder, intent-only IPC and a preload facade (10 §6) are *placement* rules. Without fixed folders, they leak. | — |
| Speed | — | Ceremony (interfaces, wiring) slows Day 1 when the goal is a visible board. |
| Unknowns | — | The harness `runs … --json` contract (F-1) does not exist yet. Adapters written now will change. |

**Decision: layer now, but only along lines the app already has.** Electron's three processes are a hard boundary whatever we do (separate runtimes, separate builds). Shared domain code is the only addition. Add a port only where a second implementation or a test fake exists **today**: `StudioApi` (fixture vs IPC), `Transport` (Direct vs Wsl/fake), `GhClient`/`HarnessClient`/`GitClient` (fake in `app/` unit tests), `Confirm` (native dialog vs auto-confirm in tests), `FileWatcher` (fake in tests). Everything else (the logger, for one) is a plain module until a second implementation appears. The cost is about half a day of tsconfig and wiring on Day 1 [inferred]. The answer to "against" is that F-1 churn stays inside one adapter folder (`src/main/adapters/harness/`).

### 2. Hexagonal across the process boundary

```
renderer (sandboxed)            preload (sandboxed)             main (Node, privileged)
features → studio port ──IPC──▶ facade: window.studio ──IPC──▶ ipc/register → app/* → ports ◀─ adapters → gh/git/devscene/fs
   ▲  StudioApi type             (implements StudioApi)          (handlers)   (services)          (spawn via process/argv)
   └──────────────── all three import src/shared (domain + contract), never each other ───────────────┘
```

- **Domain** (`src/shared/domain/`) is pure TS that both processes need: `Run`, `Issue`, `RunPhase`, `RunStatus` and badge derivation, `columnOf(run): 'todo'|'inProgress'|'done'`, the trust rules (`github-actions[bot]` progress comment only; Actions run state beats labels; branch JSON untrusted, Issue #1 "Data source"), the pure branch-name regex (the `git check-ref-format` call is I/O and stays in main), and `Result`/`StudioError`. No I/O and no globals. [inferred]
- **Contract** (`src/shared/contract/`) is the IPC contract: `studio-api.ts` (the `StudioApi` interface, the renderer's port; 01's sketch), `studio-live.ts` (the push event types; 03's sketch), channel names, intents, and the payload validators (library choice in 05). It is hand-written. 01, 03 and 06 sketch this as a top-level `contract/`; this file places it at `src/shared/contract/` (07 should use one path). [inferred]
- **The harness's JSON Schema types are a different contract.** They are generated and consumed only by main's harness adapter, which maps them to domain types (the expause "remapper" idea). So they live in `src/main/adapters/harness/schema/` (generated, never hand-edited), not in a top-level `contract/` the renderer could import. [inferred]
- **Main's hexagon:** `ports/` (interfaces), `adapters/` (implementations), `app/` (services that use only ports and domain, grouped per area, not one class per use case), `ipc/` (the driving adapter: validates input, calls `app`, returns `Result`), and `main.ts` (the composition root).
- **Renderer's hexagon:** features and state depend on `StudioApi`, received from a React context. `main.tsx` (the composition root) picks the adapter by **build mode**, not by `window.studio ?? fixture`. That way the fixture code is left out of the packaged app and can never act as a silent fallback (01 §5, 05).

```ts
// src/main/ports/transport.ts
export interface Transport { spawn(cmd: Argv, opts: SpawnOpts): ChildHandle }   // Direct | Wsl
// src/main/main.ts  (composition root, wired by hand)
const transport = process.platform === 'win32' ? wslTransport(distro) : directTransport();
const gh = ghCli(transport); const runs = runsService({ gh, harness: harnessCli(transport), registry: fsRegistry() });
registerIpc(ipcMain, { runs, intents: intentsService({ gh, harness, confirm: electronConfirm(dialog) }) });
// src/renderer/main.tsx
const studio: StudioApi = import.meta.env.MODE === 'browser' ? createFixtureStudio(scenario()) : window.studio;
```

### 3. Folder tree (whole repo)

```
devscenestudio/
├── src/
│   ├── shared/                 LAYER shared: pure TS used by every process; no electron, node:*, DOM or React
│   │   ├── domain/             Run, Issue, RunPhase, columnOf, trust rules, branch regex, Result/StudioError
│   │   └── contract/           studio-api.ts (StudioApi), studio-live.ts (push events), intents, channel names, validators
│   ├── main/                   LAYER main: Electron main process (Node, privileged)
│   │   ├── main.ts             composition root: build adapters, services, IPC, window
│   │   ├── app/                services per area (runs read-model, intents, repos, doctor); ports + shared only
│   │   ├── ports/              GhClient, GitClient, HarnessClient, Transport, FileWatcher, Confirm
│   │   ├── adapters/           implementations of ports, one folder each
│   │   │   ├── gh/             `gh` CLI client → domain (GitHub API client later behind the same port)
│   │   │   ├── git/            `git` client (check-ref-format, branch/merge state)
│   │   │   ├── harness/        `devscene … --json` client; schema/ = generated harness types (never edit)
│   │   │   ├── transport/      direct.ts, wsl.ts (Strategy behind Transport)
│   │   │   ├── fs/             file watcher, local registry.json reader, log tail
│   │   │   └── electron/       native confirm dialog, shell/openExternal wrappers
│   │   ├── process/            the one argv builder + spawn helper (security rules in 05)
│   │   ├── ipc/                registers contract channels → app services; input validation, sender checks
│   │   ├── window/             BrowserWindow creation, session/CSP hardening (05)
│   │   └── log/                logger module (file in app logs dir); a plain module, not a port
│   ├── preload/                own tsconfig; harness routes it to `general` (§4): sandboxed facade exposing `studio`
│   │   └── preload.ts
│   └── renderer/               LAYER renderer: React UI; no electron, no node:*
│       ├── index.html
│       ├── main.tsx            composition root: choose IPC or fixture adapter, mount providers
│       ├── studio/             StudioApi adapters: ipc.ts (window.studio), fixture.ts + fixtures/ (scenarios, streams)
│       ├── state/              stores/subscriptions over StudioApi (design in 03)
│       ├── features/           board/, run-detail/, log-tail/, repo-picker/, doctor/: screens + their hooks
│       ├── ui/                 shared presentational components (no StudioApi access)
│       └── markdown/           sanitised markdown rendering (05)
├── tests/                      LAYER tests: cross-layer suites only (06): contract/, e2e/ (Playwright), stubs/bin/, setup-dom.ts
├── scripts/                    build/sign helpers (exists)
├── build/                      electron-builder resources, entitlements (exists)
├── vm/                         Linux VM tooling (exists)
├── docs/                       research and design docs
└── .claude/context/            harness conventions docs (one per layer, written at item 3)
```

**Unit and component tests sit next to the code** (`*.test.ts[x]`), so each layer's implementer writes its own tests. This is not a style choice: an implementer works only inside its dispatched layer path and returns a blocker otherwise (devscene `plugin/agents/layer-implementer.md:48`), and the plan writer puts a unit's required test file in that unit's own task (`task-plan-writer.md:129`) [verified]. Runner choice is in 06.

**Issue #1 item 2 layout compared with this proposal:**

| Issue #1 suggestion | Problem | This proposal |
|---|---|---|
| `app/` = renderer, `app/main/` inside it | Layer paths overlap. `layers[].path` is compared with a change's file paths to check it landed in its layer (devscene `docs/config.md:137`), so a renderer unit could legally edit main. | Sibling `src/main`, `src/renderer` |
| main and preload together in `app/main/` | Preload is sandboxed: `require` loads only `electron`, not local files [3]. Its rules differ from Node main's, and one conventions doc would mix them. | Separate `src/preload` folder and tsconfig; its rules live in their own section of `conventions.md` (§4) |
| `contract/` = generated harness types | Only main parses harness output. Putting the types at the top level invites the renderer to use raw harness shapes. The IPC contract, which is the one all processes share, has no home. | `src/shared/contract` (IPC) + `src/main/adapters/harness/schema` (generated) |
| Moving from today's `src/*` | Churn with no gain. `src/{main,preload,renderer}` is the electron-vite convention [1]. | Keep `src/*` |

The one good idea in it, a dedicated contract location, is kept.

### 4. Harness layer map

`layers[]` keys are `name`, `path` and `conventions`, all required, and at least one row must have `path: "."` (devscene `docs/config.md:136-138,178`) [verified]. Config order is the **bottom-up ship order** the plan writer splits cross-layer work in, with the catch-all last (devscene `plugin/agents/task-plan-writer.md:105`) [verified]. Each task touches exactly one layer, and the implementer stops if it needs another (`layer-implementer.md:48`) [verified]. So **every extra layer adds a task to every cross-cutting feature**, which argues for few layers.

```json
[
  { "name": "shared",   "path": "src/shared",   "conventions": ".claude/context/shared.md" },
  { "name": "main",     "path": "src/main",     "conventions": ".claude/context/main.md" },
  { "name": "renderer", "path": "src/renderer", "conventions": ".claude/context/renderer.md" },
  { "name": "tests",    "path": "tests",        "conventions": ".claude/context/tests.md" },
  { "name": "general",  "path": ".",            "conventions": ".claude/context/conventions.md" }
]
```

`config set layers` accepts this JSON, and `doctor` then reports `layer-profile` PASS [verified: scratch run, devscene 0.7.1 [9]].

- **Why these units:** each is one runtime with one rule set a reviewer can check alone. A typical *read* feature ("show run phase on the card") is shared (type and rule) → main (read-model) → renderer (badge): three tasks. A new *verb* is the same three tasks plus the preload line (below). [inferred]
- **Preload has no row (decision).** It is one ~30-line file that changes only when a verb is added. A row of its own would add a task to every new verb, and the payoff is smaller than it looks: per-unit `layer-reviewer` runs only in the semi-autonomous flows and the autonomous user-review flow, never the autonomous plan flow (its agent description), and the end-of-branch `branch-reviewer` checks the whole diff against every conventions doc anyway. A catch-all dispatch reads **every** conventions document (`layer-implementer.md:17,82`) [verified]. So preload work routes to `general`, and `conventions.md` gets a short "Preload (sandboxed facade)" section: CommonJS only, `import type` only unless bundled, no `ipcRenderer` exposure (01, 05). If the preload is bundled (04/06), it can build its verbs from the contract's channel table, and then a new verb needs no preload edit at all. Cost: a permanent `layer-drift` warning for `src/preload` (below). Reconsider if 05 wants a dedicated security reviewer on the preload. [inferred]
- **A new verb leaves the typecheck red between tasks.** `StudioApi` lives in `shared`, but main (`satisfies Handlers<StudioApi>`, 01), the renderer's fixture and the preload implement it. The shared task that adds a verb makes the whole-tree `tsc -b` fail in those projects until their tasks land. Each unit runs the whole-tree typecheck, and a failure wholly outside the unit's change is recorded as an evidence downgrade, not a blocker (`layer-implementer.md:154`) [verified]. Bottom-up order forces the shared task first, so the choice is: **accept the downgrades, and say so in `shared.md`.** The Run gates phase checks the final tree. [inferred]
- **Merged `domain` and `contract` into one `shared` layer:** both are pure, small, dependency-free TS. Separate layers would add a task to every new IPC verb. Their conventions fit in one doc with two sections. [inferred]
- **Not split:** main into app/adapters, or renderer into state/ui. Most main features touch a service and its adapter together, and most renderer features touch a hook and a component together. Splitting would double the task count for no review benefit. The rules inside each layer are enforced by lint (§5). [inferred]
- **`tests` row (decision, cross-checked with 06).** 06 is right that unit and component tests must be co-located (§3). It rejects a `tests` layer in the sense of expause's `src/test/unit/<layer>/` mirror tree, which this file does not propose. The `tests` row here covers only suites that span layers and belong to no single one: the IPC contract suite, stub binaries and Playwright specs. Those have their own rules (scenario-by-URL, `data-testid`, stub `PATH`), which earn their own `tests.md`; the harness gives every detected preset a `tests` row with that document for the same reason (`docs/cli.md` §4 "What a preset's layer profile carries") [verified]. Use one root, `tests/`, holding what 06 sketches as `test/` and `e2e/`. Cost: one conventions doc, and a feature that adds an e2e spec adds a `tests` task (it would be a `general` task otherwise). Fixture scenarios stay in `src/renderer/studio/fixtures/` because browser mode ships them, so a new browser-mode scenario is two tasks (renderer fixture, then tests spec). [inferred]
- **`general`** uses the shared doc `conventions.md`, the harness's own name (devscene `cli/src/detect/presets.ts:101-132`) [verified].
- **Will `init` detect it? No.** Row 3 (`layered-clean-arch`) needs at least two of `data/`, `domain/`, `presentation/` *directly* under the app dir or its `src/`, `app/`, `lib/`, `internal/` or `pkg/` (`docs/cli.md` §4 row 3; `findLayeredRoot` tests exactly `<root>/<name>`, `signals.ts:651-662`). `src/shared/domain` is one level too deep. With no other match, the result is row 17, `flat:fallback`: only `general`, and no `tests` row, because `flat` has no entry in `PRESET_TEST_ROOTS` (`presets.ts:556-567`; `docs/cli.md` §4) [verified; reproduced by `init --dry-run` on the proposed tree [9]]. **Avoid naming a top-level `src/api/` or `src/handlers/`,** which would silently select `api-service` with one bogus `api` layer [verified: row 5, and the review's scratch run].
- **Forcing detection was considered and rejected.** Renaming to `src/domain` + `src/data` (main) + `src/presentation` (renderer) would make `init` emit `data`/`domain`/`presentation` rows pointing at `data-layer.md` etc. (`presets.ts:104-108`). But it would leave preload homeless, mislabel main (it is window, IPC and process control, not "data"), and break the electron-vite convention. All to save one `config set` command, run once. [inferred]
- **After `init`:** run `devscene config set layers '<json above>'`, then `/devscene:analyze` to fill the conventions docs. `doctor` will then warn twice. `layer-drift` names `build, scripts, vm, src/preload` as routed to the catch-all, and that warning is permanent: add them as layers or accept it, because a `detection.review` verdict does not clear it (`docs/cli.md` §7, `layer-drift` bullet). `setup-analysis` warns until `/devscene:analyze` writes the four new conventions docs. [verified: scratch `init` + `config set layers` + `doctor`, devscene 0.7.1 [9]]

### 5. Dependency rules and their enforcement

| From ↓ may import → | shared/domain | shared/contract | main | preload | renderer | externals |
|---|---|---|---|---|---|---|
| shared/domain | — | ✗ | ✗ | ✗ | ✗ | none |
| shared/contract | ✓ | — | ✗ | ✗ | ✗ | validator lib only |
| main/app | ✓ | ✓ | `ports/` only | ✗ | ✗ | none (no `electron`, `node:child_process`) |
| main/adapters, process | ✓ | ✓ | ports, process, log | ✗ | ✗ | node:*, `electron` only in `adapters/electron` |
| main/ipc, main.ts | ✓ | ✓ | all of main | ✗ | ✗ | `electron` |
| preload | type-only | type-only (or bundled, 01) | ✗ | — | ✗ | `electron` |
| renderer/features, state, ui | ✓ | ✓ (types) | ✗ | ✗ | not `studio/*` adapters; `ui/` not `state/` | react, DOM |
| renderer/main.tsx, studio | ✓ | ✓ | ✗ | ✗ | all | — |
| tests | ✓ | ✓ | ✓ | ✓ | ✓ | test tooling |

Tools, checked live on 2026-11-25:

| Tool | Status | Fit with ESLint flat config / TS 6.0.3 | Cost here | Verdict |
|---|---|---|---|---|
| **TS project references** | Built in | Tested on TS 6.0.3: a renderer→main import fails with **TS6307** "not listed within the file list of project". renderer→shared builds. Only a **referenced** project may not disable emit (**TS6310** "Referenced project … may not disable emit"), so `shared` uses `emitDeclarationOnly` with an outDir cache; the leaf projects `main`, `preload`, `renderer` may stay `noEmit`. `tsc -b` then exits 0 **and emits no `.js`**. [verified, scratch test [7]] | Four tsconfigs plus a root solution file. Needed anyway: shared gets `types: []` (so `document` or `process` cannot compile in domain), main gets Node types and no DOM, renderer gets DOM + JSX + bundler resolution. Exact `lib` and flags in 06 §3. | **Use. Enforces the process boundaries for free.** `commands.typecheck` becomes `tsc -b`. |
| **ESLint `no-restricted-imports`** (core) | ESLint 10.15.0 (published 2026-11-13) [4] | Tested: flat-config `files: ["src/renderer/ui/**"]` with `patterns: [{group: ["**/adapters/**"]}]` flags the relative `../adapters/ipc.js`. [verified, scratch test] Matches the specifier string, not the resolved path. `allowTypeImports` exists [5]. | About 6 config blocks. No extra dependency beyond ESLint + typescript-eslint (8.74.0, peer `typescript >=4.8.4 <6.1.0`, so OK on 6.0.3 [4]), which 06 adds anyway. | **Use** for the rules inside each process. |
| eslint-plugin-import-x `no-restricted-paths` | 4.18.1, last modified 2026-11-09, active [4] | Matches **resolved** paths by zone, which removes the specifier-string caveat above. Not tested here. | One plugin plus a resolver. | Skip at this size; the first swap if specifier matching proves leaky. |
| eslint-plugin-boundaries | 7.4.4, 2026-11-15, active [4] | Works on ESLint 10 flat config (tested). v7 already deprecates the `rules` option for `policies`, and needs a resolver for NodeNext `.js`→`.ts` specifiers. In the test, one of two violations went unreported with the node resolver (not diagnosed). [verified] | Plugin + resolver + element config. | Skip for now. Reconsider if the rules outgrow ~10 patterns. |
| dependency-cruiser | 18.9.0, 2026-11-22, active; node `^22\|\|^24\|\|>=26` [4] | Separate CLI, not ESLint. Supports TypeScript `>=2 <7 \|\| >=7.1 <8` (fine for 6.0.3; **not 7.0.x**). [verified: npm `supportedTranspilers`] | Second config language, second CI step. Gives graphs and cycle checks. | Skip. Its graph output is nice to have, not needed at this size. |

**Recommendation:** project references for "which process may see which" plus core `no-restricted-imports` for "inside a process". Total cost about 1–2 hours on Day 1 [inferred]. Both run inside the harness's existing `typecheck`/lint gates (06).

**Build dependency (settled in 07).** Once the root `tsconfig.json` becomes a solution file, today's `"build": "tsc -p tsconfig.json && …"` emits nothing and `npm start`/`dist:mac` would ship a stale or empty `dist/` (`package.json:14-18`) [verified: scratch test [7]]. So the tsconfig split and a bundler must land in **the same change**, and the bundler builds main, preload (CommonJS, 01) and renderer. Both candidates fit this tree unchanged: 04 recommends electron-vite 6, 06 recommends Vite (renderer) plus a small esbuild script (main, preload) with electron-vite as fallback. This file does not pick; 07 does. Do not merge the tsconfig split before the build change. [inferred]

### 6. Owner question 3: SOLID and patterns, concretely

| Principle / pattern | Where in Studio | File | Payoff for this app |
|---|---|---|---|
| Ports & adapters (DIP) | main services depend on `GhClient`, `HarnessClient`, `Transport`…; renderer depends on `StudioApi` | `src/main/ports/*.ts`, `src/shared/contract/studio-api.ts` | F-1 churn stays in `adapters/harness/`. Services unit-test with fakes and no Electron. Browser mode works at all. |
| Composition root, hand-wired DI | one place per process builds the object graph | `src/main/main.ts`, `src/renderer/main.tsx` | Wiring is visible in about 30 lines. Tests wire fakes the same way. No container, decorators or reflect-metadata. |
| Strategy | `Transport = Direct \| Wsl`, chosen once from `process.platform` | `src/main/adapters/transport/{direct,wsl}.ts` | Everything above spawn is OS-agnostic. Windows (item 4) is one new file. A mocked `wsl.exe` slots in for the argv fuzz (item 19). |
| One argv builder (typed function, not a fluent builder) | `ghArgv({ cmd, repo, json })`, `gitArgv({ cmd, args })` | `src/main/process/argv.ts` | One place enforces `--`/`--end-of-options`, `--repo` and branch validation (10 §6). One fuzz target. A fluent API would add surface without adding checks. |
| Read-model (not Repository) | `Run[]` merged from Actions runs, labels, PRs, artifacts and the local registry, with trust rules applied | `src/main/app/runs.ts` + `src/shared/domain/trust.ts` | Item 5's merge logic lives in one testable function. The UI never sees untrusted inputs. Read-only, so no CRUD Repository. |
| Adapter | `StudioApi` via IPC vs via fixtures; `gh` CLI now, REST later behind `GhClient` | `src/renderer/studio/{ipc,fixture}.ts`, `src/main/adapters/gh/` | The same feature code runs in Electron, in Playwright browser mode and for the QA agent. |
| LSP, checked by tests | fixture and IPC adapters must behave the same | 06's `describeStudioApi` suite in `tests/contract/` | Runs against the fixture adapter and against preload client + main handlers over an in-memory IPC pair, so no Electron is needed. Real Electron IPC is covered only by 06's 2–3 `_electron` smoke specs. Cost: one suite, written once (06). |
| Facade | preload exposes `studio` verbs, never `ipcRenderer` | `src/preload/preload.ts` | The whole renderer-reachable surface is one reviewable file. Unbundled: an explicit object `satisfies StudioApi` with a **type-only** import (sandboxed `require` cannot load local files [3]). Bundled (04/06): verbs built from the contract's channel table, so a new verb needs no preload edit. |
| Command as data | intents (`pause`, `drop`, `start`, `answer`) are a typed union. Main builds the exact argv, shows it in the native confirm, then executes | `src/shared/contract/intents.ts`, `src/main/app/intents.ts` | The confirm dialog shows exactly what will run (08 §3.10). One audit and log point. Plain data and a `switch`, no command classes. |
| Result / Either | expected failures (`gh-auth`, `not-found`, `untrusted-repo`, `cancelled`) as values | `src/shared/domain/result.ts` (about 15 lines) | Typed errors survive IPC, which a thrown error does not [2]. Skip `neverthrow`-style libraries: 15 lines suffice. |
| SRP / ISP | one adapter per external tool; narrow ports (`GhClient` has only the calls used) | `src/main/ports/` | Fakes stay tiny, and a reviewer sees which `gh` calls exist. |

Observer (run and log subscriptions) is 03's design. OCP appears only through the Strategy above: don't design extension points beyond Direct/Wsl.

**Skip:**
- DI containers (inversify, tsyringe): decorators plus metadata for a graph of about 10 objects.
- Use-case-per-file classes (§8).
- A global event bus: typed subscriptions are easier to trace (03).
- Repository CRUD interfaces: the app writes nothing to a store of its own.
- Abstract factories, class hierarchies for domain entities (plain types + functions).
- Barrel `index.ts` files: they create cycles and hide the import paths that lint rules match.

### 7. Error handling and logging per layer

| Layer | Errors | Logging |
|---|---|---|
| shared/domain | Pure functions return `Result`. No throws for expected cases. | none |
| main/adapters | Map exit codes and stderr to `StudioError` kinds (`gh` not authed, binary missing, non-zero exit). Never leak raw stderr upward unmasked (masking in 05). | Log command name, exit code and duration. argv is redacted (05). |
| main/app | Combine `Result`s. Throw only on bugs. | Domain-level events (run state change), at debug level |
| main/ipc | Catch-all: an unexpected throw becomes `{kind:'unexpected', id}`, logged with that correlation id. Handlers always resolve with a `Result`, because the renderer's rejected `Error` is a different object [2]. | Yes, the boundary log |
| preload | No logic, no handling | none |
| renderer | `Result` errors → inline state or toast. A React error boundary per feature, so the board survives a broken detail screen. | `console` only (visible to Playwright, 06). No file access. |

One logger module in main (`log/logger.ts`), writing to the app's logs directory and passed to adapters and services by the composition root. It has one implementation, so it is not a port (§1); tests pass a no-op function of the same type. Library choice is open and not evaluated here.

### 8. Owner question 6: expause_web as a model

Read: `docs/architecture/ARCHITECTURE.md` (474 lines) and a scan of `src/`.

| expause_web | Carries over? | Why |
|---|---|---|
| Three layers, top-down: `Presentation → Domain → Data`; "Domain can import from Data" (`ARCHITECTURE.md:183-191`), and 193 files under `src/domain/` import `@/data` | **No: inverted here.** | Studio points dependencies *at* the domain (ports in main, `StudioApi` in the renderer), so adapters depend on domain types, not the reverse. What carries over is the *idea* of named layers with written import rules. |
| Domain entities separate from wire DTOs; remappers (`:255-297`) | **Yes.** | Harness JSON and `gh` JSON → domain `Run`/`Issue`, inside `main/adapters/{harness,gh}`. The renderer sees only domain types. |
| "Never call data services directly - always go through use cases" (`:164`) | **Yes**, as "features use `StudioApi`, never adapters", and enforced by lint. | expause states it in prose but also allows "Presentation can import from Domain and Data" (`:189`). An unenforced, contradictory rule is the lesson. |
| Use-case-per-file classes (`domain/usecases/`, 186 `.ts` files under 46 folders) | **No.** | `usecases/feed/fetchFeedUseCase.ts` delegates entirely to `MediaService`; on error it logs and returns an empty list (lines ~27-38), so callers cannot tell a failure from an empty feed. That is a layer that adds a file and hides failures. Studio has about 10 intents and 5 reads: grouped service modules in `main/app/` (`runs.ts`, `intents.ts`, `repos.ts`) carry the same logic without ceremony. Add a dedicated module only when an operation orchestrates several ports *and* has rules (e.g. "start run": trust check → confirm → drop). |
| Firebase services, Cloud Functions client | No | There is no backend. Data comes from `gh`, `git`, `devscene` and files. |
| Redux Toolkit, TanStack Query | No (03 decides) | State is pushed from main, not fetched from a server cache. |
| Dexie / IndexedDB | No | No local DB. Truth lives in GitHub and the harness (Issue #1 "Data source"). |
| Barrel exports (`:168`) | No | See §6 skip list. |
| Feature folders under `presentation/feature/` | **Yes** | → `src/renderer/features/*` |
| Doc vs code drift | Lesson | The doc's tree shows flat `usecases/*.ts`, while the code has `usecases/<area>/`, `domain/services/` and `src/infrastructure/`, none of which the doc lists. Here the conventions docs are reviewed by the harness (`/devscene:analyze`), and the rules are in lint, not prose. |

## Recommendation for the spike

**Day 1 (renderer, browser mode):**
1. Create `src/shared/domain/{run,issue,board,trust,result}.ts` and `src/shared/contract/studio-api.ts`. `StudioApi` holds only the reads Day 1 needs (`listRuns`, `showRun`, `listIssues`, a log subscription; shape per 03).
2. Write `src/renderer/studio/fixture.ts` with scenarios and `studio/ipc.ts` (`window.studio`), selected in `main.tsx` by build mode.
3. Build `features/board`, `features/run-detail` and `features/log-tail` against `StudioApi` only, with co-located tests.
4. In **one change**: split tsconfigs into `src/{shared,main,preload,renderer}/tsconfig.json` plus a root solution, set `typecheck: tsc -b` (typecheck only), and move `build` to the bundler 07 picks (04/06), which also bundles the preload. Add the `no-restricted-imports` blocks once ESLint lands (06).

**Day 2 (main, preload):**
1. Write `ports/{transport,gh,confirm}.ts` and `adapters/transport/direct.ts`.
2. Write `process/argv.ts`, then `adapters/gh/` (one read) and `adapters/electron/confirm.ts`.
3. Write `app/runs.ts` (the read-model) and `ipc/register.ts`.
4. Write the preload facade (`satisfies StudioApi`, or built from the channel table if bundled).
5. Leave `adapters/harness/` as a stub until F-1.

**Item 3:** `npx devscene init` → `devscene config set layers '<§4 json>'` → `/devscene:analyze` (writes `shared.md`, `main.md`, `renderer.md`, `tests.md`, and the Preload section of `conventions.md`).

## Answers to the owner's questions

- **Q2:** Yes. The smallest clean architecture is one folder per process (`main`, `preload`, `renderer`) plus `shared`, with a hexagon inside main and a port plus two adapters in the renderer. The harness gets 3 source layers (`shared`, `main`, `renderer`) plus `tests` and the catch-all; the one-file preload rides on the catch-all. That is the minimum because browser mode and the harness layer map both need it on Day 1. Everything else (use-case classes, containers, buses) is skipped.
- **Q3:** See the §6 table. The patterns that pay off here are ports/adapters, hand-wired composition roots, Strategy for the transport, one argv-builder function, the run read-model, the fixture/IPC Adapter, the preload Facade, intents as data, and `Result` over IPC.
- **Q6:** Partly. Its feature folders and DTO→domain remapping carry over. Its dependency direction does not: it is top-down with domain importing data, while Studio inverts it. Its use-case-per-file layer, Firebase, Redux, Dexie and barrels do not carry over either, for the reasons in §8.

## Risks and open questions

- **TypeScript 6.0.3 is a deliberate pin behind npm `latest` (7.0.2, 2026-07-08; 7.1.0-beta 2026-10-20) [4].** The binding constraint is typescript-eslint 8.74.0's peer `<6.1.0`. dependency-cruiser excludes 7.0.x but admits `>=7.1 <8`. Whether project references behave the same under TS 7 is not checked.
- **Build:** the tsconfig split breaks today's `tsc`-only build unless a bundler lands with it (§5). The tool pick (electron-vite 6 per 04, or Vite + esbuild per 06) is 07's.
- **Preload without a row:** fine while it is one file. If 05 wants a security-focused reviewer on the renderer-reachable surface, add a `preload` row back (one more task per verb unless the facade is generated).
- **Renderer tsconfig** will use `moduleResolution: bundler` (Vite) while shared is also compiled under `nodenext` for main. Shared must use explicit `.js` import specifiers. Not tested in this pass. [inferred]
- **Overlapping layer paths** (`general` `.` vs the others): the harness routes by the task's layer tag, but I did not find how it resolves a path that matches two rows. The proposal has no overlaps besides the catch-all.
- **Path names for 07:** 01, 03 and 06 write a top-level `contract/` (and 06 a top-level `domain/`, `test/`, `e2e/`); this file uses `src/shared/{domain,contract}` and one `tests/`. 05 ties the harness-schema types to `contract/`; this file keeps them in `src/main/adapters/harness/schema/`. 07 should settle one set.
- The F-1 harness contract shape is unknown, so `adapters/harness/` and the generated schema location may move inside main.

## Sources

1. https://electron-vite.org/guide/dev — recommended `src/main`, `src/preload`, `src/renderer` structure — accessed 2026-11-25
2. https://www.electronjs.org/docs/latest/api/ipc-renderer — `invoke`: "the `Error` object in the renderer process will not be the same as the one thrown in the main process" — accessed 2026-11-25
3. https://www.electronjs.org/docs/latest/tutorial/sandbox — sandboxed preload `require` loads only `electron` and "cannot load files"; bundler recommended — accessed 2026-11-25
4. npm registry (`npm view`): eslint 10.15.0 (published 2026-11-13); typescript-eslint 8.74.0 (peer TS `>=4.8.4 <6.1.0`); eslint-plugin-boundaries 7.4.4 (2026-11-15); eslint-plugin-import-x 4.18.1 (modified 2026-11-09); dependency-cruiser 18.9.0 (2026-11-22, `supportedTranspilers.typescript`); typescript dist-tags `latest` 7.0.2, `beta` 7.1.0-beta, 6.0.3 (2026-04-16); eslint-plugin-import 2.32.0 (last release 2025-06-20, stale, not used) — accessed 2026-11-25
5. https://eslint.org/docs/latest/rules/no-restricted-imports — `patterns.group`, `regex`, `allowTypeImports` — accessed 2026-11-25
6. https://www.typescriptlang.org/docs/handbook/project-references.html — `composite` requires all files matched by `include`, and `declaration` — accessed 2026-11-25
7. Scratch tests (TS 6.0.3, ESLint 10.15.0, eslint-plugin-boundaries 7.4.4) in the session scratchpad: TS6307/TS6059 on a cross-project import; TS6310 only when a *referenced* project sets `noEmit`; a leaf `noEmit` project referencing an `emitDeclarationOnly` shared builds with exit 0 and zero `.js` files; `no-restricted-imports` matches relative specifiers; boundaries rule fires with deprecation warnings — run 2026-11-25
8. `/Users/daniel/Work/devscene/docs/config.md:136-138,178` — `layers[]` keys, catch-all requirement
9. devscene 0.7.1 CLI (`cli/dist/cli.js`) on a scratch repo with the §3 tree: `init --dry-run` → `flat` (signal `flat:fallback`); `init`; `config set layers '<§4 json>'` accepted; `doctor` → `layer-profile` PASS, `layer-drift` WARN `build, scripts, vm, src/preload`, `setup-analysis` WARN (4 conventions docs missing) — run 2026-11-25. The review's run of the same kind covers `src/api/`/`src/handlers/` → `api-service`.
10. `/Users/daniel/Work/devscene/docs/cli.md` §4 (detection rows 3, 5, 17; "What a preset's layer profile carries"), §7 (`layer-drift`: two-level search reaches siblings inside `src/`; `detection.review` "for reporting, never as a gate"), §8 (`config set layers`)
11. `/Users/daniel/Work/devscene/cli/src/detect/signals.ts:651-662` (`findLayeredRoot`), `cli/src/detect/presets.ts:101-132` (conventions file names, `tests`/`general`), `:556-567` (`PRESET_TEST_ROOTS`, no `flat` entry)
12. `/Users/daniel/Work/devscene/plugin/agents/task-plan-writer.md:105` (one layer per task, bottom-up order, catch-all last), `:129` (a unit's required test file in its own task); `plugin/agents/layer-implementer.md:17,48,82,154` (catch-all sees the whole map; stop outside the layer path; catch-all reads every conventions doc; whole-tree typecheck failure outside the change is an evidence downgrade); `plugin/agents/layer-reviewer.md` description (flows where per-unit review runs)
13. `/Users/daniel/Work/expause/expause_web/docs/architecture/ARCHITECTURE.md:1-127,164,168,183-191,255-297`; `src/domain/usecases/` (186 files); `src/domain/usecases/feed/fetchFeedUseCase.ts:12-38` (logs at :34, returns empty list); `grep -rl "from '@/data" src/domain` → 193 files
14. `/Users/daniel/Work/devscenestudio/src/preload/preload.ts`, `package.json:14-18` (tsc-only build, `main: dist/main/main.js`), `tsconfig.json` — current code
15. GitHub Issue #1 (items 2, 3, 5, "Data source") and `docs/product-startup-research/10-recommendation.md:16,305,403-404` — suggested layout, argv rules, layers set by hand
16. Sibling research files read for path and tool consistency: `01-electron-process-model.md` (TL;DR, §4 typed IPC sketch), `03-reactive-data-flow.md` (`contract/studio-live.ts`), `04-performance.md` (electron-vite 6), `05-security-architecture.md` (`contract/` and TypeBox), `06-testing-and-tooling.md` (TL;DR, §2 build, §4–§6 tests and fixtures, §9 reuse table) — read 2026-11-25
