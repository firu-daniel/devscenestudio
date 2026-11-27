# 01 — Electron's process model and IPC
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

- **Electron is a browser plus Node.js, not a UI framework.** It ships Chromium (156 in 45.5.0) and Node 24.22.3 [verified, S3]. It has no component library. React runs in the renderer exactly as it does on the web. What Electron adds is a privileged Node process (main) and a small set of native APIs (dialogs, menus, `shell`, `safeStorage`, and so on). So yes: the UI half is "React for the web"; the other half is a Node backend that runs on the user's machine and talks to the UI over IPC instead of HTTP.
- **Three places code runs:** *main* (Node, one per app, owns windows, spawns `gh`/`git`/`devscene`/`wsl.exe`, watches files, calls GitHub), *renderer* (Chromium page, no Node, runs React), and *preload* (a sandboxed bridge script; with `sandbox: true` it can `require('electron')` and nothing else) [verified, S1, S4]. `utilityProcess` is an optional fourth (a Node child that Chromium manages) for work that would block main.
- **IPC choice per traffic type:** request/response uses `ipcRenderer.invoke` with `ipcMain.handle`. Live pushes (runs, Issues, doctor) use `webContents.send` with one preload-wrapped listener per subscription. High-rate log lines use the same push, **batched** in main (one message carrying an array of lines per tick). `MessagePort` is held in reserve for a direct utilityProcess-to-renderer stream if 04 shows main-thread contention [verified, S5, S6; inferred choice].
- **Everything crossing the bridge is copied by structured clone.** Plain data (objects, arrays, strings, numbers, Dates, Maps) survives. Class instances lose their prototype, Errors lose custom properties, Symbols are dropped, and C++-backed objects (`process.env`, `BrowserWindow`) fail. Functions are the one exception: `contextBridge` **proxies** them, which is how a subscription callback and its `unsubscribe` function cross [verified, S2, S5]. Rule: the IPC contract is plain JSON-like DTOs only.
- **Typed IPC: hand-written, no library.** Define one `StudioApi` TypeScript interface in a shared contract file. The preload implements it with `invoke`/`on`; main registers handlers checked against it with `satisfies`. The browser-mode fixture implements the same interface. Cost: about 100–150 lines, zero dependencies. electron-trpc 1.0.0 (2026-10-30) now works in sandboxed renderers, but it is four weeks old after a two-year gap, brings in tRPC 11, and exposes a generic transport rather than named verbs. Not worth it at about 15 verbs [verified, S9–S12; inferred choice].
- **Browser-mode seam = one `studio` object, chosen by build mode.** The renderer only ever calls `getStudio()`. The Electron build returns `window.studio` (from the preload) and fails loudly if it is missing; only the browser-mode build compiles in the fixture implementation. Same interface, so the Playwright and QA agents exercise the same React code.
- **Lifecycle work the spike must add to the current `main.ts`:** a single-instance lock; `app://` served by `protocol.handle` (or the experimental `protocol.registerSource`) instead of `loadFile`/`file://`; a central child-process registry that `before-quit` drains; and sender validation on every handler [verified, S7, S8, S13].
- **Sandboxed-preload trap for this repo:** the build is `tsc` only. A sandboxed preload cannot `require` a local file, so if `preload.ts` imports any *runtime* value (for example a channel-name constant) from the contract, it breaks at load time. Either keep preload imports `import type` only, or bundle the preload (esbuild, one line). It must also stay CommonJS: sandboxed preloads run "without an ESM context" and ignore `"type": "module"`, so adding that field or bundling the preload as ESM breaks it the same way [verified, S16]. Electron 45 also removed the `Buffer` and `setImmediate` globals from sandboxed preloads [verified, S1, S4].

## Scope

This file covers what Electron is, its processes, its IPC primitives and serialization rules, the typed-IPC options, the browser-mode seam's interface shape, and the lifecycle concerns that shape the architecture. It leaves to other files: the folder tree and layer map (02), store and stream design in the renderer (03), throughput and latency numbers (04), the CSP, fuses, argv builder and sender-validation detail (05), and test tooling (06).

Current code read: `src/main/main.ts` (one window with `contextIsolation`, `sandbox`, `nodeIntegration: false`, `ready-to-show`, window-open and navigation denied, `loadFile`) and `src/preload/preload.ts` (exposes a frozen `studio.versions` only). No IPC exists yet.

## Findings

### 1. What Electron provides vs. what we build

| Concern | Electron provides | Studio builds or adds |
|---|---|---|
| UI rendering | Chromium (HTML/CSS/JS) | React 18/19 components, styling, routing (none needed: two screens) |
| UI components | **Nothing.** No widgets, no design system | Board, cards, detail, log view. A small headless lib is optional |
| Backend runtime | Node 24 in main [verified, S3] | Process spawning (`node:child_process`), `fs.watch`, NDJSON parsing |
| Process ↔ UI transport | `ipcMain`/`ipcRenderer`, `contextBridge`, `MessageChannelMain` | The typed `StudioApi` contract and its two implementations (preload, fixtures) |
| Windows | `BrowserWindow`, `ready-to-show` | Window state (size), one main window |
| App lifecycle | `app` events, `requestSingleInstanceLock` | Child-process registry and cleanup on quit |
| Serving the UI | `protocol.handle` / `protocol.registerSource` | The `app://` handler with path confinement (05) |
| Packaging/updates | electron-builder, electron-updater (third-party, already pinned) | Signing config (done, Day 0), Linux signature hook |

**Native modules Studio needs** (all main-process only unless noted):

| Module | Studio use | Needed in v1? |
|---|---|---|
| `dialog.showMessageBox` | The OS-native confirmation for start, answer and resume (10 §6) | **Yes** |
| `shell.openExternal` | Open an Issue or PR in the browser (validate `https://github.com/…` only) | Yes |
| `shell.openPath` / `showItemInFolder` | Reveal a run's log folder | Likely |
| `Menu` | App menu (macOS needs one for Cmd+Q, copy and paste to work) | Yes (default template is fine) |
| `nativeTheme` | Light/dark. CSS `prefers-color-scheme` already works in the renderer; the module is needed only for an in-app override | Optional |
| `safeStorage` | Encrypting a stored token. Studio uses `gh`'s auth, so it stores no secret | **No**. If ever needed, use the async API (sync methods deprecated in 45, removed in 46) [verified, S4] |
| `net.fetch` | GitHub HTTP from main through Chromium's network stack (system proxy, certificates) | Optional; `gh api` may cover it (see §3) |
| `Notification` | "Run needs an answer" alert | Later |
| `powerMonitor` | Pause polling on sleep | Later |
| `Tray`, `globalShortcut`, `autoUpdater` (built-in) | Not needed; electron-updater covers updates | No |

### 2. The processes

```
┌─────────────── main process (Node 24, one) ───────────────┐
│ app lifecycle · BrowserWindow · protocol app://            │
│ ipcMain handlers (intent verbs) ── validate sender         │
│ sources: child_process spawn(gh, git, devscene, wsl.exe)   │
│          fs.watch · polling timers · net.fetch / gh api    │
│ dialog · shell · Menu                                      │
│        │ optional: utilityProcess.fork(worker.js)          │
└────────┼───────────────────────────────────────────────────┘
         │ IPC (structured clone)
┌────────┴────────── renderer process (Chromium, sandboxed) ┐
│ preload (isolated world): require('electron') only         │
│   contextBridge.exposeInMainWorld('studio', {verbs, on*})  │
│ ─────────────── world boundary ────────────────────────── │
│ page (main world): React app → window.studio              │
└────────────────────────────────────────────────────────────┘
```

| Process | Runs | Can access | Studio places here |
|---|---|---|---|
| **Main** | Node + Electron main APIs | Everything: fs, child processes, network, native UI | All sources (spawns, watches, polling), argv builder, `Direct \| Wsl` transport, IPC handlers, native dialogs |
| **Renderer (page)** | Chromium, web APIs only | No Node, no `require` [verified, S6] | React UI, stores (03), rendering pipeline (markdown, ANSI) |
| **Preload** | Before the page, in an isolated world | With `sandbox: true`: `require` loads only `electron`, `electron/renderer` and `electron/common` (giving `contextBridge`, `ipcRenderer`, `webFrame`, `webUtils`, `nativeImage`, `crashReporter`), plus a reduced `process` and web APIs. No Node built-ins, `Buffer` or `setImmediate` [verified, S1, S4] | Only the `studio` object: verbs map to `invoke`, `on*` subscriptions map to wrapped `ipcRenderer.on`. No logic |
| **utilityProcess** | Node in a Chromium-managed child; must be forked after `ready` [verified, S7] | Node APIs; talks to main over `process.parentPort` and can take `MessagePortMain`s | Nothing in the spike. A candidate later for CPU-heavy parsing (big log backfill, ANSI pre-tokenising) or crash-prone watchers |
| **child_process** | Any OS binary | Whatever the binary can | `gh`, `git`, `devscene`, `wsl.exe --exec …` |

**Where Studio's work runs:**

| Need | Where | Why |
|---|---|---|
| `spawn('gh'|'git'|'devscene', argv)` | main (`node:child_process`, `shell: false`) | Spawning is asynchronous and cheap on main. Line splitting of stdout is O(bytes) [inferred] |
| `wsl.exe --exec devscene …` | main, the same spawn path with the `Wsl` transport | One argv builder (05). Killing `wsl.exe` may not kill the Linux-side process tree, so cancelation should use the harness's own verbs (`pause`/stop) rather than signals alone [inferred, to be tested on the Windows VM; related report: S14] |
| NDJSON from `devscene runs watch --json` | main: a line splitter plus `JSON.parse` per line | Events arrive at human rates (run updates, heartbeats). Not worth a utilityProcess [inferred] |
| Log tail (high rate) | main reads and splits; batched push to renderer | Move to utilityProcess plus `MessagePort` only if 04 measures main-thread jank |
| `fs.watch` on run folders | main | Event-driven, negligible CPU. Debounce in main (03) |
| GitHub HTTP | main, via `gh api` (reuses `gh` auth, no token in Studio) or `net.fetch` | The renderer's CSP has `connect-src 'none'` (`src/renderer/index.html`), which should stay. Never fetch from the renderer |

The Electron docs' own guidance for utility processes is "untrusted services, CPU intensive tasks or crash prone components" [verified, S6]. None of Studio's v1 sources match that at expected volumes. The cost of adding one later is low if source modules are plain Node modules that do not import `electron` (02).

### 3. IPC primitives

| Primitive | Direction | Semantics | Studio use |
|---|---|---|---|
| `ipcRenderer.invoke` ↔ `ipcMain.handle` | R→M→R | Promise request/response. A thrown error reaches the renderer with **only its `message`** [verified, S5] | All intent verbs: `listRepos`, `runDetail`, `startRun`, `pauseRun`, `answer`… Return `{ok, value} \| {ok:false, code, message}` results rather than relying on thrown errors |
| `ipcRenderer.send` ↔ `ipcMain.on` | R→M | Fire-and-forget | `subscribe`/`unsubscribe` notices (or fold them into `invoke`) |
| `webContents.send` ↔ `ipcRenderer.on` | M→R | Push, no reply [verified, S5] | Live updates: `runs:updated`, `issues:updated`, `log:lines` (batched), `doctor:updated` |
| `ipcRenderer.sendSync` | R→M | Blocks the renderer | **Never** (the docs advise against it) [verified, S5] |
| `MessageChannelMain` / `MessagePort` | Any ↔ any, after a transfer | Streams, multiple messages per request. Ports transfer only via `webContents.postMessage`/`ipcRenderer.postMessage`, not `send`/`invoke`. Reaching the page under context isolation needs a `window.postMessage` relay in the preload [verified, S8] | Reserve: a direct utilityProcess → renderer log stream. More moving parts and a second path into the main world, so not in the spike |
| `webContents.ipc` | M, per window | Handlers scoped to one WebContents [verified, S13] | Not needed with one window |

**Serialization rules (the contract's design constraints):**

| Value | Over `invoke`/`send` (structured clone) | Over `contextBridge` |
|---|---|---|
| Plain objects, arrays, primitives, `Date`, `Map`, `Set`, typed arrays | Copied [verified, S17] | Copied (and frozen) per the cloneable-types row [verified, S2, S17] |
| Class instance (`new Run(...)`) | Copied as a plain object, **prototype lost** | Same: prototype dropped [verified, S2] |
| `Error` | Copied; custom fields lost; from `handle`, only `message` survives [verified, S2, S5] | Copied; custom properties lost |
| Function | **Fails** (DataCloneError) [verified, S17] | **Proxied**: callable across worlds [verified, S2] |
| Promise | Fails as a value (`invoke` returns one itself) [inferred from structured clone, S17] | Supported [verified, S2] |
| Symbol | Fails [verified, S17] | Dropped [verified, S2] |
| Node streams, `EventEmitter`, `ChildProcess`, `process.env`, `BrowserWindow` | Fail (C++-backed objects per S5; the rest are non-cloneable per S17) [verified, S5, S17] | Not supported |
| `ipcRenderer` itself | n/a | Blocked since Electron 29 [verified, S2] |

Consequence: domain values crossing IPC are **DTO types** (`type RunSummary = {...}`), not classes. A stream is modelled as "subscribe returns an unsubscribe function; pushes carry arrays of DTOs".

Every push is copied twice: by structured clone into the preload's isolated world, then by `contextBridge` into the page, which **freezes** it ("all other values are copied and frozen") [verified, S2]. The cost is negligible at Studio's batch sizes (04). For 03, it means stores must never mutate pushed DTOs in place, because that throws in strict mode [inferred].

**Sender validation.** Every handler checks `const f = event.senderFrame; if (!f || f.origin !== APP_ORIGIN || f.parent !== null) reject` before acting. Use the origin, not the URL, because `about:blank`, `blob:` and sandboxed documents have URLs that do not identify who controls them; reject a null frame ("may be null if it has gone away"). Both are checklist item 17 [verified, S13]. Top-frame-only is our addition [inferred]. `APP_ORIGIN` is `app://<host>`, which is a real origin only because `app` is registered `standard: true` [inferred]. Wrap this once in a `handle(channel, fn)` helper in main so no handler can skip it. Detail is in 05.

**Subscription pattern in the preload** (never pass the raw `IpcRendererEvent` through, because it leaks `ipcRenderer` via `event.sender`; checklist item 20 [verified, S5, S13]):

```ts
onRunsUpdated: (repo: RepoId, cb: (e: RunsEvent) => void) => {
  const h = (_e: unknown, msg: { repo: RepoId; e: RunsEvent }) => { if (msg.repo === repo) cb(msg.e); };
  ipcRenderer.on("runs:updated", h);
  void ipcRenderer.invoke("subscribe", { topic: "runs", repo });   // tells main what to watch
  return () => {
    ipcRenderer.off("runs:updated", h);
    void ipcRenderer.invoke("unsubscribe", { topic: "runs", repo });
  };   // the function is proxied back
},
```

The returned unsubscribe closure is required, not just convenient: each `contextBridge` crossing creates a new proxy for the page's callback, so an `off(cb)` API could never find the listener to remove [inferred from S2]. 03 must keep this shape. Main keys subscriptions by (webContents, topic, key) and makes `subscribe` idempotent, so a duplicate call does not start a second source [inferred].

Electron 45 note: `ipcRenderer` in sandboxed preloads is now a native `EventEmitter`. The *static* `events` helpers (`EventEmitter.once`, `listenerCount`, `init`), previously reachable through `require('events')`, are gone; the instance methods (`on`, `off`, `once`, `removeListener`) are unchanged [verified, S4]. Don't `require('events')` in the preload.

**Which primitive for which traffic:**

| Traffic | Primitive | Notes |
|---|---|---|
| Query (repos, Issues, run detail) | `invoke` | Returns DTOs |
| Command (start, pause, resume, answer) | `invoke` | The handler shows the native confirmation (`dialog.showMessageBox`) before it acts; the renderer cannot skip it |
| Live state (runs, Issues, doctor) | `webContents.send` pushes of a snapshot or a delta | The renderer resubscribes after a reload; main sends a snapshot first (03) |
| Log lines | `webContents.send("log:lines", {runId, lines[]})`, flushed per tick (e.g. 16–50 ms [inferred]; numbers in 04) | One IPC message per batch, not per line |

### 4. Typed IPC options (checked 2026-11-25 against npm and GitHub)

| Option | Last release | Electron 45 fit | Assessment |
|---|---|---|---|
| **Hand-written typed map** (one `StudioApi` interface plus `satisfies` checks) | n/a | Native | ~100–150 lines. Named verbs as the bridge (matches the 10 §6 "intent-only IPC" bar literally). The browser fixture implements the same interface for free. **Recommended** |
| `electron-trpc` (jsonnull) | **1.0.0, 2026-10-30**; previous 0.7.1, 2024-12-07 [verified, S9, S10] | Peer `electron >=35`, tRPC `^11.10`. 1.0 fixes sandboxed renderers (#116), adds an `allow` option for `senderFrame` checks and supports subscriptions [verified, S10] | Capable, but a fresh major rewrite after a two-year pause (403 stars, 3 open issues). Adds `@trpc/server` and `@trpc/client`. The preload exposes a **generic** `electronTRPC` transport that carries any procedure path. That is still safe (the router is the allow-list), but it is not "verbs only". By default `createIPCHandler` also registers the library's own preload on the session unless passed `preload: false` [verified, S10]. Overkill for about 15 verbs |
| `electron-trpc-experimental` (fork) | 1.0.0-alpha.1, 2025-06-18 [verified, S9] | Untested on 45 | Alpha, and superseded by electron-trpc 1.0. Avoid |
| `trpc-electron` (mat-sz fork) | 0.1.2, 2025-01-06 (over 12 months old) [verified, S9] | Unknown | Stale. Avoid |
| `@egoist/tipc` | 0.4.0, 2026-07-17 (previous 0.3.2, 2024-07) [verified, S9, S11] | Peer `electron >=26`, peer `@tanstack/react-query` | Small, typed router; couples to React Query. A reasonable middle ground, but a single-maintainer project with sparse releases |
| `@electron-toolkit/typed-ipc` | 1.0.2, 2024-11-11 (over 12 months old) [verified, S9] | Peer `electron >=13`; needs `@electron-toolkit/preload` (3.0.2, 2025-04-19), which exposes a **generic any-channel `ipcRenderer` wrapper** (`send`, `invoke`, `sendSync`, `on`, `postMessage`, …) to the page as `electronAPI.ipcRenderer` [verified, S12] | Conflicts with the intent-only bar. Avoid |
| `electron-typed-ipc`, `typed-ipc`, `interprocess` | 2022–2023 [verified, S9] | Pinned to old Electron | Dead. Avoid |

**Recommendation:** hand-written. What it costs: writing the channel map once and keeping three implementations (preload, main handlers, fixture) in step. The compiler enforces this through the shared interface, so drift becomes a type error. What it buys: no dependency on a four-week-old major, a preload that literally lists its verbs (easy to review for security), and a browser-mode fixture that is a plain object. Revisit electron-trpc if the verb count passes about 40 or if input validation per procedure (zod) becomes desirable [inferred].

Sketch (contract, a few lines; file placement in 02):

```ts
// contract/studio-api.ts — types only, so tsc-only preload stays loadable
export interface StudioApi {
  listRepos(): Promise<Result<Repo[]>>;
  runDetail(repo: RepoId, branch: string): Promise<Result<RunDetail>>;
  startRun(repo: RepoId, issue: number): Promise<Result<void>>;   // main shows native confirm
  pauseRun(repo: RepoId, branch: string): Promise<Result<void>>;
  onRunsUpdated(repo: RepoId, cb: (e: RunsEvent) => void): Unsubscribe;
  onLogLines(repo: RepoId, branch: string, cb: (lines: LogLine[]) => void): Unsubscribe;
}
// main:    const handlers = { listRepos: async () => …, … } satisfies Handlers<StudioApi>;
// preload: contextBridge.exposeInMainWorld("studio", { listRepos: () => ipcRenderer.invoke("listRepos"), … } satisfies StudioApi);
```

`Handlers<T>` is a mapped type that turns each promise method into an `ipcMain.handle` function and drops the `on*` members. Keep the channel names as literal strings in the preload, or bundle it (see the trap in the TL;DR).

### 5. The browser-mode seam

```ts
// renderer: the only access point to the outside world
export function getStudio(): StudioApi {
  if (import.meta.env.MODE === "browser") return createFixtureStudio(fixtures); // dead-code-eliminated in the Electron build
  const s = (window as { studio?: StudioApi }).studio;
  if (!s) throw new Error("Preload failed: window.studio is missing");          // fail loudly, never fall back
  return s;
}
```

- **Choose by build mode, not by presence of `window.studio`.** Inside Electron, a missing `window.studio` means the preload failed (for example the runtime-import trap above). Falling back to fixtures would make a packaged Studio quietly show fake runs and Issues [inferred]. So the Electron build throws a visible error, and the fixture implementation and its `__studioFixture` hook are compiled only into the browser-mode build (a Vite mode or alias), absent from packaged apps [inferred].
- **In a plain browser** (Vite dev server in browser mode, Playwright, the harness QA agent), `createFixtureStudio` returns an in-memory implementation. Its `on*` methods are backed by a tiny emitter, and a test hook (for example `window.__studioFixture.emit("runs", …)`) drives live updates so tests can assert UI reactions.
- **Rule:** no renderer module touches `window.studio` or `ipcRenderer` directly, only `getStudio()`, injected once (React context, or the store layer from 03). That rule is what 02's lint boundary should enforce.
- Because the interface carries only clone-safe DTOs, fixture data is plain JSON files, and the same files can seed main-side unit tests.

Cost: one fixture implementation (~100 lines plus JSON) kept in step by the shared type. What it buys: v1's browser-mode requirement, Linux CI QA with no Electron, and fast UI iteration.

### 6. App lifecycle concerns

| Concern | Electron API | What Studio does | Current code |
|---|---|---|---|
| Single instance | `app.requestSingleInstanceLock()`; the primary gets `second-instance` (use `additionalData`, since argv may be reordered) [verified, S7] | Quit if the lock is not obtained; focus the existing window on `second-instance`. Two instances would double-spawn watchers and race on files | Missing |
| Serving the UI | `protocol.registerSchemesAsPrivileged` **before** `ready`; `protocol.handle` after `ready`. The docs' full example rejects `..` paths. `protocol.registerSource` (experimental) serves a directory with no JS handler and refuses paths outside `root` [verified, S8] | `app://` with `standard`, `secure` and `supportFetchAPI`; confined to `dist/renderer`. Electron checklist item 18 says to avoid `file://` [verified, S13]. Handler order: reject a host other than the one bundle host and any method other than GET; `decodeURIComponent(pathname)`; `p = path.resolve(root, '.' + decoded)`; reject unless `path.relative(root, p)` is non-empty, does not start with `..` and is not absolute; then `net.fetch(pathToFileURL(p))`. Decoding before the check matters: the docs example checks the raw `pathname`, so a later decode would let `..%2F` through [inferred]. `registerSource` does this natively: paths outside `root` and methods other than GET/HEAD fail with `ERR_FILE_NOT_FOUND`, and "no request touches the main thread" [verified, S8]. But it is experimental; 05 decides, along with the fuse set | Uses `loadFile` (`src/main/main.ts:24`) |
| Window creation | `BrowserWindow` with `show: false` plus `ready-to-show` | Keep. Also keep the deny-all `setWindowOpenHandler` and `will-navigate` guard | Present (`main.ts:4-26`) |
| Renderer reload or crash | `render-process-gone`, page reload | Main keeps the sources running; the renderer resubscribes on load and receives a snapshot. A reload or navigation keeps the same `WebContents`, so `destroyed` alone would leave stale subscriptions and double every push. Drop all of a `webContents`' subscriptions on main-frame navigation (`did-start-navigation` with `isMainFrame`, or `did-navigate`), on `render-process-gone` and on `destroyed`; `subscribe` is idempotent per (webContents, topic, key) [verified events, S13; design inferred; electron-trpc 1.0 fixed the same class of bug, S10] | n/a |
| Quit | `before-quit` → windows close → `will-quit` → `quit`. `app.exit()` skips the events. On Windows, shutdown or logout skips them [verified, S7] | One `ProcessRegistry` in main: every spawn registers and is removed on `exit`. On `before-quit`, call `preventDefault()` once, kill all (SIGTERM, then SIGKILL after a timeout; on Windows, `taskkill /T` for trees), then `app.quit()` again. Long-running harness runs are **not** Studio's children to kill. Studio watches them; it does not own them | Missing |
| macOS window lifecycle | `activate`, `window-all-closed` | Keep the current pattern. Note the sources keep running with zero windows on macOS, so pause polling when no window is open | Present (`main.ts:28-38`) |

## Recommendation for the spike

**Day 1 (browser mode first):**
1. Write `StudioApi` (types only) with the ~6 verbs the screens need plus `onRunsUpdated` and `onLogLines`, and `Result<T>`.
2. Write `getStudio()` (fixtures only in the browser-mode build; throws in Electron if the preload is missing) and the fixture implementation with a test emit hook. React uses it via context. Nothing in the renderer imports `electron`.

**Day 2 (Electron side):**
1. Preload: replace the `versions`-only object with the `StudioApi` implementation (verbs via `invoke`, `on*` via wrapped `on`/`off`, returning unsubscribe). Keep imports `import type` only, or add an esbuild step for the preload.
2. Main: one `handle()` helper that validates `senderFrame` (non-null, `origin`, top frame) and registers each handler from a `satisfies Handlers<StudioApi>` object; a `ProcessRegistry`; `subscribe`/`unsubscribe` handlers keyed per webContents and cleared on navigation; a batched `log:lines` push; the single-instance lock; `app://` via `protocol.handle` with the decode-then-confine order from §6; `before-quit` cleanup.
3. Native confirm via `dialog.showMessageBox` *inside* the `startRun` handler, not as a separate renderer-invoked step.
4. No utilityProcess, no MessagePort, no IPC library. Measure (04) before adding any.

## Answers to the owner's questions

**Q1. How do the parts fit together, and is it "like React for the web"?** Think of an Electron app as a website and its backend server packaged together on one machine:

- The **renderer** is the website: a Chromium tab running your React app. It is React for the web, with the same components and hooks. It has no Node and cannot touch files or processes.
- The **main process** is the "server": a Node program that opens windows and does everything privileged. For Studio, that means running `gh`, `git`, `devscene` and `wsl.exe`, watching folders, calling GitHub, and showing native dialogs.
- **IPC** replaces HTTP between them. `invoke`/`handle` is like a `fetch` to an API route. `webContents.send` is like a server push (a WebSocket message).
- The **preload** is a small script that decides which API functions the website gets: `window.studio.startRun(...)` and nothing else.
- **Utility processes** are extra Node workers for heavy jobs. Studio does not need one yet.
- Electron provides the browser, Node, the IPC pipes and a handful of native OS calls. It provides **no UI components**. We build the UI (React), the API contract, the process and file sources, and the glue.

**Q4 (Electron part only).** Electron's contribution to reactivity is the push primitive (`webContents.send`, optionally `MessagePort`) and proxied callbacks across `contextBridge`. There is no observable or store layer. Studio adds the subscription shape (`on*` returning an unsubscribe) and the store behind it (see 03).

**Q5 (this area).** Batched pushes keep IPC message counts low (performance numbers in 04). Named verbs plus sender validation plus no raw `ipcRenderer` keep the privileged surface reviewable (05).

## Risks and open questions

1. **Preload loading under `tsc`.** Any runtime import in `preload.ts` breaks the sandboxed preload. Decide in 06 whether to bundle the main, preload and renderer builds (esbuild or Vite) on Day 1. The renderer will need a bundler for React anyway.
2. **Killing processes on Windows/WSL.** `ChildProcess.kill()` kills only the direct child: Node documents that descendants survive on Linux [verified, S18], and on Windows tree kill needs `taskkill /T` [secondary, S14], and killing `wsl.exe` may orphan the Linux side [inferred, to be tested on the Windows VM]. The spike should test cancelation of a `wsl.exe --exec` child on a Windows VM. Prefer harness-level stop verbs.
3. **electron-trpc 1.0 is very new.** If it proves stable over the next releases, it becomes a credible upgrade path when the verb count grows. Not blocking.
4. **`protocol.registerSource` is experimental** and its version of introduction is undocumented [verified, S8]. Prefer `protocol.handle` with an explicit confinement check unless 05 decides otherwise.
5. **A missing preload must fail loudly.** If `window.studio` is absent in the Electron build, `getStudio()` throws and the UI shows an error; it never falls back to fixtures (§5).
6. **Quit cleanup timing.** The docs do not describe an async-cleanup pattern for `before-quit` [verified, S7]. The `preventDefault` → cleanup → `quit()` pattern is common practice but should be tested so Cmd+Q never hangs (use a hard timeout).

## Sources

1. https://www.electronjs.org/docs/latest/tutorial/sandbox — sandboxed preload: `require` limited to `electron`; no Node built-ins, `Buffer` or `setImmediate`; bundler recommended — accessed 2026-11-25
2. https://www.electronjs.org/docs/latest/api/context-bridge — type support table (functions proxied, prototypes dropped, Errors copied, Symbols unsupported); `ipcRenderer` not sendable since 29 — accessed 2026-11-25
3. https://releases.electronjs.org/release/v45.5.0 — 45.5.0 released 2026-11-24; Chromium 156.0.8078.109, Node 24.22.3 — accessed 2026-11-25
4. https://www.electronjs.org/docs/latest/breaking-changes — Electron 45: sandboxed-preload shims and globals removed, native `EventEmitter` for `ipcRenderer`, sync `safeStorage` deprecated — accessed 2026-11-25
5. https://www.electronjs.org/docs/latest/tutorial/ipc — IPC patterns, structured clone limits, `handle` errors pass only `message`, avoid `sendSync`, don't leak the event — accessed 2026-11-25
6. https://www.electronjs.org/docs/latest/tutorial/process-model — main, renderer, preload roles; utility process use cases — accessed 2026-11-25
7. https://www.electronjs.org/docs/latest/api/app and https://www.electronjs.org/docs/latest/api/utility-process — single-instance lock, quit event order, `app.exit`, `child-process-gone`; `utilityProcess.fork` after `ready`, `parentPort`, stdio — accessed 2026-11-25
8. https://www.electronjs.org/docs/latest/api/protocol and https://www.electronjs.org/docs/latest/tutorial/message-ports — `registerSchemesAsPrivileged`/`handle`/`registerSource` and traversal check; port transfer rules and the preload relay — accessed 2026-11-25
9. npm registry (`npm view <pkg> time`) for electron-trpc, electron-trpc-experimental, trpc-electron, @egoist/tipc, @electron-toolkit/typed-ipc, @electron-toolkit/preload, electron-typed-ipc, typed-ipc, interprocess — release dates and peer ranges — accessed 2026-11-25
10. https://github.com/jsonnull/electron-trpc/releases (electron-trpc@1.0.0, 2026-10-30) — sandbox fix #116, `allow` option, Electron ≥35, tRPC 11; #231: auto-registered preload unless `preload: false`, requests cancelled on navigate/reload/crash/close — accessed 2026-11-25
11. https://github.com/egoist/tipc — last push 2026-07-17 — accessed 2026-11-25
12. https://github.com/alex8088/electron-toolkit — typed-ipc and preload packages; `packages/preload/src/index.ts` exposes a generic any-channel `ipcRenderer` wrapper incl. `sendSync` — accessed 2026-11-25
13. https://www.electronjs.org/docs/latest/tutorial/security (items 17, 18, 20) and https://www.electronjs.org/docs/latest/api/web-contents (`ipc`, `postMessage`, `render-process-gone`, `destroyed`) — accessed 2026-11-25
14. https://github.com/vercel/hyper/pull/3794 (2019, **older than 12 months**) — taskkill to kill Windows descendant trees; https://github.com/microsoft/terminal/issues/2425 (2019, **older than 12 months**) — a WSL bash process survives its window closing (secondary, anecdotal) — accessed 2026-11-25
15. `src/main/main.ts:1-38`, `src/preload/preload.ts:1-12`, `src/renderer/index.html:5-8` (CSP `connect-src 'none'`), `tsconfig.json` (tsc only, `module: nodenext`) — local code, read 2026-11-25
16. https://www.electronjs.org/docs/latest/tutorial/esm — sandboxed preloads run without an ESM context; preloads ignore `"type": "module"` — accessed 2026-11-25
17. https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Structured_clone_algorithm — what structured clone copies and what throws (functions, Symbols, DOM nodes) — accessed 2026-11-25
18. https://nodejs.org/api/child_process.html (`subprocess.kill`) — signal handling on Windows; "on Linux, child processes of child processes will not be terminated" — accessed 2026-11-25
