# Review — 01-electron-process-model.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

The file is accurate on almost every load-bearing fact I re-checked live today. Electron 45.5.0 is npm `latest`, released 2026-11-24, with Chromium 156.0.8078.109 and Node 24.22.3. The Electron 45 sandboxed-preload removals and the `safeStorage` sync deprecation (removal in 46) check out. The `contextBridge` rules hold: functions are proxied, prototypes are dropped, Error custom fields are lost and Symbols are dropped. `invoke` passes only `message`. All the npm release dates and peer ranges match the registry. The recommendation is well proportioned: hand-written typed IPC, no library, no utilityProcess, no MessagePort.

There is one design flaw in the browser-mode seam: it silently falls back to fixtures in production (M1). There are also gaps in three places:
- sender validation, which needs origin rather than URL, a null `senderFrame` check, and an inferred top-frame check (S1);
- subscription cleanup on reload (S2);
- `app://` path confinement (S3).

On top of that, one citation is wrong (S5) and one Electron 45 note is overstated (S4).

## Must fix

**M1. The browser-mode fallback silently serves fixtures inside Electron.**
- **Location:** §5, `getStudio()`, which returns `window.studio ?? createFixtureStudio(fixtures)`, and the line "the fixture code is still bundled but not used (or excluded by a build flag)".
- **Problem:** The fallback fires whenever `window.studio` is missing. Inside Electron that happens exactly when the preload fails to load. The file itself names the likeliest cause in its TL;DR trap: a runtime import in a `tsc`-built sandboxed preload. When it happens, a packaged Studio would quietly show fake runs and Issues instead of failing. The fixture also exposes a `window.__studioFixture.emit` test hook in the main world, which a shipped build should not have. The "or excluded by a build flag" alternative is left optional, but it is the part that matters.
- **Evidence:** §5 of the file itself; the sandbox tutorial confirms that a sandboxed preload cannot `require` local files: https://www.electronjs.org/docs/latest/tutorial/sandbox.
- **Fix:** Choose the implementation by build mode, not by whether `window.studio` is present. Suggested text:

  > `getStudio()` returns `window.studio` in the Electron build and **throws a visible error if it is missing** (preload failed). The fixture implementation and its `__studioFixture` hook are compiled only into the browser-mode build (e.g. `import.meta.env.MODE === "browser"` / a Vite alias), so they are absent from packaged apps.

  Add one line to Risks saying that a missing preload must fail loudly.

## Should fix

**S1. Sender validation: use `origin`, handle a null frame, and tag the top-frame rule.**
- **Location:** §3, "Sender validation": "checks `event.senderFrame` (its `url`/`origin` must be the app's own `app://` origin, and it must be the top frame)".
- **Problem:** Security checklist item 17 says to use the origin and not the URL. The reason given is that "about:blank, blob: and sandboxed documents have URLs that do not identify who controls them". The same item notes that the frame "may be null if it has gone away". The file offers `url` as an equal option and never mentions null, so a naïve `event.senderFrame.url` dereference can throw. The top-frame requirement is a sensible addition, but the checklist doesn't say it, so it is [inferred], not [verified, S13].
- **Evidence:** https://www.electronjs.org/docs/latest/tutorial/security (item 17).
- **Fix:** Replace the sentence with:

  > Every handler checks `const f = event.senderFrame; if (!f || f.origin !== APP_ORIGIN || f.parent !== null) reject` — origin, not URL (checklist item 17 [verified, S13]); a null frame (gone away) is rejected [verified, S13]; top-frame-only is our addition [inferred]. `APP_ORIGIN` is `app://<host>`, which is a real origin only because `app` is registered `standard: true`.

**S2. Subscriptions leak or duplicate on renderer reload.**
- **Location:** §6 row "Renderer reload or crash": "Subscriptions are tracked per `webContents.id` and dropped on `destroyed`".
- **Problem:** A reload or navigation keeps the same `WebContents`, so `destroyed` never fires. The old subscriptions stay registered in main. When the new page resubscribes (as the same row prescribes), every push is then sent twice, and log batches double. electron-trpc 1.0 had to fix the same class of problem: its release notes say "requests are cancelled when their page navigates away, reloads, crashes or closes".
- **Evidence:** https://github.com/jsonnull/electron-trpc/releases (electron-trpc@1.0.0 notes, #231); https://www.electronjs.org/docs/latest/api/web-contents.
- **Fix:** Use this text:

  > Drop all of a `webContents`' subscriptions on main-frame navigation (`did-start-navigation` with `isMainFrame`, or `did-navigate`), on `render-process-gone`, and on `destroyed`; make `subscribe` idempotent per (webContents, topic, key).

  Also show in the §3 sketch that `onRunsUpdated(repo, cb)` must tell main what to watch, through an `invoke("subscribe", …)` or a `send`. At the moment the preload code ignores `repo`, and nothing starts the source.

**S3. The `app://` path-confinement advice is too thin for a security-bar item.**
- **Location:** §6 row "Serving the UI" ("The docs' full example rejects `..` paths"); Recommendation, Day 2 step 2 ("`app://` via `protocol.handle` with path confinement").
- **Problem:** The docs example (`path.relative` + `!startsWith('..')` + `!isAbsolute`) is correct, but it has two gaps:
  - It works on the raw `pathname`. If the handler later decodes percent-escapes so that files with spaces load, `..%2F` would decode only after the check passed.
  - It shows no answer for unknown hosts.

  The file defers the detail to 05. 01 still prescribes the Day 2 code, though, so it should state the order of operations. It should also note that `registerSource` already returns `ERR_FILE_NOT_FOUND` for paths outside `root`, supports only GET and HEAD, and "no request touches the main thread". Those facts are the reason to prefer it, against the risk that it is experimental.
- **Evidence:** https://www.electronjs.org/docs/latest/api/protocol: the `app` example (`const { host, pathname } = new URL(req.url)`, `path.relative` check), and the `registerSource` text ("A path that resolves outside `root` … fails with `net::ERR_FILE_NOT_FOUND`").
- **Fix:** Add this to the row:

  > Handler order: reject host ≠ the one bundle host and method ≠ GET; `decodeURIComponent(pathname)`; `path.resolve(root, '.' + decoded)`; reject unless `path.relative(root, p)` is non-empty, does not start with `..` and is not absolute; then `net.fetch(pathToFileURL(p))`. `registerSource` does all of this natively (and off the main thread) but is experimental; 05 decides.

**S4. The Electron 45 `ipcRenderer` note is overstated.**
- **Location:** §3: "the static helpers `once`, `listenerCount` and `init` are gone [verified, S4]. Use `on`/`off` only."
- **Problem:** The breaking-changes entry removes only the static `events` module helpers, which were reachable through `require('events')`. It says "the instance API is preserved", so `ipcRenderer.once(...)` still works. "Use `on`/`off` only" reads as if the instance methods were removed.
- **Evidence:** https://www.electronjs.org/docs/latest/breaking-changes (45.0: "Behavior changed: native EventEmitter" and "Removed static helpers").
- **Fix:** Use this text:

  > the *static* `events` helpers (`EventEmitter.once`, `listenerCount`, `init`) are gone; instance methods (`on`, `off`, `once`, `removeListener`) are unchanged. Don't `require('events')` in the preload.

**S5. S14 misses its claim, and both of its links are old.**
- **Location:** §2 ("killing `wsl.exe` may not kill the Linux-side process tree") and Risk 2, both cited to S14.
- **Problem:** https://github.com/microsoft/WSL/issues/5092 is titled "WSL2 distro failing to startup with code 4294967295" (opened 2020-04-15). It says nothing about orphaned Linux processes. The Hyper PR #3794 ("Use taskkill on Windows to kill all descendant processes on exit") does support the Windows process-tree point, but it is about five years old. The brief requires sources older than about 12 months to be flagged, and these weren't.
- **Evidence:** `gh api repos/microsoft/WSL/issues/5092` (title and date); `gh api repos/vercel/hyper/pulls/3794` (title). I found no primary microsoft/WSL issue that states the exact behaviour. Related reports: https://github.com/microsoft/terminal/issues/2425 (a bash process survives after its window closes) and https://github.com/microsoft/terminal/issues/5731.
- **Fix:** Drop WSL#5092. Cite microsoft/terminal#2425 as [secondary, anecdotal, 2019], and mark the WSL orphan claim [inferred, to be tested on the Windows VM]. Risk 2 already plans that test. Flag Hyper #3794 as older than 12 months; the Node `child_process.kill` docs are a primary source for the "no tree kill on Windows" point.

**S6. Small citation and wording mismatches in the serialization and library tables.**
- **§3, "Function: Fails (DataCloneError)", "Promise: Fails" and "Symbol: Fails" over `invoke`/`send`:** these are cited to S5, but the IPC tutorial names only DOM objects and C++-backed objects. These rows follow from the structured clone algorithm. Cite https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Structured_clone_algorithm, or tag them [inferred from structured clone].
- **The contextBridge column's "Date, Map, Set, typed arrays: Copied":** S2 doesn't list these. It has only a "Cloneable Types → see linked document" row. Say "copied per the cloneable-types row [verified, S2 + MDN]".
- **§4, `@electron-toolkit/preload` "exposes `ipcRenderer` itself":** `ipcRenderer` can't cross the bridge since Electron 29. The package exposes a generic wrapper over any channel (`send`, `invoke`, `sendSync`, `on`, `postMessage`, …) as `electronAPI.ipcRenderer` (checked in `alex8088/electron-toolkit` `packages/preload/src/index.ts`). The conclusion stands, but the wording should be: "exposes a generic any-channel `ipcRenderer` wrapper (including `sendSync`) to the page".
- **The log flush interval "16–50 ms":** this is untagged. Tag it [inferred] and point to 04.

## Nice to have

**N1. The sandboxed preload must stay CommonJS.** Electron's ESM doc says "Sandboxed preload scripts are run as plain JavaScript without an ESM context", and preloads ignore `"type": "module"`. With `module: nodenext` and no `"type"` in `package.json`, `tsc` emits CJS today. If the repo ever adds `"type": "module"`, or the preload is bundled as ESM, it breaks the same way the TL;DR trap does. Add one clause to the trap bullet.

Source: https://www.electronjs.org/docs/latest/tutorial/esm; `package.json`; `tsconfig.json`.

**N2. electron-trpc 1.0 auto-registers its own preload script.** By default, `createIPCHandler` registers a library preload on the session, unless you pass `preload: false`. This is one more point against it under the intent-only bar, and it is worth a clause in §4.

Source: release notes for #231; `packages/electron-trpc/src/main/registerPreload.ts`; `src/preload/exposeElectronTRPC.ts`, which exposes `sendMessage` and `onMessage` over one generic channel and so confirms the "generic transport" claim.

**N3. Every push is copied twice, and the copy that arrives is frozen.**
- The IPC structured clone reaches the isolated world, then `contextBridge` copies and freezes it into the main world ("all other values are **copied** and **frozen**", S2).
- This is negligible at Studio's batch sizes, but worth one line for 04.
- For 03, it means stores must not mutate pushed DTOs in place: it throws in strict mode.

**N4. Endorse the unsubscribe pattern explicitly.** Each `contextBridge` crossing creates a new proxy, so the page could never remove a listener by passing the same callback again. Returning an unsubscribe closure from the preload, as the sketch does, is the right shape, not just a convenient one. Add one sentence so 03 doesn't "simplify" it to an `off(cb)` API.

**N5. The `safeStorage` row is correct but could be shortened.** It is verified: deprecated in 45, removed in 46. Studio stores no secret, so "No" alone, plus the async-API note, is enough.

### Checked and correct (no action)

- **Electron 45.5.0** is npm `latest`, with 46 in alpha. The release page confirms 2026-11-24, Chromium 156.0.8078.109 and Node 24.22.3.
- **The sandbox `require` allow-list and the absence of `Buffer`/`setImmediate`** are confirmed, as are the Electron 45 removal of shims and globals and the `safeStorage` sync methods being deprecated in 45 and removed in 46.
- **`contextBridge`:**
  - functions are proxied;
  - Promises are supported;
  - prototypes are dropped and class instances are copied without them;
  - Error custom properties are lost;
  - Symbols are dropped;
  - since 29, `ipcRenderer` arrives as an empty object.
- **The IPC tutorial:**
  - `handle` errors keep only `message`;
  - avoid `sendSync`;
  - wrap listeners so the event is not leaked.
- **MessagePorts** transfer only through `postMessage`, and need a `window.postMessage` relay under context isolation.
- **`app`:**
  - `second-instance` argv may be reordered (use `additionalData`);
  - `app.exit` skips the quit events;
  - on Windows, shutdown or logout skips them too;
  - the docs give no pattern for async cleanup in `before-quit`.
- **`registerSchemesAsPrivileged`** must be called before `ready`, and `registerSource` is experimental with no version of introduction documented.
- **The utility-process use-case quote** matches the process-model page.
- **npm:**
  - electron-trpc 1.0.0 (2026-10-30, after 0.7.1 on 2024-12-07; peers `electron >=35`, `@trpc/* ^11.10`; 403 stars, 3 open issues);
  - electron-trpc-experimental 1.0.0-alpha.1 (2025-06-18);
  - trpc-electron 0.1.2 (2025-01-06);
  - @egoist/tipc 0.4.0 (2026-07-17, after 0.3.2 in 2024-07; React Query is a required peer);
  - @electron-toolkit/typed-ipc 1.0.2 (2024-11-11);
  - @electron-toolkit/preload 3.0.2 (2025-04-19);
  - electron-typed-ipc, typed-ipc and interprocess date from 2020–2023.
- **Local code:** `src/main/main.ts:4-26` and `:24` (`loadFile`), `:28-38`; the `src/preload/preload.ts` versions-only object; the `src/renderer/index.html:7` CSP with `connect-src 'none'`; `tsconfig.json` (`nodenext`, `tsc` only). All match the file.
- **Consistency with `../product-startup-research/10-recommendation.md`:** intent-only IPC, the OS-native confirm in main, and `contract/` placement are all consistent. No contradiction found.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1** — Applied. `getStudio()` now picks by build mode, throws if `window.studio` is missing in Electron, and keeps the fixtures and `__studioFixture` out of packaged builds. Updated the TL;DR, §5 and Day 1, and added Risk 5.
- **S1** — Applied. The check now uses `origin` and rejects a null frame (re-checked against security item 17, which does not mention the top frame, so that rule is tagged [inferred]).
- **S2** — Applied. Subscriptions are now dropped on main-frame navigation, `render-process-gone` and `destroyed`, and `subscribe` is idempotent. The §3 sketch now sends `subscribe`/`unsubscribe` with `repo`. The electron-trpc #231 wording was confirmed.
- **S3** — Applied. Added the decode-then-confine handler order to the §6 row. `registerSource` facts (ERR_FILE_NOT_FOUND outside root or for non-GET/HEAD, off the main thread) were re-checked live.
- **S4** — Applied. The breaking-changes page confirms the instance API is preserved. Only the static `events` helpers are gone.
- **S5** — Applied. Dropped WSL#5092 (confirmed to be an unrelated startup error) and cited microsoft/terminal#2425. Both 2019 sources are flagged as older than 12 months, and the WSL orphan claim is now [inferred, to be tested]. The Node `kill` docs were added as S18, but they state the descendant point for **Linux**, not Windows, so the Windows tree claim stays [secondary, S14].
- **S6** — Applied. Clone rows are now cited to MDN (S17), with Promise as [inferred]. The cloneable-types wording is fixed. The toolkit preload wording now says "generic any-channel wrapper incl. `sendSync`" (confirmed in source). The flush interval is tagged [inferred].
- **N1** — Applied. Added the CommonJS clause to the TL;DR trap (ESM tutorial re-checked; added as S16).
- **N2** — Applied. Added a clause to the §4 electron-trpc row saying `createIPCHandler` auto-registers its preload (confirmed in the #231 notes).
- **N3** — Applied. Added a paragraph to §3 on the double copy and frozen pushes (03 must not mutate DTOs).
- **N4** — Applied. Added a sentence to §3 saying the unsubscribe closure is required.
- **N5** — Applied. Shortened the `safeStorage` row.
