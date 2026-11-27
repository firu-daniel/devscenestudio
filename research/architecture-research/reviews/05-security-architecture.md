# Review — 05-security-architecture.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-25

## Summary

The file is well researched and almost every version and API claim holds up when re-checked live. The choke-point structure fits the app's size: most choke points are files the spike writes anyway. Two Day 1 recommendations fail when actually run, though. I tested them in Electron 45.5.0 with a page served by `registerSource` under the file's CSP:

- **M1.** The README-prescribed `TRUSTED_TYPES_POLICY: null` makes DOMPurify render **nothing** under `require-trusted-types-for 'script'`, and it emits two TT violations.
- **M2.** The "0 CSP violations" corpus gate cannot pass as specified, even when sanitising works.

The remaining findings cover consistency with 10 §6 and 06, coverage gaps, overstated TypeBox reasoning, and miscounted ceremony.

**Verified correct** (all re-checked 2026-11-25):

- **Versions:** TypeBox 1.4.7, zod 4.6.7, DOMPurify 3.5.0, Vite 8.3.8, ESLint 10.15.0, fast-check 4.11.0, markdown-it 15.0.3, React 19.3.1, valibot 1.5.0, @electron/fuses 2.1.3.
- **DOMPurify:** the 3.5.0 release note and both advisories.
- **Electron checklist:** #17 wording at `v45.5.0`, PR #53684 (merged 2026-09-07), 20 checklist items.
- **`protocol.registerSource`:** marked Experimental; added in 45.0.0 by #54521 (and fixed in 45.1.0 by #55178).
- **Vite GHSA-p4f5-76q4-ffq7:** critical, no CVE id, affects `>=8.3.0 <=8.3.6`, patched in 8.3.7.
- **Fuses:** the 9-fuse list; `wasmTrapHandlers` is absent from electron-builder 26.18.1's `FuseOptionsV1`; ASAR integrity covers macOS and Windows only.
- **Sender check:** the expression works.
- **TypeBox and the harness schemas:** TypeBox compiles the harness's plain draft-07 schemas.

## Must fix

**M1. `TRUSTED_TYPES_POLICY: null` breaks rendering under the file's own CSP.**

- **Location:**
  - TL;DR bullet 2 of "Changes since 08";
  - §3 snippet ("`TRUSTED_TYPES_POLICY: null` is the README's prescription for exactly this pattern");
  - Day 1 ("DOMPurify **3.5.0** (default mode, `TRUSTED_TYPES_POLICY: null` inside the `studio-html` policy)");
  - Risk 2.
- **Problem:** the README does say this (DOMPurify 3.5.0 `README.md` §"What about DOMPurify and Trusted Types?", lines 196–203). But with `null`, DOMPurify passes a raw **string** to `new DOMParser().parseFromString()` (`dist/purify.es.mjs:1864-1866`), and that call is itself a Trusted Types sink. When it throws, DOMPurify falls back to `documentElement.innerHTML = dirty` (`:1871`), which is a second sink.
- **Evidence (Electron 45.5.0, Chromium 156):** I ran a test page served by `protocol.registerSource` with the header `default-src 'none'; script-src 'self'; require-trusted-types-for 'script'; trusted-types studio-html`. Calling `policy.createHTML('<b>hi</b><img src=x onerror=alert(1)>')` with `TRUSTED_TYPES_POLICY: null`:
  - returned an **empty string**;
  - fired `require-trusted-types-for` violations for `DOMParser parseFromString` and `Element innerHTML`.

  Two alternatives both rendered `<b>hi</b><img src="x">` with no TT violation:
  - (a) no `TRUSTED_TYPES_POLICY` option, with CSP `trusted-types studio-html dompurify`;
  - (b) a module-private pass-through policy passed as `TRUSTED_TYPES_POLICY`, with CSP `trusted-types studio-html studio-purify`.

  The test script is in the session scratchpad (`etest/`).
- **Fix:** promote Risk 2's fallback to the default. Replace the §3 snippet with:

```ts
// renderer/ui/safe/policy.ts — the only createPolicy calls (lint)
// CSP: trusted-types studio-html dompurify
export const html = trustedTypes.createPolicy('studio-html', {
  createHTML: (md) => DOMPurify.sanitize(mdit.render(md), CFG), // RETURN_TRUSTED_TYPE stays false
});
```

  Then:
  - add `dompurify` to the `CSP` constant in §4;
  - change the Day 1 bullet to match;
  - rewrite Risk 2 as "confirmed in a scratch test; the corpus re-checks it".
  - Without `'allow-duplicates'`, DOMPurify creates `dompurify` at import time, before any page script runs, so a later XSS cannot claim the name. State this as the reason it is safe.
  - Drop the TL;DR claim that the README's `null` advice "is needed to avoid a CSP violation per page".

**M2. The "0 CSP/TT violations" corpus gate fails on correctly sanitised input.**

- **Location:** §7 suite 1 ("0 CSP/TT violations (`securitypolicyviolation` listener)"); §3 ("the corpus's CSP-violation counter must read 0"). This inherits 10 §5's Day 1 threshold.
- **Problem:** in the same test with a working setup, `DOMPurify.sanitize` *alone* (output not assigned anywhere) fired a `script-src-attr` violation for `onerror=` and a `style-src-attr` violation for `style=`. The parse document inherits the page's CSP reporting. Default DOMPurify also **keeps** `style` attributes, so rendering a sanitised `<i style=…>` fires a second `style-src-attr` violation, because the file's CSP has `style-src 'self'`. Every hostile corpus row therefore trips the counter even though nothing executes.
- **Evidence:** the scratch test output was `SANITIZED=<b>hi</b><i style="color:red">x</i>` followed by `VIOLATION style-src-attr`. The `onerror` input gave `VIOLATION script-src-attr` with no assignment.
- **Fix:**
  1. Add a fixed `ALLOWED_ATTR` (`href`, `title`, `class`, `alt`) to `CFG` beside `ALLOWED_TAGS`, so `style` never reaches the DOM.
  2. Redefine the gate: **0 `require-trusted-types-for`/`trusted-types` violations, 0 dialogs/executions, 0 off-origin requests, 0 `javascript:` hrefs**. Record `script-src-attr`/`style-src-attr` reports, but don't fail on them, since they are the CSP blocking the payload as intended.
  3. Note the deviation from 10 §5's "0 CSP violations" wording so 07 can carry it.

## Should fix

**S1. The Electron dev loop contradicts 06.**

- **Location:** TL;DR "Electron dev runs also load `app://` (a `vite build --watch` output) … HMR lives in browser mode only"; §5 last row; Q5.
- **Problem:** 06 picks `scripts/dev.mjs` with Vite `createServer` and lists `dev` as "Human, Electron with HMR" (`06-testing-and-tooling.md:60`, `:204`). Its Risk 1 relaxes the CSP in serve mode. The two files give incompatible dev loops, and neither cross-references the other.
- **Fix:** state the conflict explicitly for 07. The trade-off:
  - (a) 05's way: one origin and no dev branch in the sender check or CSP, but no HMR in the Electron window;
  - (b) 06's way: allow `http://localhost:<port>` as a second origin only when `!app.isPackaged`, with a release assertion that the packaged origin list holds `app://studio` alone.

  Then recommend one. For a one-developer app, (b) with the `isPackaged` guard and the release assertion is defensible. Either way, say so in both files.

**S2. The runner's `cwd` deviates from the bar without saying so.**

- **Location:** §1 row "6 Repo trust gate" ("the runner's `cwd`/`--repo` slots take `TrustedRepo | Home` only"); the §2 sketch `gitShowRef(...) => ({…, cwd: repo})`.
- **Problem:** 10 §6 item 6 and 08 §3.11 require "Spawn `devscene … --cwd <repo>` with the **process** cwd outside the repo" (the `.npmrc`/`npx` resolution risk). 05 allows `TrustedRepo` as the process cwd for any executable.
- **Fix:** make `cwd` per-`KnownExe`. For `devscene` and `gh`, cwd is always `Home`, and the repo goes in `--cwd`/`--repo`. Only `git` may run with cwd in a `TrustedRepo`, always with the hardening flags. A cleaner alternative: `git -C <TrustedRepo>` with cwd `Home` everywhere. Add a unit assertion that no `Command` for `devscene` has a repo cwd.

**S3. Coverage gaps against 10 §6.**

- **Location:** the §1 table.
- **Problem:** several bar items have no placement:
  - item 5: non-member warning; no auto-start and no batch start;
  - item 8: `CLAUDE_CONFIG_DIR` and "including inside WSL"; watcher and diagnostics exclusion (only a `\.claude` grep is given);
  - item 9: supply chain (lockfile, `--ignore-scripts`, 7-day cooldown, SHA-pinned actions, zizmor) and the 14-day patch cadence;
  - item 11: harness blockers H1/H1′/H2/H12;
  - item 4: on Windows, security-relevant reads happen inside WSL, never over `\\wsl$`.
- **Fix:** add short rows.
  - Item 5: the `startRun` schema takes exactly one `issueNumber` (no array), and no verb exists that starts without a user gesture. The non-member flag is computed in main from the re-fetched `author_association` and shown in the native modal.
  - Item 11: **`answer`/`resume` verbs are absent from `verbs.ts` until H1+H1′ ship**, with an IPC contract test asserting it. This is the cheapest architectural enforcement of a release blocker.
  - Item 8: the confined reader and watcher roots resolve `CLAUDE_CONFIG_DIR` (both sides of WSL) into a deny list.
  - Item 9: a row pointing at the repo/CI config owner (not a code layer).
  - Item 4: the confined reader's Windows implementation runs inside WSL through the transport.

**S4. TypeBox compatibility and ESM claims are overstated.**

- **Location:** validation table, "agents mostly know the 0.x API, which 1.x stays compatible with [verified, 19]"; Risk 3 "TypeBox 1.x is ESM-only … If the Day 2 main build stays CommonJS … use zod 4 instead".
- **Problem, compatibility:** the README (typebox 1.4.7, `readme.md:355`) promises "backwards compatibility with `0.x` **types**", not the 0.x API.
  - The package was renamed: `typebox` 1.x versus `@sinclair/typebox`, whose 0.34.52 is still published as LTS.
  - The compiler moved from `@sinclair/typebox/compiler` (`TypeCompiler.Compile`) to `typebox/schema` (`Schema.Compile`, a default export).
  - Agents trained on 0.x will write the old imports and pull in the wrong package.
- **Problem, ESM:** the ESM-only risk does not apply. Electron 45.5.0 ships Node 24.22.3, and I loaded `typebox/build/schema/index.mjs` via `require()` from a CommonJS Electron main with no error (`require(esm)`). 06 also bundles main with esbuild, which inlines ESM into CJS.
- **Fix:**
  - Retag the compatibility claim as "0.x schemas compatible; API and package name changed".
  - Add `@sinclair/typebox` to `no-restricted-imports`, and name the import (`import Schema from 'typebox/schema'`).
  - Drop the CommonJS clause from Risk 3, keeping only the single-maintainer point (verified: sinclairzx81 has 818 of about 830 commits).

**S5. The TypeBox rationale leans on a contract that does not exist yet.**

- **Location:** TL;DR "The harness already speaks JSON Schema (draft-07 + ajv in `devscene/schemas/`), so one validator covers IPC arguments, the harness `--json` contract, branch-committed JSON and Studio's own settings file."
- **Problem:** today's harness schemas are `devscene.config.schema.json` and `flow-graph.schema.json` (draft-07, `/Users/daniel/Work/devscene/schemas/`). The `runs --json` contract and its schema are a *planned* harness follow-up (10 §8 F-1), and `run_analytics/` JSON has no schema at all. The technical claim does hold: TypeBox 1.4.7 `Schema.Compile` accepted both draft-07 files unchanged. It passed `task_plan_writing.graph.json`, rejected all 6 `negative/flow-graph-schema-*.json`, and rejected every config negative I ran.
- **Fix:** reword as "the harness uses draft-07 JSON Schema for its config today and plans one for `runs --json` (10 §8 F-1). TypeBox validates both as-is (scratch test 2026-11-25)". Keep the pick, but make the contract benefit explicitly conditional, which the file's own "switch to zod 4 if…" already implies. Also note that runtime validation alone does not give `contract/` its TS types: either codegen or `Static` inference is still needed, so say which.

**S6. A generated preload is ceremony, and it conflicts with 01.**

- **Location:** §1 row "2 Intent-only preload": "`preload/preload.ts` generated from `shared/ipc/verbs.ts`".
- **Problem:** 01 recommends a hand-written channel map, with "a preload that literally lists its verbs (easy to review for security)" (`01-electron-process-model.md:161`). A codegen step adds a build stage and makes the security-critical file less readable, for about 15 verbs.
- **Fix:** keep the preload hand-written. Keep the unit test "exposed keys === verb table", which already catches drift.

**S7. Proportion: the counts are understated, and the estimate omits new tests.**

- **Location:** §1 "Cost: ≈ 12 lint entries … five brands …"; Q2 "five brand types"; the 0.5 O-d effort line.
- **Problem:**
  - The file names **seven** brands: `BranchName`, `RepoSlug`, `TrustedRepo`, `IssueNumber`, `FreeText`, `Confirmed`, `DistroName`.
  - The §1/§5/§7 lint entries count about 16: `dangerouslySetInnerHTML`, 4 HTML sinks, `createPolicy`, `fixture/**`, `new BrowserWindow`, `ipcRenderer`, `ipcMain`, `shell`, `child_process`/`utilityProcess`, `node:fs`, `dialog`, `setAsDefaultProtocolClient`, `getBuiltinModule`, domain purity.
  - Several tests are new rather than "already in 10 §5": the IPC contract test, the asar fixture listing plus the marker string, the CSP header release assertion, and the `registerSource` traversal e2e. 10 §5 Day 2 lists only the fuse read-back and the debug-port check.

  The structure itself is proportionate. Each choke point is a file the spike writes anyway, and the core-ESLint-only approach matches 02's tested choice.
- **Fix:**
  - Correct the counts.
  - Estimate ≈ 0.5–1 O-d.
  - Trim where the payoff is low:
    - keep `Confirmed`, `TrustedRepo`, `BranchName` and `FreeText`, which each block a named threat;
    - make `RepoSlug`, `IssueNumber` and `DistroName` plain validated values (schema/regex at the IPC edge) unless the argv builder needs them as brands;
    - drop the `__STUDIO_FIXTURE__` marker, since the lint rule plus the asar listing suffice.

## Nice to have

**N1. Standard-scheme claim: the citation overstates.**

- **Location:** §2 "A non-standard scheme serialises to an opaque origin (`null`) … [verified, 9: standard schemes get origin semantics]".
- **Problem:** the protocol doc at `v45.5.0` (lines 94–118) covers relative URLs, the FileSystem API and storage, not origins. The claim is true, though: with `standard: false`, `mainFrame.origin` was `"null"` and the page did not load in my test.
- **Fix:** retag as "[verified: scratch test]", or cite Chromium's url origin rules.

**N2. Confirm the sender check by test, and keep it.**

- **Location:** §2.
- **Evidence:** a `srcdoc` sub-frame of `app://studio/index.html` (with `nodeIntegrationInSubFrames`) reported `origin === 'app://studio'` and reached the handler, and `senderFrame === sender.mainFrame` was `false` for it and `true` for the main frame, including after a reload.
- **Fix:** cite this as direct evidence for the main-frame identity clause, alongside source 17.

**N3. The release assertion versus the Day 5 CDP test build.**

- **Location:** §1 row 9 ("no `remote-debugging-port` switch unless `!app.isPackaged`").
- **Problem:** 10 §5 Day 5 attaches Playwright MCP over CDP to a *test build*, which may be packaged.
- **Fix:** name the mechanism, for example a separate build config or env-gated flag that the release assertion proves absent from release artifacts.

**N4. The choke-point count is inconsistent.**

- **Location:** TL;DR "Eight choke points"; §8 item 1.
- **Problem:** §8 item 1 lists nine globs (it adds external links and the settings store), and Q2 says "Each is one file", yet the transport is a directory.
- **Fix:** align the numbers.

**N5. Pin the fuse read-back tool.**

- **Location:** §4 fuses ("CI reads back with `npx @electron/fuses read`").
- **Problem:** in this repo `npx @electron/fuses` resolves electron-builder's transitive **1.8.0** (`npm ls @electron/fuses`), whose `FuseV1Options` stop at index 7 (no `WasmTrapHandlers`).
- **Fix:** use `npx @electron/fuses@2.1.3 read --app …`.

**N6. A local citation is off by one.**

- **Location:** §4.
- **Problem:** `src/main/main.ts:25` should be `:24` (`void window.loadFile(...)`). The `index.html:5-8` meta CSP citation is correct.

**N7. The sandboxed-preload wording is correct and could be cited more precisely.**

- **Problem:** the sandbox doc at `v45.5.0` (line 53) does say `require` "can only load the `electron` module". No fix is needed, but quoting it would pre-empt the common belief that `events`/`timers`/`url` are still loadable.

## Review resolution
> Date: 2026-11-25 · Fix agent

- **M1** Partially applied: `TRUSTED_TYPES_POLICY: null` dropped everywhere (confirmed in `purify.es.mjs:1864-1871`). But the review's safety reason is wrong for 3.5.0: DOMPurify creates `dompurify` lazily on first `sanitize` (`:1166-1169, 1456`), not at import. So the default is the review's tested variant (b), a module-private `studio-purify` pass-through created when `policy.ts` loads. CSP updated to `trusted-types studio-html studio-purify`; (a) kept as the fallback in Risk 2.
- **M2** Applied: fixed `ALLOWED_ATTR` added (markdown-it tables also emit `style=`, `:2190, 2224`). Gate redefined as 0 TT violations / executions / off-origin requests / `javascript:` hrefs, with `*-src-attr` reports recorded only. The deviation from 10 §5 is recorded for 07 (Risk 9).
- **S1** Applied: recommends (b), the dev origin only when `!app.isPackaged` plus a release assertion. TL;DR, §2, §4, §5 and Q5 updated. 06 is being revised concurrently, so the remaining cross-file alignment is an open item for 07 (Risk 8).
- **S2** Applied: process cwd is always `$HOME`, and the repo goes in `git -C`, `devscene --cwd` or `gh --repo`. WSL uses `--cd ~`. Added a unit assertion that no `Command` has a repo cwd.
- **S3** Applied: added rows for item 5 (one `issueNumber`, no gesture-less verb, non-member flag), item 8 (`CLAUDE_CONFIG_DIR` and WSL deny list, watcher and diagnostics exclusion), item 9 (supply chain → repo/CI config), item 4 (WSL-side reader) and item 11 (`answer`/`resume` absent until H1+H1′, H2, H12).
- **S4** Applied: compatibility retagged as "0.x types only, package and compiler renamed". Added the `@sinclair/typebox` lint ban and the `typebox/schema` import. Dropped the CommonJS clause; the single-maintainer point is kept.
- **S5** Applied: the contract benefit is now conditional on F-1. Types are stated: IPC uses TypeBox in `src/shared/contract/` with `Static`; harness types are generated into 02's `adapters/harness/schema/` from the same JSON Schema.
- **S6** Applied: the preload is hand-written as an explicit verb list (01 §4). The keys === channel table test is kept.
- **S7** Partially applied: counts corrected (≈ 16 lint entries), new tests acknowledged, estimate now 0.5–1 O-d. Brands trimmed to `Confirmed`/`TrustedRepo`/`BranchName`/`FreeText`. The fixture marker is kept instead of the asar listing, because under 02/06's single-entry `__BROWSER_MODE__` design only a marker catches fixture code inlined into a chunk (06 already proposes it).
- **N1** Applied: retagged to the review's scratch test (source 24).
- **N2** Applied: the sub-frame evidence is cited in the §2 rule.
- **N3** Applied: the Day 5 CDP build is the unpackaged `dist/` (as with 06's `_electron` runs), and the release assertion covers packaged artifacts only.
- **N4** Applied: nine choke points, consistent across TL;DR, §8 and Q2, each "one file or one directory".
- **N5** Applied: `npx @electron/fuses@2.1.3 read --app …` (repo resolves 1.8.0, re-checked).
- **N6** Applied: `main.ts:24` (re-checked).
- **N7** Rejected (no change needed): the row already cites source 13 and the review confirms the wording.
- **Alignment with 02** (from the dispatch): every path now uses 02's tree (`src/shared/{domain,contract}`, `main/window`, `main/ipc`, `main/process`, `main/adapters/{electron,fs,transport}`, `renderer/markdown`, `renderer/studio`). §8 became "Fit with 02", with one remaining ask: only `runner.ts` may import `adapters/transport/`. It also answers 02's question: no preload row and no security reviewer.
