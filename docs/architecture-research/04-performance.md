# 04 — Performance consequences of the architecture
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

> **Measurement caveat (applies to every number tagged "verified locally").** All local measurements were taken while the owner's Mac was also running a DevScene headless Gates phase, which loads CPU, memory and disk heavily. Every absolute time or rate below (ms, fps, CPU %, µs) is **noisy and an upper bound**. Memory figures (MB) are noisy **in an unknown direction**: memory pressure makes macOS compress pages, which can under-report working set and RSS. Byte sizes of bundles are deterministic and unaffected. Only **relative comparisons between variants measured in the same run** support the conclusions. Absolute targets (board ≤ 1.5 s, idle RSS, ≈ 0% hidden CPU, frame times) are left for the spike to measure on an idle machine (§8).

- **IPC is not the bottleneck; what the renderer does per message is.** Measured on Electron 45.5.0 (M4, under heavy load; absolute values are noisy upper bounds, and the ≈ 10× batched-vs-single ratio is the finding): a 2-line `invoke` round trip takes < 0.1 ms. A 300-card snapshot (110 KB serialized) round-trips in 0.8 ms. 10,000 single-line `webContents.send` messages take 18 ms in total, and the same lines in 500-line batches take 1.3 ms. At 2k lines/s, unbatched IPC costs ≈ 4 ms of wall time per second (≈ 2–5% if the machine were 3–5× slower; wall time, not measured CPU time [inferred]). Batch anyway: the saving is the renderer's per-message work, not the transport. [verified locally, §2]
- **A `MessagePort` is not faster than `webContents.send`.** It was 4.9 ms against 3.7 ms for 2,000 messages (under load; the gap is within noise, so read it as "no faster"). Choose it for lifecycle reasons (closing a stream closes a port), not for speed. Semantics are in 01 and 03. [verified locally]
- **Nothing measured here needs a `utilityProcess` in v1.** One costs ≈ 56 MB working set (measured under load and memory pressure; noisy) and ≈ 40 ms to spawn (Electron's own figure, Linux x64 release build [3]). The workloads it would offload take milliseconds: `JSON.parse` of 700 KB takes 1.2 ms, and ANSI-stripping plus NDJSON parsing of 2,000 lines takes < 1 ms (plain Node 22, under load, so upper bounds). The real main-process hazards are **sync calls** (`execSync`, `spawnSync`, `readFileSync` in handlers) and **backtracking regexes**: `(a+)+$` on 28 characters blocked for 4 s. Design source adapters as message-in/message-out (see 02) so moving one into a `utilityProcess` later is cheap. [verified locally + inferred]
- **300 cards do not need virtualisation. The log tail does.** The board mounts 3,604 DOM nodes in 8–35 ms. A one-card update takes 0.7 ms p50 even when the whole board re-renders. Memoised cards with per-id selectors cut that to 0.3 ms. That ≈ 2× gap is near the noise band, so memoisation is recommended on design grounds. The log is different: a naive React list of 10k lines ran at **26 fps with 36 ms per frame**. A virtualised list (TanStack Virtual, 50 DOM nodes) needed **0.6 ms per frame at 75 fps** at 2k lines/s. All of these were measured under heavy load, so the absolute values are noisy upper bounds. The ≈ 60× naive-vs-virtual ratio is robust. [verified locally, §3]
- **Keep `backgroundThrottling` at its default (true).** In a hidden window, a 16 ms timer fired 11 times in 10 s, `requestAnimationFrame` fired 0 times, and the renderer used 0% CPU (the counts reflect throttling behaviour; the CPU % was measured under load and is not the spike's target measurement). With throttling off, the page claimed `visibilityState: "visible"` while hidden and ran at full rate. **Main-process timers are never throttled.** `gh` polling in main must slow itself to 03's hidden cadence (≈ 5 min) when the window is hidden, minimised or occluded, and stop on `powerMonitor` `suspend`/`lock-screen` (§4; proposed policy for 07). [verified locally + docs]
- **Consequence for the store (03): the log ring buffer ingests on arrival and renders on rAF.** rAF stops when the window is hidden. A "pending lines" array flushed only in rAF would grow without bound while the window is hidden. Push into the ring at once (O(1), bounded) and use rAF only to schedule the render. [verified locally + inferred]
- **Startup:** bundle main, preload and renderer. 06 picks Vite for the renderer plus esbuild for main and preload (electron-vite as the fallback); performance is identical either way. The renderer needs a bundler for React anyway, and the Electron docs ask for a single bundled file. Start the `gh` calls in main at `ready`, in parallel with window creation: they cost ≈ 0.6 s (02 §4) and dominate the 1.5 s board budget. Skip custom V8 snapshots. `module.enableCompileCache()` loads in Electron 45 main (one cold-vs-warm run under disk load, so unconfirmed), and a small bundled main would gain only a few ms, so it can wait. [verified locally + docs]
- **Library choice barely moves the installer**, which is dominated by Electron at ≈ 90–130 MB compressed (02). Measured min+gzip, React external for the bindings: react+react-dom 69 KB, markdown-it 41 KB, DOMPurify 12.5 KB, TanStack Virtual 11 KB, react-window 6.5 KB, RxJS 8.6 KB (typical operators) to 18.6 KB (everything), zustand 0.4 KB, RTK + react-redux 9.5 KB. The one size trap is shipping `node_modules` unbundled: react-dom is 8 MB, RTK 7 MB and RxJS 4.5 MB unpacked. Keep renderer libraries in `devDependencies`, bundled. [verified locally]
- **Memory risks are architectural, not volumetric.** A 10k-line ring costs ≈ 3–5 MB per run, on each side where 03 keeps one (main and renderer); both sides need a cap. The leaks to design out are preload `on*` verbs without an unsubscribe (React StrictMode mounts twice; HMR and reloads re-register), and main-side child processes or stream subscriptions that outlive a renderer reload. Every subscription is keyed by `webContents.id` and torn down on reload or destroy. [inferred]

## Scope

Covered: how the architecture's choices (process placement, IPC shape, store shape, render strategy, hidden-window policy, bundling, library picks, subscription lifecycle) affect the spike's targets. The targets are 300 cards, a 10k-line ring with frame-batched appends, a board populated in ≤ 1.5 s with live `gh`, ≈ 0% CPU over 10 min hidden, idle RSS, installer size and a log tail at 1–2k lines/s. Also covered: how the spike measures them.

Left to others: the semantics of the IPC primitives (01), layering and file placement (02), the choice of store and stream library (03, which this file constrains in §3.3), security (05) and test tooling (06; this file only names the perf probes). Framework-level size, RAM and spawn numbers are in `../product-startup-research/02-performance.md` and are not repeated here.

## Findings

### 0. How the numbers here were measured

Measured 2026-11-25 on the owner's machine: Apple M4, macOS (Darwin 24.6), Electron **45.5.0** (Chrome 156.0.8078.109, Node 24.22.3), the repo's pinned binary, React 19.3.1, `@tanstack/react-virtual` 3.14.28. Scripts were throwaway micro-benchmarks: a hidden or shown `BrowserWindow` with `contextIsolation` and `sandbox`, a `contextBridge` preload (so the cross-world copy is included in the numbers), and medians of 7–200 repetitions.

**All runs happened under heavy concurrent load.** A DevScene headless Gates phase was running on the same Mac (CPU, memory and disk heavily loaded). The absolute times and rates are therefore **noisy upper bounds**: frame times, CPU %, IPC times and parse times. RSS and working set are noisy **in an unknown direction**: under memory pressure macOS compresses pages, which can under-report them (Electron omits `residentSet` on macOS [15]), while load can also inflate them. What the file relies on is the **ratio between variants run back to back in the same script** (batched vs single IPC, memoised vs naive board, virtual vs naive log, throttled vs unthrottled hidden window). Each variant pair shared the same load, though load can drift within a run, so small ratios (under ≈ 2×) are not significant. Every table of local numbers below is tagged **(under load; noisy upper bound)**. The spike re-measures every absolute target on an idle machine (§8).

**An M4 is fast.** Expect a 2019-era Intel laptop or a Linux VM with a virtual GPU to be several times slower [inferred]. Read every number as a ratio between options, and as an upper bound on how cheap the cheap option is. [inferred]

**Runtimes.** The §1 parse, ANSI and regex timings ran in plain Node 22.23.2 (`jp.mjs`), not in Electron. The `v8.serialize`/`structuredClone` row, the `worker_threads`/`utilityProcess` rows and everything in §§2–5 ran inside Electron 45.5.0 (Node 24.22.3). [verified locally]

### 1. Main-process blocking

The main process runs the window event loop. Electron's guidance is "Under no circumstances should you block this process and the UI thread with long-running operations", and it advises against sync IPC [1]. Measured costs of the work this app does on main:

| Work on main | Measured (M4, plain Node 22.23.2 unless noted; under load, noisy upper bound) | Verdict |
|---|---|---|
| `JSON.parse`, 69 KB (300 cards) | 0.13 ms | Fine on main |
| `JSON.parse`, 700 KB | 1.2 ms | Fine on main |
| `JSON.parse`, 7 MB | 12.6 ms | Close to a frame. Avoid on main if it recurs, and never per event |
| NDJSON split + `JSON.parse`, 2,000 events | 0.67 ms | Fine: a 2k/s stream costs ≈ 0.07% of one core |
| ANSI strip (linear regex), 2,000 lines | 0.17 ms | Fine |
| `v8.serialize` / `structuredClone` of 300 cards (Electron 45 main, Node 24.22.3) | 0.14 / 0.31 ms | Fine |
| Catastrophic regex `/^(a+)+$/` on 28 chars | **4,027 ms** | The real hazard: one bad regex on a log line freezes every window |
| `spawnSync('gh', …)` (network) | ≈ 520–630 ms (02 §7) | **Never on main.** Use async `spawn` |

Rules that follow [inferred from the table]:

- **Never on main:** `execSync`/`spawnSync`/`execFileSync`, `fs.*Sync` inside IPC handlers or timers, `ipcRenderer.sendSync`, and any regex with nested quantifiers applied to untrusted text (log lines, Issue bodies). Small `readFileSync` before the first window exists (config, under ≈ 100 KB) is harmless.
- **Allowed on main:** async `spawn` with streamed stdout, `fs.promises`, `fs.watch`, and parsing of NDJSON events and JSON files up to a few MB.
- **Lint for it:** forbid `*Sync` imports in `src/main/**` except in a bootstrap file. Rule wiring belongs to 06.

**`utilityProcess` and `worker_threads`: what an extra process costs.**

| Option | Measured cost | Buys | Use when |
|---|---|---|---|
| Stay on main (async) | 0 | Simplest. All Electron APIs available | Default for v1: every measured task is ≤ 1 ms |
| `worker_threads` in main | +9.3 MB RSS in main (under load; noisy) | CPU isolation for pure JS (big JSON, diffing). No Electron APIs inside | A single CPU-bound job over ≈ 16 ms is found in a trace |
| `utilityProcess.fork` | **+56 MB working set** (the Node Utility Process row; under load and memory pressure, noisy in an unknown direction); spawn to first message ≈ 40 ms (Linux x64 release build, n = 40) after Electron's Aug 2026 snapshot work [3] | Crash isolation, its own event loop, `MessagePortMain` to a renderer [2] | A source adapter crashes or blocks main in practice, or Windows WSL stream handling turns out to be heavy |

The `utilityProcess` docs make no performance claims [2]. The 56 MB figure is a macOS working-set number, which overstates the private memory. **Verdict: no utility process in the spike.** The cost is ≈ 56 MB of idle RAM, which flip condition 3 counts, plus a second message hop. There is nothing to offload. Keep the escape hatch open: each source (`gh` poller, `runs watch` stream, log tailer) should be an object that takes commands and emits messages, with no Electron imports. It can then run in a `utilityProcess` unchanged (layering in 02). [verified locally + inferred]

### 2. IPC cost

Electron serialises IPC payloads with the structured clone algorithm (01 has the semantics). Measured on Electron 45.5.0, main → sandboxed renderer through a `contextBridge` callback, timed from the first send to the renderer's ack. **(Under load; noisy upper bound.** The ≈ 10× batched-vs-single ratio is the finding. Single vs `MessagePort` differ by < 2×, which is within noise.)

| Pattern | Total time | Per line |
|---|---|---|
| 2,000 log lines, one `send` each | 3.7 ms | 1.9 µs |
| 2,000 lines in 60 batches of 34 (one batch per frame at 2k/s) | 0.34 ms | 0.17 µs |
| 10,000 lines, one `send` each | 17.9 ms | 1.8 µs |
| 10,000 lines in batches of 500 | 1.3 ms | 0.13 µs |
| `MessagePort`, 2,000 single | 4.9 ms | 2.5 µs |
| `MessagePort`, 60 batches | 0.48 ms | — |
| `MessagePort`, 10,000 single | 24.5 ms | 2.4 µs |
| `invoke` round trip, tiny payload | p50 < 0.1 ms, p95 0.1 ms | — |
| `invoke` returning 300 cards (110 KB v8-serialized, 123 KB JSON) | p50 0.8 ms, p95 1.0 ms | — |

What this means for the architecture [inferred from the table]:

- **Batch log lines in main, per stream.** Use a time window (≈ 16–50 ms) or a line count (≈ 500), whichever comes first, and send `string[]`. Batching is ≈ 10× cheaper in transport. More importantly, it turns 2,000 renderer callbacks per second, each of which could touch the store, into 20–60.
- **Board updates: 03's `patch` (`upsert`/`remove`) is fine as specified [22].** Run events arrive at a few per second at most (Issue #1: phase changes and heartbeats). 03's 100 ms coalescing is harmless but not needed for performance: it would save nothing measurable at this rate. [inferred]
- **Never re-send the whole state per event.** A 300-card snapshot costs ≈ 1 ms, which is cheap once at load and on reconnect, and wasteful on every heartbeat. The pattern is `snapshot` once, then `patch`es (03), which matches the harness stream (Issue #1).
- **Keep steady-state messages under ≈ 1 MB.** No measurement here shows a cliff, but serialisation is linear in size, and a 7 MB parse already costs ≈ 13 ms (§1). One exemption: 03's log `reset` on subscribe carries up to 10k lines (≈ 1.2 MB at 120 chars). Extrapolating linearly from the 110 KB `invoke` (0.8 ms), it costs ≈ 10 ms once per subscribe or show [inferred]. Send it whole; chunk it into 500-line pieces only if the spike measures it over a frame. The renderer never ships its ring back.
- **CPU of unbatched IPC.** The table is wall time from first send to ack, not CPU time across main, renderer and the IPC thread. At 2k lines/s it is ≈ 4 ms of wall time per second, ≈ 2–5% on a 3–5× slower machine [inferred]. Batching removes it either way.
- **`MessagePort` gives no speed-up.** Use it where a stream needs its own close semantics (03, 01).

**No primary or credible secondary benchmark of Electron IPC from 2025–2026 was found.** The table above is the only current data. The Electron performance doc gives no numbers [1].

### 3. Renderer

#### 3.1 Board: 300 cards

Measured in Electron 45.5.0 with React 19.3.1 production builds. Each card has ≈ 12 DOM nodes (title, status, phase, unit, branch, three labels, a timestamp). The time covers render, commit and forced layout via `flushSync` plus `offsetHeight`; paint is not included. **(Under load; noisy upper bound.** The B-vs-A ratio is ≈ 2×, near the noise band. Variant B is recommended on design grounds, one update re-rendering one card, more than on this measurement.)

| Variant | Mount | DOM nodes | One-card update p50 / p95 |
|---|---|---|---|
| A: the whole `Map` selected at the top, cards not memoised (every update re-renders 300 cards) | 35 ms (includes JIT warm-up, as it ran first) | 3,604 | 0.7 / 1.6 ms |
| B: ids selected at the top; each `memo` card subscribes to its own record through `useSyncExternalStore` | 8.4 ms | 3,604 | **0.3 / 0.7 ms** |

- **No virtualisation for the board** (confirms startup 02 §6 [19]). 3.6k nodes mount in under 40 ms and update in about 1 ms even when written naively. Virtualising three independent columns would add scroll-sync complexity and hide off-screen cards from accessibility tools and Playwright locators, for no visible gain. (Electron has no built-in find bar; a future `webContents.findInPage()` would only search mounted cards.) Revisit above ≈ 2,000 cards. [verified locally + inferred]
- **Not measured: column moves.** The update changed `phase` and `updated`, never `status`, so moving a card between columns is untested. Day 1 adds that case.
- **Still build variant B.** It costs one `memo` and a per-id selector. In return, one `patch` upsert re-renders one card, which keeps the board flat on slow hardware (§0). **Constraint for 03:** the store must be normalised by id and must support a per-id subscription that returns a stable reference for unchanged records. Structural sharing is needed: replacing every record on every snapshot defeats `memo`. The column lists must change identity only when membership or order changes, not when a card's fields change.
- **Keys:** use the run or Issue id, never the array index. With index keys, a card moving between columns re-mounts both columns' tails. [inferred]
- **React Compiler 1.0** (stable since 2025-10-07 [4]) would memoise automatically. With Vite 8, `@vitejs/plugin-react` 6.x dropped Babel, so the compiler needs `@rolldown/plugin-babel` as an extra build step [5][secondary]. **Skip it for the spike.** The hand-written `memo` on `Card` gives the same benefit at this size. Reconsider when the component count grows.
- **CSS containment:** `contain: content` on `.card` is free and limits layout invalidation to the card. `content-visibility: auto` on columns would skip off-screen rendering, but it changes scrollbar sizing and is unnecessary at 300. [inferred]

#### 3.2 Log tail: 10k-line ring, 2k lines/s

Measured: steady state with the ring prefilled to 10k lines, a producer at 2,000 lines/s, one rAF flush per frame, 5 s per variant. "Work" is ingest + render + forced layout per frame. The display ran at ≈ 75 fps. Rows were plain strings, not the ANSI `spans[]` rows the spike will render, so the per-row cost is understated. **(Under load; noisy upper bound.** The ≈ 60× gap between the naive and virtual variants is far outside any load noise. It confirms startup 02 §6 [19].)

| Variant | fps | Work per frame p50 / p95 | Frames > 33 ms | DOM nodes |
|---|---|---|---|---|
| React, all 10k rows rendered (index keys) | **26** | **36 / 41 ms** | 113 | 10,001 |
| Imperative DOM: append text nodes, trim the oldest beyond 10k, no React | 75 | 3.0 / 3.7 ms | 1 | 10,001 |
| **React + TanStack Virtual**, fixed 16 px rows, pinned to the bottom | 75 | **0.6 / 1.2 ms** | 0 | ≈ 50 |

- **Virtualise the log.** Use fixed-height, non-wrapping rows: wrapping needs measured rows, which costs more and adds scroll jumps. Variable heights are an option for later.
- **Library:** both candidates are maintained. **TanStack Virtual** 3.14.28 was released 2026-11-22; its hook measured 11 KB min+gz (React external). **react-window** 2.5.4 was released 2026-11-21; it was rewritten as v2 in 2025-08, and the `List` component measured 6.5 KB [6][verified: npm, GitHub]. Both let us render our own row component, so CSP and Trusted Types do not discriminate. Choose TanStack Virtual because it is the variant measured here (0.6 ms per frame), and its hook exposes `scrollToIndex`, `getTotalSize` and the scroll element directly, which fits a bottom-pinned list with a "follow" toggle. The 4.5 KB difference is irrelevant (§6). react-window would also do. [verified locally + inferred]
- **Keys:** key rows by an absolute, monotonically increasing line number (`seq`) stored with each ring entry, not by ring position. This is for correctness: stable text selection and scroll anchoring while lines stream in. The benchmark did not isolate keys (both variants used position keys; the naive one was slow because React reconciled 10k elements per frame). [inferred]
- **DOM text, not canvas.** xterm.js 6.0.0 (min+gz 87 KB measured) or a hand-rolled canvas would give terminal-grade throughput. But it loses native selection, browser-mode find, screen-reader access and the simple "text nodes through the closed-palette ANSI parser" rule (10 §6). The virtualised DOM list already uses ≈ 1 ms per frame. [verified locally + inferred]
- **Parse ANSI once at ingest,** into `{seq, spans[]}`, never in render (02 §6 says the same). The measured cost is 0.17 ms per 2,000 lines.
- **Containment:** `contain: strict` on the scroll container, which has a fixed size, so appends never invalidate layout outside it. This was used in the measured variants.

#### 3.3 rAF batching and the hidden window: constraints for 03

```
IPC batch ──► ring.push(lines)   // immediately: O(1), bounded at 10k
                 └─► scheduleRender()  // sets a dirty flag; one rAF per frame at most
rAF ──► if dirty: notify subscribers → the virtual list re-reads ring.length / seq
```

- Ingesting on arrival keeps memory bounded while hidden. rAF does not run in a hidden window (measured: 0 callbacks in 10 s), so "queue in an array, flush in rAF" grows without bound until the window is shown, and then delivers one huge frame. [verified locally]
- The ring is a mutable structure with a version counter. React reads it through `useSyncExternalStore(subscribe, () => ring.seq)`. It is not an immutable array copied per batch: copying 10k entries 60 times a second is the kind of cost the naive variant paid. **Constraint for 03.**

### 4. Idle CPU and the hidden window

Measured over 10 s per case, with a page running a 16 ms `setInterval` and a rAF loop. **(Under load; noisy upper bound.** The CPU % values are not the spike's ≈ 0% target measurement. The timer and rAF counts, 625 → 11 and 749 → 0, are a throttling behaviour, not a load effect.)

| Window state | `backgroundThrottling` | `visibilityState` | 16 ms timer fires | rAF fires | Renderer CPU | Renderer wake-ups/s | All processes CPU |
|---|---|---|---|---|---|---|---|
| Shown | true (default) | visible | 625 | 749 | 0.25% | 83 | 0.59% |
| `hide()` after show | **true** | hidden | **11** | **0** | **0%** | 2 | 0.15% |
| `hide()` after show | false | **visible** (!) | 625 | 750 | 0.23% | 79 | 0.62% |

- **Keep `backgroundThrottling: true`.** With it off, Electron reports the page as visible even when it is hidden [7], so `visibilitychange`-based pausing silently stops working. [verified: docs + locally]
- Chromium throttles hidden-page timers to once per second at first, and to once per minute after 5 minutes hidden for chained timers [8] (Chrome 88 post, Jan 2021: older than 12 months, but the behaviour matches the measurement above). The renderer therefore idles by itself. **The main process does not.** Node timers in main are not throttled. [inferred: Chromium's throttling applies to Blink pages]
- **Pausing policy, owned by main (proposed for 07; aligned with 03 §6's cadence table [22]).** One scheduler module holds every timer and reads one "activity state" with three levels. The intervals are 03's; 04 only fixes which signals switch levels [inferred; event names verified in docs 7, 9]:

| Activity state | Signals | `gh` polling | Streams and logs |
|---|---|---|---|
| **Visible** (focused or not) | `show`, `restore`, `focus`, `blur`; renderer `visibilitychange` → visible | 03's focused cadence (20–60 s; PRs 5 min). On entering: refresh at once if the data is older than that interval | Forward everything |
| **Hidden** (hidden, minimised, or fully occluded on macOS) | `hide`, `minimize`; renderer `visibilitychange` → hidden, reported through 03's `studio.app.setVisible` intent | 03's hidden cadence: ≈ 5 min for Issues and Actions runs, PRs off | Keep the `runs watch` stream (event-driven, idle) and main's rings. Stop forwarding log lines; on show, main sends a `reset` from its ring (03 protocol) |
| **Suspended** | `powerMonitor` `suspend`, `lock-screen` | Stopped | Stopped. On `resume`/`unlock-screen`, reconnect the streams and expect a fresh `snapshot` (Issue #4 Day 4), then go to Visible or Hidden |

  Why slow rather than stop when hidden: two conditional `gh api` calls every 5 min are a handful of `gh` spawns per 10 minutes, well inside the < 0.5% average of the §8 pass criterion [inferred], and the board is never more than 5 min stale when shown or when a later notification or menu-bar view reads it. Why no separate "blurred" tier: a visible window is being looked at, and 03 has none. On battery (`powerMonitor` `on-battery`, macOS and Windows) doubling the intervals is optional.

  On Wayland, `minimize` fires only for client-side decorations [7], and macOS occlusion fires no main-side event, so the renderer's `visibilitychange` (through the intent verb) is the signal main must trust; the window events are a fast path.
- **No running animations.** A spinning badge on every In Progress card keeps the compositor waking up while the window is visible (02 §5). Use a static badge, or a CSS animation under `@media (prefers-reduced-motion: no-preference)` that stops when the window is hidden. Chromium stops it there anyway, because rAF and compositor frames stop. [inferred]
- The ≈ 0%-over-10-minutes target is then mostly a test of main's discipline: only the 5-min poll, no other timers, no `fs.watch` storms. Main is where to measure it (§8).

### 5. Startup

| Choice | Effect on time to a populated board (target ≤ 1.5 s) | Verdict |
|---|---|---|
| Plain `tsc` (today: `package.json` `build`) | Main loads as many CommonJS files, and every `require` costs, especially on Windows [1]. The renderer cannot import bare `react` from `file://` without a bundler | Replace. React forces a bundler on the renderer anyway |
| **Vite 8 (renderer) + esbuild 0.28.2 (main, preload)**, per 06 | One bundled CJS file each for main and preload, a bundled renderer. Bundled output per the Electron docs [1] | **Per 06** (07 makes the final pick). 06's reasons are maintenance (electron-vite has one maintainer: 354 commits against 2 for the next contributor [10]) and browser mode, which needs a plain Vite config anyway [21] |
| electron-vite 6.0.0 (2026-10-14, Vite 6–8) [10] | Same runtime result: one config bundles main, preload and renderer, with renderer HMR | Fallback (06: if its `scripts/dev.mjs` grows past ≈ 100 lines). **Performance does not discriminate:** builds are seconds and the output is equivalent either way |
| Code splitting / lazy `import()` | Loading from a local `app://` or `file://` asar costs ≈ no network. Lazy-loading markdown-it + DOMPurify (≈ 53 KB gz) behind the detail screen saves a few ms of parse | Optional. Do it only for the detail-screen chunk |
| V8 code cache, renderer | Chromium caches compiled scripts by default (`v8CacheOptions: "code"`) [11] | Nothing to do |
| V8 code cache, main | `module.enableCompileCache()` loads in Electron 45 main and wrote a cache tagged `v24.22.3-arm64`. One run: `require('typescript')` (8.7 MB) 62 ms cold → 16 ms on the second launch. Caveats: no "off, second launch" baseline, so OS file-cache warming under heavy disk load is a confound; untested for a main bundle inside an asar; no Electron doc or issue mentions the API. A bundled main of < 1 MB gains ≈ 1–5 ms [inferred] | Skip for v1. It needs a writable cache directory under `userData`. Revisit if main grows [verified locally, single run] |
| Custom V8 snapshot (`loadBrowserProcessSpecificV8Snapshot` fuse, electron-mksnapshot) | Electron's browser process already boots from an embedded Node snapshot. Since Aug 2026 (shipped in v42.10.0, v43.5.0 and v44.0.0) the other Node-hosting processes do too: `utilityProcess.fork()` to first message 86 → 40 ms on a Linux x64 release build [3]. A custom app snapshot adds build complexity and an extra fuse | **Not worth it.** `electron_xcache` (v44+) is "intentionally left undocumented" [12] |
| `ready-to-show` + `show: false` | Already in `src/main/main.ts:9,22` | Keep. Note that `show: false` starts with `visibilityState: "visible"` [7] |
| `Menu.setApplicationMenu(null)` [1] | Saves default-menu setup | **Not on macOS:** the default menu provides Cmd+C/V/Q. Consider it on Linux/Windows only |
| **Start `gh` in main at `ready`, in parallel with window creation** | `gh` costs ≈ 0.6 s per call (02 §4) and dominates. Waiting for the renderer to mount and ask first adds ≈ window + bundle time (≈ 100–300 ms [inferred]) in series | **Do it.** Main caches the in-flight snapshot promise, and the renderer's first `getBoard()` awaits it |

### 6. Bundle and installer size of library picks

Measured with esbuild 0.28.2: `--minify`, ESM, production `NODE_ENV`, `gzip -9`. For the React bindings (TanStack Virtual, react-window, zustand, RTK + react-redux, react-query), `--external:react --external:react-dom --external:'react/*' --external:'react-dom/*'`, and the outputs were checked to import `react` rather than contain it (a first run had bundled React into every binding and overstated them by 3–9 KB gz). Release dates from the npm registry [6]. (Byte sizes are deterministic, so the background load does not affect them.)

| Package (version, release date) | min | min+gz | Unpacked in `node_modules` | Note |
|---|---|---|---|---|
| react + react-dom/client 19.3.1 (2026-10) | 223 KB | 69 KB | react-dom 8.1 MB | Baseline |
| markdown-it 15.0.3 (2026-10-16) | 100 KB | 41 KB | 2.1 MB | The heaviest of the required libraries. Lazy-load on the detail screen |
| dompurify 3.5.0 (2026-11-22) | 32 KB | 12.5 KB | 1.6 MB | Required (10 §6) |
| @tanstack/react-virtual 3.14.28 (2026-11-22) | 37 KB | 11 KB | 65 KB | Includes `@tanstack/virtual-core` |
| react-window 2.5.4 (2026-11-21) | 18 KB | 6.5 KB | 439 KB | |
| rxjs 7.8.2 (**2025-02-22**, >12 months; `next` = 9.0.0-beta.1) | 66 KB (everything) / 28 KB (13 typical operators) | 18.6 / 8.6 KB | 4.5 MB | Size does not decide it. 03 decides on merit. Note the stale stable line |
| zustand 5.1.0 (2026-11-06) | 0.6 KB | 0.4 KB | 112 KB | Matches 03's ≈ 0.5 kB |
| @reduxjs/toolkit 2.15.0 + react-redux 9.3.1 | 24 KB | 9.5 KB | 7.1 MB (RTK) | |
| @tanstack/react-query 5.108.4 | 33 KB | 10 KB | — | |
| @xterm/xterm 6.0.0 | 344 KB | 87 KB | 5.9 MB | Not recommended (§3.2) |

- **Effect on the installer: under 0.5% whatever the pick.** Every candidate together is < 1 MB minified, against Electron's ≈ 90–130 MB compressed (02). [verified locally + 02]
- **The trap is unbundled `node_modules`.** electron-builder packs production `dependencies` into the asar and leaves `devDependencies` out [13][secondary: electron-vite docs]. If React, RTK and RxJS sat in `dependencies` unbundled, ≈ 20 MB of unpacked sources would ship. **Rule:** with a bundler, every renderer and main library goes in `devDependencies`, and `dependencies` stays empty unless a native module or a runtime-required file forces it. [inferred]
- Renderer parse time scales with the min size, so lazy-loading markdown-it is the only split worth doing (§5).

### 7. Memory

| Item | Size | Bound |
|---|---|---|
| Renderer log ring, 10k lines × ≈ 120 chars (UTF-16, plus span objects) | ≈ 3–5 MB per run [inferred] | One ring per open log. Keep at most N (for example 3) rings for recently viewed runs, LRU, and drop the rest |
| Main log rings (03 keeps a per-run `LogRing` in main too) | ≈ 3–5 MB per watched run [inferred] | One per run with a live log source. Drop a ring when its run finishes and no renderer subscribes, and cap the total (for example 10 rings, LRU), so a busy repo cannot grow main by 50+ MB |
| Board state, 300 cards | ≈ 0.1–0.3 MB | Fine |
| Measured idle baseline, a near-empty page | Working set: Browser 145 MB, GPU 56 MB, Network service 37 MB, renderer 72 MB (≈ 310 MB sum). **Under load and memory pressure; noisy in an unknown direction, not a baseline** | macOS working set double-counts shared pages. 02 measured GitHub Desktop at 170–210 MB RSS. Day 2 records the real app (§8) |

**Leak patterns this architecture must design out** [inferred; listener behaviour is standard Node `EventEmitter`]:

1. **Preload `on*` verbs without an unsubscribe.** Each `ipcRenderer.on` adds a listener. React StrictMode mounts effects twice in dev, and HMR and `location.reload()` re-run effects. Rule: every subscription verb returns `() => void`, which calls `ipcRenderer.removeListener` with the same wrapper function. Detection: in dev, warn if `ipcRenderer.listenerCount(channel)` exceeds the expected count.
2. **Main-side streams outliving the renderer.** If the renderer subscribes to a log tail and then reloads, main keeps the tailer and keeps sending to a page that no longer listens. Rule: main keys every subscription by `webContents.id`, and on `did-start-navigation` (main frame), `render-process-gone` and `destroyed` it disposes all of them, killing child processes it started for them. Here the store design (03) and the process model (01) meet.
3. **Unbounded collections.** "Pending lines" arrays (§3.3), per-run event histories, and `Map`s of seen ids that are never pruned. Every collection fed by a stream needs a cap.
4. **Child processes.** A `gh` call that hangs (network) keeps a process and its buffers alive. Give each spawn a timeout and an `AbortSignal`, and kill the process group on dispose (02 §7 of the startup research covers the cost; Day 4 tests for orphans).

### 8. How to measure in the spike

| Question | Tool | Where |
|---|---|---|
| CPU and memory of every process over time (idle RSS, ≈ 0% CPU hidden) | `app.getAppMetrics()`: per-process `cpu.percentCPUUsage`, `idleWakeupsPerSecond`, `memory.workingSetSize` [14] | Main |
| Per-process private memory and heap | `process.getProcessMemoryInfo()` (async, KB; on macOS use `private`, as `residentSet` is absent), `getHeapStatistics()`, `getBlinkMemoryInfo()`. Available in sandboxed renderers [15] | Main and renderer |
| Where main or the renderer spends a slow second | `contentTracing.startRecording` / `stopRecording` → Perfetto trace, opened at ui.perfetto.dev [16] | Main, behind a dev flag |
| Renderer frames, long tasks, React commits | Chrome DevTools Performance panel; React DevTools Profiler | Dev build |
| Time to a populated board, repeatable | `performance.mark` in the renderer plus a main-side t0. Playwright `_electron.launch` reads the result (06 owns the test) | Test build |
| Log tail at 1–2k lines/s on the Linux VMs | A fixture producer (a child that prints N lines/s) plus the frame counter below | Day 3 |
| Installer size, unpacked size | `ls -l dist/*.zip *.AppImage *.deb`; `du -sh` of the `.app` | Day 2/3 |
| macOS physical footprint, which matches Activity Monitor | `footprint <pid>` or `vmmap --summary <pid>` | Day 2, for the record |

**A small harness (≈ 60 lines, dev and test builds only, enabled by `STUDIO_PERF=1`):**

```ts
// src/main/perf/sampler.ts — writes a JSONL line every 10 s to userData/perf.jsonl
const t0 = performance.timeOrigin;              // first line of main.ts
setInterval(() => {
  const m = app.getAppMetrics();
  append({ t: Date.now(), hidden: !win.isVisible(),
    cpu: m.map(p => [p.type, p.cpu.percentCPUUsage, p.cpu.idleWakeupsPerSecond]),
    ws:  m.map(p => [p.type, p.memory.workingSetSize]) });
}, 10_000).unref();
ipcMain.on('perf:mark', (_e, name) => append({ mark: name, ms: performance.now() })); // 'board-populated'
```

```ts
// renderer: after the first non-empty snapshot is committed
useEffect(() => { if (cards.length) requestAnimationFrame(() => perf.mark('board-populated')); }, [cards.length > 0]);
// log tail: count frames over 33 ms while the producer runs; expose window.__perf for Playwright
```

Spike procedure [inferred]:

- **Board ≤ 1.5 s:** launch the packaged app 10 times. Take the median of `board-populated − t0`, with live `gh` and a warm file cache. Report the `gh` share separately (time the main-side fetch).
- **Hidden ≈ 0% CPU:** show the window, wait 30 s, `hide()`, sample for 10 minutes. Pass if the sum over all processes averages < 0.5% and nothing main-side wakes more often than the poll policy allows (§4).
- **Idle RSS:** 10 minutes after launch, with the board shown. Record the working-set sum and the `footprint` total.
- **Log tail:** at 2k lines/s for 60 s, record frames over 33 ms and the p95 work per frame. Target: no long frames on the M4, and a recorded value on the VMs.

The micro-benchmark numbers in §§1–4 come from throwaway scripts, not from this harness. They should be re-checked on the real code, not trusted as targets.

## Recommendation for the spike

**Day 1 (renderer, browser mode)**
1. Bundle per 06 (Vite for the renderer, esbuild for main and preload; electron-vite is the fallback, 07 picks). Keep `dependencies` empty.
2. Store (whatever 03 picks): normalised by id, with per-id subscriptions, structural sharing, and column id lists that keep their identity across field-only updates. Use `memo(Card)` keyed by id. No board virtualisation. `contain: content` on cards.
3. Log tail: a ring of 10k `{seq, spans}` entries, ANSI parsed at ingest (03 also keeps one per run in main; cap both, §7). Ingest immediately and render at most once per rAF through a version counter. TanStack Virtual with fixed 16 px rows, keyed by `seq`, bottom-pinned with "follow" mode, and `contain: strict` on the container.
4. Fixture IPC in browser mode mimics main's batching (03's `reset` then `append` batches of `string[]`, `snapshot` then `patch`), so the renderer is exercised the same way in both modes.
5. Add a board case that moves a card between columns (status change), and check that only the two affected column lists change identity (§3.1).
6. Lazy-load markdown-it and DOMPurify with the detail screen.
7. Add the frame counter and `perf.mark` hooks (§8) from the start, so Playwright can assert on them.

**Day 2 (main and shell)**
1. Main runs no sync I/O after bootstrap. Async `spawn` only, each with a timeout and an `AbortSignal`. No nested-quantifier regexes on log or Issue text.
2. Log batching in main: flush every 16–50 ms or every 500 lines, whichever comes first.
3. One scheduler module owns every timer and follows the §4 activity policy: Visible → 03's focused cadence, Hidden (window events or the renderer's `setVisible`) → ≈ 5 min, Suspended (`powerMonitor`) → stopped. On show, refresh if stale and send a log `reset` from main's ring. Keep `backgroundThrottling` at its default.
4. Subscription registry keyed by `webContents.id`, disposed on navigation, reload, `render-process-gone` and `destroyed`. Every preload `on*` verb returns an unsubscribe.
5. Kick off the `gh` board fetch at `app` `ready`, in parallel with window creation. The renderer awaits the cached promise.
6. No `utilityProcess` and no custom snapshot. The sampler harness goes behind `STUDIO_PERF=1`, and the four Issue #4 measurements are recorded with it.

## Answers to the owner's questions

**Q5 (performance part). What does each architectural choice cost?**

| Choice | Perf cost | Perf benefit for this app |
|---|---|---|
| Logic in main, not a `utilityProcess` | Risk of blocking main if a sync call or a bad regex slips in | Saves ≈ 56 MB and a hop. Every measured task is ≤ 1 ms |
| Intent IPC with batched log arrays | One timer per stream in main | ≈ 10× less transport, and 20–60 instead of 2,000 renderer callbacks per second |
| Normalised store + per-card selectors | One `memo`, one selector | One `patch` upsert re-renders one card: 0.3 ms against 0.7 ms on a loaded M4 (≈ 2×, near noise; the design benefit is the point) |
| Virtualised log, DOM text | One small library (11 KB gz) | 0.6 ms against 36 ms per frame at 2k lines/s (under load; the ≈ 60× ratio is robust) |
| Bounded ring, ingest-then-rAF | A mutable ring with a version counter instead of an immutable array | Bounded memory while hidden, with no burst on show |
| Main-owned activity policy | One scheduler module, and a 5-min poll while hidden | ≈ 0% CPU hidden. The renderer is throttled by Chromium, main is not |
| Bundling (Vite + esbuild, per 06) | A build tool and ≈ 80 lines of scripts (06) | Single-file main per the Electron docs, and no `node_modules` in the asar |
| Library picks (RxJS, state library, markdown-it, DOMPurify) | ≤ 41 KB gz each | Installer effect < 0.5%. Choose on merit (03, 05) |

**Q4 (performance angle).** Electron supplies the transport (structured-clone IPC, `MessagePort`) and Chromium's hidden-page throttling. We add batching in main, a bounded ring with rAF-scheduled rendering, per-id subscriptions, and a main-side pause policy. The rest is 03.

## Risks and open questions

- **No local number is a target.** All local numbers were taken under a concurrent DevScene Gates run (§0). Only same-run ratios support the conclusions; the spike re-measures every absolute value on an idle machine.
- **M4 numbers flatter everything.** The Linux VMs (virtual GPU) and older Intel Macs may show long frames where the M4 shows none. Day 3 must record the frame metrics on the 24.04 VM, not assume them.
- **Bottom-pinned virtual lists can jitter** when the user scrolls up while lines stream in. A "follow" toggle, which pauses auto-scroll when the user scrolls up, is a UX need as much as a perf one. It is not measured here.
- **Wrapping log lines** (long stack traces) would need measured row heights, which costs more per frame. The cost is unmeasured. Keep `white-space: pre` with horizontal scroll for v1.
- **macOS occlusion** marks a fully covered window as hidden, renderer side [7]. Main sees no `hide` event for that case. The §4 policy treats it as Hidden, via the renderer's `setVisible` intent (03).
- **Open items for 07 (cross-file).** (a) Hidden-window polling: 04 now proposes 03's 5-min hidden cadence with a three-level activity state (§4), replacing its earlier "stop when hidden"; 07 confirms one policy. (b) Build tool: 04 defers to 06 (Vite + esbuild, electron-vite fallback); performance does not discriminate. (c) 03's log `reset` on subscribe (up to 10k lines, ≈ 1.2 MB) exceeds 04's ≈ 1 MB message guideline; 04 exempts it as a one-off (≈ 10 ms, inferred), to be chunked only if measured over a frame. (d) Main-side `LogRing`s (03) need a cap and a drop rule (§7); 03 does not state one. (e) 03's "stop forwarding logs while hidden, `reset` on show" is 04's proposal; 03 does not yet say it. 03 was being revised during this fix, so re-check (a)–(e) against its final text.
- **The `utilityProcess` RSS (≈ 56 MB) is a macOS working-set figure.** Its private footprint is lower. Measure with `footprint` before ruling one out for Windows WSL streaming (item 4).
- **No current third-party Electron IPC benchmark exists.** §2 is a single-machine measurement.
- **Source age:** the Chromium throttling post (2021) is older than 12 months, but the local measurement agrees with it. RxJS's latest stable (7.8.2, 2025-02) is older than 12 months.

## Sources

1. https://www.electronjs.org/docs/latest/tutorial/performance — don't block main; avoid sync IPC; bundle into one file; load lazily; `Menu.setApplicationMenu(null)`; no numbers or snapshot advice — accessed 2026-11-25
2. https://www.electronjs.org/docs/latest/api/utility-process — `utilityProcess.fork`, `serviceName`, `parentPort`/`MessagePortMain`, stdin unsupported, no perf claims — accessed 2026-11-25
3. https://releases.electronjs.org/pr/52873 — Node snapshot and code cache for all Node-hosting processes (the browser process already used one; no browser-process timing given); `utilityProcess.fork()` to first message 86.1 → 39.7 ms (Linux x64 release build, n = 40); in v42.10.0, v43.5.0, v44.0.0 (Aug 2026); `LoadBrowserProcessSpecificV8Snapshot` scope — accessed 2026-11-25
4. https://react.dev/blog/2025/10/07/react-compiler-1 — React Compiler 1.0 stable 2025-10-07 (npm `babel-plugin-react-compiler` 1.0.0, 2025-10-07) — accessed 2026-11-25
5. https://recca0120.github.io/en/2026/04/14/react-compiler-vite-v6/ and `npm view @vitejs/plugin-react` (6.3.0, peer deps `@rolldown/plugin-babel`, `babel-plugin-react-compiler`) — the compiler with Vite 8 needs a separate Babel plugin [secondary + npm] — accessed 2026-11-25
6. npm registry (`npm view <pkg> version time`) and GitHub API for react-window, @tanstack/react-virtual, rxjs (dist-tags: latest 7.8.2, next 9.0.0-beta.1), zustand, markdown-it, dompurify, react/react-dom, electron-vite, vite, esbuild, @xterm/xterm; react-window 2.0.0 released 2025-08-28; bvaughn/react-window pushed 2026-11-21, TanStack/virtual pushed 2026-11-24, neither archived — accessed 2026-11-25
7. https://www.electronjs.org/docs/latest/api/browser-window — Page visibility (`backgroundThrottling` false keeps the page "visible"; `show:false` starts "visible"; macOS occlusion counts as hidden), `ready-to-show`, `paintWhenInitiallyHidden`, `hide`/`show`/`minimize`/`blur` events, Wayland `minimize` caveat — accessed 2026-11-25
8. https://developer.chrome.com/blog/timer-throttling-in-chrome-88 — hidden-page timer throttling: 1/s, then 1/min after 5 min for chained timers (Chrome 88, Jan 2021; **older than 12 months**) — accessed 2026-11-25
9. https://www.electronjs.org/docs/latest/api/power-monitor — `suspend`, `resume`, `lock-screen`, `unlock-screen`, `on-battery`/`on-ac` (macOS, Windows), `getSystemIdleState` — accessed 2026-11-25
10. https://github.com/alex8088/electron-vite, `npm view electron-vite` and `gh api repos/alex8088/electron-vite/contributors` — 6.0.0 released 2026-10-14, peer `vite ^6 || ^7 || ^8`; alex8088 354 commits, next contributor 2 (via review) — accessed 2026-11-25
11. https://www.electronjs.org/docs/latest/api/structures/web-preferences — `backgroundThrottling`; `v8CacheOptions` default `code` — accessed 2026-11-25
12. https://releases.electronjs.org/pr/53139 — `electron_xcache` host tool for main-process code caches, in v44.0.0, "intentionally left undocumented" — accessed 2026-11-25
13. https://electron-vite.org/guide/dependency-handling and https://www.electron.build/docs/tutorials/two-package-structure — packagers exclude `devDependencies`; only production dependencies ship [secondary for the electron-builder default] — accessed 2026-11-25
14. https://www.electronjs.org/docs/latest/api/app — `app.getAppMetrics()` → `ProcessMetric` (cpu, memory per process) [used in the local measurement] — accessed 2026-11-25
15. https://www.electronjs.org/docs/latest/api/process — `getProcessMemoryInfo` (async, KB, macOS has no `residentSet`), `getHeapStatistics`, `getBlinkMemoryInfo`, `getCPUUsage`; available in sandboxed renderers — accessed 2026-11-25
16. https://www.electronjs.org/docs/latest/api/content-tracing — `startRecording`/`stopRecording` after `ready`, Perfetto protobuf output, viewed in ui.perfetto.dev — accessed 2026-11-25
17. Own measurements, 2026-11-25, **taken under heavy concurrent load (DevScene Gates phase)**: Apple M4, Darwin 24.6, Electron 45.5.0 (Chrome 156.0.8078.109, Node 24.22.3) from the repo's `node_modules`, React 19.3.1, @tanstack/react-virtual 3.14.28, esbuild 0.28.2 (size bundles re-run with React external during review), plain Node 22.23.2 for the §1 parse and regex timings. Throwaway scripts (IPC send/invoke/`MessagePort`, `utilityProcess` and `worker_threads` memory, board and log render variants, hidden-window throttling, `module.enableCompileCache`, esbuild size bundles). Not committed
18. `src/main/main.ts:9,22` (`show: false`, `ready-to-show`); `package.json` (`build` = `tsc` + asset copy; devDependencies only) — this repo — accessed 2026-11-25
19. `../product-startup-research/02-performance.md` §4, §5, §6, §7 — `gh` latency ≈ 0.6 s, polling and animation guidance, spawn costs, the GitHub Desktop RSS baseline — accessed 2026-11-25
20. GitHub Issue #4 (`gh issue view 4`) — spike targets — accessed 2026-11-25
21. `06-testing-and-tooling.md` TL;DR and build-tool table — Vite 8 + esbuild pick, electron-vite as fallback, browser mode needs a plain Vite config — accessed 2026-11-25
22. `03-reactive-data-flow.md` TL;DR, §5 (per-run `LogRing` in main, `reset`/`append`, 100 ms `patch` coalescing), §6 (poll cadence focused/hidden, `studio.app.setVisible`) — draft under revision on 2026-11-25 — accessed 2026-11-25
