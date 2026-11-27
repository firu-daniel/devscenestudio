# 05 — Security architecture
> Status: reviewed · Date: 2026-11-25 · Area owner: research agent

## TL;DR

- **08 decided what; this file decides where.** Every item of the v1 bar (10 §6) maps to one *choke point*: a single module that is the only place a dangerous capability can be reached. Each choke point gets a compile-time guard (a branded type or a lint ban) and a runtime check, plus a test suite (§1 table). The architecture enforces the bar by making the unsafe path fail to compile or fail lint, not by asking reviewers to remember it. Paths follow 02's tree (`src/shared/{domain,contract}`, `src/main`, `src/preload`, `src/renderer`). [inferred]
- **Nine choke points, each one file or one directory in 02's tree:**
  1. hardening (`src/main/window/`: webPreferences, session policy, CSP string, app origin);
  2. the `app://` source (`src/main/window/appProtocol.ts`);
  3. IPC registration (`src/main/ipc/register.ts`: sender origin + schema + size cap + closed error codes);
  4. confirm (`src/main/adapters/electron/confirm.ts`: OS-native modal; act services need its `Confirmed` brand);
  5. external links (`src/main/adapters/electron/externalLinks.ts`);
  6. processes (`src/main/process/` argv + runner, the only user of `src/main/adapters/transport/`, the only `child_process` importer; env allowlist; cwd always `$HOME`);
  7. the confined file reader (`src/main/adapters/fs/`);
  8. the repo trust gate (`src/main/app/repos.ts`, `TrustedRepo` brand; persisted by the settings store in `adapters/fs/`);
  9. the renderer HTML sink (`src/renderer/markdown/`: `SafeMarkdown`, the only Trusted Types policies).
- **IPC validation: TypeBox 1.x (1.4.7, 2026-11-12) in the main process only.** Its schemas *are* JSON Schema, and `Schema.Compile` takes plain draft-07…2020-12 schemas. The harness uses draft-07 JSON Schema for its config today and plans one for `runs --json` (10 §8 F-1); TypeBox compiled both existing harness schemas unchanged in a scratch test (review, 2026-11-25). So one validator *can* cover IPC arguments, the future harness contract, branch-committed JSON and Studio's settings file, but the contract benefit is conditional on F-1 shipping a JSON Schema. zod 4.6.7 is the close second: the owner knows zod (expause_web uses zod 3), but it only *converts* from JSON Schema. Branch names and the trust/confirm brands stay hand-written domain parsers. [verified versions; inferred choice]
- **Changes since 08 (2026-11-12) that alter the build:**
  - **DOMPurify 3.5.0 (2026-11-22) ends the 3.4.x line** ("There will be no further 3.4.x release"), and two new advisories (GHSA-qm7q, GHSA-hrxw) need 3.4.18/3.5.0. Raise the floor to **≥ 3.5.0**. Both are `SAFE_FOR_TEMPLATES`-only, which we don't use. [verified, 3, 4]
  - **Do not follow DOMPurify's README advice `TRUSTED_TYPES_POLICY: null` here.** With `null`, DOMPurify hands a raw string to `DOMParser.parseFromString` (a Trusted Types sink) and falls back to `innerHTML`; under our `require-trusted-types-for 'script'` both throw, and the sanitiser returns an empty string (review's Electron 45.5.0 test; `purify.es.mjs:1864-1871`). Instead give DOMPurify a module-private pass-through policy (§3). [verified, 5, 24]
  - **Electron checklist #17 now validates `senderFrame.origin`, not the URL, and handles a `null` frame.** The doc changed in electron/electron#53684 (2026-09-07); 08's "`senderFrame.url` origin" wording predates it. [verified, 1, 8]
  - **New in Electron 45: `protocol.registerSource()` (Experimental).** It serves a directory with traversal confinement done by Electron, per-route `headers` (so the CSP goes in as a header) and no main-thread JS. It replaces most of the hand-written `protocol.handle` that 08 E12 worried about. [verified, 9]
  - **Vite GHSA-p4f5-76q4-ffq7 (critical, 2026-11-10):** RCE on the dev server, but only when it is exposed with `--host`. Browser mode must never use `--host`, and Vite must be ≥ 8.3.7. [verified, 14]
  - The fuse list is unchanged: 9 fuses in `@electron/fuses` 2.1.3. The Electron 45 checklist still has 20 items. [verified, 1, 10, 11]
- **The trust boundary is the preload/IPC seam, and every act is re-derived in main.** The renderer sends ids, never facts: `startRun({repoId, issueNumber, expectedUpdatedAt})`. Main re-fetches the issue, builds the provenance and exact text, shows the native modal from that, and only then calls the runner. A compromised renderer can request; it cannot describe what it requests. [inferred]
- **Issue #1's "Data source" trust rules are pure domain functions** (`isTrustedProgressComment`, `resolveRunStatus`, `parseBranchAnalytics`). They run in main, where the GitHub data arrives, are unit-tested with no I/O, and their output is what the renderer shows. [inferred]
- **Browser mode is a build-time fork, not a runtime flag.** `src/renderer/main.tsx` picks the adapter behind a compile-time constant (`__BROWSER_MODE__`, 01/02/06), so the production build drops `studio/fixture.ts`; CI asserts the packaged renderer holds no fixture marker string. Browser mode never bridges to a real main process; doing so would recreate the local web app that 08 graded riskiest. [inferred]
- **Electron dev loop: allow the Vite dev origin only when `!app.isPackaged`** (06's `scripts/dev.mjs` HMR loop), with a release assertion that the packaged origin list is `app://studio` alone. The earlier "dev Electron also loads `app://`" plan conflicted with 06 and cost HMR in the window; the guarded second origin is defensible for a one-developer app. 07 must confirm both files agree (open item). [inferred]
- **Studio holds no secrets.** The gh token stays inside `gh`, and Claude's credentials are never read. `safeStorage` is not needed in v1. Its one security-relevant persisted datum, the repo trust list, lives in a `0700` userData dir and is schema-validated on read. [inferred; safeStorage behaviour verified, 12]

## Scope

Covers: where each v1 bar item lives (layer, process, module), how the structure stops it being bypassed, IPC validation library choice, untrusted-data flow, Electron hardening placement, browser-mode risks, secrets and persistence, and how the security CI suites attach to layers.

Not here:
- the threat model and the bar itself: 08 §1–§3, §6.2 and 10 §6, taken as given;
- IPC primitives (`invoke`/`send`/`MessagePort`, utility process): see 01;
- the folder tree: see 02 (paths below follow 02's reviewed tree; §8 checks the fit);
- the reactive flow: see 03;
- performance: see 04;
- test tooling detail (runner, Playwright config): see 06.

## Findings

### 1. The bar, placed

Paths follow 02's tree; `src/` is omitted in the table. "Lint" means ESLint 10 core rules (`no-restricted-imports`, `no-restricted-syntax`, `no-restricted-properties`) with per-file `files`/`ignores` overrides: no plugin needed [verified, 15]. "Brand" means a TypeScript branded type that only one function can produce.

| 10 §6 item | Process / layer | Module | How the architecture enforces it | Test | Spike day |
|---|---|---|---|---|---|
| 1 Markdown → DOMPurify → Trusted Types | Renderer / UI rendering | `renderer/markdown/SafeMarkdown.tsx`, `renderer/markdown/policy.ts` | Only file allowed `dangerouslySetInnerHTML` (lint, `no-restricted-syntax` on `JSXAttribute[name.name='dangerouslySetInnerHTML']`); `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` banned in the renderer (lint); **runtime:** CSP `require-trusted-types-for 'script'; trusted-types studio-html studio-purify` makes any other sink throw. React 19.3.1 assigns `__html` straight to `innerHTML`, so a `TrustedHTML` passes through [verified, 6] | XSS corpus (Playwright) | 1 |
| 1 No remote images, links `https:` only | Renderer / UI rendering | `SafeMarkdown` config (`ALLOWED_URI_REGEXP`, image → link rewrite); CSP `img-src 'self' data:` | Same single sink; CSP is the second layer | XSS corpus | 1 |
| 1 Closed-palette ANSI, OSC/DCS dropped | Renderer / UI rendering | `renderer/markdown/ansi.ts` (pure parser → `{text, cls}[]`) + the log-tail `LogLine` (text nodes only) | Parser output has no HTML type; React text interpolation only | Unit (parser) + corpus ANSI rows | 1 |
| 1 Bidi/invisible as glyphs | Main (modal text) + renderer (answer form) | `shared/domain/text.ts` → `revealInvisible` (pure) | One function used by both the confirm adapter and the answer view | Unit | 2 (modal) |
| 1 CSP | Main (header) / build (browser mode) | `CSP` constant in `main/window/hardening.ts`, consumed by the `app://` source headers and by the Vite preview server | One constant, imported in both places; never a `<meta>` in the shipped HTML | Corpus counts TT violations; release assertion reads the header | 1 (preview), 2 (app://) |
| 2 contextIsolation, sandbox, nodeIntegration off | Main / window | `main/window/hardening.ts` → `secureWebPreferences` | Only `main/window/` may call `new BrowserWindow` (lint, `no-restricted-syntax` `NewExpression[callee.name='BrowserWindow']`); `app.enableSandbox()` as a global backstop [verified, 13] | Unit: snapshot of `secureWebPreferences` | 2 |
| 2 Intent-only preload | Preload (harness `general` row, 02 §4) | `preload/preload.ts`, **hand-written**: an explicit object literal listing each verb `satisfies StudioApi` (01 §4) | `ipcRenderer` import banned outside the preload (lint); each verb binds to `ipcRenderer.invoke(channel, arg)`; push callbacks strip the event object (checklist #20 [verified, 1]); the sandboxed preload can only `require('electron')` anyway [verified, 13]. No codegen: a literal list is the most reviewable form of the security-critical file | IPC contract test: exposed keys === the contract's channel table | 2 |
| 2 Sender-frame check | Main / IPC | `main/ipc/register.ts` | The **only** `ipcMain` importer (lint). Every handler goes through `register(verb, schema, service)`, which checks `frame && APP_ORIGINS.includes(frame.origin) && frame === event.sender.mainFrame` | IPC contract test: forged origin, sub-frame and `null` frame rejected; every verb has a schema | 2 |
| 2 Fuses | Packaging | `electron-builder.yml` → `electronFuses` (supported in 26.18.1 [verified, 16]) | One config block; CI reads back with `npx @electron/fuses@2.1.3 read --app …` (unpinned `npx` resolves electron-builder's transitive 1.8.0) | Release assertion | 2 |
| 2 Confined `app://` | Main / window | `main/window/appProtocol.ts` | `protocol.registerSource` (Electron confines) or `protocol.handle` with `path.relative` confinement; `standard: true, secure: true`, no `bypassCSP` | Traversal e2e (`app://studio/../…`, encoded) → no file | 2 |
| 2 Navigation / window-open / permissions denied | Main / window | `hardening.ts` → `applySessionPolicy()` + `app.on('web-contents-created')` | Applied to **every** webContents in one listener, so a future window can't forget it | Unit (handler returns deny); e2e: clicking a log link opens nothing in-app | 2 |
| 2 External links | Main / adapters | `main/adapters/electron/externalLinks.ts` | `electron`'s `shell`/`dialog` usable only in `adapters/electron/` (lint; 02 §5 already confines `electron` there); `https:` + host allowlist | Unit: `file:`, `smb:`, `ms-msdt:` refused | 2 |
| 3 One argv builder, `--end-of-options`, `--` for gh | Main / process | `main/process/argv.ts` (pure builders) | Takes `BranchName`/`TrustedRepo` brands; repo slugs, issue numbers and distro names are plain values validated by schema/regex at the IPC edge | argv fuzz (fast-check 4.11) | 2 |
| 3 One spawn site; env allowlist; never `claude`; cwd outside the repo | Main / process + adapters | `main/process/runner.ts` → `main/adapters/transport/` | **Only `adapters/transport/` imports `child_process`/`node:child_process`** (and `utilityProcess`, if 01's reserve is used), and only `runner.ts` imports `adapters/transport/` (lint). The env is built in the runner from the allowlist; executables come from a closed `KnownExe` union (`gh`/`git`/`devscene`/`wsl`) resolved at startup, `devscene` by absolute path. **Process cwd is always `$HOME`**: the repo goes in `git -C <TrustedRepo>`, `devscene --cwd`, `gh --repo` (10 §6 item 6, 08 §3.11) | Fuzz + hostile-repo fixture; unit: no `Command` has a repo cwd | 2 |
| 3 `Direct \| Wsl` transport | Main / adapters | `main/adapters/transport/{direct,wsl}.ts` behind `Transport` | The builder produces a transport-neutral `Command`; `WslTransport.wrap()` adds `-d <distro> --cd ~ --exec`, and **re-checks** that every arg is metacharacter-free (it crosses a command-line string) | Fuzz incl. mocked `wsl.exe` (`CommandLineToArgvW`) on a Windows runner | 2 (Direct), Windows runner later (Issue #1 item 4) |
| 3 Free text via stdin / `0600` file | Main / process | `Command.stdin` field | No argv slot accepts the `FreeText` brand (type) | Fuzz assertion (b) | 2 |
| 4 Realpath-confined reader | Main / adapters | `main/adapters/fs/confinedReader.ts` | Run-file reads only through it; `node:fs` banned outside `main/adapters/fs/` (lint). **On Windows** its implementation runs inside WSL through the transport, never over `\\wsl$` | Traversal + swap-race tests | post-spike (spike log tail reads a child's stdout) |
| 5 OS-native confirmation | Main / app + adapters | `Confirm` port (`main/ports/`) → `main/adapters/electron/confirm.ts` (`dialog.showMessageBox`) | Act services take a `Confirmed<ActPreview>` brand that only a `Confirm` implementation returns; `dialog` only in `adapters/electron/` (lint). The renderer has no `confirmed` field to forge | Unit: act without brand doesn't compile; e2e: XSS calling `startRun` still shows the modal | 2 |
| 5 Provenance + exact text; non-member warning | Main / app | `main/app/intents.ts` builds `ActPreview` from **main's own fetch**, including the non-member flag from the re-fetched `author_association` | Renderer args are ids + `expectedUpdatedAt` only (schema) | Unit with fixture gh responses | 2 |
| 5 No auto-start, no batch start | Contract + main | `startRun` schema takes exactly one `issueNumber` (no array); no verb starts anything without a user gesture | Schema + verb table | IPC contract test | 2 |
| 5 Global stop | Main / app | `main/app/intents.ts` (`stopAll`) | Not confirm-gated (stopping is safe) | e2e | post-spike (needs harness verb, D6) |
| 6 Repo trust gate | Main / app + adapters | `main/app/repos.ts` | `TrustedRepo` brand produced only by `repos.require(realpath)`; the argv builder's repo slots take `TrustedRepo` | Hostile-repo fixture | Type on Day 2; store post-spike |
| 7 GitHub-state trust rules | Shared / domain | `shared/domain/trust.ts` (pure) | Called by the read-model in main (`main/app/runs.ts`); renderer receives the classified result | Unit (table-driven) | post-spike (spike makes one `gh` read) |
| 8 Secret masking, never `.stream.jsonl` | Domain (masker) + main (reader) | `shared/domain/text.ts` → `maskSecrets`; the log source in main never opens `*.stream.jsonl` (allowlist of file names) | Masking applied in main before data crosses IPC, so the renderer never holds the secret | Unit (pattern corpus) | 2 (log tail) |
| 8 Never read `~/.claude*` or `CLAUDE_CONFIG_DIR`, incl. inside WSL; excluded from watchers and diagnostics | Main / adapters | `adapters/fs/` reader and watcher roots | Both resolve `~/.claude*` and `CLAUDE_CONFIG_DIR` (host and WSL side) into a deny list checked after realpath; the diagnostics writer uses the same list. No API takes a free path | Unit (deny list) + CI grep `\.claude` / `credentials.json` in `src/` | 2 |
| 9 No debug port, no URL scheme | Main / window + packaging | `main/window/` adds `remote-debugging-port` only when `!app.isPackaged`; no `setAsDefaultProtocolClient` (lint). Day 5's CDP test build is the **unpackaged** `dist/` (06 runs `_electron` there for the same fuse reason), so no release artifact carries the switch | Lint + release assertion on the packaged artifacts | Release assertion | 2 |
| 9 Signed builds / Linux verify hook | Packaging | electron-builder config + updater hook module | Out of this file's structure; see 08 §3.6 | Day 3 tamper test | 3 |
| 9 Supply chain (lockfile, `--ignore-scripts`, 7-day cooldown, SHA-pinned actions, zizmor), 14-day patch cadence | Repo / CI config (not a code layer) | `package-lock.json`, `.npmrc`, `.github/workflows/` | Owned by the repo/CI setup, not by a code layer; listed so 07 assigns it | zizmor in CI | 1 (lockfile, `.npmrc`), later CI |
| 10 Anthropic invariants | All | No module may reference `claude` as an executable (`KnownExe` excludes it); no Claude sign-in UI or token capture | Type + CI grep | CI grep | 2 |
| 11 Harness blockers H1/H1′ | Contract + main | `answer`/`resume` verbs are **absent** from the contract's channel table until H1 + H1′ ship | Cheapest architectural enforcement of a release blocker | IPC contract test asserts the verbs are absent | 2 |
| 11 H2, H12 | Main / app | No API-key configuration verb; auto-doctor never runs on an untrusted repo (needs `TrustedRepo`, item 6) | Verb table + brand | IPC contract test | post-spike |

**Cost:** ≈ 16 lint entries in one flat-config block (`dangerouslySetInnerHTML`, 4 HTML sinks, `createPolicy`, `studio/fixture*`, `new BrowserWindow`, `ipcRenderer`, `ipcMain`, `shell`/`dialog`, `child_process`/`utilityProcess`, transport import, `node:fs`, `setAsDefaultProtocolClient`, `getBuiltinModule`), four brands (`Confirmed`, `TrustedRepo`, `BranchName`, `FreeText`, each blocking a named threat), one registration wrapper. Several tests are new rather than already in 10 §5 (IPC contract test, fixture marker, CSP header assertion, `registerSource` traversal e2e). Most entries overlap 02 §5's import rules. **Buys:** every bypass is a lint or type error that the harness reviewers and CI catch mechanically. [inferred]

**Limit:** lint sees only our source. A dynamic `require`, `process.getBuiltinModule('child_process')` (Node ≥ 22.3) or a dependency that spawns (electron-updater does) is not caught. Hence `getBuiltinModule` in the `no-restricted-properties` list. Dependencies are a supply-chain matter (08 §3.7). [inferred]

### 2. The trust boundary as an architectural seam

```
renderer (untrusted: assume XSS)           preload (sandboxed)             main (trusted)
  StudioApi port ── window.studio.startRun({repoId, issueNumber, expectedUpdatedAt})
                                    ── ipcRenderer.invoke('startRun', arg) ──►
                                                                    main/ipc/register.ts:
                                                                      1 frame && APP_ORIGINS.includes(frame.origin)
                                                                        && frame === sender.mainFrame
                                                                      2 schema (TypeBox) + byte cap
                                                                      3 service: main/app/intents.ts startRun(arg)
                                                                          re-fetch issue (gh) → ActPreview
                                                                          confirm port → native modal → Confirmed
                                                                          argv.build(...) → runner.run(cmd)
                                                                      4 map errors → closed codes (Result, 02 §6)
```

Rules (each is a check in `register.ts` or a type):

| Rule | Why here | Cost |
|---|---|---|
| Origin, not URL; `null` frame rejected; main frame only | Checklist #17 as of electron#53684: "Use the origin, not the URL: `about:blank`, `blob:` and sandboxed documents have URLs that do not identify who controls them, and the frame may be null" [verified, 1, 8]. `frame.origin` of a child `about:blank` window returns the *parent's* origin [verified, 17], so the main-frame identity check is what excludes child windows. Direct evidence (review's Electron 45.5.0 test): a `srcdoc` sub-frame of `app://studio/index.html` reported `origin === 'app://studio'` and reached the handler, and `senderFrame === sender.mainFrame` was `false` for it and `true` for the main frame, also after a reload [verified, 24] | 3 lines |
| `APP_ORIGINS` = `['app://studio']` in packaged builds; plus the Vite dev origin only when `!app.isPackaged` | 06's dev loop serves the Electron window from `http://localhost:<port>` for HMR. The guard keeps it out of release builds; a release assertion checks the packaged list holds `app://studio` alone | 2 lines + 1 assertion |
| `app` scheme registered `standard: true` | A non-standard scheme serialises to an opaque origin (`null`), and the origin check would then be meaningless. With `standard: false`, `mainFrame.origin` was `"null"` and the page did not load (review's Electron 45.5.0 test) [verified, 24] | none |
| One argument object per verb, schema-validated, size-capped (e.g. 256 KB, matching 08 §5.3) | Main is the only process allowed to trust; the renderer may send anything | ≈ 1 schema per verb |
| Ids in, facts derived in main | The modal must show what *main* fetched, or an XSS controls the text the human approves | Re-fetch costs one `gh` call per act (acceptable: acts are rare) |
| Errors leave as `{code: 'stale'\|'untrusted_repo'\|'invalid'\|…}` | Raw `Error.message` leaks paths and stderr into a page that may be XSS'd | A small enum |
| No generic verbs (`exec`, `readFile`, `openPath`) | 08 E1 | – |

**Validation library.** Validation runs in main only (the preload can't load modules beyond `electron`, and the renderer is untrusted, so validating there buys nothing). Bundle size and CSP `eval` limits therefore don't matter.

| | zod 4.6.7 | valibot 1.5.0 | TypeBox 1.4.7 | hand-written guards |
|---|---|---|---|---|
| Last release | 2026-10-12 | 2026-09-09 | 2026-11-12 | – |
| JSON Schema | `toJSONSchema` and `fromJSONSchema` (conversion) [verified, 18] | export only (separate package) | **is** JSON Schema; `Schema.Compile` takes plain draft 3…2020-12 schemas, tested on the official suite [verified, 19] | none |
| TS inference | excellent | excellent | good (`Static<>`) | manual, drifts |
| Module format / TS | dual / any | dual / any | **ESM only**, TS 6.0–7.0+ [verified, 19] | – |
| Familiarity | owner uses zod 3 in expause_web (`package.json:35`) | low | low. 1.x keeps "backwards compatibility with `0.x` **types**" only: the package was renamed (`typebox`, not `@sinclair/typebox`, whose 0.34.x stays published as LTS) and the compiler moved to `import Schema from 'typebox/schema'` (`Schema.Compile`), so agents trained on 0.x will write the old imports [verified, 19] | – |
| Fit here | IPC: great. Harness contract: needs codegen or the converter | IPC only | **IPC + (future) harness `--json` + branch JSON + settings with one validator** | fine for 1–2 primitives only |

**Pick TypeBox 1.x.** Cost: one ESM-only dependency, which is not a problem here: Electron 45.5.0's Node 24 loads it via `require(esm)` from a CommonJS main (review's test), and 06 bundles main with esbuild anyway. A smaller ecosystem than zod. Buys, if F-1 ships a JSON Schema: the harness's schema validates as-is, so the generated harness types in `src/main/adapters/harness/schema/` (02 §2) and the runtime check come from one file, with no second schema to drift. That benefit is conditional; **switch to zod 4** if the harness ends up publishing TS/zod types instead. Where the types come from:
- **IPC payloads:** TypeBox schemas authored in `src/shared/contract/` (02 lists "validators" there), TS types by `Static<typeof X>`. Main compiles and runs them; the renderer and preload use `import type` only. Keep the schemas in their own file, apart from the channel names, so a bundled preload never pulls in `typebox`.
- **Harness output:** TS types generated from the harness's JSON Schema into `adapters/harness/schema/`, and the same JSON file compiled by `Schema.Compile` at runtime.

Lint: add `@sinclair/typebox` to `no-restricted-imports`. `BranchName` stays a hand-written brand, because it carries `git check-ref-format`, which no schema expresses. Repo slugs, issue numbers and distro names are plain schema/regex-validated values at the IPC edge. [inferred]

**The argv builder and transport, structurally:**

```ts
// src/shared/domain: brand types, pure shape check
type BranchName = string & { readonly __brand: 'BranchName' };
export function isBranchShape(s: string): boolean { /* 08 §3.2 rule 2 regex */ }
// src/main/process/argv.ts: pure, no I/O; cwd is always HOME, the repo goes in -C
export const gitShowRef = (repo: TrustedRepo, b: BranchName): Command =>
  ({ exe: 'git', args: ['-C', repo, ...GIT_HARDENING, 'show-ref', '--end-of-options', b], cwd: HOME });
// src/main/process/runner.ts: the only importer of adapters/transport (which alone imports child_process)
export function run(cmd: Command, t: Transport): Child { const env = buildEnv(ALLOWLIST); return t.spawn(cmd, env); }
```

`check-ref-format` needs a spawn, so the domain only checks the shape. The builder module exposes `validateBranch(candidate): Promise<BranchName>`, which runs `git check-ref-format --branch` through the runner with a fixed argv. Only that function mints the brand. [inferred]

### 3. Untrusted data flow

| Input (08 §1.3) | Enters at | Classified / sanitised at | Reaches renderer as | Rendered by |
|---|---|---|---|---|
| Issue title/body, PR text, comments, `question_<n>.md` | `gh` adapter (main) | Main: size cap; provenance fields attached; **not** sanitised (the renderer sanitises at the sink) | `{markdown: string, provenance}` | `SafeMarkdown` only |
| Progress comment (GitHub read model) | `gh` adapter | `shared/domain/trust.ts`: `isTrustedProgressComment(c)` = `c.user.login === 'github-actions[bot]'` **and** the exact marker shape | `{status, source: 'bot'\|'ignored'}` | Badge |
| Labels vs Actions run state | `gh` adapter | `resolveRunStatus(actionsRun, labels)`: Actions wins; mismatch → `warning` | `{status, warning?}` | Badge |
| `run_analytics/` JSON on a branch | `gh`/git adapter | Schema (TypeBox) + size cap; `parseBranchAnalytics` keeps **numbers only** | numbers | Plain text |
| `registry.json`, `status.json` | `adapters/fs` (main) | Schema; paths kept only if inside the validated `stateDir` (08 §3.3) | ids, statuses (no paths) | – |
| Run log lines (child stdout / file) | runner / confined reader | `shared/domain/text.ts` `maskSecrets`, run in main; ANSI kept raw | `string` lines | `ansi.ts` → `LogLine` (text nodes) |
| `harness.config.json` of a detected repo | `adapters/fs` | Schema; `stateDir`/`scriptsDir` relative, no `..`, realpath inside the repo | – | – |

Placement rules:
- **Sanitise at the sink, classify at the source.** HTML sanitisation happens once, in the renderer's `SafeMarkdown`, because that is the only place the DOM and Trusted Types exist, and a sanitised string carried across IPC could be mis-rendered elsewhere. *Trust* decisions (who wrote it, which source wins) happen in main, in pure domain functions, before data crosses IPC. The renderer never decides trust. [inferred]
- **Masking happens in main.** It is display hygiene (08 §3.8), but doing it before IPC means a renderer compromise can't read unmasked secrets either. "Reveal" is a verb that returns one unmasked span after a click. [inferred]
- **The rendering layer has no other HTML path.** `SafeMarkdown`'s pipeline: `markdown-it` 15.0.3 (`html: false`, `linkify: true`; its `validateLink` already rejects `javascript:|vbscript:|file:|data:` except four image types [verified, 20]) → DOMPurify ≥ 3.5.0, default mode, fixed `ALLOWED_TAGS` **and** fixed `ALLOWED_ATTR` (`href`, `title`, `class`, `alt`), `ALLOWED_URI_REGEXP = /^(https:|#)/` → returned as `TrustedHTML` from **our** policy:

```ts
// src/renderer/markdown/policy.ts: the only createPolicy calls (lint)
// CSP: trusted-types studio-html studio-purify
const purifyTT = trustedTypes.createPolicy('studio-purify', {  // module-private pass-through for DOMPurify's own parse
  createHTML: (s) => s, createScriptURL: (s) => s,
});
export const html = trustedTypes.createPolicy('studio-html', {
  createHTML: (md) => DOMPurify.sanitize(mdit.render(md), { ...CFG, TRUSTED_TYPES_POLICY: purifyTT }), // RETURN_TRUSTED_TYPE stays false
});
```

Why not the README's `TRUSTED_TYPES_POLICY: null` [verified, 5]: with `null`, DOMPurify passes a raw string to `DOMParser.parseFromString`, itself a Trusted Types sink, then falls back to `documentElement.innerHTML` (`purify.es.mjs:1864-1871`). Under `require-trusted-types-for 'script'` both throw, and the review's Electron 45.5.0 test returned an **empty string** plus two TT violations. Two variants rendered `<b>hi</b><img src="x">` with no TT violation: the module-private policy above, and omitting the option while adding `dompurify` to `trusted-types` [verified, 24]. Pick the module-private one: DOMPurify 3.5.0 creates its `dompurify` policy **lazily** on the first `sanitize` call (`_getDefaultTrustedTypesPolicy`, `purify.es.mjs:1166-1169, 1456`), not at import, whereas `policy.ts` claims both names when the module loads, before any data renders. Without `'allow-duplicates'` no later script can claim them again, and the pass-through reference never leaves the module. The corpus re-checks this on Day 1.

**Why `ALLOWED_ATTR`:** default DOMPurify keeps `style`, and markdown-it itself emits `style="text-align:…"` on table cells (`dist/markdown-it.cjs.js:2190, 2224`). Under `style-src 'self'` every such attribute fires a `style-src-attr` report. Dropping `style` loses table alignment and nothing else. [verified, 20, 24]

### 4. Electron hardening placement (single source of truth)

`src/main/window/hardening.ts` exports four things and nothing else configures security:

| Export | Content | Consumed by |
|---|---|---|
| `APP_ORIGINS` | `['app://studio']`; plus the Vite dev origin only when `!app.isPackaged` (§2) | `ipc/register.ts`, `window/appProtocol.ts`, window creation (`loadURL` accepts only these) |
| `CSP` | `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; require-trusted-types-for 'script'; trusted-types studio-html studio-purify` | `app://` route headers; Vite preview config (browser mode); release assertion |
| `secureWebPreferences(preloadPath)` | `contextIsolation: true, sandbox: true, nodeIntegration: false, webSecurity: true, webviewTag: false, navigateOnDragDrop: false, spellcheck: false` | `src/main/window/` only |
| `applySessionPolicy(app)` | `setPermissionRequestHandler` → deny; `setPermissionCheckHandler` → false; `setDevicePermissionHandler` → false; `web-contents-created` → `will-navigate`/`will-frame-navigate`/`will-redirect` preventDefault (unless same-origin reload), `setWindowOpenHandler` → `externalLinks.open(url)` + `{action:'deny'}` (no `will-navigate` exception for the dev origin beyond same-origin reload), `will-attach-webview` preventDefault | `main.ts` once, before the first window |

Notes:
- `connect-src 'none'`: the renderer fetches nothing; all data comes over IPC. Browser mode's fixture adapter is in-bundle, so it needs no network either. The dev-server CSP (06 Risk 1: relaxed in serve mode for the Fast Refresh preamble) applies only to `vite` serve; the shipped and `vite preview` CSP is this constant. [inferred]
- **The CSP constrains the UI-library choice (D11, 02):** `style-src 'self'` forbids runtime CSS-in-JS that injects `<style>` tags (emotion, styled-components) unless it is given a nonce. React's `style={{}}` goes through CSSOM and is allowed. Prefer a library with static CSS. [inferred]
- **CSP delivery: header, not meta.** The checklist calls the header "preferred" and meta a fallback for `file://` [verified, 1]. `frame-ancestors` is ignored in a meta tag [verified, 21]. Today's `src/renderer/index.html:5-8` carries a meta CSP without Trusted Types; Day 2 moves it to the header. Keeping the meta too is harmless (both apply), but then the two must match. Drop the meta once the header is in.
- **`app://` source: prefer `protocol.registerSource` (Electron 45, Experimental).** Each route has a `root`, an `index` and `headers`. "A path that resolves outside `root` … fails", and "no request touches the main thread" [verified, 9]. That moves E12's confinement from our code into Electron's, and the CSP rides in `headers`. Cost: an Experimental API can change in a minor release, which would mean rewriting about 15 lines in one file. Fallback: the documented `protocol.handle` + `path.relative` pattern [verified, 9]. The traversal test stays either way. [inferred]
- **Fuses** (in `electron-builder.yml`, `electronFuses`):

  | Fuse (9 in `FuseV1Options` [verified, 11]) | Default | Set | Note |
  |---|---|---|---|
  | `RunAsNode` | on | **off** | Use `utilityProcess` if 01 needs a Node child [verified, 10] |
  | `EnableCookieEncryption` | off | on (optional) | No cookies used; harmless |
  | `EnableNodeOptionsEnvironmentVariable` | on | **off** | Also disables `NODE_EXTRA_CA_CERTS` for *Studio's own* main process [verified, 16]. Children still get it via the env allowlist (08 §1.4) |
  | `EnableNodeCliInspectArguments` | on | **off** | |
  | `EnableEmbeddedAsarIntegrityValidation` | off | **on** | macOS and Windows only; **no effect on Linux** [verified, 10] |
  | `OnlyLoadAppFromAsar` | off | **on** | |
  | `LoadBrowserProcessSpecificV8Snapshot` | off | off | Not needed without a custom snapshot |
  | `GrantFileProtocolExtraPrivileges` | on | **off** | "If you aren't serving pages from `file://`, you should disable this fuse" [verified, 10] |
  | `WasmTrapHandlers` | on | on | Not exposed by electron-builder 26.18.1's `FuseOptionsV1` [verified, 16]; leave it at the default |

  The repo has no fuse config yet (`electron-builder.yml` has no `electronFuses`), and `src/main/main.ts:24` still uses `loadFile`. That is fine for Day 0, but Day 2 must flip both, because `GrantFileProtocolExtraPrivileges=false` assumes no `file://` pages.

### 5. Browser mode

| Risk | Control | Enforced by |
|---|---|---|
| Fixture IPC ships in the packaged app | `src/renderer/main.tsx` imports `studio/fixture.ts` only through a dynamic import behind the compile-time `__BROWSER_MODE__` constant (01 §5, 06), so the Electron build drops it; fixture data sits in `studio/fixtures/` | Lint: nothing but `main.tsx` imports `studio/fixture*`. Release assertion: the packaged renderer bundle has no fixture marker string (06's one-line test). That catches fixture code inlined into any chunk, which a file-path listing of `app.asar` would miss, so the marker replaces the asar listing |
| A runtime flag (`?mock=1`, env var) switches a shipped app to fixtures | No runtime switch exists: the constant is replaced at build time; the Electron build throws if `window.studio` is missing rather than falling back (01 §5) | Structure |
| Dev server reachable beyond the machine | Vite binds `localhost` by default; **never `--host`** (GHSA-p4f5-76q4-ffq7: dev-server RCE when exposed, fixed in 8.3.7) [verified, 14]; Vite ≥ 8.3.7 | `vite.config` with `server.host: '127.0.0.1'`, `strictPort` |
| Browser mode grows a "real" backend (proxying to main/gh) | Forbidden: that is 08's local web app, which needs the §2d controls and suite 3 | Conventions doc + review; the `StudioApi` port has exactly two adapters |
| Corpus runs against a weaker CSP than the app | The XSS corpus runs on **`vite preview`** (the production build) with the `CSP` constant as a header, not on the dev server (HMR/react-refresh inject inline scripts that need a relaxed dev CSP) | Playwright config (06) |
| Electron dev window loads `http://localhost` and gets real IPC | Allowed only when `!app.isPackaged` (06's HMR loop): `APP_ORIGINS` gains the dev origin in that case alone, bound to `127.0.0.1` with `strictPort`. A packaged build never trusts it | `APP_ORIGINS` + sender check; release assertion: packaged origin list = `app://studio` |

### 6. Secrets and persistence

- **Holds nothing of Claude's, nor the gh token.** `gh` reads its own `hosts.yml`/keychain; Studio passes `GH_CONFIG_DIR`/`XDG_CONFIG_HOME` through the env allowlist and never reads the token (no `gh auth token` call; lint/CI grep for it). [inferred]
- **What Studio persists** (small JSON in `app.getPath('userData')`, dir `0700`, file `0600`, atomic tmp + rename, TypeBox-validated on read; invalid → defaults plus a warning):
  - the trusted repos (realpath list), which is security-relevant;
  - the selected repo and window state, which are not.

  One module, `src/main/adapters/fs/settings.ts`, owns it behind a port; `main/app/repos.ts` is the only writer of the trust list. The renderer reads settings only through verbs, and trust changes only via a native-confirmed `trustRepo` verb.
- **safeStorage: not needed.** Nothing stored is secret. A same-user process can edit the trust list, but a same-user attacker can already run `devscene` directly, so 08's model doesn't defend against it. safeStorage would add Keychain prompts on macOS and is plaintext (`basic_text`) on Linux without a secret store [verified, 12], so it buys nothing here. Revisit only if Studio ever stores a token (e.g., a GitHub App user token for a hosted mode). [inferred]
- **Crash reports/diagnostics** go through `maskSecrets` + `$HOME → ~` in the same module that writes them, and skip every path on the §1 item 8 deny list.

### 7. CI security suites, attached to layers

| Suite (08 §4.3) | Layer under test | Runs where | Asserts | Day |
|---|---|---|---|---|
| 1 XSS corpus (50 → 150+) | Renderer rendering (`SafeMarkdown`, `LogLine`) | Playwright, browser mode, `vite preview` + `CSP` header | 0 dialogs/executions, 0 off-origin requests, 0 `javascript:` hrefs, **0 `require-trusted-types-for`/`trusted-types` violations** (`securitypolicyviolation` listener). `script-src-attr`/`style-src-attr` reports are recorded, not failed: `DOMPurify.sanitize` alone fires them while parsing a hostile row (its parse document inherits the page's CSP reporting), even though nothing executes [verified, 24]. This narrows 10 §5's "0 CSP violations" wording; 07 should carry the change | 1 |
| 2 argv fuzz (10k/PR) | Main process (`process/argv.ts`, `adapters/transport/wsl.ts`) | Node unit (fast-check 4.11.0); mocked `wsl.exe` on `windows-latest` | Reject or safe argv; free text never in argv; byte-identical round trip | 2 (Direct); Windows job with item 4 |
| 4 Traversal | `window/appProtocol.ts`, `adapters/fs/confinedReader.ts` | Electron e2e (protocol); Node unit (reader) | No file outside root; swap race refused | 2 (protocol); reader post-spike |
| 5 Hostile-repo fixture | Main app + process (`app/repos.ts` → runner) | Node integration with a recording fake `PATH` | No spawn before trust; planted `core.fsmonitor`/`.mcp.json` env/`node_modules/.bin/devscene` never run | post-spike (Day 2 adds the type) |
| 6 Release assertions | Packaging | After `electron-builder` | Fuses read back (`@electron/fuses@2.1.3`); no debug port; no fixture marker; CSP header present; packaged `APP_ORIGINS` = `app://studio` only | 2 |
| IPC contract (new, cheap) | Main IPC adapter | Node unit | Every verb in the contract's channel table registered with a schema; preload keys === channel table; `answer`/`resume` absent until H1+H1′; `startRun` takes one `issueNumber`; forged origin/sub-frame/`null` frame rejected. Lives in 06's `tests/contract/` suite | 2 |
| Trust rules (new, cheap) | Domain | Node unit, table-driven | Lookalike comments, label/run mismatch, string-in-number analytics | post-spike |
| Lint bans | All layers | `eslint` in the harness gate | The §1 lint entries | 1 (renderer rules), 2 (main rules) |

Tooling detail (runner, coverage, where Playwright gets the CSP report) is 06's.

### 8. Fit with 02's tree and layer map

02 (reviewed) already meets what this file needs; the remaining asks are small:

1. **Every choke point has a stable glob in 02's tree:** `main/window/` (hardening, app protocol), `main/ipc/`, `main/adapters/electron/` (confirm, external links), `main/process/` + `main/adapters/transport/`, `main/adapters/fs/` (confined reader, settings), `main/app/repos.ts`, `renderer/markdown/`. Ask: 02 §5 lets `main/adapters` import `process/`; add that only `process/runner.ts` may import `adapters/transport/`.
2. **Domain is pure** (02 §5, `types: []`): brand *types*, the branch shape check, `trust.ts` and `text.ts` (`maskSecrets`, `revealInvisible`) live in `src/shared/domain/`; minting functions live in main. Brands guard against accidents; a cast to a brand outside its minting module is a review finding.
3. **The contract** (`src/shared/contract/`) holds the channel table and the TypeBox schemas (separate files). The renderer and an unbundled preload import it with `import type` only.
4. **Fixture code** stays in `renderer/studio/fixture.ts` + `fixtures/`, reachable only from `main.tsx` behind `__BROWSER_MODE__`.
5. **No security layer and no preload row.** The security rules go in the conventions documents of the layers owning the choke points (`main.md`, `renderer.md`, `shared.md`) and in `conventions.md`'s "Preload (sandboxed facade)" section, which `general` dispatches read. 02 asked whether 05 wants a dedicated preload reviewer: no. The preload is one hand-written file, the contract test checks its keys, and the end-of-branch reviewer reads every conventions doc (02 §4). [inferred]

## Recommendation for the spike

**Day 1 (renderer, browser mode):**
- `src/renderer/markdown/` sink:
  - markdown-it 15.0.3, DOMPurify **3.5.0** (default mode, fixed `ALLOWED_TAGS` + `ALLOWED_ATTR`, module-private `studio-purify` pass-through as `TRUSTED_TYPES_POLICY` inside the `studio-html` policy, §3);
  - ANSI parser;
  - `LogLine` with text nodes.
- `StudioApi` port, `main.tsx` with `__BROWSER_MODE__`, `studio/fixture.ts` (02, 06).
- The `CSP` constant (with `trusted-types studio-html studio-purify`) served by `vite preview`.
- Renderer lint bans: `dangerouslySetInnerHTML`, `innerHTML` & co., `createPolicy`, `studio/fixture*` imports.
- The 50-string corpus with the TT-violation gate (§7).
- Lockfile and `.npmrc` (`ignore-scripts`); pin Vite ≥ 8.3.7 and bind 127.0.0.1.

**Day 2 (main, preload, packaging):**
- `src/main/window/`: `hardening.ts` (four exports), window creation, `appProtocol.ts` on `registerSource` with the CSP header and a traversal e2e; drop `loadFile` and the meta CSP.
- `src/main/ipc/register.ts`:
  - origin (`APP_ORIGINS`, dev origin only when `!app.isPackaged`) + main frame + `null` check;
  - TypeBox schema (`import Schema from 'typebox/schema'`);
  - byte cap;
  - closed error codes.
- Hand-written preload listing each verb (01 §4).
- Brands (`BranchName`, `TrustedRepo` type, `FreeText`, `Confirmed`), `process/argv.ts`, `process/runner.ts` (env allowlist, `KnownExe`, cwd always `$HOME`) and `adapters/transport/{direct,wsl}.ts`.
- `adapters/electron/confirm.ts` with the `Confirmed` brand, and the `startRun` service re-fetching the issue (provenance, non-member flag).
- Mask log lines in main.
- `electronFuses` in `electron-builder.yml`.
- Main lint bans.
- argv fuzz (Direct + pure Wsl wrapper).
- IPC contract test.
- Release assertions.

**Day 3:** the Linux update verify hook (08 §3.6), unchanged by this file.

**Post-spike (v1):**
- the trust store and the hostile-repo fixture;
- the confined reader (WSL-side on Windows), its deny list and the traversal suite;
- the GitHub trust rules and their unit table;
- the mocked-`wsl.exe` Windows job (with Issue #1 item 4);
- the settings store;
- CI supply-chain items (SHA-pinned actions, zizmor, cooldown).

Effort on top of the spike plan: ≈ 0.5–1 O-d for the lint block, four brands, the IPC wrapper and the new tests (IPC contract test, fixture marker, CSP header assertion, `registerSource` traversal e2e); 10 §5 Day 2 lists only the fuse read-back and debug-port check. [inferred]

## Answers to the owner's questions

- **Q1 (what Electron provides vs what we build), security slice.** Electron provides:
  - process isolation (`sandbox`, `contextIsolation`);
  - the bridge (`contextBridge`);
  - the sender identity (`senderFrame.origin`);
  - a confined static server (`registerSource`);
  - session permission and navigation hooks;
  - fuses;
  - native dialogs.

  We build the policy on top: the channel table, the schema check, "ids in, facts derived in main", the argv builder, the trust store, the trust rules and the sanitiser sink. Nothing in Electron stops a preload from exposing `exec`; only our structure does.
- **Q2 (smallest clean architecture).** The nine choke points are the security minimum. Each is one file or one directory in 02's tree, and most are files the spike writes anyway. They need no framework, only a lint block and four brand types.
- **Q3 (patterns, where they live).**
  - **Choke point / Gateway:** `process/runner.ts`, `ipc/register.ts`, `adapters/fs/confinedReader.ts`.
  - **Strategy:** `Transport` (`direct.ts` | `wsl.ts`).
  - **Ports & Adapters:** `StudioApi`, with `studio/ipc.ts` | `studio/fixture.ts`; `Confirm` with the native and test adapters. This is what makes browser mode safe to exclude.
  - **Branded types (parse, don't validate):** brand types in `shared/domain/`, minted only in main.
  - **Command object:** `Command` passed from builder to runner.

  Skipped: a policy engine, decorators for authorisation and an IPC framework. A one-user app with ~15 verbs gains nothing from them.
- **Q5 (security consequences of each choice).** Browser mode costs one build fork and one CI assertion; a runtime switch would have been a shipped backdoor. A guarded dev origin buys HMR in the Electron window and costs one `!app.isPackaged` branch plus a release assertion. Validation in main only makes library size and `eval` irrelevant. Sanitising at the sink keeps DOMPurify where Trusted Types can vouch for it. Masking in main keeps secrets out of an XSS'd renderer. `registerSource` trades an Experimental API for Electron-side confinement.
- **Q6 (expause_web).** The validated-boundary habit carries over (zod at the data edge; here TypeBox at the IPC edge). The event bus and client-side stores have no security role here. A web app's single origin has no equivalent to the preload seam, so the seam rules (§2) are new.

## Risks and open questions

1. **`registerSource` is Experimental.** If it changes or misbehaves on Day 2, fall back to `protocol.handle` with the documented confinement; the traversal test catches either.
2. **DOMPurify under enforced Trusted Types.** The README's `TRUSTED_TYPES_POLICY: null` was confirmed broken in a scratch test (empty output, two TT violations); the module-private pass-through policy works there (§3). The Day 1 corpus re-checks it in the real build. Fallback: omit the option and add `dompurify` to `trusted-types`.
3. **TypeBox 1.x has a single maintainer** (sinclairzx81, about 818 of 830 commits), and its contract benefit depends on F-1 shipping a JSON Schema. If it doesn't, use zod 4; the `register(verb, schema, fn)` signature hides the choice.
4. **Lint is not a boundary.** It doesn't see dependencies, `getBuiltinModule` or dynamic `require`. The backstops are code review against the conventions documents and the hostile-repo/fuzz suites.
5. **ASAR integrity does nothing on Linux.** `OnlyLoadAppFromAsar` still narrows the search path, but a same-user process can modify the AppImage's or deb's files. That is accepted under 08's same-user model.
6. **`EnableNodeOptionsEnvironmentVariable=false` also drops `NODE_EXTRA_CA_CERTS` for Studio's main process.** That matters only if main itself makes HTTPS calls behind a TLS-intercepting proxy. With `gh` doing the network, it doesn't; re-check if 03 adds direct GitHub API calls from main (Electron's `net` uses the OS store, but Node `fetch` does not) [inferred].
7. **Re-fetching on every act** adds one `gh` round trip (≈ hundreds of ms) before the modal. That is acceptable for rare acts; 04 may want a cache with an `updated_at` check instead.
8. **Open item for 07: the Electron dev loop.** This file now accepts 06's `scripts/dev.mjs` HMR loop with the dev origin guarded by `!app.isPackaged` plus a release assertion. 06 is being revised concurrently and does not yet reference this guard; 07 must make both files state the same `APP_ORIGINS` rule and dev-only CSP relaxation.
9. **Open item for 07: 10 §5 wording.** The Day 1 gate "0 CSP violations" becomes "0 Trusted Types violations, 0 executions" (§7); 07 should carry the change into the spike checklist (Issue #4).

## Sources

1. https://www.electronjs.org/docs/latest/tutorial/security — 20-item checklist; #5 permissions, #7 CSP header "preferred", #17 `validateSender` on `frame.origin` with `null` handling, #20 don't pass the IPC event to callbacks. Checked at tag `v45.5.0` via `gh api repos/electron/electron/contents/docs/tutorial/security.md?ref=v45.5.0` — accessed 2026-11-25 [verified]
2. `research/product-startup-research/08-security.md` §1.3, §2a, §3.1–§3.13, §4.3, §6.2; `10-recommendation.md` §1.5, §5, §6 — local [verified]
3. `gh api repos/cure53/DOMPurify/releases/latest` — 3.5.0, 2026-11-22, "There will be no further 3.4.x release"; `npm view dompurify` — accessed 2026-11-25 [verified]
4. `gh api repos/cure53/DOMPurify/security-advisories` — GHSA-qm7q-q8h9-jg8q (2026-11-14, medium, `SAFE_FOR_TEMPLATES`, fixed 3.4.18), GHSA-hrxw-jjj6-2g2j (2026-11-23, low, fixed 3.5.0) — accessed 2026-11-25 [verified]
5. DOMPurify 3.5.0 `README.md` "What about DOMPurify and Trusted Types?" (`TRUSTED_TYPES_POLICY: null` inside your own policy) and `dist/purify.es.mjs:1037-1060, 1441-1456` (internal `dompurify` policy, `TRUSTED_TYPES_POLICY` option), `:1166-1169` (default policy created lazily on first use), `:1864-1871` (raw string to `DOMParser.parseFromString`, `innerHTML` fallback when no policy) — from `npm pack dompurify@3.5.0`, accessed 2026-11-25 [verified]
6. React `packages/react-dom-bindings/src/client/ReactDOMComponent.js` at tag `v19.3.1`, lines 669 and 1034: `domElement.innerHTML = nextHtml` (no stringification, so `TrustedHTML` passes); `npm view react` 19.3.1 — accessed 2026-11-25 [verified]
7. `/Users/daniel/Work/devscenestudio/src/main/main.ts:9-24`, `src/preload/preload.ts`, `src/renderer/index.html:5-8`, `electron-builder.yml` — current skeleton (no fuses, `loadFile`, meta CSP without Trusted Types) — local [verified]
8. electron/electron#53684, "fix: check the sending frame for internal guest, window and reply IPCs" (2026-09-07), including "docs: validateSender example checks senderFrame.origin" — `gh api repos/electron/electron/commits?path=docs/tutorial/security.md` — accessed 2026-11-25 [verified]
9. https://www.electronjs.org/docs/latest/api/protocol — at `v45.5.0`: `protocol.registerSource` (Experimental; routes, `root`, `headers`, outside-root paths fail, no main-thread involvement), `protocol.handle` confinement example, `request.initiatorOrigin`, standard-scheme semantics; `docs/api/structures/protocol-route.md`; electron/electron#54521 (`semver/minor`, backported to 45-x-y), mentioned in the v45.0.0 / v45.1.0 release notes — accessed 2026-11-25 [verified]
10. https://www.electronjs.org/docs/latest/tutorial/fuses — at `v45.5.0`: 9 fuses with defaults; ASAR integrity on macOS and Windows; `grantFileProtocolExtraPrivileges` advice — accessed 2026-11-25 [verified]
11. https://github.com/electron/fuses `src/config.ts` — `FuseV1Options` 0–8, `strictlyRequireAllFuses`; `npm view @electron/fuses` 2.1.3 (2026-06-29) — accessed 2026-11-25 [verified]
12. https://www.electronjs.org/docs/latest/api/safe-storage — at `v45.5.0`: Keychain/DPAPI scope, Linux `basic_text` fallback — accessed 2026-11-25 [verified]
13. https://www.electronjs.org/docs/latest/tutorial/sandbox — at `v45.5.0`: sandboxed preload `require` loads only `electron`; bundle to split; `app.enableSandbox()` in `docs/api/app.md` — accessed 2026-11-25 [verified]
14. https://github.com/vitejs/vite/security/advisories/GHSA-p4f5-76q4-ffq7 — critical, 2026-11-10, dev-server RCE only with `--host`/`server.host`; patched 8.3.7; `npm view vite` 8.3.8 — accessed 2026-11-25 [verified]
15. `npm view eslint` 10.15.0 (2026-11-16); core rules `no-restricted-imports`, `no-restricted-syntax`, `no-restricted-properties` — https://eslint.org/docs/latest/rules/ — accessed 2026-11-25 (rule docs in eslint/eslint `docs/src/rules/`) [verified]
16. `node_modules/app-builder-lib/out/configuration.d.ts:256-260, 505-560` (electron-builder 26.18.1): `electronFuses?: FuseOptionsV1`; no `wasmTrapHandlers` key; nodeOptions fuse also gates `NODE_EXTRA_CA_CERTS` — local [verified]
17. https://www.electronjs.org/docs/latest/api/web-frame-main — at `v45.5.0`: `frame.origin` vs `frame.url`, child `about:blank` window reports the parent's origin — accessed 2026-11-25 [verified]
18. `npm view zod` 4.6.7 (2026-10-12); `npm pack zod@4.6.7`: `v4/classic/from-json-schema.d.ts`, `jitless` option in `v4/core/core.d.ts`, `new Function` in `v4/core/compile.js` — accessed 2026-11-25 [verified]
19. https://github.com/sinclairzx81/typebox README — JSON Schema JIT compiler for drafts 3–2020-12, plain schemas accepted by `Compile`, official test suite; `readme.md:355-356` (1.x "TS 6.0–7.0+ … backwards compatibility with `0.x` types … ESM only"; 0.x LTS as `@sinclair/typebox`), `readme.md:164` and `build/schema/index.d.mts:3` (`import Schema from 'typebox/schema'`, default export); `npm view typebox` 1.4.7 (2026-11-12); repo pushed 2026-11-16 — accessed 2026-11-25 [verified]
20. `npm pack markdown-it@15.0.3` (2026-10-16): `dist/markdown-it.cjs.js:4213-4214` `BAD_PROTO_RE`/`GOOD_DATA_RE`; `:2190, 2224` table cells get `style="text-align:…"` — accessed 2026-11-25 [verified]
21. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors — "This directive is not supported in the `<meta>` element" (mdn/content `index.md:37`) — accessed 2026-11-25 [verified]
22. `npm view valibot` 1.5.0 (2026-09-09); `npm view fast-check` 4.11.0; `/Users/daniel/Work/expause/expause_web/package.json:35` (`zod ^3.23.8`); `/Users/daniel/Work/devscene/package.json:20` and `schemas/*.json` (ajv, draft-07) — accessed 2026-11-25 [verified]
23. GitHub Issue #1 ("Data source" trust rules, items 2, 8, 9) and Issue #4 (Day 1/Day 2 checklist; Day 4 moved to item 4) via `gh issue view` — accessed 2026-11-25 [verified]
24. Review of this file, `reviews/05-security-architecture.md` (2026-11-25): scratch tests in Electron 45.5.0 (Chromium 156) with a `registerSource` page under this file's CSP — `TRUSTED_TYPES_POLICY: null` → empty output + TT violations; module-private policy and `dompurify`-allowlisted variants render cleanly; `DOMPurify.sanitize` alone fires `script-src-attr`/`style-src-attr` reports; `standard: false` → origin `"null"`; `srcdoc` sub-frame origin and `senderFrame === sender.mainFrame`; TypeBox `require(esm)` from a CJS main; TypeBox `Schema.Compile` on the harness's draft-07 schemas and negatives. Not re-run by the fix pass (no GUI runs); DOMPurify behaviour re-checked against source [5] [verified by reviewer]
25. Sibling files read for path alignment: `01-electron-process-model.md` (TL;DR, §4 hand-written typed map, §5 build-mode selection), `02-layered-architecture.md` (§2–§5 tree, layer map, dependency rules), `06-testing-and-tooling.md` (§2 `scripts/dev.mjs`, `__BROWSER_MODE__`, Risk 1) — read 2026-11-25; `npm ls @electron/fuses` in this repo → 1.8.0 via electron-builder — local [verified]
