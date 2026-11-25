# Review — 03-reactive-data-flow.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

The facts hold up well. Every library version and date I re-checked against the npm registry today is correct: RxJS 7.8.2 / 8.0.0-alpha.14 / 9.0.0-beta.1, Zustand 5.1.0 (2026-11-06), Jotai 3.0.2, RTK 2.15.0, react-redux 9.3.1, TanStack Query 5.108.4, Preact signals 3.12.0, MobX 7.1.7, React 19.3.1. Zustand's `useStore` is `React.useSyncExternalStore`. TC39 Signals is Stage 1. Electron 45.5.0 is Chromium 156 / Node 24.22.3. The webContents event line numbers are right. The `gh api -i` 304 behaviour (exit 1, `gh: HTTP 304`) reproduces, and a 304 does not move `X-Ratelimit-Used`. `gh issue list` is GraphQL in the gh source. The expause_web citations match the files. The Zustand pick and "no RxJS, no TanStack Query, no RTK" are sound.

The main problem is proportion. Around a correct core (adapter → pure reducer in main → snapshot + upsert/remove → Zustand), the file builds a protocol layer that the brief's "basic, not a framework of our own" rule does not support. It has epoch + gapless seq over in-process IPC, ref-counted subscriptions with a 30 s grace, a 100 ms coalescing publisher, a `seq` demand on the not-yet-existing harness verb, and per-field provenance. Together these overload Day 2. The reconnect sketch on the central path also has a real bug: a silent child is never killed.

## Must fix

**M1 — Reconnect sketch leaks the silent child and dies on a heartbeat timeout** (§5 "Reconnection with a fresh snapshot", code block).
- **Problem.** The child is spawned with the outer `signal`, so nothing kills it when the heartbeat watchdog fires. A hung `wsl.exe`/`runs watch` stays alive while the loop spawns a second one. That is the orphan case 10 §5 Day 4 tests ("pgid kill leaves no orphans"). And if `ndjson(..., { heartbeatTimeoutMs })` signals a timeout by throwing, which is the natural way, the `for await` rejects and the whole adapter exits, because nothing catches it.
- **Evidence.** The sketch itself. 05-harness-integration.md:80 and the Risks bullet ("A long-lived `runs watch` through `wsl.exe` can fail silently").
- **Fix.** Use a per-attempt controller, a try/finally that kills the process group, and a catch:
  ```ts
  for (let attempt = 0; !signal.aborted; attempt++) {
    const run = new AbortController(); const stop = () => run.abort();
    signal.addEventListener('abort', stop, { once: true });
    try {
      const child = transport.spawn(argv, { signal: run.signal });   // kills the pgid on abort (05/01)
      for await (const ev of ndjson(child.stdout, { heartbeatTimeoutMs: 3 * HB, signal: run.signal })) { attempt = 0; emit(ev); }
    } catch (e) { emit({ kind: 'status', state: 'reconnecting', reason: String(e) }); }
    finally { run.abort(); signal.removeEventListener('abort', stop); }
    await sleep(backoff(attempt), signal);
  }
  ```

**M2 — The live protocol and lifecycle are over-engineered for this app and the spike** (TL;DR bullets 5–6; §4 Publisher row; §5 Ordering 1–2, lifecycle table, coalescing table; Recommendation Day 2 items 5–9).

The app is small: one window, one active repo, about 300 cards, run updates at human rates. The `runs watch` verb does not exist yet (10 §5: "the harness verb does not exist yet"; F-1 is unscheduled). The brief asks for "layers and placement rules, not a framework of our own". Measured against that:
- **`epoch` + gapless `seq` main→renderer.** Electron IPC to one webContents is ordered and does not drop messages. The file admits a gap "almost never happens on local IPC". The two real cases, a renderer reload and a source restart, are already covered by "every subscribe starts with a snapshot" and "a source restart re-sends a snapshot". Rule: *any `snapshot` replaces the mirror*. Epoch and seq add a resync path in the renderer (`useBoardLive` hand-waves "and resubscribe" from inside the callback) that is hard to test and never fires.
- **Asking the harness for per-event `seq`** (Ordering 2, Risk 1). Lines from one pipe cannot be lost or reordered. The file's own mitigation, whole-object `run_updated`, already heals any lost event. That leaves an unneeded contract demand on F-1. Keep `ts` (useful for the gh-vs-watch `updated_at` comparison) and drop `seq`.
- **Ref-counted `shared()` + 30 s grace.** The board subscribes once at the root, and v1 has one window. Ref-counting only pays off for the "detail pop-out later" multi-window case, which is not v1. The grace timer guesses at a respawn cost nobody has measured yet (Risk 4 says so). For the spike: one subscription per `(webContents, topic)`, and stop the old repo's sources on a repo switch. Add the grace only if Day 4 measures a costly WSL respawn. Spike check 9's "Two windows → one `runs watch` child" tests a non-v1 feature. Drop it.
- **100 ms patch coalescing + a diffing publisher.** At human event rates, forwarding each normalised `run_updated` as a one-entity upsert costs nothing and needs no timer or diff step. Keep batching for logs only, where 10 §5 asks for it.
- **The heartbeat watchdog is justified.** WSL silent-failure risk (05 Risks), and it is cheap. Keep it, with M1's fix.
- **Day 2 load.** 10 §5 gives Day 2 1.5 days for the main process, the native modal, fuses, packaging and the updater. Items 5–9 add four utilities with fake-timer tests, two adapters, a read-model with merge and a precedence table, a publisher and a LiveHub. That does not fit.

**Fix.** Rewrite TL;DR bullets 5–6, Ordering 1–2, and Day 2 as a minimal core:
1. The WatchAdapter (with M1's fix) and a single GhPollAdapter for open issues.
2. Pure `reduce` in main.
3. Snapshot on subscribe and on source restart, then one-entity `upsert`/`remove`.
4. Subscriptions keyed by `webContents.id`, dropped on reload/destroyed.
5. Log ring + batch.

Move epoch/seq, ref-count + grace, coalescing, multi-window and full `mergeRun` precedence to a "Later, add when …" table, each with its trigger. Also correct the "about 300 lines" estimate (see S3).

## Should fix

**S1 — The REST `/issues` endpoint also returns pull requests, and paginates** (§6 table row "Open issues").
- **Problem.** `GET /repos/{o}/{r}/issues` lists PRs as issues, with a `pull_request` key, and returns 30 items per page by default. Used as written, the To Do column fills with PRs and silently truncates.
- **Evidence.** https://docs.github.com/en/rest/issues/issues#list-repository-issues ("GitHub's REST API considers every pull request an issue").
- **Fix.** Add: "Filter out items carrying `pull_request` in the normaliser. Use `per_page=100`. Only the first page is cheap to poll by ETag, so if a repo has more than 100 open issues, poll page 1 by ETag and refetch all pages only when it changes."

**S2 — The Jotai "can tear" verdict is inferred, not verified** (§3 table, Jotai row).
- **Problem.** The source reading is right: `useAtomValue` → `useAtomValueRaw` uses `useReducer` + `useEffect`, and `useAtomValueRawSync` uses uSES (checked at https://unpkg.com/jotai@3.0.2/dist/react/useAtomValueRaw.js and `useAtomValueRawSync.js`). But "can tear" is a conclusion drawn from that code, not something the source states. Jotai avoids uSES on purpose to keep time slicing, which is a trade-off, not a defect. The tag overstates.
- **Fix.** Tag the "can tear" part **[inferred]**. Lead the verdict with the stronger reason, which is fit: "an atom per entity or one big atom, plus a brand-new major. Its default hook trades guaranteed tear-freedom for time slicing [inferred from source]."

**S3 — "About 300 lines" is tagged [verified] and is low** (TL;DR bullet 1 "[verified, §1]"; Q4 answer).
- **Problem.** §1 verifies the primitives, not the line count. The file's own parts already sum past 300: Subscribable 30 + retry 15 + batch 20 + shared 25 + LogRing ×2 at about 60 each + two reducers + normaliser + publisher + LiveHub + preload demux + two adapters + FixtureLive.
- **Fix.** Tag the count [inferred]. After M2's trim, estimate the minimal core per file, roughly 400–600 lines plus tests.

**S4 — The `gh issue list` GraphQL claim can be upgraded, and the exit-code cause belongs in the text** (§6 bullets 2–3).
- **Problem.** Both claims are verifiable. In gh v2.100.0, `pkg/cmd/issue/list/http.go:91` calls `client.GraphQL(...)`. `pkg/cmd/api/api.go:553–564` turns any status > 299 into `HTTP <code>` plus `SilentError`, i.e. exit 1. So exit 1 is generic and not specific to 304, which is why the status line must be parsed. I also re-ran the check today: the 304 left `X-Ratelimit-Used` unchanged at 96.
- **Fix.** Tag the GraphQL claim [verified] and cite `https://github.com/cli/cli/blob/v2.100.0/pkg/cmd/issue/list/http.go#L91` and `.../pkg/cmd/api/api.go#L553-L564`. Add "exit 1 covers every HTTP ≥ 300, so map only a parsed `304` status line to 'unchanged'; anything else is an error".

**S5 — The API shape is inconsistent with 01** (§8 `StudioLive` and the preload comment).
- **Problem.** 01 settles on per-topic `on*` members of one `StudioApi` (`onRunsUpdated`, `onLogLines`, 01:164–165) and per-topic channels (`runs:updated`, `log:lines`, 01:98, 139). 03 introduces a separate `studio.live.board/runLog` with a single `live:event` channel demuxed by `subId`. 03's `MessagePort` row also says "the same cleanup with no bookkeeping", but 01:100 notes that under context isolation the port needs a `window.postMessage` relay in the preload. Nor does 03 mention that 01 leaves MessagePort out of the spike (01:210).
- **Fix.** Use 01's names and channel model, or state the change and the reason, so that 07 does not have to reconcile them. Add "MessagePort is out of the spike (01)" to that row.

**S6 — The Windows log path is not wired** (§4 diagram; §5 log rows).
- **Problem.** Logs come only from "`fs.watch` registry/logs". On Windows the logs live inside WSL, where `\\wsl$` cannot be watched. The `runs watch` contract carries a `log` event type for exactly this (05-harness-integration.md:164). The file never routes `WatchEvent{type:'log'}` into the per-run `LogRing`.
- **Fix.** Add `log` → `LogLines` in the normaliser table. State that on the `Wsl` transport, logs arrive only through the watch stream, and on `Direct` through either the stream or a tail.

**S7 — Per-field provenance `Sourced<T>` is heavier than the need** (§7).
- **Problem.** Wrapping every field in `{value, from, at}` doubles the DTO surface across IPC and in every selector. The stated need is to label a few fields, such as phase, and to flag a disagreement.
- **Fix.** Keep `mergeRun` pure in main, which is correct. Emit a plain `RunView` plus a small `provenance: { phase?: Source; state?: Source }` and a `conflict?: string`. Leave the full precedence table to the data-layer item, as the file already does.

**S8 — Reload detection via `did-start-navigation` is fragile** (§5 lifecycle, "Renderer reload" row).
- **Problem.** The event fires before the navigation commits, and only for navigations that start. With navigation denied by the security bar (01:19), the realistic cases are reload and crash. A `did-start-navigation` that is later cancelled would drop live subscriptions.
- **Fix.** Use a hello on preload load instead, or in addition: the preload sends `live:hello` once when it runs, and main drops any old subscriptions for that `webContents.id`. Keep `render-process-gone` and `destroyed`. Mark which of these the spike checks with the "log the subscription count" test.

## Nice to have

**N1 — §6 polling budget.** The cadence table works out to about 60 (issues) + 180 (runs at 20 s) + 12 (PRs) ≈ 250 requests/h per repo, not "≈ 300". Say "per active repo" and note that only the selected repo is polled.

**N2 — §6 `x-poll-interval`.** GitHub sends this header on a few endpoints, notably events. Say "honour it when present".

**N3 — §9 eventBus usage.** "34 files use it" counts `eventBus.ts` itself (`grep -rl eventBus src | wc -l` = 34). Say "33 files import it".

**N4 — "Ask F-1".** On first use, gloss it as "harness follow-up F-1 (10-recommendation.md §8, line 382)".

**N5 — Risk 8.** The RxJS 7.8.2 age (21 months) is correct, and RxJS 9.0.0-beta.1 (2026-10-09) is the `next` dist-tag. Mention that the 9.x beta line is active, so "revisit" has a concrete target.

**N6 — §3 Zustand "cannot tear".** Correct by construction (uSES). Add "at the cost of de-opting transitions", which the concurrency note already covers, so the TL;DR does not oversell it.

## Checked and correct (no action)

- **npm (2026-11-25).** rxjs latest 7.8.2 (2025-02-22), 8.0.0-alpha.14 (2024-01-12), 9.0.0-beta.0 (2026-08-04), 9.0.0-beta.1 (2026-10-09); repo pushed 2026-11-19. zustand 5.1.0 (2026-11-06T14:07Z). jotai 3.0.0 (2026-09-08), 3.0.2 (2026-11-09). react 19.3.1 (2026-10-14). RTK 2.15.0, react-redux 9.3.1, @tanstack/react-query 5.108.4, @preact/signals-react 3.12.0, mobx 7.1.7, mobx-react-lite 5.1.4.
- **Library sources.** https://unpkg.com/zustand@5.1.0/esm/react.mjs: `useStore` calls `React.useSyncExternalStore`. TanStack `useBaseQuery.js:46` uses uSES, and `index.d.ts` exports `streamedQuery as experimental_streamedQuery`.
- **TC39.** https://github.com/tc39/proposal-signals README: "Stage 1". `tc39/proposals/stage-1-proposals.md:91` lists Signals, with notes dated 2024-04 and 2024-06.
- **Electron.** releases.json: 45.5.0 = Chromium 156.0.8078.109, Node 24.22.3. In web-contents.md v45.5.0, `did-start-navigation` is at l.313, `render-process-gone` l.485, `destroyed` l.503, `send` l.2060 and `postMessage` l.2117. context-bridge.md says Functions are supported both ways and shows the safe `ipcRenderer.on` wrapper.
- **gh 2.100.0, run locally.** The 304 repro matches Source 27 (stdout `HTTP/2.0 304 Not Modified`, stderr `gh: HTTP 304`, exit 1), and the rate-limit count did not change.
- **expause_web.** `package.json` (react ^18.3.1, RTK ^2.2.7, react-query ^5.90.5). `eventBus.ts:3–75` has a typed map, `on()` returning an unsubscribe, and `onPrefix`. `useContentTags.ts:115–121`. `subscribeToChatUpdatesUseCase.ts:1–41` ("thin domain pipe … no Redux dispatch") and `:89–105` (returns `Unsubscribe`). `STATE_MANAGEMENT.md:49–55`. `REACT_STATE_BEST_PRACTICES.md` (verdict: "Redux only for truly global, shared, cached data").
- **Issue #1.** The trust rules in "Data source" match §7.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1 — Applied.** §5.2 now uses a per-attempt `AbortController`, try/catch/finally that always kills the child, and emits `reconnecting` on a watchdog timeout instead of exiting the loop.
- **M2 — Applied.** Re-checked against 01 and 10 §5: TL;DR, §4, §5 and Day 2 now describe the minimal core (WatchAdapter, one issues GhPollAdapter, pure reduce, snapshot + one-entity upsert/remove, subscriptions per webContents, log ring + batch). Epoch/seq, harness `seq`, ref-count + grace, coalescing, multi-window, full precedence, runs/PR polling and RxJS moved to the §5.4 "Add when" table with triggers. Two-window spike check dropped.
- **S1 — Applied.** Verified on docs.github.com and the pagination guide (30 default, 100 max): normaliser drops `pull_request` items, `per_page=100`, page-1 ETag strategy.
- **S2 — Applied.** Jotai row tags "can tear" [inferred], notes the deliberate time-slicing trade, and leads with fit.
- **S3 — Applied.** Count re-tagged [inferred]; itemised per-file estimate in §4 gives ≈550–700 lines plus tests (slightly above the review's 400–600 once the Query client and fixture events are counted).
- **S4 — Applied.** Verified `issue/list/http.go:91` (GraphQL) and `api/api.go:553–564` (any status > 299 → exit 1) at v2.100.0; claims now [verified], only a parsed `304` is "unchanged".
- **S5 — Applied.** Uses 01's `StudioApi` `on*` members and channels (`onRunsUpdated`/`runs:updated`, `onLogLines`/`log:lines`, invoke `subscribe`/`unsubscribe`); adds `onIssuesUpdated` for 01's existing `issues:updated` channel; MessagePort row says "not in the spike (01)" and notes the preload relay.
- **S6 — Applied.** Verified 05-harness:164 `log` event; normaliser maps `log` → `LogLines`; `Wsl` gets logs only from the stream, `Direct` from the stream or a tail.
- **S7 — Applied.** `Sourced<T>` replaced by a plain `RunView` with optional `provenance: {phase?, state?}` and `conflict?`.
- **S8 — Applied.** Preload `hello` plus `render-process-gone`/`destroyed`; divergence from 01 §6's `did-start-navigation` stated with the reason and flagged for 07 (Risk 8); spike check covers reload and forced crash.
- **N1 — Applied.** Budget ≈250/h per active repo, only the selected repo polled; spike polls issues only (60/h).
- **N2 — Applied.** "Honour `x-poll-interval` when present" (best-practices l.31 confirms the conditional wording).
- **N3 — Applied.** Re-ran the grep (34 including `eventBus.ts`); text says 33 files import it.
- **N4 — Applied.** F-1 glossed with `10-recommendation.md` §8, line 382 (verified).
- **N5 — Applied.** RxJS revisit trigger now names the 9.x beta line (`next` dist-tag).
- **N6 — Applied.** TL;DR Zustand bullet notes the transition de-opt.
- **Owner note (TanStack Query) — Applied, recommendation changed.** Verified live: 5.108.4 (2026-11-23), peers `react ^18 || ^19`, ≈90.7 M weekly downloads (on par with Zustand), docs position it as a server-state cache used alongside client-state stores. New §3.1: use TanStack Query for on-demand `invoke` reads (run detail/analytics, Issue/PR detail, doctor) and commands (`useMutation`), with `networkMode: 'always'`, `retry: 1`, `staleTime: 30 s`; keep Zustand for push-fed live state; the only bridge is a live upsert invalidating that run's detail query. One store for everything is simpler only if v1 has just one or two on-demand reads.
