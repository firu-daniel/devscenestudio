# Review — 04-performance.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

This is a strong, measurement-backed file. Its main conclusions hold: batch log IPC, virtualise the log but not the board, no `utilityProcess` in v1, keep `backgroundThrottling` on, ingest on arrival and render on rAF, and let main own the pause policy. I re-read the throwaway scripts (`ipcbench`, `renderbench`, `idlebench`, `cc`, `sizes`, `jp.mjs`). Most measure what the file says they measure.

The 15:18 revision adds the heavy-load caveat, which mostly satisfies the mandatory finding (M1). A few residual items remain.

Four other things need fixing:
- The library size table is wrong: React was bundled into every React-binding measurement (M2).
- The Day 1 recommendation of electron-vite contradicts 06, which picks Vite + esbuild (M3).
- The hidden-window polling policy contradicts 03 (M4).
- One startup number cites a PR that does not contain it (S2).

**The 3–5× question.** If every absolute number were 3–5× worse, **no conclusion would change**:
- **Board:** a naive one-card update at 2–3.5 ms p50 and 5–8 ms p95, and a mount of ≤ 175 ms, still fit inside a frame or a one-off. No virtualisation still holds.
- **Main-process work:** ≤ 6 ms per task, so no `utilityProcess` still holds. A higher memory cost only strengthens that verdict.
- **Log tail:** virtualised at 2–3 ms per frame against naive at 108–180 ms.
- **MessagePort:** this is a same-run ratio, so the absolute scale does not matter.
- **Hidden window:** the throttling counts are behaviour, not timing.

Only two *wordings* break at 3–5×: "unbatched IPC < 1% CPU" becomes ≈ 2–5%, and the compile-cache gain grows.

## Must fix

**M1 — Measurement under heavy load (mandatory). Largely addressed in the 15:18 revision; residual items remain.**
- **What is now in place.** The TL;DR blockquote (l.6), §0 (l.30), the per-table "(under load; noisy upper bound)" notes (l.38, 67, 95, 110, 138, 171, 204) and the reworded conclusions now say that the benchmarks ran while a DevScene headless Gates phase loaded CPU, memory and disk. They also say that only same-run ratios support conclusions, and that the spike re-measures absolute targets on an idle machine. The reworded conclusions are: MessagePort "within noise", memo "on design grounds", and the ≈ 60× and ≈ 10× ratios as the findings. That meets the requirement.
- **Residual 1: memory is not an upper bound.** "Upper bound" is wrong for memory. Under memory pressure, macOS compresses pages, so working set and RSS are *under*-reported, not inflated. Electron's own docs say `residentSet` is absent on macOS for exactly this reason (https://www.electronjs.org/docs/latest/api/process).
  - Fix l.6: "(ms, fps, CPU %, µs) is noisy and an upper bound; memory figures (MB) are noisy in an unknown direction, because memory pressure compresses pages".
  - Apply the same fix to l.30, where "RSS and working set are also distorted" should say *in which direction*.
- **Residual 2: the caveat is missing from Risks and Sources.**
  - Add to *Risks*: "All local numbers were taken under a concurrent Gates run; no absolute value is a target."
  - Add to Sources item 17: "taken under heavy concurrent load (DevScene Gates phase)".
- **Residual 3: a wrong tag in §0.** l.32 tags an inferred statement "[verified locally]". Change it to [inferred].
- **Residual 4: the 2× threshold.** With the file's own threshold, the board B/A ratio (0.7/0.3 ≈ 2.3×) is borderline. The revision already handles this well. Keep the Q5 row (l.281) worded as it is now.

**M2 — Library sizes for the React bindings include React itself (§6, TL;DR l.15, Q5 l.282).**
- **The claim.** §6 says "React marked external for the React libraries".
- **The evidence.** The outputs show otherwise.
  - Every React-binding bundle contains React's `react.transitional.element` symbol: `scratchpad/sizes/out/zustand.js`, `tanvirt.js`, `rwindow.js`, `rq.js` and `rtk.js`.
  - `tanvirt.js` also contains react-dom (`flushSync`, `createPortal`, "Minified React error").
  - None of the outputs has an external `from"react"` import.
- **The effect.** The figures are overstated by the size of React core, plus react-dom for TanStack Virtual.
  - The zustand row (3.7 KB gz) contradicts 03's bundlephobia figure of ≈ 0.5 kB gz (03 source 14). That figure is the correct one.
  - TanStack Virtual's 15.3 KB is likely ≈ 4–6 KB.
  - The react-window, react-query and RTK rows are inflated too.
- **The fix.** Re-run with `--external:react --external:react-dom --external:react/jsx-runtime`, then correct the table, TL;DR l.15 and Q5 l.282 ("One small library (15 KB gz)"). The conclusion (installer effect < 0.5%) is unaffected. The react-window vs TanStack Virtual comparison may change.

**M3 — electron-vite 6 vs 06's Vite + esbuild: an inconsistency (§5 l.167, Day 1 item 1 l.258, Q5 l.285).**
- **The problem.** 04 says "**Recommended**" and "Bundle with electron-vite 6 (06 confirms)". 06 does *not* confirm.
  - 06 TL;DR l.6 and its table l.60–61 pick **Vite 8 for the renderer plus a small esbuild script for main and preload**, with electron-vite as a fallback.
  - 06's reasons: electron-vite has a single maintainer, and browser mode needs a plain Vite config anyway.
  - I confirmed the maintainer count: alex8088 has 354 commits, and the next contributor has 2 (`gh api repos/alex8088/electron-vite/contributors`). electron-vite 6.0.0 was released 2026-10-14 and the repo was last pushed 2026-10-14.
- **What the evidence favours: 06's choice.** 04's own performance argument is a single bundled main and no `node_modules` in the asar, and both options deliver it. 04 itself says "Builds are seconds either way". So performance does not discriminate, and 06's maintenance and browser-mode arguments decide.
- **The fix.**
  - In §5: "Bundle main and preload with esbuild and the renderer with Vite (06 decides; electron-vite is the fallback). Performance is identical."
  - In Day 1 item 1: "Bundle per 06 (Vite + esbuild)".
  - In Q5: "Bundling (Vite + esbuild, per 06)".
  - Swap the esbuild-fallback row for an electron-vite-fallback row.

**M4 — The hidden-window polling policy contradicts 03 (§4 table l.154, Day 2 item 3).**
- **The problem.** 04 says: window hidden or minimised → "**Stop `gh` polling**". 03 TL;DR l.13 says: "30 s while focused, **5 min while hidden**". Day 2 builds one scheduler, so it cannot follow both.
- **What 04's own data favours.** One `gh api` call every 5 minutes is a negligible wake-up for the ≈ 0% target. Stopping entirely means stale Issue state if the window is hidden but a notification or menu-bar view is used later.
- **The fix.**
  - Align the two files: "Hidden or minimised: slow `gh` polling to ≈ 5 min (03). Stop on `suspend`/`lock-screen`."
  - Or state the disagreement explicitly for 07 to settle.

## Should fix

**S1 — §1 table header: the wrong runtime.**
- **The problem.** The header says "Node 24 in Electron 45", but `jp.mjs` is a plain Node script. Sources item 17 says "Node for the §1 parse and regex timings", and the machine's `node` is v22.23.2, which is the same as the startup research's measurements.
- **The fix.** Change the header to "Node 22.23.2 (plain Node, not Electron)". Only the `v8.serialize`/`structuredClone` row ran inside Electron, in `ipcbench/main.js`. Give that row its own note.

**S2 — §5 l.172 cites [3] for numbers [3] does not contain, and omits context [3] does give.**
- **The unsupported number.** "A 2026 PR reports 123 → 74 ms to the first main-process JS". PR 52873 reports **no browser-process number**: it says the browser process *already* booted from the snapshot. PR 53139 has no timings either (https://releases.electronjs.org/pr/52873, https://releases.electronjs.org/pr/53139).
- **The missing context.** The 86.1 → 39.7 ms `utilityProcess` figure is for a **Linux x64** release build (n = 40).
- **The fix.** Remove the 123 → 74 ms clause or cite its real source. Add "(Linux x64)" to the 40 ms figure in TL;DR l.10 and §1 l.61. Also note that the PR shipped in v42.10.0, v43.5.0 and v44.0.0, so "v44+" in l.172 is too narrow.

**S3 — `module.enableCompileCache()` (§5 l.171, TL;DR l.14).**
- **What holds up.** `scratchpad/cc/.cache/v24.22.3-arm64-…` exists, so the cache was written under Electron 45's Node 24.22.3. The claim that it "works in Electron 45 main" is therefore supported.
- **What is weak.**
  1. The script on disk is now the "off" variant (`const r="off"`), so the "on" variant cannot be re-read.
  2. "62 → 16 ms on the second launch" compares a cold first launch with a warm second one. Under heavy *disk* load, OS file-cache warming of the 8.7 MB `typescript.js` is a confound. The comparison needs an "off, second launch" baseline.
  3. The cache is untested for a main bundle loaded from inside an asar.
  4. No Electron doc or issue mentions the API; `gh search` found nothing. The tag should therefore be [verified locally, single run], not "+ docs".
- **The fix.** Add those caveats. The "skip for v1" conclusion stands.

**S4 — The log-tail key attribution is not measured (§3.2 l.120).**
- **The claim.** "With position keys every row's content changes every frame, which is what made the naive variant so slow [verified locally]".
- **The evidence.** In `renderbench/app.js`, the *virtual* variant also used position keys (`key: it.index`) and was the fastest. The naive variant was slow because React built and reconciled 10k elements per frame. The keys were not isolated.
- **A missing input.** The benchmark rows were plain strings, not the ANSI `spans[]` rows the spike will render, so the per-row cost is understated.
- **The fix.** Change the tag to [inferred]. Recommend `seq` keys for correctness (stable selection and scroll anchoring), not as the measured cause. Add "rows without ANSI spans" to the §3.2 measurement note.

**S5 — "Breaks Ctrl+F" and "find-in-page" (§3.1 l.102, §3.2 l.121).**
- **The problem.** Electron has no built-in find bar. Find needs `webContents.findInPage()` plus our own UI, so there is nothing for virtualisation to "break" in the Electron build. The point holds only in browser mode.
- **The fix.** Reword the argument as Playwright locators, accessibility and scroll-sync complexity. If find matters, mention that `findInPage` would only search mounted rows.

**S6 — Further inconsistencies with 03 on the log ring and the message shapes.**
- **(a) Where the ring lives.**
  - 03 keeps a per-run 10k `LogRing` **in main** as well as in the renderer (03 TL;DR l.10, §5 l.147).
  - 04 §2 l.86 says "the 10k-line ring stays in the renderer", and the §7 memory table counts only renderer rings, with an LRU of 3.
  - The fix: add the main-side rings (one per watched run, each ≈ 3–5 MB) to §7 and give them a cap too.
- **(b) The first message on subscribe.**
  - 03's first log message is "the current ring contents (up to 10k)". At ≈ 120 chars × 10k lines, that is ≈ 1.2 MB, which conflicts with 04's "keep messages under ≈ 1 MB".
  - The fix: say whether the reset is chunked or exempt.
- **(c) What happens on show.**
  - §4 says "stop forwarding log lines" when the window is hidden, but it does not say how the renderer catches up on show.
  - The fix: add "on show, main sends a `reset` from its ring (03 protocol)".
- **(d) Coalescing.**
  - 04 l.84 says send `run_updated` per event and do not coalesce. 03 coalesces patches over 100 ms and calls them `patch`/`upsert`, not `run_updated`.
  - The fix: use 03's vocabulary and note that its 100 ms coalescing is harmless but not needed for performance.

**S7 — The "< 1% CPU" claim for unbatched IPC (TL;DR l.8, §2).**
- **The problem.** This is derived from wall-clock throughput (`ipcbench`: first send to ack). It is not derived from CPU time across main, the renderer and the IPC thread.
- **The fix.** Tag it [inferred], or replace it with "≈ 4 ms of wall time per 2,000 lines". At 3–5× it would be ≈ 2–5%. The "batch anyway" conclusion is unaffected.

## Nice to have

**N1 — The TanStack Virtual vs react-window rationale (§3.2 l.119).**
- **The weak argument.** "Headless, so CSP and Trusted Types stay in our markup" does not discriminate:
  - Both libraries let us render our own row component.
  - Both apply positioning through React `style` props, which go through the CSSOM and are not subject to `style-src` the way inline style attributes are.
- **What I confirmed.** Both libraries are maintained:
  - TanStack/virtual: pushed 2026-11-24, `react-virtual` 3.14.28 released 2026-11-22.
  - bvaughn/react-window: pushed 2026-11-21, 2.5.4 released 2026-11-21, not archived.
- **The fix.** Justify the pick by API fit for a bottom-pinned, follow-mode list, and by the (corrected, M2) size.

**N2 — The board benchmark misses column moves.** The update only changes `phase` and `updated`; it never changes `status`. The recommendation that "column lists change identity only when membership changes" is therefore untested. Day 1 could add a move-between-columns case.

**N3 — Overlap with the startup research is small.** The overlap with `../product-startup-research/02-performance.md` is §5 (animations, polling) and §6 (no board virtualisation, ring + frame batching). 04 measures and extends those points rather than repeating them, and its Scope line already defers framework numbers. Optionally add "(confirms startup 02 §6)" next to §3.1 and §3.2.

**N4 — Verified and fine as written.**
- `backgroundThrottling` defaults to `true`. With it disabled, the visibility state "will remain `visible`". `show: false` starts "visible". macOS occlusion marks the page hidden. On Wayland, `minimize` fires only for client-side decorations. Sources: https://www.electronjs.org/docs/latest/api/browser-window and https://www.electronjs.org/docs/latest/api/structures/web-preferences.
- The docs do not mention rAF in hidden windows; that claim rests on `idlebench`, which measures it correctly: `show: true` → `hide()` → 0 rAF callbacks in 10 s.
- The performance-doc claims check out: bundle into one file, avoid sync IPC, `require` is costly on Windows, `Menu.setApplicationMenu(null)`, and the doc has no snapshot or compile-cache advice.
- `getProcessMemoryInfo` is async, reports KB, has no macOS `residentSet`, and is available in sandboxed renderers.
- The npm versions and dates in §6 match the registry today.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1** — Applied (residuals 1–3; 4 needed no change). Memory is now "noisy in an unknown direction" (TL;DR, §0, §1, §7). A Risks bullet says no local number is a target. Sources 17 records the concurrent load. The §0 tag is now [inferred].
- **M2** — Applied. Confirmed that every binding bundle contained React. Re-ran esbuild with `react`/`react-dom` (and subpaths) external and checked that the outputs import React rather than contain it. New min+gz: TanStack Virtual 11 KB, react-window 6.5 KB, zustand 0.4 KB, RTK + react-redux 9.5 KB, react-query 10 KB. Corrected §6, the TL;DR, §3.2 and Q5. TanStack is 11 KB rather than the estimated 4–6 KB because it includes virtual-core.
- **M3** — Applied. §5, Day 1 and Q5 now follow 06 (Vite + esbuild, with electron-vite as the fallback) and say performance does not decide it. 07 makes the final pick (open item b).
- **M4** — Applied, as one proposed policy. It has three activity levels: Visible (03's focused cadence), Hidden (hide, minimise or occlusion via `setVisible`: 03's ≈ 5 min, PRs off) and Suspended (stopped). There is no separate blur tier. Recorded for 07 (open item a).
- **S1** — Applied. Confirmed `jp.mjs` runs in plain Node v22.23.2. The §1 header is corrected, and the `structuredClone` row is marked as Electron. A §0 runtime note was added.
- **S2** — Applied. Confirmed that PR 52873 has no browser-process timing. Removed 123 → 74 ms, added "Linux x64" to the 40 ms figure, and listed v42.10.0/v43.5.0/v44.0.0.
- **S3** — Applied. Confirmed the script on disk is the "off" variant. Added the caveats (no "off" second-launch baseline, disk-cache confound, asar untested, no docs) and the tag [verified locally, single run]. "Skip for v1" still stands.
- **S4** — Applied. Confirmed that the virtual variant also used `key: it.index`. The `seq` key is now justified by correctness and tagged [inferred], and "rows without ANSI spans" was added to the §3.2 note.
- **S5** — Applied. The board argument is now about a11y, Playwright locators and scroll-sync, with a note on `findInPage` and mounted rows. The log argument says "browser-mode find".
- **S6** — Applied. (a) Main-side rings are added to §7 with a cap and a drop rule. (b) The `reset` is exempt from the 1 MB guideline (≈ 10 ms one-off, inferred), to be chunked only if measured over a frame. (c) "On show, main sends a `reset`" is added to §4. (d) The text uses 03's `patch`/`upsert` vocabulary, and the 100 ms coalescing is noted as harmless. 03 was being revised during this fix, so open items c–e ask 07 to re-check against 03's final text.
- **S7** — Applied. The claim is replaced with "≈ 4 ms wall time per second (≈ 2–5% at 3–5× slower)" and tagged [inferred], in the TL;DR and §2.
- **N1** — Applied. The CSP/Trusted Types argument is dropped. The pick now rests on the variant actually measured and on API fit for a bottom-pinned follow list, with the corrected sizes.
- **N2** — Applied. Added a "not measured: column moves" note in §3.1 and a new Day 1 item.
- **N3** — Applied. Added "(confirms startup 02 §6)" in §3.1 and §3.2.
- **N4** — No change needed (verified items).
