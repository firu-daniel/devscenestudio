# 03 — Reactive data flow
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

- **Electron has no reactive layer, and none is missing.** Main gets Node's push primitives: `readline` async iterators over child stdout, `events.on()` with `AbortSignal`, `fs.watch` (recursive on Linux since Node 19.1), `AbortController`. IPC gives a one-way push (`webContents.send`). The renderer gets React 19's `useSyncExternalStore` [verified, §1]. Electron ships no store, no subscription lifecycle and no reconnect logic. We write those, about 550–700 lines plus tests for the minimal core [inferred, §4 table].
- **Main: plain Node streams and a few small functions. No RxJS.** The pipeline needs map, a log batch window, a retry with backoff and an abort. RxJS 7.8.2 is the latest stable release (Feb 2025, 21 months old); 8.x stalled at alpha and the active line is 9.0.0-beta.1 (Oct 2026). Revisit RxJS 9 once it is stable, and only if three or more sources need `combineLatest`/`switchMap`-style composition [verified + inferred, §2].
- **Live state → one Zustand 5 vanilla store**, read through selector hooks. Zustand 5.1.0 (6 Nov 2026) is ≈0.5 kB gz, and its React binding *is* `useSyncExternalStore`, so it cannot tear, at the cost of de-opting transitions on store updates (§3 note). Log lines go in a separate ring buffer, not in Zustand state [verified, §3].
- **On-demand reads and commands → TanStack Query** (5.108.4, peers `react ^18 || ^19`). Use it for `invoke`-backed request/response data (run detail and analytics, issue detail, PR detail, doctor) and for commands (`useMutation`). It is the most-used React data library (≈91 M npm downloads/week, on par with Zustand), agents write it fluently, and it is built for exactly this shape. It is **not** used for live state: main owns polling and push, and copying pushes into Query's cache would create a second source of truth. The only bridge is one line: a live upsert for run X invalidates X's detail query [verified versions/docs, inferred fit, §3.1].
- **The read-model lives in main. The renderer holds a mirror.** Main owns the sources, the gh + local merge under the trust rules, and the per-run log rings. A reload or crash costs one snapshot [inferred, §4].
- **Protocol: `snapshot`, then one-entity `upsert`/`remove`, plus `status`. Rule: any `snapshot` replaces the mirror.** Main sends a snapshot on every subscribe and on every source restart. No `epoch`/`seq`: IPC to one webContents is ordered and lossless, and `run_updated` carries the whole run, so a lost event heals on the next one. API and channel names follow 01: `onRunsUpdated`/`runs:updated`, `onIssuesUpdated`/`issues:updated`, `onLogLines`/`log:lines` [inferred, §5, §8].
- **Lifecycle (minimal).** Subscriptions are keyed by `(webContents.id, topic, repo)`, `subscribe` is idempotent, and a source runs while at least one subscription needs it. The preload sends `hello` when it loads, and main drops that webContents' old subscriptions. `render-process-gone` and `destroyed` do the same. A heartbeat watchdog kills and restarts a silent `runs watch` (per-attempt `AbortController`, try/finally) [verified events, inferred design, §5].
- **gh polling.** Poll REST with `gh api -i -H 'If-None-Match: <etag>'`. A 304 does not count against the rate limit. `gh api` exits 1 on **every** HTTP status ≥ 300, so parse the status line and treat only `304` as "unchanged". `/issues` also returns PRs (filter on `pull_request`) and pages at 30 (use `per_page=100`). `gh issue list --json` is GraphQL, which has no ETags, so don't use it to poll [verified, §6].
- **Deferred, each with a trigger** (§5.4): epoch/seq, grace periods, patch coalescing, multi-window sharing, full precedence table, workflow-run and PR polling.
- **From expause_web (Q6):** carry over subscribe functions that return an `Unsubscribe`, typed event unions, "global state only for shared data", and TanStack Query for request/response reads. Leave out RTK slices and thunks, the global event bus as a backbone, and Query as a live-data cache [verified, §9].

## Scope

Covers: live data from source to React component (Q4): the platform primitives, the library choice for main and renderer, where TanStack Query fits, the pipeline stages, the subscription protocol and its lifecycle, ordering, log batching, polling, the gh/local merge point, and the expause_web comparison for state (Q6).

Leaves to others: IPC primitives, channel mechanics and the `StudioApi` contract → **01** (this file uses 01's names). Folder and layer placement (names below are placeholders) → **02**. Measured costs of IPC, rendering and virtualised log lists → **04**. The trust rules' content, argv building and log sanitising → **05**. Test strategy and the browser-mode fixture → **06**.

## Findings

### 1. What the platform gives, and what it doesn't

| Where | Primitive | Use in Studio | Source |
|---|---|---|---|
| Main (Node 24.22.3 in Electron 45.5.0) | `child_process.spawn` + `readline.createInterface({ input, crlfDelay: Infinity })`, `for await (const line of rl)` | NDJSON from `runs watch`, `git`/`gh` output, log tails | [verified] [3][4] |
| Main | `events.on(emitter, name, { signal, close })` → async iterator, ends on `AbortSignal` | Turn emitters into loops that cancel cleanly | [verified] [5] (events.md:1704–1729) |
| Main | `fs.watch(path, { recursive, signal })`. Recursive on Linux since v19.1.0; closes on `AbortSignal` | Local registry / log folder watching on the `Direct` transport (not over `\\wsl$`, see 05-harness §4) | [verified] [6] |
| Main | `AbortController` | One per source attempt; aborting kills the child and ends the loops | [verified] [5] |
| IPC | `webContents.send(channel, …args)`: one-way, Structured Clone, no reply, no backpressure | Main → renderer push (01's choice) | [verified] [1] (web-contents.md:2060) |
| IPC | `webContents.postMessage` + `MessagePortMain` | **Not in the spike** (01 §3 keeps it in reserve). Under context isolation it also needs a `window.postMessage` relay in the preload, so it is not "free cleanup" | [verified] [1][2], 01:100 |
| Preload | `contextBridge` proxies **functions in both directions**, so `onRunsUpdated(repo, cb)` can return an `unsubscribe` function | 01's `on*` members | [verified] [7] (context-bridge.md:146) |
| Main | webContents events `render-process-gone`, `destroyed` | Subscription cleanup on crash or close | [verified] [1] (web-contents.md:485, 503) |
| Renderer | `useSyncExternalStore(subscribe, getSnapshot)` | Tear-free reads from an external store | [verified] [8] |
| Renderer | DOM `Observable` (`EventTarget.when()`), Chromium ≥ 135; Electron 45.5.0 is Chromium 156 | Not used: not in Node (main), Firefox or Safari, and it buys nothing over a callback here | [verified] [9][10] |

**What Electron does not provide** [inferred]: a store; subscription bookkeeping; cleanup when a renderer reloads (listeners in main live on); reconnect or resync; batching. The IPC guide's main-to-renderer pattern is a bare `ipcRenderer.on` wrapper with no unsubscribe [verified] [11] (ipc.md:359–460). 01 §3 already fixes the preload shape: keep the wrapper `h`, return a closure that removes it, because a proxied callback can't be matched by `removeListener` [verified 01:122–136].

### 2. Main side: RxJS or plain streams?

| Option | Version / last release | What it buys here | What it costs here |
|---|---|---|---|
| **RxJS** | 7.8.2, 22 Feb 2025 (**> 12 months old**); 8.x stuck at alpha.14 (Jan 2024); 9.0.0-beta.1 (9 Oct 2026, the `next` dist-tag). Repo active (push 19 Nov 2026) [verified] [12][13] | `retry({delay})`, `bufferTime`, `switchMap` on repo change, `share` | A second paradigm for every main-process file and agent; marble-style stack traces; a major version pending. The stream still ends at an IPC boundary, which RxJS does not cross |
| **Plain Node + small functions** | n/a | `for await` + `AbortSignal`, an inline `backoff(attempt)`, a log flush timer | ≈40 lines of our own, tested with fake timers [inferred] |

**Recommendation: plain Node.** Revisit trigger: RxJS 9 is stable **and** three or more sources must be combined with time-based operators.

### 3. Renderer side: the live store

Versions, dates and sizes as of 2026-11-25 (npm registry, bundlephobia min+gz). The "tear-safe" column comes from reading each package's React binding source.

| Option | Version (released) | min+gz | Tear-safe in React 19 | Fit for snapshot + upsert/remove | Boilerplate | Verdict |
|---|---|---|---|---|---|---|
| **Zustand** | 5.1.0 (2026-11-06) | 0.5 kB | **Yes**: `useStore` is `React.useSyncExternalStore` [verified] [14] | Good: `setState(s => applyRunsEvent(s, e))` | Very low; vanilla `createStore` needs no Provider | **Pick for live state** |
| Hand-rolled store + uSES | n/a | 0 | Yes | Same | ≈40 lines | Fine fallback; loses `useShallow` |
| Redux Toolkit + react-redux | RTK 2.15.0 (2026-11-18), react-redux 9.3.1 | 14.6 kB + binding | Yes [verified] [15] | Good (reducers); RTK Query streaming via `onCacheEntryAdded` [verified] [16] | Medium–high (slices, store, Provider, typed hooks) | Overkill at this size |
| TanStack Query | 5.108.4 (2026-11-23) | 13.4 kB | Yes (uSES in `useBaseQuery`) [verified] [17] | Only by writing pushes into the cache with `setQueryData`; `experimental_streamedQuery` is still experimental [verified] [17] | Medium | **Not for live state; yes for on-demand reads (§3.1)** |
| Jotai | 3.0.2 (2026-11-09; 3.0.0 on 2026-09-08) | 3.3 kB | Not guaranteed by default: `useAtomValue` uses `useReducer`+`useEffect` (a deliberate trade for time slicing); `useAtomValueRawSync` uses uSES [verified source] [18]; "can tear" is our reading [inferred] | Awkward: an atom per entity, or one big atom | Low | No: poor fit for entity upserts, and a brand-new major |
| Preact signals (`@preact/signals-react`) | 3.12.0 (2026-08-04) | 3.1 kB | Uses uSES [verified] [19] | Fine | Low, but its own model (and a Babel transform for auto-tracking) | No: a build transform and a second reactivity model. TC39 Signals is still **Stage 1** [verified] [20] |
| MobX + mobx-react-lite | 7.1.7 (2026-11-13) / 5.1.4 | 15.1 + 1.9 kB | Yes [verified] [21] | Fine (mutable observables) | Medium | No: mutable proxies hide where state changes. Pushed DTOs are also frozen by `contextBridge` (01:118) |

**Concurrency note** [verified] [8]: a store update during a transition falls back to a blocking render with any uSES store. Fine here: card updates are tiny. For log filtering or search, wrap the *input* in `useDeferredValue`, not the store.

### 3.1 TanStack Query: where it fits and where it doesn't

The owner notes TanStack Query is everywhere. That is true, and it is worth using here, for one job.

| Fact | Value | Source |
|---|---|---|
| Version / React 19 | 5.108.4 (2026-11-23), peers `react ^18 \|\| ^19`; docs: "compatible with React v18+"; depends only on `@tanstack/query-core` | [verified] [17][28] |
| Adoption | ≈90.7 M npm downloads in the week to 2026-11-24 (Zustand ≈96.1 M, RTK ≈51.9 M, SWR ≈27.9 M); ~50.6 k GitHub stars, pushed 2026-11-25 | [verified] [29] |
| What it is for | "fetching, caching, synchronizing and updating **server state**"; the docs call Zustand/Redux client-state libraries and say Query "can be used alongside" them | [verified] [28] |
| Defaults that matter in Electron | `networkMode: 'online'` **pauses queries when `navigator.onLine` is false**; refetch on mount, window focus and reconnect; 3 retries with backoff; inactive data GC'd after 5 min; structural sharing keeps unchanged references | [verified] [28] |

Studio has two kinds of data, and they want different tools [inferred]:

| Data | Shape | Tool | Why |
|---|---|---|---|
| Board: runs, Issues, connection status | Pushed by main (`runs:updated`, `issues:updated`), changes on its own | **Zustand** | Main is already the cache and poller. Query's staleness and refetch rules would duplicate main's poll scheduler, and `setQueryData` for every push puts a live stream in a request cache |
| Log tail | High-rate push, ring buffer | **`LogRing`** | Neither library fits a capped append-only stream |
| Run detail + analytics, Issue detail, PR detail, doctor, repo list | Request/response via `invoke` (01's `runDetail`, …), read when a screen opens | **TanStack Query** | Gives loading/error states, deduping, back-navigation cache, cancellation of stale responses and invalidation, which a hand-written `useEffect` fetch gets wrong (races, no cache) |
| Commands (start, pause, resume, answer) | `invoke`, main shows the native confirm | **`useMutation`** | Pending/error state per button; `onSuccess` invalidates the affected detail |

**One store for everything instead?** It means writing loading/error/cache/race handling into Zustand for every on-demand read, or one generic `useInvoke` hook (≈40 lines) that agents would extend into a worse Query. With about five reads and four commands, Query's cost (one dependency, one `QueryClientProvider`, three defaults to set) is smaller than that code [inferred]. If v1 ends up with only one or two reads, a plain hook is fine; that is the only case where one store is simpler.

**Rules that keep the two from overlapping** [inferred]:
- Query never holds data that main pushes. Zustand never holds request/response data.
- `queryFn` calls a `getStudio()` verb and throws on `Result` error, so Query's error state works: `queryFn: () => unwrap(getStudio().runDetail(repo, branch))`.
- `QueryClient` defaults: `networkMode: 'always'` (reads are local IPC, and some are local files that work offline), `retry: 1`, `staleTime: 30_000` (a refocus doesn't fire a gh call every time).
- The one bridge: when `applyRunsEvent` upserts or removes run X, call `queryClient.invalidateQueries({ queryKey: ['runDetail', repo, X] })`. Main stays the only poller.
- Browser mode: the fixture `StudioApi` (01 §5) backs both the `on*` pushes and the `queryFn`s, so nothing else is needed.

### 4. The pipeline (minimal core)

```
 SOURCE ADAPTERS (main)            NORMALISE (pure)       READ-MODEL (main, pure)        PUSH (01)             RENDERER
 runs watch --json (NDJSON)  ──┐
   spawn → readline → JSON     │   run_updated/removed ─→  reduce + mergeRun  ───────→  runs:updated    ───→ applyRunsEvent → Zustand
   (log events, see below)     ├─→ IssueUpserted       ─→  (trust rules)      ───────→  issues:updated  ───→ applyIssuesEvent ┘ → useRunCard(id), useColumn(c)
 gh api poll (ETag, 304)     ──┤   LogLines            ─→  per-run LogRing    ── 50 ms → log:lines       ───→ LogRing (rAF) → useLogTail(branch)
 fs.watch logs (Direct only) ──┘
```

| Stage | Responsibility | Pure? | Notes |
|---|---|---|---|
| Source adapter | Spawn or poll; bytes → lines or JSON; retry with backoff; the heartbeat watchdog | No (I/O) | One per source kind. The transport (`Direct \| Wsl`) is injected, so the adapter never branches on OS |
| Normaliser | Validate against the `contract/` types and map: `snapshot` → `RunsSnapshot`, `run_updated` → `RunUpserted`, `run_removed` → `RunRemoved`, `log` → `LogLines`, `heartbeat` → watchdog only; gh issues → `IssueUpserted` (drop items carrying `pull_request`) | **Yes** | Untrusted input; a validation failure is counted and logged, never thrown into the loop |
| Read-model | `reduce(model, event) → { model, changed }`, plus `mergeRun(remote, local)` | **Yes** | The unit-testable heart |
| Publisher | Sends `snapshot` on subscribe and after `reduce` of a source snapshot; otherwise one `upsert`/`remove` per changed entity | No | No timer, no diff step: events arrive at human rates |
| Renderer reducers | `applyRunsEvent(state, e)` replaces only the changed entity, so other cards keep their identity and skip re-rendering | **Yes** | Must copy, not mutate: pushed DTOs are frozen (01:118) |

**Logs per transport** [verified 05-harness-integration.md:80, 164; inferred routing]: on `Wsl`, logs arrive **only** as `log` events on the `runs watch` stream, because `\\wsl$` cannot be watched. On `Direct`, they come from the stream, or from `fs.watch` + a tail when the stream is unavailable. Both feed the same per-run `LogRing`.

**Why the read-model lives in main** [inferred]: it survives a renderer reload or crash (the resubscriber gets one snapshot); the trust-rule merge happens next to the raw sources, before untrusted data reaches the UI; and the browser-mode fixture only has to emit `snapshot`/`upsert`, not fake NDJSON and gh. Cost: state held twice (a few hundred KB at most).

**Size of the minimal core** [inferred estimate]:

| Piece | ≈ lines |
|---|---|
| `contract/` live event types | 50 |
| WatchAdapter + `ndjson()` with heartbeat | 120 |
| GhPollAdapter (issues, ETag, 304) | 80 |
| Normaliser | 60 |
| `reduce` + `mergeRun` stub | 80 |
| Subscription registry + publisher | 70 |
| `LogRing` (one module, used on both sides) + log flush | 60 |
| Renderer store, reducers, hooks, Query client + bridge | 100 |
| Fixture live events (on top of 01's fixture) | 40 |
| **Total** | **≈ 550–700**, plus tests |

### 5. Lifecycle, ordering, log batching

#### 5.1 Subscription lifecycle

| Event | What happens |
|---|---|
| Root mounts `useBoardLive(repo)` | Preload `onRunsUpdated`/`onIssuesUpdated` → `invoke('subscribe', {topic, repo})` (01:128). Main records `(webContents.id, topic, repo)`; idempotent. If no source runs for that (repo, topic), start it. Main sends a `snapshot` to this subscriber |
| Repo switch / unmount | The unsubscribe closure → `invoke('unsubscribe', …)`. When a (repo, topic) has no subscribers left, abort its sources immediately |
| Preload loads (first load or reload) | Preload sends `hello` once. Main drops every subscription for that `webContents.id`. The page then subscribes afresh and gets snapshots |
| `render-process-gone` / `destroyed` | Same drop as `hello` [verified events] [1] |
| App quit | Abort everything; children are killed by process group (01 §6) |

`hello` replaces 01 §6's `did-start-navigation` trigger [inferred]: that event fires before a navigation commits, so a cancelled navigation would drop live subscriptions, and with navigation denied (01:19) the real cases are reload and crash. `hello` arrives on the same ordered channel as the following `subscribe`, so there is no race. 07 should carry this into the lifecycle table. The spike's "log the subscription count" check covers reload (`hello`) and crash (`render-process-gone`, forced with `process.crash()`).

#### 5.2 Reconnect with a fresh snapshot

```ts
for (let attempt = 0; !signal.aborted; attempt++) {
  const run = new AbortController(); const stop = () => run.abort();
  signal.addEventListener('abort', stop, { once: true });
  try {
    emit({ kind: 'status', state: attempt ? 'reconnecting' : 'connecting' });
    const child = transport.spawn(argv, { signal: run.signal });            // abort kills the process group (01 §6)
    for await (const ev of ndjson(child.stdout, { heartbeatTimeoutMs: 3 * HB, signal: run.signal })) {
      attempt = 0; emit(ev);                                                // first event is `snapshot`
    }
  } catch (e) { emit({ kind: 'status', state: 'reconnecting', reason: String(e) }); }  // watchdog timeout, spawn error, bad JSON
  finally { run.abort(); signal.removeEventListener('abort', stop); }       // never leave a silent child alive
  await sleep(backoff(attempt), signal);                                    // 1 s → 30 s cap, ±20 % jitter
}
```

The per-attempt controller is what kills a hung `wsl.exe`/`runs watch` when the watchdog fires (the orphan case 10 §5 check 4 tests). The read-model **replaces** the watch-sourced slice on every `snapshot` and publishes a `snapshot`; the renderer swaps its mirror. 10 §5 wants a resync within 5 s after `wsl --shutdown`; the first retry at 1 s fits [inferred].

#### 5.3 Ordering and batching

- **Main → renderer:** none needed. Messages to one webContents arrive in order, and the two gap cases (reload, source restart) both end in a snapshot [inferred].
- **Harness → main:** lines from one pipe are ordered and lossless. `run_updated` carries the whole run (05-harness §4 sends `run?` whole) [verified] [22], so ask harness follow-up **F-1** (`10-recommendation.md` §8, line 382) only for a `ts` per event, for the gh-vs-watch comparison. No `seq`.
- **gh poll vs watch for the same run:** compare `updated_at`; an older poll never overwrites a newer watch value (§7).
- **Log lines:** main appends to a per-run `LogRing` (10 000 lines) and flushes `log:lines` every 50 ms or 500 lines. The first message after subscribe is the current ring contents; the renderer starts with an empty ring, so no separate reset message is needed. The renderer pushes into its own `LogRing` and bumps a version counter once per `requestAnimationFrame`; `useLogTail` reads it through uSES; virtualised list (04). A batch over the cap is truncated with a `{ skipped: n }` line. `webContents.send` gives no backpressure, so the rings and the flush window are the bound [inferred from [1]].

#### 5.4 Deferred: add when the trigger happens

| Mechanism | Add when |
|---|---|
| `epoch` + gapless `seq` on pushes | A transport that can drop or reorder (MessagePort relay, utilityProcess, network), or a measured mirror divergence |
| `seq` on `runs watch` events (harness ask) | The harness stream becomes lossy (e.g. goes through a relay) |
| Ref-count with a grace period before stopping a source | Day 4 (10 §5 check 4) measures a costly `runs watch` respawn on a quick repo toggle |
| Coalescing board patches (≈100 ms) | Profiling (04) shows bursts of `run_updated` causing visible jank |
| One source shared by several windows | A detail pop-out window (not v1) |
| Full `mergeRun` precedence table | The data-layer item (Issue #1 item 5) and 05 define it; the spike ships Issue #1's three rules as tests |
| Workflow-run and PR polling (§6 rows 2–3) | Remote (GitHub-executed) runs and the Done column are wired after the spike |
| RxJS 9 | Stable, and three or more sources need time-based composition |

### 6. Polling gh: cadence and conditional requests

| Data | Endpoint (REST, conditional) | Focused | Hidden/minimised | After an action | In the spike |
|---|---|---|---|---|---|
| Open issues (To Do) | `GET /repos/{o}/{r}/issues?state=open&per_page=100` | 60 s | 5 min | Immediately, then 5 s × 3 | **Yes** |
| Workflow runs `harness …` | `GET /repos/{o}/{r}/actions/runs?…` | 20 s while a run is active, else 60 s | 5 min | Immediately, then 5 s × 6 | Later |
| PRs (Done) | `GET /repos/{o}/{r}/pulls?state=closed&…` | 5 min | off | On a run reaching review/gates | Later |

- **`/issues` returns PRs too** ("GitHub's REST API considers every pull request an issue"), and pages at 30 by default, max 100 [verified] [30][31]. The normaliser drops items with a `pull_request` key. Poll only page 1 by ETag; if a repo has more than 100 open issues, refetch all pages only when page 1 changes [inferred].
- Send `If-None-Match` with the stored ETag; a 304 costs no primary rate limit when authorised. Honour `x-poll-interval` **when present** (GitHub sends it on a few endpoints). Keep parameters identical between polls and avoid `sort=updated` [verified] [23].
- **gh CLI behaviour [verified] [27][32]:** a 304 prints `HTTP/2.0 304 Not Modified` (with `-i`), writes `gh: HTTP 304` to stderr and exits 1. Exit 1 is generic: `api.go:553–564` turns **any** status > 299 into `gh: HTTP <code>` and a silent error. So the adapter parses the `-i` status line, maps only `304` to "unchanged", and treats anything else as an error. A 304 left `X-Ratelimit-Used` unchanged in a local re-run.
- `gh issue list --json` calls `client.GraphQL(...)` (`pkg/cmd/issue/list/http.go:91`), and GraphQL has no ETags, so every poll would cost rate limit. Use `gh api` REST for anything polled [verified] [32].
- Budget at the focused cadence, per **active repo** (only the selected repo is polled): issues 60/h + runs 180/h + PRs 12/h ≈ 250 requests/h before 304 savings, against 5 000/h authenticated. The spike polls issues only: 60/h [inferred from [23]].
- Visibility: the renderer reports `document.visibilityState` through one intent (`setVisible`). Main's poll scheduler is the only reader. One scheduler per repo, ±10 % jitter, no overlapping polls per endpoint.

### 7. Merging gh with local registry data (trust rules)

The rules come from Issue #1 "Data source" [verified] [24]: git/gh are primary; local registry and logs only add detail; a progress comment counts only if `github-actions[bot]` wrote it; Actions run state wins over labels; JSON committed on a branch is untrusted. The data-flow consequence [inferred]:

```ts
// read-model/mergeRun.ts: pure, no I/O
type Source = 'actions' | 'label' | 'botComment' | 'localRegistry' | 'watch';
type RunView = RunSummary & { provenance?: { phase?: Source; state?: Source }; conflict?: string };
function mergeRun(r: RemoteRun | undefined, l: LocalRun | undefined): RunView { /* rules as a small table */ }
```

- The merge happens in main's read-model, never in components. `RunView` stays a plain DTO; `provenance` labels only the fields the UI shows a source for ("phase from local registry"), and `conflict` flags a disagreement.
- Branch-JSON fields (analytics, statistics) are display-only and arrive through the on-demand `runDetail` read, not the board. They never drive state, actions or column placement.
- Local `watch` data may give a *finer* phase than gh, but never a contradicting terminal state. If Actions says completed and local says running, Actions wins and `conflict` is set.
- The full precedence and its tests belong to 05 and the data-layer item (Issue #1 item 5).

### 8. Sketches

**Contract (adds to 01's `StudioApi`; 01 owns the channels):**

```ts
// contract/studio-api.ts (live part)
export type LiveEvent<T, Id> =
  | { kind: 'snapshot'; items: T[] }                 // any snapshot replaces the mirror
  | { kind: 'upsert'; item: T }
  | { kind: 'remove'; id: Id }
  | { kind: 'status'; source: 'watch' | 'gh'; state: 'connecting' | 'live' | 'reconnecting' | 'stale'; since: string };
export type RunsEvent = LiveEvent<RunView, string /* branch */>;
export type IssuesEvent = LiveEvent<IssueView, number>;
export type LogLine = { text: string } | { skipped: number };

// in StudioApi (01:172–173, plus onIssuesUpdated for 01's `issues:updated` channel)
onRunsUpdated(repo: RepoId, cb: (e: RunsEvent) => void): Unsubscribe;
onIssuesUpdated(repo: RepoId, cb: (e: IssuesEvent) => void): Unsubscribe;
onLogLines(repo: RepoId, branch: string, cb: (lines: LogLine[]) => void): Unsubscribe;
```

**Store, connector, hooks (renderer):**

```ts
export const boardStore = createStore<BoardMirror>()(() => EMPTY);              // zustand/vanilla

export function useBoardLive(repo: RepoId) {                                    // mounted once at the root
  const qc = useQueryClient();
  useEffect(() => {
    const studio = getStudio();
    const offRuns = studio.onRunsUpdated(repo, e => {
      boardStore.setState(s => applyRunsEvent(s, e), true);                     // pure; snapshot replaces
      if (e.kind === 'upsert' || e.kind === 'remove')
        qc.invalidateQueries({ queryKey: ['runDetail', repo, e.kind === 'upsert' ? e.item.branch : e.id] });
    });
    const offIssues = studio.onIssuesUpdated(repo, e => boardStore.setState(s => applyIssuesEvent(s, e), true));
    return () => { offRuns(); offIssues(); };
  }, [repo, qc]);
}
export const useRunCard = (branch: string) => useStore(boardStore, s => s.runs.get(branch));
export const useColumn  = (c: Column) => useStore(boardStore, useShallow(s => s.order[c]));
export const useRunDetail = (repo: RepoId, branch: string) =>
  useQuery({ queryKey: ['runDetail', repo, branch], queryFn: () => unwrap(getStudio().runDetail(repo, branch)) });
```

### 9. expause_web: what carries over (Q6)

What expause_web does [verified]:
- `src/infrastructure/eventBus.ts:3–75`: a typed, in-process `Map<string, Set<handler>>` bus. `on()` returns an unsubscribe; there is also prefix matching. 33 files import it, mostly to sync "item X changed" across screens (`useContentTags.ts:115–121`).
- `src/domain/usecases/chat/subscribeToChatUpdatesUseCase.ts:1–41, 89–105`: a subscribe use case is a "thin domain pipe". It maps DTO → entity, routes by change type, returns an `Unsubscribe`, and does not touch Redux. The Firestore SDK provides snapshot+delta, ordering and reconnect.
- `docs/architecture/STATE_MANAGEMENT.md`: RTK slices as Flutter Cubits. Its own note (lines 49–55) and `REACT_STATE_BEST_PRACTICES.md` retreat to "Redux only for truly global state, local state for one screen, React Query for API data".

| Idea | Carries over? | Why |
|---|---|---|
| Subscribe function returning `Unsubscribe`; thin pipe, no store access | **Yes** | The same shape as 01's `on*` members and the source adapters |
| Typed event map | **Yes, as discriminated unions** (`RunsEvent`, normaliser events) | Same type-safety without string keys |
| A global in-process event bus | **No** as the backbone | Events cross a process boundary; the read-model and pushes replace "screen A tells screen B", and a bus would hide data flow from reviewer agents |
| "Global store only for shared data; local `useState` for one screen" | **Yes** | Board mirror and connection status in Zustand; dialog, form and pending state local |
| RTK slices per feature + thunks | **No** | Thunks do I/O in the renderer; here I/O lives in main behind intents. Keep only the pure-reducer habit |
| TanStack Query for API data | **Yes for request/response reads and commands; no for live data** | Same role as in expause_web ("React Query for API data"); main stays the live cache and poller (§3.1) |
| Firestore listener semantics (snapshot, then changes; SDK reconnects) | **As a model** | Studio re-creates the contract by hand: snapshot, upsert/remove, reconnect with snapshot |
| Dexie / IndexedDB | **No** | Nothing needs to persist in the renderer. See 02 |

Note: expause_web is on React 18.3 [verified] [25]. Studio starts on React 19.3.1 (latest, 2026-10-14) [verified] [26]. Both Zustand and TanStack Query are uSES-based and support it.

## Recommendation for the spike

**Day 1 (renderer, browser mode)**
1. Add `zustand@5.1.0` and `@tanstack/react-query@5.108.4` (pinned), React 19.3.x. One `QueryClient` with `networkMode: 'always'`, `retry: 1`, `staleTime: 30_000`.
2. Add the live types to `contract/` (§8) and the pure `applyRunsEvent`/`applyIssuesEvent`, with unit tests: snapshot replaces, upsert keeps other identities, remove.
3. Extend 01's fixture `StudioApi` to replay a JSON fixture of `snapshot` + timed `upsert`s + `log:lines` batches, with a test hook to push events (06). Build the board, detail screen and log tail in a plain browser.
4. Hooks: `useBoardLive`, `useRunCard`, `useColumn`, `useConnection`, `useLogTail` (Zustand/`LogRing`); `useRunDetail` and the command mutations (Query). Components import only hooks.

**Day 2 (main), the minimal core only**
5. `WatchAdapter` (§5.2: spawn the **stand-in** `runs watch` from 10 §5 through the transport, readline, heartbeat watchdog, per-attempt abort) and one `GhPollAdapter` for open issues (`gh api -i` + ETag, only a parsed 304 is "unchanged", drop PRs, `per_page=100`).
6. Normaliser, pure `reduce` + `mergeRun` stub (Issue #1's three rules as tests), per-run `LogRing` with the 50 ms flush.
7. Subscription registry keyed by `(webContents.id, topic, repo)` inside 01's `subscribe`/`unsubscribe` handlers; snapshot on subscribe and on source restart; drop on `hello`, `render-process-gone`, `destroyed`.
8. Spike checks: kill the stand-in → badge shows "reconnecting" → fresh snapshot within 5 s, and no orphan child. Reload and crash the window → subscription count returns to its previous value. 10k-line burst → UI stays responsive (04 measures).

**Not in the spike:** everything in §5.4, RxJS, RTK, devtools, persistence.

## Answers to the owner's questions

**Q4: How do live updates flow from a child process or watched file to a React component?**
Child stdout → `readline` async iterator → a pure normaliser → a pure read-model reducer in **main** (merging gh + local under the trust rules) → a `snapshot` on subscribe, then one `upsert`/`remove` per change on `runs:updated`/`issues:updated` (01) → the preload's `onRunsUpdated(repo, cb)` → a pure `applyRunsEvent` into a **Zustand** store → selector hooks (`useRunCard`) via `useSyncExternalStore` → components. Log lines take a parallel path: ring buffers on both sides, 50 ms batches, one rAF-paced re-render. Screens that read on demand (run detail, analytics, Issue/PR detail) use **TanStack Query** over `invoke`, and a live upsert invalidates the matching detail. Electron gives the pipes (Node streams, `webContents.send`, lifecycle events) and React gives `useSyncExternalStore`. We add the adapters, the reducers, a subscription registry, reconnect-with-snapshot and log batching: about 550–700 lines, not an observable framework.

**Q5 (this area's part).** Performance: entity upserts keep untouched cards' identity; logs are batched (50 ms main, rAF renderer) and capped by rings. Measure in 04. Security: the merge and validation sit in main before data crosses IPC; the renderer only receives normalised views. Details in 05.

**Q6 (state and live updates).** See §9. Keep subscribe functions, typed events, "global only when shared", and TanStack Query for request/response reads. Drop the global event bus as a backbone, RTK slices and thunks, and Query as a live-data cache.

## Risks and open questions

1. **`runs watch` does not exist yet** (F-1). The spike runs against a stand-in. Ask F-1 for a `ts` per event; `seq` is not needed (§5.3).
2. **gh 304 handling relies on CLI behaviour** (exit 1 for any status ≥ 300, `gh: HTTP 304`), which is code, not a documented contract. Pin it with an adapter test and re-check on gh upgrades. Alternative: call REST directly with `gh auth token` (05 decides whether main may hold the token).
3. **The heartbeat interval is not specified yet.** The watchdog multiple (3×) needs the harness value.
4. **Cadences are guesses.** Tune after the spike with real WSL restart costs (04, 10 §5 check 4); that measurement also decides whether a grace period is needed (§5.4).
5. **Zustand 5.1.0 is 19 days old.** Low risk (API stable since 5.0). Pin the exact version. TanStack Query ships patch releases almost daily; pin it too.
6. **Two state tools.** The split rule (pushed data → Zustand, requested data → Query) must go into the renderer conventions document (02), or agents will mix them.
7. **Disagreement UI** (local says running, Actions says completed) needs a design decision. Flagged, not solved here.
8. **`hello` vs 01's `did-start-navigation`** must be reconciled in 07 (§5.1).
9. **Sources older than 12 months:** RxJS 7.8.2 (Feb 2025) is the current stable; the 9.x beta line is active. TC39 Signals has been at Stage 1 since Apr 2024.

## Sources

All accessed 2026-11-25.

1. https://raw.githubusercontent.com/electron/electron/v45.5.0/docs/api/web-contents.md — `send` (l.2060, Structured Clone), `postMessage` + `MessagePortMain` (l.2117), `did-start-navigation` (l.313), `render-process-gone` (l.485), `destroyed` (l.503).
2. https://raw.githubusercontent.com/electron/electron/v45.5.0/docs/tutorial/message-ports.md — the `close` event extension on ports, GC closes ports (l.71–80).
3. https://releases.electronjs.org/releases.json — Electron 45.5.0 = Chromium 156.0.8078.109, Node 24.22.3, 2026-11-24.
4. https://raw.githubusercontent.com/nodejs/node/v24.x/doc/api/readline.md — `rl[Symbol.asyncIterator]()` stable (l.393–404), `crlfDelay`.
5. https://raw.githubusercontent.com/nodejs/node/v24.x/doc/api/events.md — `events.on(emitter, name, {signal, close, highWaterMark})` (l.1704–1729).
6. https://raw.githubusercontent.com/nodejs/node/v24.x/doc/api/fs.md — `fs.watch` recursive on Linux since v19.1.0, `AbortSignal` close (l.5240–5255).
7. https://raw.githubusercontent.com/electron/electron/v45.5.0/docs/api/context-bridge.md — functions proxied both ways (l.128, 146); safe `ipcRenderer.on` wrapper pattern (l.155–175).
8. https://raw.githubusercontent.com/reactjs/react.dev/main/src/content/reference/react/useSyncExternalStore.md — transition fallback to blocking (l.60), don't suspend on store values (l.62), stable `subscribe` (l.410–435).
9. https://chromestatus.com/feature/5154593776599040 — DOM Observable API, Chrome desktop milestone 135.
10. https://github.com/WICG/observable — DOM Observable proposal (context for 9).
11. https://raw.githubusercontent.com/electron/electron/v45.5.0/docs/tutorial/ipc.md — Pattern 3 main→renderer (l.359–460); Structured Clone (l.561).
12. npm registry `rxjs` (`npm view rxjs time`) — 7.8.2 on 2025-02-22; 9.0.0-beta.1 on 2026-10-09 (`next` dist-tag); `sideEffects: false`. Bundlephobia rxjs@7.8.2: 65.1 kB min / 17.8 kB gz.
13. https://github.com/ReactiveX/rxjs/releases (via `gh api`) — 8.0.0-alpha.14 2024-01-12; 9.0.0-beta.0 2026-08-04; repo pushed 2026-11-19.
14. https://unpkg.com/zustand@5.1.0/esm/react.mjs — `useStore` = `React.useSyncExternalStore`. npm: 5.1.0 on 2026-11-06. Bundlephobia: 833 B min / 491 B gz.
15. npm `@reduxjs/toolkit` 2.15.0 (2026-11-18), bundlephobia 40.1 kB / 14.6 kB gz; https://unpkg.com/react-redux@9/dist/react-redux.mjs uses `useSyncExternalStore`; react-redux 9.3.1.
16. https://raw.githubusercontent.com/reduxjs/redux-toolkit/master/docs/rtk-query/usage/streaming-updates.mdx — `onCacheEntryAdded`, `updateCachedData`, `cacheEntryRemoved`.
17. npm `@tanstack/react-query` 5.108.4 (2026-11-23; `npm view` peers `react ^18 || ^19`, dependency `@tanstack/query-core` 5.108.4), bundlephobia 46.6 kB / 13.4 kB gz; https://unpkg.com/@tanstack/react-query@5.108.4/build/modern/useBaseQuery.js (uSES l.46); https://unpkg.com/@tanstack/query-core@5.108.4/build/modern/index.d.ts exports `streamedQuery as experimental_streamedQuery`.
18. https://unpkg.com/jotai@3.0.2/dist/react/useAtomValueRaw.js (`useReducer` + `useEffect`) and `useAtomValueRawSync.js` (uSES). npm: 3.0.0 on 2026-09-08, 3.0.2 on 2026-11-09; bundlephobia 7.9 kB / 3.3 kB gz.
19. https://unpkg.com/@preact/signals-react@3.12.0/runtime/dist/runtime.mjs — uses uSES. npm 3.12.0 on 2026-08-04; bundlephobia 8.5 kB / 3.1 kB gz.
20. https://github.com/tc39/proposal-signals (README l.4: Stage 1) and https://github.com/tc39/proposals (Stage 1 table, notes 2024-04 / 2024-06).
21. npm `mobx` 7.1.7 (2026-11-13; 7.0.0 on 2026-07-30), `mobx-react-lite` 5.1.4 (2026-11-21); https://unpkg.com/mobx-react-lite@5.1.4/dist/mobxreactlite.esm.js uses uSES; bundlephobia 15.1 kB + 1.9 kB gz.
22. /Users/daniel/Work/devscenestudio/docs/product-startup-research/05-harness-integration.md:80, 164 — `runs watch` event types (`snapshot`, `run_updated`, `run_removed`, `log`, `heartbeat`), snapshot-first, exit on stdin close, no watching `\\wsl$`; 10-recommendation.md:290 (check 4: 5 s resync, no orphans), :382 (F-1).
23. https://raw.githubusercontent.com/github/docs/main/content/rest/using-the-rest-api/best-practices-for-using-the-rest-api.md — avoid polling, `x-poll-interval` "if a response includes" it (l.31), conditional requests and 304 not counted (l.25–33, 76–129).
24. GitHub Issue #1 (`gh issue view 1`), "Data source" bullet and item 5 — trust rules and data sources.
25. /Users/daniel/Work/expause/expause_web: `package.json` (react ^18.3.1, @reduxjs/toolkit ^2.2.7, @tanstack/react-query ^5.90.5); `src/infrastructure/eventBus.ts:3–75` (34 files match `eventBus` including itself); `src/domain/usecases/chat/subscribeToChatUpdatesUseCase.ts:1–41, 89–105`; `src/presentation/feature/contentTag/contentTagsPage/hooks/useContentTags.ts:115–121`; `docs/architecture/STATE_MANAGEMENT.md:49–55`; `docs/REACT_STATE_BEST_PRACTICES.md`.
26. npm `react` 19.3.1, released 2026-10-14.
27. Local check, gh 2.100.0, 2026-11-25: `gh api -i -H 'If-None-Match: <etag>' 'repos/firu-daniel/devscenestudio/issues?state=open'` → `HTTP/2.0 304 Not Modified`, stderr `gh: HTTP 304`, exit code 1; `X-Ratelimit-Used` unchanged.
28. TanStack Query docs (main branch): https://raw.githubusercontent.com/TanStack/query/main/docs/framework/react/overview.md (server state, l.6), `installation.md` (l.42: "compatible with React v18+"), `guides/does-this-replace-client-state.md` (l.8–15: server- vs client-state, use alongside), `guides/important-defaults.md` (refetch on mount/focus/reconnect, 3 retries, 5 min GC, structural sharing), `guides/network-mode.md` (default `online`; `always` for non-network `queryFn`s).
29. https://api.npmjs.org/downloads/point/last-week/{@tanstack/react-query,zustand,@reduxjs/toolkit,swr} — 2026-11-18…24: 90.7 M, 96.1 M, 51.9 M, 27.9 M; https://api.github.com/repos/TanStack/query — 50.6 k stars, pushed 2026-11-25.
30. https://docs.github.com/en/rest/issues/issues#list-repository-issues — "GitHub's REST API considers every pull request an issue"; `pull_request` key.
31. https://raw.githubusercontent.com/github/docs/main/content/rest/using-the-rest-api/using-pagination-in-the-rest-api.md — default 30 per page (l.20), `per_page` max 100 for most endpoints (l.69).
32. https://github.com/cli/cli/blob/v2.100.0/pkg/cmd/issue/list/http.go#L91 (`client.GraphQL`) and https://github.com/cli/cli/blob/v2.100.0/pkg/cmd/api/api.go#L553-L564 (status > 299 → `gh: HTTP <code>`, `SilentError`).
