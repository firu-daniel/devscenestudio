# 08 — Security threat model and required depth
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent · Review: `reviews/08-security.md` (resolution at its end)

## TL;DR

- **The asset that matters most is not a credential. It is the ability to start a headless `claude` run.** Any path that drops a task prompt, writes an answer file or dispatches `devscene-run.yml` gives the attacker an autonomous coding agent on the user's repo, on the user's subscription or API bill. The `gh` token comes second, and it is bounded by what `gh` can do. Studio never holds Claude credentials in any mode. Each mode keeps it that way for a different reason (§1.4). [inferred]
- **Ranked by residual risk once the MUST controls are in: native ≈ Tauri 2 < Electron < hosted remote-only < local web app < hosted + connector.** The axis is **per-user** residual risk: hosted ranks below local web for one user, but its worst case is every user's repos, so it is worse in aggregate (§4.4). The webview shells sit close to native because the UI never loads remote content and its IPC can be cut down to intent verbs. The local web app's residual risk is structural: a socket that spawns processes, reachable by other OS users, by every Windows user through WSL `localhostForwarding`, and by hostile web pages wherever Host/Origin/token checks have a gap. The hybrid adds "one XSS on the hosted origin → process spawn on every connected machine". [inferred, §2]
- **Estimated security effort for v1, in 03's owner-days (O-d), point ± 30%:** Electron ≈ 5.5 (3.9–7.2), Tauri ≈ 6.0 (4.2–7.8), native ≈ 5.75 in total for three apps (4.0–7.5; ≈ 1.9 per app), local web app ≈ 7.75 (5.4–10.1), hosted remote-only ≈ 8.5 (6.0–11.1) plus ongoing operations, hybrid ≈ 15.5 (10.9–20.2). **Tauri's security work is ≈ 0.5 O-d more than Electron's** (capabilities + isolation + `cargo-deny`), offset by a smaller recurring cost (no Chromium to ship every 8 weeks). Against 03's ≈ 27 O-d v1, a desktop shell adds about 20–22% for security, the local web app about 29%, and the hybrid about 57%. [inferred, §4.2]
- **Cross-cutting MUSTs, whatever the mode:**
  - GitHub Markdown through `markdown-it` (`html: false`), then DOMPurify **≥ 3.4.17, latest and auto-tracked** (about 25 advisories in 2026, at least one bypassing the default configuration, §3.1), behind a Trusted Types policy;
  - no remote images; logs rendered as text nodes through a closed-palette ANSI parser that drops OSC sequences;
  - every process call built as an argv array from one validated builder: `--end-of-options`/`--` before refs, branch names validated by regex and `git check-ref-format --branch`, `wsl.exe … --exec`, never a shell string; `devscene` resolved once by absolute path, never through `npx` in a repo;
  - run files read only through a realpath-confined reader;
  - **a confirmation per start, answer and resume, rendered by the privileged side** (an OS-native modal in a desktop shell), so a renderer XSS cannot click through it (§3.10); no batch start; a global stop button;
  - **detected repos are untrusted until the user confirms each one**: no `doctor`, `git` or `devscene` spawn in an untrusted repo (§3.11);
  - **GitHub state is trusted only from `github-actions[bot]` markers and the Actions API**, not from labels or branch-committed JSON (§3.12).

  Ship them with three CI suites: an XSS corpus, an argv fuzz test, and (local modes) a DNS-rebinding/CSRF/WebSocket test. A per-window start budget is SHOULD, not MUST, once the native confirmation is in. [inferred, §3–§4]
- **Prompt injection is mostly the harness's to contain, and the harness contains it well.** It has a sandbox with `failIfUnavailable`, a `dontAsk` allowlist, credential denials, the prompt-injection screen ("a tripwire, never a boundary") and actor checks on every GitHub trigger. The app's job: show where a task came from (issue author ≠ labeller, last edit time), show the text the run will actually receive, require a confirmation that names it, and display the screen's verdict. It must never add a path that turns untrusted text into a run without a human. [verified harness code, §3.5]
- **Harness findings (§5), for follow-up issues in devscene. Separate from the app's own controls above.** Ranked by severity:
  - **H1 (High, confirmed by settings analysis, runtime test pending):** the sandboxed agent can write the main checkout's `autonomous_inbox/`, plus its own run copy's `answer_<n>.md` and `RESUME` markers. A prompt-injected run can then start new runs and answer its own parks. The Edit allow covers the repo root; in the state dir, the write protection covers `registry.json` only.
  - **H1′ (High, confirmed by settings analysis, runtime test pending):** the same grants reach every **sibling run copy** (answering or resuming *other* runs' parks) and the **main checkout's whole working tree** outside the protected list: `.claude/CLAUDE.md`, `.claude/context/`, `package.json`, `node_modules/`. The owner's next interactive session or tool run there reads or executes them unsandboxed, and none of it reaches the run's branch or PR.
  - **H2 (High for API-key users):** no per-run or per-day **cost** ceiling on task runs (`--max-budget-usd` is set only for the $1 mention reader). Subscription users are bounded by the usage gate.
  - **H3 (Medium):** run logs and `.stream.jsonl` are `0644`, are not redacted, and the `harness-state` artifact (400-day retention) is readable by anyone with read access, which on a public repo means any signed-in user.
  - **H4 (Medium):** the watchdog `kill -9`s a pid read from the registry without checking that it is still the run's process.
  - **H5 (Medium):** the `claude` CLI is installed unpinned in jobs that receive the OAuth secret, and the mention plugin is fetched by a mutable tag.
  - **H6 (Medium):** the trigger snapshot names the labeller but not the issue's author or its last-edit time.
  - **H12 (Medium):** `devscene doctor` copies every string from the repo's `.mcp.json` docs-server `env` into a spawned process's environment (`LD_PRELOAD`, `PYTHONPATH`, `BASH_ENV` …), so running `doctor` on an untrusted repo can execute code.
  - H7–H11: Low–Medium to Info.

  The GitHub workflows themselves are notably well hardened: `permissions: {}`, SHA-pinned actions, `env:`-only interpolation, no `pull_request_target`, an actor allow-list that defaults to the owner, and a job-surface check. [verified, §5]
- **Recommendation:**
  - **v1 = a desktop shell (Tauri 2 or Electron) for local and remote runs.** On security alone Tauri edges ahead (capabilities + isolation pattern, mandatory signed updates, smaller supply chain on the UI side).
  - **Optionally, a hosted remote-only app later,** read-mostly at first.
  - **The local web app is acceptable only as an opt-in developer mode** behind every §2c control and its CI tests.
  - **Do not ship the hybrid connector in v1.**
  - **The minimum v1 bar is §6.2.** Its two app-side preconditions: the start/answer/resume confirmation is an OS-native modal (§3.10), and no process is spawned in an untrusted repo (§3.11).
  - **Harness blockers:** H1 + H1′ block any Studio feature that answers or resumes runs (otherwise the answer form is not a real human checkpoint). H2 blocks only if Studio exposes API-key configuration. [inferred]

## Scope

**Covered:** assets, trust boundaries and untrusted inputs; a STRIDE threat model per delivery mode (Electron, Tauri 2, native, local web app, hosted remote-only, hosted + connector); cross-cutting threats (XSS, argument injection, path traversal, TOCTOU, prompt injection, update channel, supply chain, secret masking, local privilege, denial of wallet, hostile repos, spoofed GitHub state, deep links); a MUST/SHOULD control checklist with effort and CI tests; harness-side findings with path:line references; and the minimum bar for v1.

**Deferred:**
- The four modes' non-security trade-offs: 07 §4d.
- Signing costs and updater coverage: 04 §6–§8 and 01.
- The `runs --json` contract shape: 05 §5. This file adds only the security requirements it must meet (§5.3).
- WSL plumbing: 04 §2.

**Scoring:** risk is **likelihood × impact** on 1–3 scales (L1 rare / needs a local foothold, L2 plausible for a motivated attacker, L3 expected for any public-repo user; I1 nuisance, I2 repo or account damage, I3 code execution, money or secrets). Score = L × I, so 9 is the worst. All scores are [inferred].

## Findings

### 1. Assets, trust boundaries, untrusted inputs

#### 1.1 Assets

| # | Asset | Where it lives | What loss means |
|---|---|---|---|
| A1 | **Ability to start or continue a headless `claude` run** (inbox drop, `answer_<n>.md`, `RESUME`, `PARK_LOOP_CLEAR`, `workflow_dispatch` of `devscene-run.yml`, the trigger label, `@dev-scene` commands) | Local state dir; GitHub Actions | An attacker-chosen prompt runs as an agent with write access to the repo's branches, on the user's Claude subscription or API key (money, rate-limit lockout), and local runs execute on the user's machine inside the sandbox |
| A2 | The user's **`gh` token** and GitHub permissions (often `repo`, `workflow`, `read:org`) | `~/.config/gh/hosts.yml` or the OS keychain; plain text in most WSL distros (07 §2) | Push to every repo the user can write, dispatch workflows, read private code, approve/merge PRs |
| A3 | **Repos' code** (private source, unreleased work) | Working copies, run copies, GitHub | Exfiltration; malicious commits on run branches that a tired reviewer merges |
| A4 | **Run artifacts and logs** (`<branch>.log`, `.stream.jsonl`, `question_/answer_` files, `run_analytics/`, the `harness-state` artifact) | State dir; Actions artifacts (400-day retention) | Contain tool output: file contents, env dumps, test fixtures, sometimes secrets (§3.8) |
| A5 | **Studio's own release channel** (signing keys, updater key, npm publish rights, the domain) | Owner's machines/CI | One compromise ships code to every user's machine with access to A1–A4 |
| A6 | Hosted only: **users' GitHub App user tokens and refresh tokens** (8 h / 6 months [verified, 6]) | BFF session cookie or server store | Multi-tenant breach: A2-equivalent for every signed-in user |
| A7 | Claude credentials (`~/.claude*`, Keychain item, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` secrets) | Outside the app by design | Studio must never be a path to them (§1.4) |

#### 1.2 Trust boundaries

```
 [GitHub: issues, PR text, comments, artifacts]    [npm / crates / update feed]
          │  untrusted text, untrusted zips                 │ supply chain
          ▼                                                 ▼
 ┌──────── UI (renderer / browser tab) ────────┐   B1: render boundary (XSS)
 │ board, detail, log tail, answer form         │
 └──────────────┬───────────────────────────────┘
                │ B2: privilege boundary — IPC (shell) | HTTP/WS (local web, connector) | BFF (hosted)
 ┌──────────────▼───────────────────────────────┐
 │ Core: intent verbs → argv builder → spawn     │   B3: process boundary (argv injection)
 └──────┬──────────────┬──────────────┬─────────┘
        │gh/git        │devscene runs │ wsl.exe (Windows) ── B4: Windows↔WSL boundary
        ▼              ▼              ▼
   GitHub API     state dir: registry, inbox, markers, logs   ── B5: filesystem (traversal, TOCTOU, other users)
                       │
                       ▼ watcher → claude -p (sandbox, dontAsk)  ── B6: harness boundary (prompt injection)
```

#### 1.3 Untrusted inputs (who controls them)

| Input | Who can write it | Reaches | Notes |
|---|---|---|---|
| Issue title and body | **Anyone**, on a public repo (and any member on a private one); editable at any time by the author | To Do cards, detail, the start confirmation, **the task prompt** (trigger snapshot `remote-run.sh:4653`) | The trigger authorises the **labeller**, not the author (`remote-run.sh:262-271`). Bidi and invisible characters are possible |
| Issue/PR comments | Anyone (public) | Progress view; `conversation.md` for the mention reader (`remote-run.sh:620-628`) | `<!-- devscene` markers are trusted only from `github-actions[bot]` with an exact shape (`remote-run.sh:688-694`) |
| Branch names | Derived by the harness from titles (`hr_derive_branch`), or user-entered; any writer can push branches | Cards, argv, file paths | `check-ref-format` allows `$`, `(`, `)`, `;`, `'`, `` ` `` and `!`, but rejects a leading `-` only as `--branch` input [inferred: git rules]. A valid ref can still be hostile to a shell |
| `run.log`, `.stream.jsonl` | The agent, i.e. model output plus tool output (file contents, test output, command output) | Log tail | Treat as attacker-controlled: a poisoned repo file read by the agent is echoed into the log |
| `question_<n>.md` (clarifications) | The agent (possibly prompt-injected) | The answer form | A question can be phrased to get the human to approve something ("type YES to allow pushing to main") |
| `harness-state` artifact zip | The run job (`remote-run.sh save`), from files the session wrote | Detail screen (hosted/remote) | Zip-slip, symlinks (the harness skips links, `sandbox-record.md:180-181`), oversized files |
| `registry.json`, `status.json`, `repos.json` | The watcher and scripts. **Not** the sandboxed agent for `registry.json` (write-denied, `.claude/settings.autonomous.json:256`), but **any same-user process** | Board state, **paths** (`worktree`, `log_path`) and pids | No `schema` field today (05). Paths from it must not be trusted for reads outside the run roots |
| Markers and answers in a run copy | The user, **the run's own sandboxed agent** (§5, H1), **and any other run's agent** (sibling copies, H1′) | Studio's status badges | A badge is only as trustworthy as the writer |
| **Repos picked up by the repo scan** (Issue items 8–9): any folder with a `harness.config.json`, such as a cloned OSS repo, an extracted tarball or a shared drive | **Whoever wrote that folder** | `doctor` auto-runs, `git`/`devscene` spawns with cwd in the repo, `stateDir`/`scriptsDir` used as roots | `doctor` applies the repo's `.mcp.json` env overlay to a child (H12); `npm view` reads the repo's `.npmrc`; `.git/config` can set `core.fsmonitor`, `core.pager`, `diff.external`, `core.sshCommand`, `filter.*`; `"stateDir": "../../.."` moves §3.3's confinement root. **Untrusted until the user confirms it (§3.11)** |
| **Main checkout working tree** (`package.json`, `.npmrc`, `node_modules/.bin/`) | The user, **and any sandboxed run** (H1′) | Any `npx`/`npm` Studio runs with cwd in the repo | `npx devscene` prefers a repo-local `node_modules/.bin/devscene`. Resolve the CLI by absolute path from `$HOME` (§3.2 rule 1) |
| GitHub read model: `sdlc-harness: <state>` **labels**, the **progress comment**, `run_analytics/` / `branch_statistics/` **committed on the branch** (Issue item 5) | Labels: anyone with triage. Comments: anyone (public repo). Branch files: anyone who can push the branch | Board columns, status, analytics | The harness trusts `<!-- devscene` markers only from `github-actions[bot]` (`remote-run.sh:683-694`); Studio must apply the same rule (§3.12) |
| Custom URL scheme (deep links, 04 §9, 07 8.5) | **Any web page** the user visits | Navigation, if a scheme is registered | v1 registers none; any later scheme is navigation-only (§3.13) |
| Update feed / npm / crates | The release pipeline; mirrors; registries | Code execution in Studio | A5 |
| Hosted: OAuth `state`/`code`, webhook payloads | The internet | The BFF | CSRF on login, token substitution |

#### 1.4 "The app never touches Claude credentials": how each mode keeps it

| Mode | Mechanism | Residual |
|---|---|---|
| Desktop shell / native | Never reads `~/.claude*`, the Keychain item or `ANTHROPIC_*`. Spawns only `gh`, `git`, `devscene` and `wsl.exe`, **never `claude`**; the watcher and `remote-run.sh` do that. Child env is built from an **allowlist**: `PATH`, `HOME`, `LANG`/`LC_*`, `WSL_UTF8`, `WSLENV`, plus the passthroughs the helpers need to work: `SSH_AUTH_SOCK` (git over SSH), `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY`/`NODE_EXTRA_CA_CERTS` (corporate networks), `XDG_CONFIG_HOME`/`GH_CONFIG_DIR`/`GH_HOST` (gh config). **Explicitly denied** even if a future allowlist widens: `ANTHROPIC_*`, `CLAUDE_*`, `GIT_*`, `NODE_OPTIONS`, `LD_*`/`DYLD_*`, `BASH_ENV`, `ENV`. A user's exported `ANTHROPIC_API_KEY` is therefore never passed to helpers. Crash and telemetry scrubbers drop `sk-ant-…`, `CLAUDE_CODE_OAUTH_TOKEN=…` and `gh[pousr]_…` | The **user-scope** OS keychain is readable by any same-user process, so "the app cannot" is a policy enforced by code review and a CI grep, not by the OS. [inferred] |
| Local web app | Same as above, and the server never exposes env, file reads outside run roots, or `doctor` raw output | Plus: an API bug (path traversal) could read `~/.claude/.credentials.json` on Linux/WSL, where it is a file. Make the path guard a MUST (§3.3) [inferred] |
| Hosted remote-only | Structurally impossible: the service has only GitHub App user tokens. Claude credentials live in the repo's Actions secrets, which no GitHub App permission in Studio's set can read (Secrets is a separate permission; never request it) | A Studio-dispatched run *spends* the repo owner's Claude credits, even though the app never sees the secret (denial of wallet, §3.10). [inferred] |
| Hosted + connector | Hosted half as above; connector as the local web app | Both |

### 2. Threat models per delivery mode

Each table is STRIDE-ordered. **L×I** is the score before the MUST controls; the "after" column assumes §4's MUST list.

#### 2a. Desktop shell — Electron (v45.x)

Attack surface: a renderer loading only bundled code (`app://` custom protocol), a preload `contextBridge` API, the main process spawning helpers, the updater, the Chromium Electron bundles, and the CDP port in test builds.

| ID | STRIDE | Threat and scenario | Vulnerable component | L×I | After |
|---|---|---|---|---|---|
| E1 | E (elevation) | **XSS → IPC.** An issue body carries `<img src=x onerror=…>`, or markdown that a lax renderer turns into an `<a href="javascript:…">`. The script calls `window.studio.startRun({prompt: …})`, or a generic `exec` if one was exposed | Markdown renderer; preload API breadth | 3×3=9 | 1×2 *only with a native confirmation* (§3.10); 1×3 if the confirmation is renderer HTML, which the XSS can click |
| E2 | E | **Navigation or new-window escape.** A link in a log opens `https://evil` inside the app window, which then holds the preload API if the preload is attached to every frame | Missing `will-navigate`/`setWindowOpenHandler` [verified, 1] | 2×3=6 | 1×1 |
| E3 | E | **`shell.openExternal` abuse.** A run log prints a `file:///…/evil.command`, `smb://` or `ms-msdt:` URL that a "click to open" passes to `openExternal` → OS handler RCE (Electron checklist #15 [verified, 1]) | Link handler | 2×3=6 | 1×1 |
| E4 | S (spoofing) | **IPC sender spoofing.** A sub-frame (an iframe of rendered HTML) sends IPC. The checklist says to validate the sender frame's origin, not only the URL [verified, 1] | `ipcMain.handle` | 1×3=3 | 1×1 |
| E5 | T (tampering) | **Fuses left on.** `runAsNode` / `nodeCliInspect` / `NODE_OPTIONS` let a same-user process run code as the signed app and inherit its TCC grants (Documents access) [verified, 1; inferred for TCC] | Packaging | 2×2=4 | 1×1 |
| E6 | T | **Update hijack.** A malicious `latest.yml` or binary. electron-updater checks Authenticode on Windows (`verifyUpdateCodeSignature`, publisherName) and relies on the code signature on macOS, but **on Linux checks only the sha512 from the same manifest** (deb and AppImage), with no verify hook, in the shipping 6.8.12 line [verified, 9]. `allowDowngrade` defaults to `false`; it is documented as cross-channel only, but in code (`isUpdateAvailable`) it gates *any* older version, and setting `channel` or `allowPrerelease` flips it to `true` [verified, 9]. 7.0 (alpha) adds an opt-in Ed25519 `updateManifestPublicKey` and a `verifyUpdateFile` hook (a stub by default; `allowUnverifiedLinuxPackages` defaults to true) [verified, 9] | Updater, release host | 1×3=3 (Linux 2×3) | 1×3 (Linux: host = trust root) |
| E7 | T | **Chromium n-day.** Electron supports only the latest 3 majors (07); a stale build ships known renderer RCEs. The renderer loads no remote content, so it needs an E1 foothold first (T5's reasoning, applied here too) | Release cadence | 1×3=3 | 1×3 |
| E8 | I (information disclosure) | **Secrets in log tail** shown on screen, screen-shared or copied into a bug report | Log view | 3×2=6 | 2×1 |
| E9 | E | **CDP port in a release build** (from agent-QA work, 07 §1): any local process drives the privileged renderer | Build flags | 1×3=3 | 1×1 (CI asserts absent) |
| E10 | D (denial) | **Denial of wallet.** A UI bug or a scripted renderer starts N runs | Start verb | 2×3=6 | 1×2 (budget, §3.10) |
| E11 | I | **Supply chain** (npm, Electron's large dev tree). See 07 §2 and §3.7 | Build | 2×3=6 | 1×3 |
| E12 | I | **Custom-protocol path traversal.** A hand-rolled `app://` handler that maps the URL path to disk without confinement serves any file (`app://studio/../../.ssh/id_ed25519`). Electron's own `protocol.handle` example confines with `path.relative` and rejects `..`/absolute paths with a 400 [verified, 20] | Protocol handler | 2×3=6 | 1×1 |

**Electron-specific MUST:**
- `contextIsolation`, `sandbox` and `nodeIntegration: false` (defaults since 12 and 20 [verified, 1]);
- load the UI from a custom protocol, not `file://` (checklist #18). Register `app` as `standard, secure` with no `bypassCSP`, and confine the handler to the bundle as in Electron's example (E12), with a traversal test (§4.3 item 4);
- act verbs (`start`, `answer`, `resume`, `drop`) confirmed by `dialog.showMessageBox` from the **main** process (§3.10), never by renderer HTML;
- CSP by header from the protocol handler;
- `will-navigate` deny-all and `setWindowOpenHandler` deny-all, with the external-link allowlist `https:` + host allowlist only (`github.com`, the product domain);
- preload exposes only intent verbs with typed arguments;
- every `ipcMain.handle` checks `event.senderFrame.url` origin === `app://studio`;
- fuses: `RunAsNode=false`, `EnableNodeOptionsEnvironmentVariable=false`, `EnableNodeCliInspectArguments=false`, `EnableEmbeddedAsarIntegrityValidation=true`, `OnlyLoadAppFromAsar=true`, and `GrantFileProtocolExtraPrivileges=false` (on by default; Electron: "If you aren't serving pages from `file://`, you should disable this fuse"). `EnableCookieEncryption` and `WasmTrapHandlers` are optional [verified, 21];
- `ses.setPermissionRequestHandler` deny-all;
- ship within 2 weeks of each Electron security release. **Why it matters more for Electron:** Tauri's webview on Windows (WebView2 Evergreen) and macOS (WKWebView) is patched by the OS vendor, while an Electron user's exposure window is Electron's release lag *plus* Studio's release lag *plus* the user's update lag. That is the real argument for Tauri on the n-day axis.

Note 04 §1: use `utilityProcess`, not `ELECTRON_RUN_AS_NODE`.

#### 2b. Desktop shell — Tauri 2 (2.12.x)

Same shape, different mechanisms. Rust core, system webview (WKWebView / WebView2 / WebKitGTK 4.1).

| ID | STRIDE | Threat and scenario | Vulnerable component | L×I | After |
|---|---|---|---|---|---|
| T1 | E | **XSS → `invoke`.** Same as E1. Mitigation layers: the capabilities ACL (plugin permissions per window label, remote origins none by default) [verified, 3]. **Caveat: app commands "are allowed to be used by all the windows and webviews of the app" unless `AppManifest::commands` restricts them** [verified, 3] | `#[tauri::command]` surface | 3×3=9 | 1×2 *only with a native confirmation* (`tauri-plugin-dialog` from Rust, §3.10) |
| T2 | E | **Over-broad `shell` plugin scope.** A capability allow-lists `gh` with a regex arg scope; argument injection through it (`gh api -X DELETE …`) | `capabilities/*.json` | 2×3=6 | 1×1. Don't enable `shell:allow-execute`; spawn from Rust (04 §1) |
| T3 | T | **Frontend dependency tampering with IPC.** A compromised npm UI dependency calls commands. The **isolation pattern** routes every IPC through a sandboxed iframe hook, AES-GCM with per-run keys, so the hook can validate arguments [verified, 2]. Cost: no ES modules in the isolation app on Windows; small overhead [verified, 2] | Frontend supply chain | 2×3=6 | 1×2 |
| T4 | T | **Update hijack.** Signatures are mandatory and "cannot be disabled"; downgrades are refused unless a custom `version_comparator` is set; TLS is enforced in production [verified, 4]. **Key loss = no further updates to installed users** [verified, 4]. Linux updater is AppImage-only (04); deb users update through the package manager | Updater key custody | 1×3=3 | 1×3 (key custody, §3.6) |
| T5 | T | **WebKitGTK n-day** on LTS distros that lag (WSA-2026-0001…0006 so far in 2026 [verified, 22]) | Linux runtime | 2×2=4 | 2×2 (not in our control; with no remote content, it needs E1/T1 first) |
| T6 | I | Secrets in log tail | Log view | 3×2=6 | 2×1 |
| T7 | E | **`asset:` / `convertFileSrc` protocol scope** too wide, so the renderer reads `~/.ssh` | `assetProtocol.scope` | 2×3=6 | 1×1 (leave it disabled) |
| T8 | D | Denial of wallet | Start command | 2×3=6 | 1×2 |
| T9 | I | **Supply chain:** npm (UI) + crates.io (arrayref incident, 07) | Build | 2×3=6 | 1×3 |

**Tauri-specific MUST:**
- one window label (`main`); capabilities granting only `core:default` minus what's unused;
- **no** `shell`/`fs` plugin permissions for the webview;
- app commands restricted through `AppManifest::commands`, and each is an intent verb; act verbs confirmed by a `tauri-plugin-dialog` modal opened **from Rust**, never by webview HTML (§3.10);
- the isolation pattern on, with a hook that schema-validates arguments;
- `dangerousDisableAssetCspModification` off; CSP in `tauri.conf.json`;
- updater key in a hardware-backed or CI-secret store with an offline backup (§3.6).

**SHOULD:** `cargo-deny` + `cargo-vet` (§3.7).

#### 2c. Native toolkit (SwiftUI/AppKit, GTK4, WinUI 3), the baseline

No HTML engine renders untrusted content, so **the XSS → privilege class disappears**, as long as nobody embeds a `WKWebView`/`WebView2` for Markdown. If Markdown must render richly, use `AttributedString(markdown:)` on macOS, which doesn't execute script, or a GTK/WinUI text renderer. [inferred]

| ID | STRIDE | Threat | L×I | After |
|---|---|---|---|---|
| N1 | E | Argument injection (§3.2): the same builder bug possible in each of 3 codebases, so 3× the review surface | 2×3=6 | 1×2 |
| N2 | T | Update hijack (Sparkle EdDSA on macOS, per-platform on others) | 1×3 | 1×3 |
| N3 | I | Secrets in logs | 3×2 | 2×1 |
| N4 | E | Link handling (`NSWorkspace.open` with `file:`/custom schemes from logs) | 2×3 | 1×1 |
| N5 | D | Denial of wallet | 2×3 | 1×2 |
| N6 | – | **Parity risk:** a control fixed on one OS and missed on two | 2×2 | 2×2 |

Native is the lowest-risk baseline per codebase, but triples the places a control can be missing (03, 06).

#### 2d. Local web app (`devscene-studio serve` on 127.0.0.1; inside WSL on Windows)

The privileged boundary is a **network socket**. Attack trees for the worst outcome, "attacker starts a run on the victim's machine":

```
GOAL: POST /api/runs/drop (or WS "drop") accepted
├── OR from a web page the victim visits
│   ├── CSRF: <form method=POST action=http://127.0.0.1:PORT/api/runs/drop>    ← blocked by: custom header + token + Origin check
│   ├── DNS rebinding: evil.com → 127.0.0.1, same-origin fetch                   ← blocked by: exact Host allowlist
│   ├── Cross-site WebSocket hijacking (WS not subject to CORS; LNA gates WS only in Chrome ≥ 147) ← blocked by: Origin check on upgrade + token
│   └── Image/GET side effects from a GitHub markdown image rendered in Studio   ← blocked by: GET is side-effect free; img-src 'self'
├── OR from another local principal
│   ├── another OS user on the same host (loopback has no per-user ACL)          ← blocked by: per-install secret in a 0600 file
│   ├── (Windows) any Windows user/process via localhostForwarding from WSL       ← same; plus the bind check
│   ├── (Windows, mirrored mode) LAN if bound 0.0.0.0 and Hyper-V firewall opened ← blocked by: refuse non-loopback bind
│   └── same-user malware                                                         ← NOT blocked (same as any desktop app)
├── OR XSS inside Studio's own origin (GitHub text, logs)                         ← cookie + token are same-origin: only sanitizer/CSP/TT help
└── OR token leak: URL query in history/logs/Referer, `ps` argv, env of children ← fragment-only, exchanged for HttpOnly cookie
```

| ID | STRIDE | Threat and scenario | Vulnerable component | L×I | After |
|---|---|---|---|---|---|
| W1 | S | **DNS rebinding** to `127.0.0.1:PORT`. The attacker page is same-origin after the rebind. Defence: an exact-match Host allowlist (`127.0.0.1:PORT`, `localhost:PORT`, `[::1]:PORT`) on every HTTP request and upgrade [secondary, 07 #23] | HTTP server | 3×3=9 | 1×3 |
| W2 | S | **CSRF** with `text/plain` or form bodies (no preflight). Defence: reject any write without a custom header, without an exact `Origin`, or with `Origin: null` | Router | 3×3=9 | 1×3 |
| W3 | S | **Cross-site WebSocket hijacking.** WebSockets are not gated by CORS. Chrome ≥ 147 prompts before a public page opens a WebSocket (or WebTransport) to loopback (ChromeStatus "Local network access restrictions for WebSockets" and "… for WebTransport", both shipping in 147) [verified, 5]. Chrome 142–146, Firefox and Safari don't gate it, and WebRTC is still ungated, so the Origin check on upgrade + token stays MUST. L stays 3 before controls | WS upgrade handler | 3×3=9 | 1×3 |
| W4 | S | **Another OS user** on a shared Linux box or a Windows machine with several accounts. With NAT `localhostForwarding` (default on), a WSL service bound to 127.0.0.1 is reachable from Windows `localhost` [verified, 07 #22/#42], so by every Windows session [inferred] | Socket ACL | 2×3=6 | 1×3 (secret in a `0600` file; no unauthenticated endpoint, health included) |
| W5 | I | **LAN exposure.** Mirrored mode can "Connect to WSL directly from your local area network"; the Hyper-V firewall is on by default from WSL 2.0.9 and must be opened by an admin rule [verified, 7]. Risk exists if someone binds `0.0.0.0` "to make it work" | Bind config | 1×3=3 | 1×3 (refuse non-loopback; CI test) |
| W6 | E | **XSS in Studio's origin** = full API, with cookie and token (Host/Origin/token checks don't help). The act confirmation here is a server-issued one-time nonce bound to the payload hash; it stops replay and blind CSRF but **not** XSS, which can read the nonce and confirm. That is why W6 stays I3 after controls, unlike E1/T1 | Renderer | 3×3=9 | 1×3 |
| W7 | I | **Token leakage** through the query string (history, Referer, proxy logs), argv (`ps`), or a child process env | Launcher | 2×3=6 | 1×2 |
| W8 | I | **Path traversal** on `/api/runs/:branch/log`, `..%2f`, or a registry `log_path` pointing at `~/.claude/.credentials.json` | File API | 2×3=6 | 1×1 |
| W9 | D | Denial of wallet through repeated drops | Act API | 2×3=6 | 1×2 |
| W10 | T | **npm distribution of the server itself:** a compromised maintainer token publishes a trojaned `devscene-studio` that runs at next `npx` | Publish pipeline | 2×3=6 | 1×3 (trusted publishing, no tokens, §3.7) |
| W11 | R (repudiation) | No audit of who acted (browser tab vs a curl script) | Act API | 2×1 | 1×1 (audit log) |

The residual stays higher than a shell's because every row W1–W5 is a control that must be **correct forever**, and each new endpoint can regress it. That is why the CI tests in §4.3 are MUST, not SHOULD. [inferred]

#### 2e. Hosted web app, GitHub App sign-in, remote runs only

No local spawning. The privileged boundary is the **BFF holding GitHub App user tokens**. With Actions RW, a token can `workflow_dispatch`, which starts a run that spends the repo's Claude credits.

| ID | STRIDE | Threat and scenario | Vulnerable component | L×I | After |
|---|---|---|---|---|---|
| H-1 | E | **Stored XSS from GitHub text** in the SPA. It acts as the user: create issues, apply the trigger label (start runs), post `@dev-scene answer …` comments, dispatch. Every repo the token reaches is in scope. A browser has no native modal the page can't click, so the confirmation does not lower I here (as W6) | SPA renderer | 3×3=9 | 1×3 |
| H-2 | S | **Login CSRF / OAuth mix-up.** Missing `state`, missing PKCE (`S256` supported [verified, 6]), so the attacker's account is bound to the victim's session | BFF auth | 2×2=4 | 1×1 |
| H-3 | I | **Token theft at rest.** A server-side token store (needed for background polling) breached, giving 6-month refresh tokens for every user [verified, 6] | Store | 1×3=3 per user, ×N users | 1×3 (no store in v1; encrypted `HttpOnly` cookie; rotation on refresh) |
| H-4 | I | **Cross-tenant data leak.** Cache keyed by `repo` and not by user, or a CDN caching an artifact proxy response, so user B sees user A's private run logs | BFF caches, CDN | 2×3=6 | 1×2 |
| H-5 | T | **Artifact proxy zip-slip / zip bomb.** A crafted `harness-state` zip (run-controlled content) exhausts the serverless function or writes outside temp | Artifact proxy | 2×2=4 | 1×1 (stream entries in memory, cap sizes, no disk extraction) |
| H-6 | E | **Over-broad GitHub App permissions** (Contents RW, Workflows, Administration, Secrets). Request only Issues RW, PRs R, Actions RW, Contents R, Metadata R (07 §4c). **Never Secrets or Workflows.** This set cannot set the `DEVSCENE_REMOTE_STOP` repository variable (that needs Variables RW and admin-level rights), so hosted "global stop" = cancel the run's workflow (Actions RW) plus an "open settings" link (§3.10) | App registration | 2×3=6 | 1×2 |
| H-7 | S | **Subdomain/cookie tossing** from the marketing site (a shared parent domain) | DNS/cookies | 1×2 | 1×1 (separate registrable domain or `__Host-` cookies) |
| H-8 | D | Denial of wallet: an XSS or a bug dispatches runs on many repos | Dispatch verb | 2×3=6 | 1×2 |
| H-9 | R | No audit: dispatches show as the *user* in GitHub (good for audit), but Studio-side actions aren't logged | BFF | 1×1 | – |
| H-10 | I | **Operator compromise** (owner's Vercel/Cloudflare account, CI, domain) gives malicious JS to every user | Ops | 1×3 | 1×3 (2FA/passkeys, deploy protection, SRI is moot for first-party) |

The worst case differs in kind from the local modes. No local RCE, but **one bug reaches every user's repos**, and the operator takes on GDPR processor duties (07 §4c). The residual is "medium, concentrated". [inferred]

#### 2f. Hosted UI + local connector

It inherits **all of 2d and 2e**, plus:

| ID | Threat | L×I | After |
|---|---|---|---|
| C1 | **Hosted XSS → local spawn on every connected machine.** The connector must trust the hosted origin by CORS, so any script on that origin is trusted | 3×3=9 | 2×3. Even with local confirmation (pairing code or OS notification), users click through prompts |
| C2 | **Hosted operator compromise → fleet-wide local RCE** (H-10 × W*) | 1×3 ×N | 1×3 ×N |
| C3 | Chrome LNA prompt fatigue (public origin → loopback) [verified, 5]; Safari/Firefox behaviour untested (07) | 2×2 | 2×2 |
| C4 | Version skew: a hosted UI updated instantly against an old connector with an old security posture | 2×2 | 1×2 (the connector refuses unknown contract majors) |

Only this mode turns a web vulnerability into machine compromise at scale. [inferred]

### 3. Cross-cutting threats and controls

#### 3.1 XSS from GitHub content and logs

| Surface | MUST | Why |
|---|---|---|
| Markdown (issue/PR bodies, comments, questions) | `markdown-it` with `html: false`, `linkify: true`, then **DOMPurify ≥ 3.4.17** (latest, 2026-10-12 [verified, 10]), **auto-tracked, with the floor raised on every advisory**, with `ALLOWED_TAGS` = a fixed short list (which also keeps out tags like `selectedcontent`) and `ALLOWED_URI_REGEXP` = `^(https:|#)`. 2026 brought **25 repository advisories** [verified, 11]. Most need non-default options (`IN_PLACE` ≈ 10, `SAFE_FOR_TEMPLATES` + `RETURN_DOM`, `CUSTOM_ELEMENT_HANDLING`, hooks, `ADD_TAGS` predicates), but **at least one bypassed the default configuration**: GHSA-87xg-pxx2-7hvx (CVE-2026-47423, high, "XSS via `selectedcontent` re-clone", plain `DOMPurify.sanitize(dirty)` on 3.4.4, fixed 3.4.5) [verified, 11]. Others: GHSA-r47g-fvhr-h676 (fixed 3.4.6), GHSA-rp9w-3fw7-7cwq (3.4.7), CVE-2026-0540 (rawtext, fixed 3.3.2 / 2.5.9). Still use **default mode** only (no `IN_PLACE`, no `SAFE_FOR_TEMPLATES`, no `RETURN_DOM`), but don't treat it as safe on its own: this record is the case for Trusted Types + CSP as independent layers | Two independent layers; the sanitizer is the only layer that sees HTML, and it does fail |
| Images | **No remote images.** Replace them with a link "image: host/path". `img-src 'self' data:` | Tracking-pixel IP leak; GET-CSRF to a localhost API (§2d) |
| Links | `https:` only; `rel="noopener noreferrer"`; shells open them through the external-link allowlist; show the full URL on hover | E2/E3 |
| ANSI logs | A parser that emits **text nodes** plus `class` from a closed SGR palette (`ansi-red` …). Never `innerHTML`. Drop every OSC sequence (OSC 8 hyperlinks, OSC 52 clipboard), DCS/APC, and C0 controls but `\n`/`\t`. Cap line length (e.g. 8 KB) and count (virtualised) | An OSC 8 link renders an attacker URL behind innocent text; OSC 52 matters if logs are ever piped to a terminal (§3.5 hand-off) [inferred] |
| Bidi / invisible | Render U+202A–202E, U+2066–2069, U+200B–200D, U+2060, U+FEFF (anywhere but offset 0), U+00AD, U+180E and U+E0000–E007F as visible escape glyphs **in the start confirmation and the answer form** | The harness pre-scans these classes, including U+2060 and U+FEFF (`prompt-injection-screen.sh:34-38`); the human must see them too |
| Copy buttons | "Copy log" never copies revealed secrets (§3.8). Any "copy command" button strips bidi characters and C0 controls before writing the clipboard | Pastejacking into a terminal |
| CSP | `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'` (+ the API origin); `frame-ancestors 'none'`; `base-uri 'none'`; `form-action 'none'`; **`require-trusted-types-for 'script'; trusted-types studio-dompurify`** | Trusted Types is **Baseline 2026** (newly available since Feb 2026; Firefox 148, Safari 26) [verified, 12]. WebKitGTK is reported to enable it by default from 2.50.0 (2025-09-17) [secondary, per the review; not found in the 2.50.0 release note]. Ubuntu 22.04/24.04 have it only if their webkit2gtk-4.1 security updates are at 2.50 or later, so Studio's doctor view should report the WebKitGTK version, and TT stays defence in depth, not the only control [inferred] |
| Framework | React/Svelte text interpolation only. Lint-ban `dangerouslySetInnerHTML` / `{@html}` except in the one sanitizer component | One reviewed sink |

#### 3.2 Command and argument injection (`gh`, `git`, `wsl.exe`, `devscene`)

Rules for **one** argv builder module, the only place `spawn` is called. [inferred unless tagged]

1. **argv arrays, `shell: false`, absolute executable paths** (resolved once, 05 §2). On Windows, never spawn `.cmd`/`.bat` (Node's BatBadBut class, CVE-2024-27980 [secondary]). The only Windows executable is `C:\Windows\System32\wsl.exe`.
   - **Resolving `devscene` (MUST):** resolve it once by absolute path with the resolver's cwd at `$HOME`, never a repo. Refuse a resolved path that lies inside any detected repo (`node_modules/.bin/devscene` planted by a run, H1′) or in a group- or world-writable directory. Never run `npx`/`npm` with cwd in a repo; 05 §2's `npx -y devscene@<min>` fallback, if kept, runs from `$HOME` with `--cwd <repo>`.
   - 05 §2 resolves the CLI on Windows with `wsl.exe … -- bash -ilc 'command -v …'`, which goes through a shell, unlike rule 5's "always `--exec`". That is harmless because the string is a constant with nothing interpolated; it is the one allowed exception, and it must stay constant.
2. **Branch validation:** `^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$` (the class includes `_`, so harness names like `chore_devscene_env_variables` pass), no `..`, no `//`, no `@{`, no path component starting with `.`, no trailing `/` or `.lock`, **and** `git check-ref-format --branch` whose printed name equals the input. That second check is the harness's own rule; it catches `@{-1}` expansion (`harness-run-lib.sh:3014-3025`). The regex is stricter than git's on purpose: git allows `$()`;'`, which are harmless in argv but dangerous anywhere a string becomes a shell line (terminal hand-off, `bash -c`). The fixtures include real harness branches (`chore_devscene_env_variables`, `feat_x`), so the suite fails if the validator ever rejects them.
3. **End-of-options:** `git … --end-of-options <rev>` (git ≥ 2.24) or `--` before pathspecs. **`gh` (pflag) supports only `--`, not `--end-of-options`** (`unknown flag: --end-of-options`, observed), so never add it to `gh` argv; put values in flag form (`--repo`, `-f key=value`, `--body-file -` with stdin) and never positional free text. **Always pass `--repo`**, so `gh` never infers the repo from a hostile `.git/config` remote. `gh api` paths are built from validated `owner/repo` and numeric ids only. (`gh` extensions and aliases cannot shadow built-in commands, so extension hijack is not a threat.)
4. **Free text never in argv:** prompts, answers and issue bodies go through **stdin or a `0600` temp file** (`--prompt-file`, `--answers-file`, `--body-file`). That also keeps them out of `ps` and of Windows command-line quoting.
5. **`wsl.exe`:** always `wsl.exe -d <distro> --cd <linux-path> --exec <abs-path> <args…>`. `--exec` runs "without using the default Linux shell"; without it, `wsl.exe -- cmd` goes through the shell and `$( )` expands [verified, 13: WSL source and `Resources.resw`; the Learn page documents neither flag]. Windows→WSL argv crosses a **command-line string** (Windows has no argv): Node quotes it by MSVCRT rules, and `wsl.exe` parses it with its own rules, which are poorly documented (04 §2 [59]). So:
   - (a) keep argv to validated, metacharacter-free tokens (rule 2 makes branches safe);
   - (b) pass everything else by stdin or file;
   - (c) validate `<distro>` against `wsl.exe -l -q` output (`^[A-Za-z0-9._-]+$`);
   - (d) fuzz it (§4.3). `wsl.exe`'s exec mode re-parses the command line with `CommandLineToArgvW` (`microsoft/WSL` `src/windows/common/WslClient.cpp`) [verified, 13], so a mocked `wsl.exe` can apply the same parser on any Windows runner.
6. **Repo paths** must be in the detected **and trusted** repo set (realpath-compared, §3.11), never taken from the UI as free text.
7. **Environment and git hardening:** pass the §1.4 allowlist only; set `GIT_TERMINAL_PROMPT=0` and `GH_PROMPT_DISABLED=1`; never `GIT_DIR`/`GIT_*` from the user env. For every `git` call Studio runs in a repo: `git --no-pager -c core.pager=cat -c core.fsmonitor=false -c core.hooksPath=/dev/null -c diff.external= -c protocol.ext.allow=never`, plus `-c core.sshCommand=ssh` on the network verbs Studio runs. A run can't write the main `.git` (denied, `settings.autonomous.json:236-256`), but Studio also reads repos it did not set up (§3.11). Set `GIT_CONFIG_NOSYSTEM=1` only if testing shows it breaks no user setups. `safe.directory` doesn't help: the repos belong to the same user [inferred].

#### 3.3 Path traversal reading run files

- Studio reads only `<stateDir>/{autonomous_logs,clarifications/<branch>,run_analytics,branch_statistics,flow_progress}` of **trusted detected repos and their registered run copies**.
- **Validate the root first.** `stateDir` and `scriptsDir` come from the repo's own `harness.config.json`, and the harness joins `stateDir` without a `..` check (`hr_state_path`, `harness-run-lib.sh:3202-3215`). Accept them only if relative, free of `..`, and their realpath lies inside the repo; otherwise `"stateDir": "../../.."` moves the confinement root to `$HOME`.
- Algorithm (macOS/Linux): build the path from validated parts (§3.2 rule 2), then `realpath` both root and target, then require `target.startsWith(root + sep)`, then open with `O_NOFOLLOW` where available. Re-check after open with `fstat` (inode/dev) against `lstat` to defeat a swap (§3.4).
- **Windows is different.** Windows `realpath` doesn't resolve Linux absolute symlinks behind `\\wsl.localhost` (they appear as LX reparse points), and over 9P there is no `O_NOFOLLOW` and no reliable inode compare. So on Windows, do every security-relevant run-file read **inside WSL**, through `devscene runs … --json` (05 §5) or a fixed reader under `wsl.exe --exec`; use `\\wsl$` paths for nothing security-relevant. [inferred; to confirm in 04's WSL measurement]
- **Never follow `log_path` or `worktree` from `registry.json` blindly.** Accept them only if they resolve inside the repo's own `stateDir` or a sibling run-copy root the harness itself names (05: run copies `<workRoot>/<repo>-<branch>`). The harness already treats links in bundles as hostile (`sandbox-record.md:180-181`), and Studio must too.
- Artifact zips: read entries in memory; refuse names with `..`, absolute paths, symlink entries, more than N entries or uncompressed > 50 MB.

#### 3.4 TOCTOU on state files

| Race | Effect | Control |
|---|---|---|
| Registry read while the watcher `mv`s a new copy | A partial read is impossible (the harness writes tmp + `mv`, `harness-run-lib.sh:3532-3540`), but a stale read is not | Read once, parse once; never read-modify-write the registry from Studio. **Studio is never a registry writer**: acts go through `devscene runs …` (05) |
| Check "branch free" → drop inbox file | Two drops race (Studio + `/devscene:branch-prompt`) | The collision guard belongs in the harness verb (`runs drop`), under the harness's lock, never in the app |
| `lstat` → open on a run file a sandboxed agent controls | Symlink swap to `~/.ssh/id_ed25519` between check and open | `O_NOFOLLOW` + `fstat` compare (§3.3); serve bytes only from the opened fd |
| Answer form shows `question_3.md`, the agent rewrites it before submit | The user answers a different question | Show the question's sha256 or mtime; `runs answer` takes `--expect-sha` and refuses on mismatch (§5.3) |
| Issue edited between review and Start | The run gets text the user never saw | Start confirmation shows `updated_at`. **Remote:** Studio applies the label only if `updated_at` still equals the reviewed value (re-fetch, compare, label). The harness snapshots text at label time (`remote-run.sh:4653`), so the window is seconds, not unbounded |

#### 3.5 Prompt injection: app versus harness

Issue text, review rounds and answers flow into an agent with write access to a branch. Division of labour:

| Owned by **the harness** (already present, verified) | Owned by **the app** (to build) |
|---|---|
| Sandbox with `failIfUnavailable`, `allowUnsandboxedCommands: false` and an empty network allowlist (`settings.autonomous.json:112-126`) | **Provenance on every card and in the start dialog:** issue author, author association (OWNER/MEMBER/CONTRIBUTOR/NONE), labeller, `created_at` / `updated_at`, "edited after labelling" flag |
| `dontAsk` with a closed allow list, a deny floor, and credentials denied for files and env (`:30-153`) | **Show exactly what the run receives** (title + body + provenance footer, as the trigger composes it), not a re-rendered approximation |
| Prompt-injection screen, deterministic prescan + LLM reviewer, "a tripwire, never a boundary" (`prompt-injection-screen.sh:7-10`; `prompt-injection-reviewer.md:10`) | **Display the screen's verdict and findings** when the harness exposes them (it records them in the ledger and park files, §5.3). An UNSAFE park shows as a red badge with the excerpt, never as an ordinary question |
| Trigger and command authorization: writer + `DEVSCENE_RUN_ACTORS` allow-list, owner-only by default (`remote-run.sh:4366-4455`) | **Require explicit confirmation naming the branch and the source** for every start, answer and resume. No drag-to-start without a dialog (Issue item 11 already has a confirmation; keep it on drag too) |
| Mention reader: read-only tools, closed decision set, `--max-budget-usd 1`, credential echo check (`remote-run.sh:600-660`) | **Warn for non-member authors** ("This issue was written by @x, who has no write access. Starting runs an agent on their text.") and default to *off* the one-click start for them |
| Answer files screened before use (`prompt-injection-screen.sh:50-56`) | **Answers typed in Studio are the user's.** Never pre-fill them from issue comments or model output |

**Not the app's job:** detecting injection by itself (no model in the app; regex heuristics would be false comfort). **Never the app's:** auto-starting a run on any GitHub event. [inferred]

**Terminal hand-off (Issue item 10):** when Studio opens a terminal to run `/devscene:harness-analyze`, it passes a **fixed** command with no interpolated repo text, and never `cat`s logs into it (OSC 52 / title-injection escapes). [inferred]

#### 3.6 Update channel and code signing

| Mechanism | Verified behaviour | Key custody (MUST) |
|---|---|---|
| Tauri updater | Signature mandatory and cannot be disabled; downgrades refused by default; TLS enforced; **lost key = stranded installs** [verified, 4] | Private key + password as CI secrets in a **protected environment with required reviewers** (GitHub's hardening guide recommends environment secrets with reviewers [verified, 8]); offline encrypted backup in two places; document a key-rotation release (ship the new pubkey in an update signed by the old key) |
| electron-updater 6.8.x | Windows: Authenticode against `publisherName` (`verifyUpdateCodeSignature`, default true); macOS: the app must be signed; **Linux deb/AppImage: sha512 from the manifest only**; dpkg/apt verify no signature on a local `.deb` [verified, 9]. `allowDowngrade=false` (cross-channel only) [verified, 9] | Signing certs on HSM/cloud signing (Azure Artifact Signing or OV on a token, 04 §7); Apple Developer ID in the notary pipeline. For Linux, **add a detached minisign/sigstore signature check in a custom `verify` hook**, or accept that the GitHub Releases account is the trust root |
| Native | Sparkle EdDSA (macOS); MSIX/Authenticode (Windows); distro signing (Linux) | Same custody rules |
| Local web app via npm | No signature at install; integrity = npm registry + provenance | **npm trusted publishing** (OIDC, `id-token: write`, provenance automatic), npm CLI ≥ 11.5.1, and **"Require two-factor authentication and disallow tokens"** on the package [verified, 14] |
| Hosted | The deploy *is* the update | Deploy only from protected `main` with required review; host account with passkeys |

**Downgrade / freeze attacks:** an attacker replays an old, valid manifest (freeze) to keep users on a vulnerable build. Mitigations: manifests carry a `releaseDate`, and the client warns when the newest manifest it can see is more than 60 days old; a minimum-version kill switch in a separately signed file. SHOULD, not MUST, for v1. [inferred]

**Owner account takeover is the dominant risk** to A5 (GitHub, Apple, npm, the domain registrar, the host). MUST: hardware keys or passkeys on all of them; no long-lived npm or PAT tokens in CI. [inferred]

#### 3.7 Supply chain

Incidents for context (07 §2): the npm Mini Shai-Hulud waves (Apr–Aug 2026) and the crates.io `arrayref` republish (2026-08-20, live 86–107 min).

| Control | MUST/SHOULD | Note |
|---|---|---|
| Lockfile committed; `npm ci --ignore-scripts` in CI; allow-list the few packages that need install scripts (`electron` downloads its binary) | MUST | Worms spread through `postinstall` |
| **Dependency cooldown** (Dependabot `cooldown`, Renovate `minimumReleaseAge` ≈ 7 days) | MUST | Every 2026 malicious version was pulled within hours to days (07 #15: 86–107 min) [inferred] |
| Actions pinned by full SHA; `permissions: {}` at workflow level; **zizmor** (v1.32.0, 2026-11-02 [verified, 15]) in CI | MUST | Mirrors the harness's own practice (§5.1) |
| Rust: **`cargo-deny`** (advisories, licences, bans, sources; v0.20.2 [verified, 15]) | MUST if Tauri | |
| Rust: `cargo-vet` with imported audits (Mozilla, Google, Bytecode Alliance) | SHOULD | High setup cost for a solo owner; `cargo-deny` + cooldown covers most of it [inferred] |
| npm `audit signatures` / provenance checks on direct deps | SHOULD | |
| Minimal deps: no UI kit with 1,000 transitive deps; one Markdown lib + DOMPurify + one ANSI parser | MUST | Each is also an XSS-relevant component |
| Publish Studio with trusted publishing + provenance (npm) / SLSA attestations (`actions/attest-build-provenance`) for desktop binaries | MUST (npm) / SHOULD (desktop) | |
| Tauri isolation pattern (contains a compromised UI dep's IPC use) | SHOULD | §2b T3 |

#### 3.8 Secrets in logs shown in the UI

Logs carry tool output (`autonomous-format-stream.sh` keeps a 160-char command descriptor and 300-char assistant text; `.stream.jsonl` keeps whole `tool_result` bodies) and the agent's stderr (`autonomous-watcher.sh:3649`). GitHub's own guide warns that "automatic redaction is not guaranteed" [verified, 8].

- **MUST: display-time masking** with a pattern set: `gh[pousr]_[A-Za-z0-9]{36,}`, `github_pat_[A-Za-z0-9_]{80,}`, `sk-ant-[A-Za-z0-9_-]{20,}`, `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----` … `END`, `xox[baprs]-…`, `eyJ…\.…\.…` (JWT), `Authorization: (Bearer|token) \S+`, plus `KEY=VALUE` where KEY matches `/(TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE)/i`. Mask as `ghp_…••••(redacted)` with a "reveal" that requires a click and is never copied by "copy log".
- **MUST:** never show `.stream.jsonl` (it holds whole file reads). Show the formatted `.log` only.
- **MUST:** crash reports and telemetry use the same masker plus `$HOME` → `~`.
- **SHOULD:** an entropy heuristic (≥ 32 chars, Shannon > 4.0) as a dimmed warning, not a mask (false positives on hashes).
- The harness should redact at the source (§5, H3). The app's masking is display hygiene, not a boundary.

#### 3.9 Local privilege: other OS users

| Exposure | Today | Control |
|---|---|---|
| State dir files `0644`, dirs `0755` (observed: `autonomous_logs/*.log`, `autonomous_inbox/`, `clarifications/`); `registry.json` `0600` (mktemp + `mv`) [verified, local `stat`] | Other users on a shared Linux host or dev box can read prompts, questions and logs | Harness-owned (H3). The app warns in its doctor view when the state dir is group- or world-readable |
| Inbox dir `0755` | Only the owner can write; another user **cannot** drop a run [verified, local `stat`] | – |
| Local web app socket | Any local user (W4) | Secret in a `0600` file; consider a Unix domain socket in a `0700` dir for the Electron/Tauri→core path [inferred] |
| Home-directory traversal | OS-dependent. macOS homes are `drwxr-x---+` with group `staff`, which every local user is in, so other accounts *can* traverse into `~/Work` and read `0644` files (observed on the owner's machine). Ubuntu ≥ 21.04 homes are `0750` with a per-user group, so other users can't [inferred from distro defaults] | The doctor-view warning above matters most on macOS |
| Windows: `\\wsl$` | Other Windows users can't open another user's WSL instance by default [inferred]; `localhostForwarding` *does* expose listeners (W4) | – |
| Studio's own config/cache (`~/Library/Application Support/…`, `$XDG_CONFIG_HOME`) | – | Create `0700`; store no tokens |

#### 3.10 Cost and denial-of-wallet guard

The harness bounds **concurrency** (`MAX_PARALLEL_RUNS_DEFAULT=5`, clamped to 1 on bubblewrap hosts, `autonomous-watcher.sh:1450-1476`). It also bounds **subscription windows** (the usage gate pauses on rate-limit events, `USAGE_PAUSE_TRIGGER`, tunables echoed at `:2324`) and **remote auto-resume** (`REMOTE_AUTO_RESUME_MAX=2`, `:1650`). It has **no dollar or count ceiling per run, per day or per repo** for task runs (§5, H2). With an API key, cost is unbounded over time. [verified]

The app MUST add, client-side:
- **a confirmation per start, answer and resume, rendered by the privileged side.** In a desktop shell the act verb (`start`, `answer`, `resume`, `drop`) opens an **OS-native modal** from the main process or Rust core (`dialog.showMessageBox` / `tauri-plugin-dialog` / `NSAlert`). The modal shows repo, branch, local/remote, the source author and a hash or excerpt of the exact text, and the verb executes only on that modal's result. The renderer never passes `confirmed: true`. If the dialog were renderer HTML, an XSS could call the verb and click "Confirm", and E1/T1 would stay at I3. In the local web app the equivalent is a server-issued one-time nonce bound to the payload hash, which stops CSRF and replay but **not** XSS (W6);
- **no batch start** ("start all To Do") in v1;
- **a visible global stop** one click from the board: `AUTONOMOUS_STOP` locally. For remote runs, `DEVSCENE_REMOTE_STOP` is a **repository variable** (`remote-run.sh:242`, read as `vars.DEVSCENE_REMOTE_STOP` in the workflows); setting it needs the Variables permission and admin-level rights. With `gh` the user's own rights apply. In the hosted app (H-6's minimal set), remote stop = cancel the run's workflow (Actions RW) plus an "open settings" link to set the variable.

The app SHOULD add:
- **a start budget:** at most N starts (default 3) per 10 minutes per repo, and at most M (default 10) per day across repos, with an explicit override dialog;
- **an anomaly banner** when more than 3 runs are live or spend (from `run_analytics`) exceeds a user-set daily figure.

*Why SHOULD and not MUST (calibration):* once every start needs a click in an OS-native modal, neither an XSS nor a script can start runs without the human, so a rate limit adds little for a solo-owner v1. The cost ceiling that matters belongs in the harness (H2). The budget becomes MUST if Studio ever adds a start path without a native modal.

The hosted mode MUST enforce the budget **server-side**, per user and per repo: a browser has no native modal, so an XSS can bypass client counters and click through the confirmation (H-8). [inferred]

#### 3.11 Untrusted repos (repo scan and auto-doctor)

Issue item 8 auto-detects repos by scanning for `harness.config.json`. Item 9 runs `devscene doctor` "on startup and whenever the repo changes". Every cloned OSS repo, extracted tarball or shared-drive folder carrying that file therefore becomes a place Studio spawns processes, with no click. Verified paths to code execution or redirection:

| Path | Evidence | Effect |
|---|---|---|
| `doctor` spawns the Python retrieval self-check with `env: { ...process.env, ...overlay, … }`, where `overlay` is every string in `.mcp.json` → `mcpServers.<docs server>.env` | `cli/src/doctor/checks.ts:6230-6251` (`runPythonSelfCheck`); reached when the repo's own config makes `pythonRetrievalApplies` true | `LD_PRELOAD=./x.so` (Linux/WSL), `PYTHONPATH=./evil`, `BASH_ENV` → code execution when the launcher is installed. Harness bug **H12**; Studio's auto-doctor makes it reachable without a click [verified] |
| `doctor` runs `npm view` with cwd in the repo | `checks.ts:5883` (`probeRegistrySpec`) | The repo's `.npmrc` (registry, proxy, `cafile`) applies [verified] |
| `stateDir`/`scriptsDir` from the repo's config | `harness-run-lib.sh:3202-3215` joins `stateDir` without a `..` check | Moves §3.3's confinement root [verified] |
| `git` in a repo whose `.git/config` the user didn't write | git semantics | `core.fsmonitor`, `core.pager`, `diff.external`, `core.sshCommand`, `filter.*` run commands [inferred: git docs] |

MUST:
- Detected repos are listed but **not trusted** until the user confirms each one, as in VS Code's Workspace Trust. Trust is keyed by realpath and stored in Studio's own `0700` config.
- No `doctor`, no `devscene` and no `git` spawn with cwd in an untrusted repo. Untrusted cards show the path and a "Trust this repo" action only.
- Spawn `devscene … --cwd <repo>` with the **process** cwd outside the repo, as the harness itself does for its own `npm`/`npx` calls (`docs/sandbox-record.md` §6 residual 1.1).
- Validate `stateDir`/`scriptsDir` before use (§3.3).
- Apply §3.2 rule 7's git hardening to every git call, trusted repo or not.
- A fixture "hostile repo" (planted `.mcp.json` env, `.npmrc`, `.git/config` with `core.fsmonitor`/`core.pager`, `"stateDir": "../.."`) in §4.3: assert that no process starts before trust, and that after trust none of the planted commands runs.

#### 3.12 Trusting GitHub state (Issue item 5's read model)

Issue item 5 builds remote state from `sdlc-harness: <state>` **labels**, the **progress comment**, and `run_analytics/` / `branch_statistics/` **committed on the branch**. Anyone with triage can set labels; anyone can comment on a public repo; anyone who can push the branch controls the committed JSON. The harness itself trusts `<!-- devscene` markers only from `github-actions[bot]` with an exact shape (`remote-run.sh:683-694`). MUST for Studio:
- trust the progress comment only when `user.login == "github-actions[bot]"` **and** it has the exact marker shape; ignore lookalikes and quotes;
- prefer Actions run state (the workflow-runs API) over labels for status; show a label/run-state mismatch as a warning, never resolve it in the label's favour;
- treat branch-committed JSON as untrusted: schema-validate it, cap its size, render numbers only (no strings into Markdown).

#### 3.13 Deep links

04 §9 and 07 8.5 discuss a custom URL scheme for "open run in Studio". Any web page can invoke a registered scheme. **v1 registers no scheme.** If one is added later, it is navigation-only (`open?repo=&branch=`, both validated by §3.2 rules 2 and 6, and the repo must already be trusted) and never carries an act verb or free text.

### 4. Depth required per mode

#### 4.1 Control checklist (M = MUST, S = SHOULD, – = n/a)

| # | Control | Electron | Tauri 2 | Native | Local web | Hosted | Hybrid |
|---|---|---|---|---|---|---|---|
| 1 | Markdown → sanitizer (DOMPurify ≥ 3.4.17, latest, auto-tracked, default mode) → TT policy; no remote images | M | M | – (no HTML) | M | M | M |
| 2 | Closed-palette ANSI parser, OSC stripped, text nodes | M | M | M (text widget) | M | M | M |
| 3 | Strict CSP + Trusted Types | M | M | – | M | M | M |
| 4 | Intent-level privileged API only (no `exec`, no path args) | M (preload) | M (commands + `AppManifest::commands`) | M (internal) | M (HTTP) | M (BFF) | M |
| 5 | Single argv builder; branch regex + `check-ref-format`; `--end-of-options`; free text via stdin/file; `wsl.exe --exec` | M | M | M ×3 | M | – (API only) | M (connector) |
| 6 | Realpath-confined reader, `O_NOFOLLOW`, registry paths not trusted | M | M | M | M | M (zip) | M |
| 7 | Display-time secret masking; never show `.stream.jsonl` | M | M | M | M | M | M |
| 8 | Provenance + exact-text confirmation for start/answer/resume, **rendered by the privileged side** (OS-native modal in shells; payload-bound nonce on the web); non-member warning | M (main-process modal) | M (Rust-side dialog) | M (native) | M (nonce) | M (nonce) | M (connector-local) |
| 9a | No batch start; one-click global stop | M | M | M | M | M (cancel workflow) | M |
| 9b | Start budget (rate, daily cap) and anomaly banner | S | S | S | S | M (server-side) | M (both) |
| 10 | Child env allowlist; never spawn `claude`; CI grep for `~/.claude`/`ANTHROPIC` | M | M | M | M | – | M |
| 11 | External-link allowlist, navigation/new-window deny | M | M | M | S | S | S |
| 12 | Fuses / capabilities hardening | M (fuses) | M (capabilities, no shell/fs plugin) | – | – | – | – |
| 13 | Isolation pattern | – | S | – | – | – | – |
| 14 | No CDP/debug port in release; CI asserts | M | M (WebView2 env) | – | – | – | – |
| 15 | Signed updates; key custody in protected environment; offline backup | M | M | M | M (npm trusted publishing, no tokens) | M (deploy protection) | M (both) |
| 16 | Linux update signature beyond sha512 | S | built in | distro | – | – | – |
| 17 | Bind 127.0.0.1 only (refuse others), Host allowlist, Origin on writes and WS, `Origin: null` refused | – | – | – | M | – | M |
| 18 | ≥ 128-bit secret in `0600` file, fragment → `HttpOnly; SameSite=Strict` cookie, custom header on writes | – | – | – | M | – | M |
| 19 | GET side-effect free; confirmation nonce on act endpoints; audit log | – | – | – | M | M | M |
| 20 | GitHub App (not OAuth App), minimal permissions, PKCE + `state`, no token store in v1, `__Host-` cookies, separate domain | – | – | – | – | M | M |
| 21 | Per-user cache keys; no CDN caching of private responses | – | – | – | – | M | M |
| 22 | Local confirmation on the connector for act verbs (not hosted-supplied) | – | – | – | – | – | M |
| 23 | Supply chain: lockfile, `--ignore-scripts`, cooldown, SHA-pinned actions, zizmor | M | M (+ `cargo-deny`) | M | M | M | M |
| 24 | Ship within 14 days of upstream security releases (Electron, DOMPurify, Tauri) | M | M | S | M | M | M |
| 25 | Privacy policy, incident response, breach notification | – | – | – | – | M | M |
| 26 | Repo trust gate: no `doctor`/`git`/`devscene` spawn in an untrusted repo; `stateDir`/`scriptsDir` validated; process cwd outside the repo (§3.11) | M | M | M | M | – | M (connector) |
| 27 | `devscene` resolved by absolute path from `$HOME`, never inside a repo or a writable dir; no `npx` with a repo cwd (§3.2 rule 1) | M | M | M | M | – | M (connector) |
| 28 | GitHub read model: progress comment only from `github-actions[bot]` with the exact marker; Actions run state over labels; branch JSON schema-validated (§3.12) | M | M | M | M | M | M |
| 29 | No custom URL scheme in v1; any later one navigation-only (§3.13) | M | M | M | – | – | – |

#### 4.2 Effort (owner-days, 03's unit; agents write the code, owner reviews and tests)

| Block | Electron | Tauri 2 | Native ×3 | Local web | Hosted | Hybrid |
|---|---|---|---|---|---|---|
| Rendering pipeline (1–3), components + review | 1.0 | 1.0 | 0.5 ×3 → 1.0 (cheaper per OS, ×3 review) | 1.0 | 1.0 | 1.0 |
| Argv builder + validators + path reader (5–6) | 1.0 | 1.0 (Rust) | 0.5 ×3 → 1.0 | 1.0 | 0.3 (zip) | 1.0 |
| Masking, provenance, no-batch, stop (7, 9a); budget (9b) only where MUST | 0.5 | 0.5 | 0.25 ×3 → 0.75 | 0.5 | 1.0 (server-side budget) | 1.25 |
| Trust gates: privileged-side confirmation (8), repo trust (26), CLI resolution (27), GitHub read model (28) | 0.5 | 0.5 | 0.25 ×3 → 0.75 | 0.75 (nonce + trust) | 0.2 (read model) | 1.0 |
| Shell hardening (11–14, 29) | 0.75 | 1.0 (capabilities + isolation) | 0.25 | – | – | – |
| Listener hardening (17–19) | – | – | – | 2.0 | – | 2.0 |
| Auth / BFF / multi-tenant (20–21) | – | – | – | – | 3.0 | 3.0 |
| Connector pairing and local confirmation (22) | – | – | – | – | – | 1.5 |
| Update signing and key custody (15–16) | 0.5 | 0.5 | 0.75 | 0.5 | 0.25 | 0.75 |
| Supply chain setup (23) | 0.25 | 0.5 (+ `cargo-deny`) | 0.5 | 0.25 | 0.25 | 0.5 |
| CI security suites (§4.3) | 1.0 | 1.0 | 0.75 | 1.75 | 1.5 | 2.5 |
| Privacy, IR, operations docs (25) | – | – | – | – | 1.0 | 1.0 |
| **Total v1, point (range = point ± 30%)** | **≈ 5.5** (3.9–7.2) | **≈ 6.0** (4.2–7.8) | **≈ 5.75 total for 3 apps** (4.0–7.5); ≈ 1.9 per app | **≈ 7.75** (5.4–10.1) | **≈ 8.5** (6.0–11.1) + ops | **≈ 15.5** (10.9–20.2) |
| Share of 03's ≈ 27 O-d v1 | ≈ 20% | ≈ 22% | ≈ 21% | ≈ 29% | ≈ 31% + ops | ≈ 57% |
| Recurring | Electron bump every 8 weeks (≈ 0.25 O-d each, ≈ 1.6 O-d/year) | Tauri/WebKitGTK tracking (low) | 3 toolchains | npm releases | **On-call, patching, GDPR requests** | Both |

How to read it [all inferred]:
- **Ranges are point ± 30%**, the same sensitivity band 03 uses. The point is the sum of the column; the range is not centred anywhere else.
- **Tauri costs ≈ 0.5 O-d more than Electron up front**: capabilities + the isolation pattern (+0.25) and `cargo-deny` (+0.25). Electron's extra cost is recurring: shipping each Chromium bump within 14 days (row 24).
- **Native is ≈ 5.75 for all three apps, ≈ 1.9 per app**, about the same total as a shell. Native is cheaper per codebase but carries three review surfaces and parity drift (N6).
- **What changed after review:** the trust-gate row is new (native confirmation, repo trust, CLI resolution, GitHub read model: +0.2 to +1.0 per mode); the start budget moved to SHOULD for the non-hosted modes (−0.25). The CI suites are unchanged: the hostile-repo fixture and the protocol traversal test (+) roughly offset the smaller MUST fuzz/XSS volumes and dropping the real-WSL PR gate (−).

#### 4.3 CI security tests

1. **XSS payload corpus (all web-tech modes, MUST).**
   - **Corpus:** a fixture that starts at about 50 strings and grows toward 150+ (every new advisory adds its payload), covering:
     - script/`onerror`/SVG `onload`/`<math>` mutation XSS; `javascript:`, `data:text/html`, `vbscript:` links, including entity-encoded and whitespace-split variants;
     - Markdown-specific: `[x](javascript:alert)`, reference links, autolinks `<javascript:…>`, HTML blocks, raw `<iframe>`, `<base>`, `<meta http-equiv>`, `<form>`;
     - DOM clobbering (`id="__proto__"`, `name=attributes`);
     - the 2026 DOMPurify bypass payloads from the advisories [11], including the default-config `selectedcontent` re-clone (GHSA-87xg-pxx2-7hvx);
     - ANSI: SGR combos, OSC 8 `\e]8;;javascript:…\e\\`, OSC 52, CSI with huge params, unterminated sequences;
     - bidi/zero-width text.
   - **Harness:** Playwright renders each string as an issue body, a comment, a question file and a log line in every component. It asserts no `dialog` event, no network request outside `self`, no `javascript:` href in the DOM, no element outside the allowlist, and a CSP violation count of 0 (the CSP report handler counts them).
   - Run it on every PR and after each dependency bump.
2. **Argument-builder fuzz (all spawning modes, MUST).**
   - **Generator:** property-based (fast-check / `proptest`), producing branches, repo paths, distro names and titles from a grammar of shell metacharacters, leading `-`, `--`, Unicode, `..`, NUL, CR/LF, `%`, `^`, `"`, `\`, and very long strings.
   - **Fixed fixtures:** real harness branch names (`chore_devscene_env_variables`, `feat_x`, names with `/`) must be **accepted**; the suite fails if the validator rejects them.
   - **Assertions, per input:**
     - (a) the builder either rejects it or produces argv where no element starts with `-` except builder-owned flags;
     - (b) free text never appears in argv;
     - (c) argv round-trips **byte-identically** through `wsl.exe --exec /usr/bin/printf '%s\0' <args>`. In CI (MUST): a mocked `wsl.exe` on a GitHub-hosted Windows runner that applies `CommandLineToArgvW`, the parser `wsl.exe` uses [verified, 13]. The real round trip on Windows + WSL is a **release-checklist step on the owner's machine**, not a PR gate: GitHub-hosted Windows runners don't support WSL2 nested virtualisation (risk #2).
   - MUST: 10k cases on every PR. SHOULD: a longer nightly run (e.g. 1M) once the suite is stable. *Calibration:* 1M nightly and a real WSL runner as a PR gate are overkill for a solo v1; the 10k PR run plus the mock catches the same classes of bug.
3. **DNS rebinding / CSRF / WebSocket suite (local web app and connector, MUST).** Against a running server:
   - `Host: evil.com:PORT`, `Host: 127.0.0.1.nip.io:PORT` and missing Host → 403;
   - cross-origin POST with `text/plain` → 403;
   - POST with `Origin: null` → 403;
   - WS upgrade with `Origin: https://evil.com` → refused;
   - token in the query string → refused (and never logged);
   - the bind address is exactly `127.0.0.1`/`::1` (`ss -ltn` / `netstat`);
   - an unauthenticated health endpoint returns no data;
   - a real-browser test: a page on `http://rebind.test` (a local resolver flips to 127.0.0.1) tries fetch + WS and gets nothing.
4. **Path traversal tests (MUST):** `..`, encoded `..%2f`, absolute, symlink-to-`~/.ssh`, a registry `log_path` outside the root, `"stateDir": "../.."` in config, swap-during-read (a race test with a symlink flip loop). Electron: `app://studio/../…` and encoded variants against the protocol handler → 400 (E12).
5. **Hostile-repo fixture (MUST, spawning modes, §3.11):** a repo with a planted `.mcp.json` env overlay, `.npmrc`, `.git/config` (`core.fsmonitor`, `core.pager`, `diff.external`) and a `node_modules/.bin/devscene`. Assert that no process starts in it before trust, that after trust none of the planted commands runs, and that CLI resolution never picks the repo-local `devscene`.
6. **Release assertions (desktop, MUST):** no `--remote-debugging-port` / `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` in the release config; Electron fuses read back with `@electron/fuses read`; Tauri capability JSON snapshot-tested (a diff needs review).
7. **Hosted (MUST):** an OAuth flow test (missing or mismatched `state` refused, PKCE required); tenant-isolation tests (user B can't read A's cached artifact); response headers (CSP, `X-Content-Type-Options`, `Cache-Control: private, no-store` on data).
8. **Supply chain (MUST):** `npm ci --ignore-scripts`, `zizmor --min-severity medium`, `cargo deny check` (Tauri), and a lockfile-diff review gate.

#### 4.4 Comparison: mode × security profile

| Mode | Attack surface | Worst-case impact | Controls effort (v1 O-d) | Residual risk after MUST |
|---|---|---|---|---|
| Native ×3 | Smallest: no HTML engine, no listener; 3 codebases | Argv bug → local command execution as the user | ≈ 5.75 total (4.0–7.5); ≈ 1.9 per app | **Low**, but parity drift (N6) |
| Tauri 2 | Webview + capability-scoped IPC; Rust core; mandatory signed updater; OS-patched webview on macOS/Windows | XSS → intent verbs, each behind a native modal | ≈ 6.0 (4.2–7.8) | **Low** |
| Electron | Webview + preload IPC; bundled Chromium you must patch; Linux updates sha512-only | Same as Tauri; plus Chromium n-day if releases lag | ≈ 5.5 (3.9–7.2) | **Low–medium** |
| Hosted remote-only | Public multi-tenant BFF + SPA; GitHub App tokens | Every user's repos via their tokens (label → run → spend) | ≈ 8.5 (6.0–11.1) + ops | **Medium per user; worst in aggregate** of the single modes |
| Local web app | Spawning socket: browser, other users, Windows forwarding, LAN misconfig | Local RCE-equivalent (start agent runs) from a web page if any check regresses | ≈ 7.75 (5.4–10.1) | **Medium** |
| Hosted + connector | Union of both, plus a trusted cross-origin bridge | Hosted XSS or operator compromise → process spawn on every connected machine | ≈ 15.5 (10.9–20.2) | **High** |

The TL;DR's order (hosted < local web) is **per user**. Hosted's worst case is every user's repos, local web's is one user's machine, so in aggregate hosted is the worse of the two. Read them as tied unless you pick an axis. [inferred]

### 5. Harness-owned (follow-up issues for devscene)

> Read-only review of `/Users/daniel/Work/devscene` at `a1d0e99` (2026-11-12). Nothing was changed. Paths are relative to that repo. Severity is for devscene users in general, not only Studio. Every path:line below was re-checked by the review at `a1d0e992` (drift of a few lines at most). H1 and H1′ are confirmed by settings analysis; their runtime behaviour still needs a measurement row in `docs/sandbox-verification.md` (risk #1). This section lists harness findings only; Studio's own controls are §3–§4.

#### 5.1 What is already strong (context for the findings)

- **Workflows.**
  - `permissions: {}` at workflow level with per-job grants (`cli/templates/github/workflows/devscene-trigger.yml:110-123`, `devscene-control.yml:259-274`).
  - Actions pinned by full SHA (`devscene-trigger.yml:133-134`).
  - Event text reaches shell only through `env:` and the event file, an explicit rule (`devscene-trigger.yml:67-70`), and every expression in the run workflow is `env:`-only (`devscene-run.yml:612-621`).
  - **Never `pull_request_target`** (`devscene-control.yml:96-97`); fork PR comments refused (`remote-run.sh:685-687`).
  - The trigger job reads no repository secret (`devscene-trigger.yml:47-48`).
  - Secrets reach the control job only on `issue_comment` (`devscene-control.yml:381-383`).
  - The run branch cannot change job files (`devscene-run.yml:762-766`, `doctor --job-surfaces`).
  - The run checkout has `persist-credentials: false` (`:741`).
- **Who can trigger.**
  - Labeller must have `write`/`admin` (`remote-run.sh:4440-4451`), and must be on `DEVSCENE_RUN_ACTORS`, which **defaults to the repo owner alone** (`:4366-4393`).
  - Bots only if listed (`:4435-4439`).
  - For an **org-owned** repo with `DEVSCENE_RUN_ACTORS` unset, the default admits **nobody** (fail-closed), not the owner (`:4366-4393`).
  - A re-run checks the re-runner, not the original sender (`:4396-4411`).
  - `repository_dispatch` senders are held to the allow-list (`:299-306`).
  - `devscene-run.yml`'s own `workflow_dispatch` re-checks `github.triggering_actor` against `DEVSCENE_RUN_ACTORS` (`devscene-run.yml:509-534`), so a writer can't bypass the label gate by dispatching the run workflow directly.
  - **On a public repo, a stranger can open an issue but cannot start a run.**
- **Unattended session.**
  - `dontAsk`; a closed allow list; a deny floor; sandbox `enabled`, `failIfUnavailable`, `allowUnsandboxedCommands: false`, `strictAllowlist`, empty network list; credentials denied as files and env vars (`cli/templates/claude/settings.autonomous.json:30-153`).
  - The per-run copy is validated against the base before launch (`autonomous-watcher.sh:2855-2880`).
  - Launch with `--settings` + `--permission-mode` (`autonomous-watcher.sh:3641-3649`).
- **Mention reader.** Read-only tools, `--restricted`, `--strict-mcp-config`, closed JSON decision set validated by `jq`, `--max-budget-usd 1`, a credential-echo check, `stop`/`clear` need confirmation (`remote-run.sh:600-660`, `:1721-1745`, `:7611-7618`; `plugin/instructions/mention_reading.md:24-31`).
- **Inbox names.** `git check-ref-format --branch` with printed-equals-input, leading `-` refused, protected branches refused (`cli/templates/scripts/lib/harness-run-lib.sh:3014-3035`).
- **Registry.** Locked read-modify-write with a `mkdir` lock, tmp + `mv` (`harness-run-lib.sh:3370-3545`); `registry.json` is write-denied to the session (`.claude/settings.autonomous.json:256`).

#### 5.2 Findings, ranked

| ID | Sev. | Finding | Evidence (path:line) | Suggested follow-up |
|---|---|---|---|---|
| **H1** | **High** | **A sandboxed run can drive the watcher.** The chain: (1) the file tools run outside the sandbox under `Edit` rules, and the base profile grants `Edit(/{{repoRoot}}/**)` and `Edit(/{{worktreeGlob}}/**)` (`cli/templates/claude/settings.autonomous.json:59-60`); (2) the sandbox grants `allowWrite: [stateDirAbs]` (`:119`), and the watcher passes `--add-dir "$main_state"` (`autonomous-watcher.sh:3647`); (3) the inbox and kill switch are `harness-runs/autonomous_inbox` and `harness-runs/AUTONOMOUS_STOP` (`:1298-1300`), under both; (4) the only state-dir entry in `deny`/`denyWrite` is `registry.json` (`.claude/settings.autonomous.json:176`, `:256`; `cli/src/generators/writeProtection.ts:188-230`); (5) the per-run render only **adds** `hr_run_protected_rel_paths` (githooks, `.mcp.json`, `.claude/settings{,.local}.json`, docs-search launcher; `harness-run-lib.sh:4140-4153`), nothing for the inbox, answers or markers; (6) the only Edit/Write hook guards three `.git` trust files (`plugin/hooks/hooks.json`; `git-trust-file-guard.sh:60`); (7) the intake `process_inbox_file` (`autonomous-watcher.sh:5133-`) checks name, branch, protection, stop, usage, cap and duplicates, **not who wrote the file**. So a prompt-injected run could, with the Write tool: (a) drop `autonomous_inbox/<x>_task_prompt.md`, which **starts a new run** (bounded by `MAX_PARALLEL_RUNS`, unbounded over time); (b) write `answer_<n>.md` beside its own `question_<n>.md` in its run copy (`<worktree>/<state_rel>/clarifications/<branch>/`, `plugin/commands/branch-answer.md:39-41`, watcher `:4303`), **answering its own park** — the screen still checks it, but the screen is a tripwire run by the session itself; (c) write `RESUME` (`:4026`, `:4563`) / `PARK_LOOP_CLEAR`; (d) delete `AUTONOMOUS_STOP` with an allowed `find … -delete` (`Bash(find:*)`, `settings.autonomous.json:49`) | **Confirmed by settings analysis, runtime test pending** (risk #1): not yet measured whether Claude Code honours the `Edit` allow for a path in `--add-dir` under `dontAsk` exactly as the profile assumes | Narrow `Edit(/{{repoRoot}}/**)` to the state-dir subtrees a session actually writes (`task_plans/`, `flow_progress/`, `run_analytics/` …): every run now uses a clone (`copy_kind: clone`, `sandbox-verification.md` CS9). Add `denyWrite` + `Edit` deny for `<stateDir>/autonomous_inbox/**`, `AUTONOMOUS_STOP`, `PAUSE*`, and in run copies `clarifications/*/answer_*.md`, `RESUME`, `PARK_LOOP_CLEAR`. Or move the control channel outside the agent's write roots (e.g. `$XDG_STATE_HOME/devscene/<slug>/control/`). Add measurement rows. The watcher could also record the author of inbox files (writer pid → not the agent) |
| **H1′** | **High** | **The same grants reach sibling run copies and the main checkout's whole working tree.** (e) `Edit(/{{worktreeGlob}}/**)` renders to `Edit(//…/devscene-*/**)`, so a compromised run can write `answer_<n>.md`, `RESUME` or `PARK_LOOP_CLEAR` into **another** parked or paused run's copy, answering other runs' human checkpoints. (f) `Edit(/{{repoRoot}}/**)` covers the main checkout outside the protected list. The rendered deny list protects `scripts/`, `githooks/`, `.mcp.json`, `.claude/settings*.json`, `harness.config.json` and `.git`, but **not** `.claude/CLAUDE.md` (present in this repo), `.claude/context/*.md` (conventions every agent loads), `.claude/agents|commands|skills/` if present, `package.json`, `.npmrc` or `node_modules/` (both present) (`.claude/settings.autonomous.json` `deny`, checked by grep). The owner's next **interactive** Claude session, IDE tasks and any `npm`/`npx` run there read or execute them **unsandboxed**. This is a sandbox escape by persistence: none of it lands on the run's branch, so PR review never sees it | **Confirmed by settings analysis, runtime test pending** (same measurement as H1) | Narrow the repo-root `Edit` allow as in H1, so the main checkout's tree is not writable at all. In the per-run render, deny other sibling copies by exact path; the render already enumerates live worktrees for their `.git` pointers (`run_profile_entries`) |
| **H2** | **High** (for API-key users) | **No cost ceiling on task runs.** Task sessions launch without `--max-budget-usd` or `--max-turns` (`autonomous-watcher.sh:3641-3649`); only the mention reader has `--max-budget-usd` (`remote-run.sh:1745`, `:7618`). The bounds that exist are concurrency (`autonomous-watcher.sh:1450`), subscription-window pauses (the usage gate, `USAGE_PAUSE_TRIGGER`; its tunables are echoed at `:2324`) and remote auto-resume (`:1650`); remote job timeout up to `7200` min self-hosted (`devscene-run.yml:607`). There is no per-day run count. Subscription users are bounded by the usage gate; API-key users are not | Verified | `RUN_MAX_BUDGET_USD` (per session) and `DAILY_RUN_CAP` tunables; pass `--max-budget-usd`; a `budget` field in `devscene runs --json` (§5.3) |
| **H3** | **Medium** | **Logs are world-readable and unredacted, locally and on GitHub.** `autonomous_logs/*.log`, `*.stream.jsonl`, `clarifications/` and `.processed/` prompts are `0644`/`0755` (observed `stat`); `.stream.jsonl` holds whole tool results (`autonomous-format-stream.sh:13-20`). No redaction step exists (no `redact`/`add-mask` in `remote-run.sh`, `harness-run-lib.sh`, `autonomous-watcher.sh`). The `harness-state` artifact (`run.log`, clarifications) is kept `retention-days: 400` (`devscene-run.yml:1073-1075`) and on a public repo its name and metadata are listable anonymously, while downloading needs any signed-in account (anonymous `GET …/actions/artifacts` → 200, anonymous `…/artifacts/<id>/zip` → 401, observed on `cli/cli`) [verified, 16]. Treat run logs on public repos as public. The `answer` credential check exists only for mention text (`remote-run.sh:655-662`) | Verified (modes); inferred (secret presence) | `umask 077` for the state dir; a redaction pass (the `hr_text_has_credential` set + common token regexes) before writing `.log` and before `save`; document that public repos publish run logs; `::add-mask::` for derived values |
| **H4** | **Medium** | **Watchdog kills a registry pid without checking identity.** `pid` from the registry → `kill -0` → `kill -9 "$pid"` + descendants (`autonomous-watcher.sh:4750-4831`). After a reboot or pid reuse, an unrelated same-user process can be killed. The registry is session-write-denied, so this is a reliability bug more than an attack | Verified | Record `pid` + start time (`ps -o lstart=`) or a process-group id; verify before signalling |
| **H5** | **Medium** | **Unpinned agent CLI and a mutable plugin tag in secret-bearing jobs.** `npm install -g @anthropic-ai/claude-code` with no version (`devscene-run.yml:797`, `devscene-control.yml:342`), in jobs that then receive `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY` (`devscene-run.yml:804-805`, `devscene-control.yml:381-383`). The mention plugin is cloned by tag `devscene--v<pin>` with only a version-string check (`devscene-control.yml:347-379`). `npx --yes devscene@<pin>` resolves transitive deps at run time (`devscene-run.yml:768, 857, 1001`). The header documents the trade-off (`devscene-run.yml:310-319`) | Verified | Pin `claude-code@<x>` with `npm ci`-style integrity (a checked-in `package-lock.json` for a tools dir); clone the plugin by **commit SHA** recorded beside `DEVSCENE_CLI_VERSION`; publish `devscene` with an `npm-shrinkwrap.json` |
| **H6** | **Medium** | **Trigger provenance omits the author.** The snapshot names the labeller and time (`remote-run.sh:4653`), not `.issue.user.login`, `author_association` or `updated_at`. The event fields are never read (`remote-run.sh:4515-4524`). A writer labelling a stranger's issue gives no signal to the run or to the PI screen that the text is third-party | Verified | Add `Written by @<author> (<association>), last edited <updated_at>` to the footer; let the screen weight `NONE`/`FIRST_TIME_CONTRIBUTOR` authors; optionally refuse when `updated_at` is later than the label event by more than N seconds |
| **H12** | **Medium** | **`doctor` applies a repo-controlled env overlay to a spawned process.** `runPythonSelfCheck` copies every string in `.mcp.json` → `mcpServers.<docs server>.env` into the child's env (`env: { ...process.env, ...overlay, … }`, `cli/src/doctor/checks.ts:6230-6251`), on the branch the repo's own `harness.config.json` enables (`pythonRetrievalApplies`). `LD_PRELOAD`, `PYTHONPATH` or `BASH_ENV` from a repo the user only *inspects* with `doctor` becomes code execution when the Python launcher is installed. Studio's auto-doctor (Issue item 9) would make it reachable without a click; Studio's side is §3.11 | Verified (code); not exploited | Allow-list the overlay keys (`DATABASE_URL` and the documented retrieval keys only); fix in the next devscene release |
| **H7** | **Low–Medium** | **Mention reader sees third-party comments and may compose an `answer`.** `conversation.md` includes the last 30 comments by anyone (`remote-run.sh:626-628`, `:1743`). The rule says to serve only the commenter (`mention_reading.md:24-31`), but an LLM decides; the resulting answer is then screened on resume. Residual: a stranger's comment steering an authorised writer's vague mention into an `answer` | Verified design; inferred risk | For `command: answer`, require the answer text to appear verbatim in the commenter's own comment, or post a confirm-request as for `stop`/`clear` |
| **H8** | **Low** | **Screen SAFE-record lives in a session-writable ledger.** SAFE is "a line in `flow_progress/<branch>_progress.md`" (`prompt-injection-screen.sh:62-66`), in the run copy the session writes. A compromised session could pre-record SAFE for an answer it is about to write (pairs with H1b). The screen is also *run by the orchestrating session itself* (header "WHO RUNS IT"), which reinforces the tripwire framing | Inferred | Keep screen records in a session-write-denied file, keyed by sha256 |
| **H9** | **Low** | **Bash allow-list breadth inside the sandbox.** `find` (`-exec`, `-delete`), `sed` (`e` command, `-i`), `awk` (`system()`) are allowed (`settings.autonomous.json:48-51`), so they are interpreters in effect. Also `git branch --delete` and `git branch -f` aren't caught by the `-D/-d` prefix denies (`:69-73`); the header says the plugin guards close compound and `-C` forms (`:17`). Contained by the sandbox, and the `scratch-run.sh` route already grants an interpreter deliberately (`:13`) | Verified rules; impact bounded | Document as residual; add `--delete`/`-f`/`--force` to the deny floor and guard |
| **H10** | **Low** | **Local timestamps without zone** in the registry (`harness-run-lib.sh:3525`, `date '+%Y-%m-%dT%H:%M:%S'`), and no `schema` field (observed). That makes it ambiguous for any consumer (05) | Verified | ISO-8601 with offset; `"schema": 1` |
| **H11** | **Info** | `jq -r '.scriptsDir'` written to `$GITHUB_ENV` unquoted (`devscene-trigger.yml:150-153`, `devscene-control.yml:304-307`). A value with a newline injects env lines (`BASH_ENV`, `NODE_OPTIONS`). The source is the default branch's `harness.config.json`, which is writer-controlled anyway | Verified | Validate `scriptsDir` against `^[A-Za-z0-9._/-]+$` before writing |

#### 5.3 What a future `devscene runs --json` contract must enforce (security)

05 §5 defines the shape. Security requirements for each verb:

1. **Validation inside the CLI, not only the app.** `branch` goes through the same `hr_inbox_branch_refusal_var` rules; repo paths must resolve to an adopted repo; free text (`--prompt-file`, `--answers-file`, `--review-file`) only by file or stdin, read with a size cap (e.g. 256 KB) and as UTF-8 only.
2. **No path echo outside roots.** `logTail` and `questions` are returned as **content**, bounded and with ANSI preserved but OSC stripped. `worktree` and `log_path` appear only if they resolve inside the repo's state dir or a registered run copy; otherwise they are omitted with a warning. The app then never opens paths itself (§3.3).
3. **Provenance fields** on `RunSummary`/`RunDetail`: `source` (`inbox|issue|dispatch|mention`), `issue{number, author, authorAssociation, updatedAt, labeller}`, `startedBy`.
4. **Screen fields:** `screen{status: safe|unsafe|pending, findings[{check, excerpt}], screenedSha}` per input file, read from a **session-write-denied** record (H8).
5. **Optimistic concurrency on acts:** `runs answer --expect-question-sha <sha>`, `runs resume --expect-status paused`. Refuse on mismatch with `error.code: "stale"` (§3.4).
6. **Act verbs are idempotent and audited.** Each appends `{ts, verb, branch, actor: "studio"|"cli"|"skill", pid}` to an append-only `autonomous_logs/actions.log` (`0600`).
7. **Budget surface:** `capabilities` reports `budget{maxParallel, dailyCap, perRunUsd}`, and `runs drop` refuses with `error.code: "budget"` when the cap is reached (H2). The app's own budget is then a second layer.
8. **Redaction:** `logTail` passes the harness's credential matcher before output (H3), so every consumer benefits.
9. **No env, no secrets, no raw `doctor` subprocess output** in any JSON response; `doctor --json` emits structured checks only.
10. **Schema and refusal:** an unknown `contract` major or registry `schema` → refuse (05). A registry whose entries fail validation are dropped with a warning, never half-read.

## Answers to the owner's questions

- **Q1/Q2 (cross-platform vs native), security lens:** native has the smallest per-app surface (no HTML engine), but three codebases triple the places a control can be missing. A webview shell with the §3.1 pipeline, intent-only IPC and native-modal confirmations gets close to native residual risk for ≈ 5.5–6.0 O-d (Electron 3.9–7.2, Tauri 4.2–7.8), about what native costs for all three apps together (≈ 5.75). Security does not justify native ×3. [inferred]
- **Q5 (native-side blockers), security lens:**
  - Linux auto-update integrity in electron-updater is sha512-only [verified, 9]; add a signature hook.
  - Tauri's updater key is unrecoverable if lost [verified, 4].
  - WebKitGTK patch lag on LTS distros (07).
  - Trusted Types is Baseline only since Feb 2026 [verified, 12]; WebKitGTK reportedly has it from 2.50, so LTS distros on older webkit2gtk-4.1 may lack it.
  - On Windows, `\\wsl$` reads can't be realpath-confined; do security-relevant reads inside WSL (§3.3).
  - Windows `wsl.exe` argv crosses a string boundary; use `--exec` plus stdin.
- **Q6 (costs):** security work ≈ 5.5 O-d for Electron (3.9–7.2), ≈ 6.0 for Tauri (4.2–7.8), ≈ 5.75 for native across three apps, ≈ 7.75 for the local web app, ≈ 8.5 for hosted (6.0–11.1) plus ongoing operations, ≈ 15.5 for the hybrid (10.9–20.2) (§4.2). Cash costs: none beyond 04's signing (hardware keys ≈ US$50–100 one-off for account protection [inferred]).
- **Q7 (momentum):** no security-relevant deprecation. DOMPurify is actively patched (3.4.17, 2026-10-12) but had about 25 advisories in 2026, one of them a default-config bypass, so auto-track it [verified, 10, 11]. electron-updater's Linux signature support exists only in the 7.0 alpha [verified, 9].

## Recommendation

### 6.1 Which modes, at what security cost

| Mode | Verdict | Condition |
|---|---|---|
| **Tauri 2 desktop shell** | **Recommended (security-first pick)** | Capabilities locked, `AppManifest::commands`, isolation pattern, updater key custody. Edge over Electron: OS-patched webviews on macOS/Windows, mandatory signed updater, narrower IPC; costs ≈ 0.5 O-d more up front |
| **Electron desktop shell** | **Recommended (equal if the release cadence is kept)** | Checklist + fuses (incl. `GrantFileProtocolExtraPrivileges=false`) + confined `app://` handler + 14-day patch SLA; Linux update signature hook (or 7.0's manifest key when stable) |
| Native ×3 | Acceptable, not recommended | Security gain is small against the 03/06 costs |
| **Hosted remote-only** | **Acceptable as a later add-on**, read-mostly first | Only after GitHub App minimal permissions, a BFF with no token store, server-side budget, and IR/privacy in place. Start with read-only plus "open on GitHub" for acts; add label/dispatch later |
| Local web app | **Developer mode only, opt-in** | Every §2d control and §4.3 suite 3 green; off by default; never the sole deliverable |
| Hosted + connector | **Not in v1** | Revisit only with a strong product reason; it carries the highest residual risk |

### 6.2 Minimum security bar for v1 (any shipped mode)

1. Rendering: §3.1 pipeline (Markdown → DOMPurify ≥ 3.4.17, auto-tracked, default mode → Trusted Types), no remote images, closed ANSI palette, CSP; XSS corpus in CI.
2. Privilege: intent verbs only; one argv builder (§3.2) with the fuzz suite; `wsl.exe --exec`; free text via stdin/file.
3. Files: realpath-confined, `O_NOFOLLOW` reader with a validated root; registry paths not trusted. On Windows, security-relevant reads happen inside WSL, not over `\\wsl$` (§3.3).
4. Human in the loop (**precondition**): provenance plus exact-text confirmation for every start, answer and resume, **shown in an OS-native modal opened by the main process / Rust core**, never renderer HTML; non-member warning; no auto-start, no batch start.
5. Money: one-click global stop (start budget SHOULD, §3.10). **Harness blockers:** if v1 offers answer or resume, **H1 + H1′** are release blockers (a run must not be able to answer its own or a sibling's park, or start runs). **H2** blocks only if Studio exposes API-key configuration; subscription users are bounded by the usage gate.
6. Secrets: never read `~/.claude*`; env allowlist; display masking; never show `.stream.jsonl`.
7. Release: signed builds and updates; keys in a protected environment with reviewers and an offline backup; owner accounts on hardware keys/passkeys; npm/crates supply-chain controls (§3.7).
8. Shell-specific: Electron checklist + fuses + confined protocol handler, or Tauri capabilities + isolation; no debug port in release (CI-asserted); no custom URL scheme.
9. Repos (**precondition**): detected repos untrusted until confirmed; no `doctor`/`git`/`devscene` spawn in an untrusted repo; `stateDir` validated; `devscene` resolved by absolute path, never via `npx` in a repo (§3.11, §3.2 rule 1).
10. GitHub state: progress comments trusted only from `github-actions[bot]` with the exact marker; Actions run state over labels; branch JSON schema-validated (§3.12).

## Risks and open questions

1. **H1 and H1′ are confirmed by settings analysis, runtime test pending.** Every link of the chain is in the shipped profile (§5.2), but no run has been observed doing it. Test plan, as a measurement row in `docs/sandbox-verification.md`: from a sandboxed `-p` session under the shipped per-run profile and `dontAsk`, use the `Write` tool to create (i) an inbox file in the main checkout's `autonomous_inbox/`, (ii) an `answer_1.md` in the run copy's `clarifications/<branch>/`, (iii) a `RESUME` file in a **sibling** run copy, and (iv) a line appended to the main checkout's `.claude/CLAUDE.md`; and with Bash, `find <stateDir> -name AUTONOMOUS_STOP -delete` on a planted stop file. Record for each whether the sandbox, the permission rules or a hook refuses it, quoting `permission_denials`. Any write that succeeds keeps its finding at High; if all are refused, H1/H1′ drop to Info.
2. **`wsl.exe` command-line parsing** is not documented on Microsoft Learn (it lists neither `--exec` nor `--`), but the WSL source is: exec mode re-parses with `CommandLineToArgvW` (`microsoft/WSL` `src/windows/common/WslClient.cpp`; flag text in `Resources.resw`) [verified, 13]. A mocked `wsl.exe` applying that parser runs on any GitHub-hosted Windows runner (CI MUST). GitHub-hosted Windows runners don't support WSL2 nested virtualisation, so the real round trip is a release-checklist step on the owner's machine (§4.3 #2).
3. **Artifact visibility on public repos: resolved.** Names and metadata are anonymous (listing → 200); downloading needs any signed-in account (anonymous zip download → 401) [verified, 16]. Treat run logs on public repos as public.
4. **The `GITHUB_TOKEN` can't push workflow-file changes.** The `GITHUB_TOKEN` permission list has no `workflows` key, while GitHub Apps have a separate "Workflows" repository permission, and `GITHUB_TOKEN` is an installation token of the Actions app [verified, derived; 17]. The harness doesn't rely on it anyway (the job-surface check).
5. **GitHub App user-token expiry: resolved, both are true.** Expiring user tokens are on by default (an app can opt out); `offline_access` is the one supported scope and forces expiry for an app that opted out. PKCE "Must be `S256`" [verified, 6]. Studio's app keeps expiry on, so `offline_access` is not needed.
6. **Effort numbers** are estimates in 03's model (point ± 30%); validate with the first spike (board + detail + native start modal with the full §3.1 pipeline).
7. **Trusted Types on older WebKitGTK.** Reportedly on by default from WebKitGTK 2.50.0 (2025-09-17), not confirmed from the release note; Ubuntu 22.04/24.04 have it only if their webkit2gtk-4.1 updates are at 2.50+. Studio's doctor view reports the version; CSP + sanitizer must stand alone below it.
8. **Chrome LNA gates WebSockets from Chrome 147** [verified, 5]. That helps the local web app's Chrome users only; Chrome 142–146, Firefox and Safari don't gate it, and WebRTC is ungated, so W3's Origin check + token stays MUST.

## Sources

1. https://www.electronjs.org/docs/latest/tutorial/security — 20-item checklist; contextIsolation default since 12, sandbox since 20; CSP; navigation and new-window limits; `shell.openExternal`; IPC sender validation; custom protocol over `file://`; fuses; links SECURITY.md at v45.3.1 — accessed 2026-11-12 [verified]
2. https://v2.tauri.app/concept/inter-process-communication/isolation/ — isolation pattern, sandboxed iframe hook, AES-GCM with per-run keys, Windows ES-module limitation, overhead — accessed 2026-11-12 [verified]
3. https://v2.tauri.app/security/capabilities/ — per-window capabilities, remote URLs off by default, platform scoping, app commands "allowed to be used by all the windows and webviews of the app" unless `AppManifest::commands` — accessed 2026-11-12 [verified]
4. https://v2.tauri.app/plugin/updater/ — signature mandatory, "cannot be disabled"; lost key strands installs; downgrades refused by default (`version_comparator`); TLS enforced in production — accessed 2026-11-12 [verified]
5. https://chromestatus.com/feature/5197681148428288 ("Local network access restrictions for WebSockets", shipping in Chrome 147) and https://chromestatus.com/feature/5126430912544768 (WebTransport, 147); background: https://developer.chrome.com/blog/local-network-access (LNA prompt in Chrome 142; its "WebSockets not yet gated" statement, 2025-06/09, is now outdated) — accessed 2026-11-12 [verified]
6. https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app — token permissions = intersection of app and user; 8 h expiry, 6-month refresh; `offline_access`; PKCE `S256`; device flow — accessed 2026-11-12 [verified]
7. https://learn.microsoft.com/en-us/windows/wsl/networking — NAT localhost access from Windows; mirrored mode "Connect to WSL directly from your local area network"; Hyper-V firewall on by default from WSL 2.0.9 (updated 2026-06-02) — accessed 2026-11-12 [verified]
8. https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions — env-var indirection for untrusted input; SHA pinning; least-privilege `GITHUB_TOKEN`; `pull_request_target` caution; "automatic redaction is not guaranteed"; environment secrets with required reviewers; self-hosted runners "should almost never be used for public repositories" — accessed 2026-11-12 [verified]
9. electron-updater source at tag `electron-updater@6.8.12` (npm dist-tag `v26`; npm `latest` = 6.8.11, 2026-10-20; `next` = 7.0.0-alpha.13), `gh api repos/electron-userland/electron-builder/contents/packages/electron-updater/src/{AppUpdater,DebUpdater,NsisUpdater}.ts` — Linux checks only the manifest sha512, no verify hook; `allowDowngrade = false`, but `isUpdateAvailable` gates any older version and setting `channel`/`allowPrerelease` sets it to `true`; Windows signature verifier. `master` (7.0 alpha) adds `updateManifestPublicKey`, `verifyUpdateFile` and `allowUnverifiedLinuxPackages` — accessed 2026-11-12 [verified]. Windows `verifyUpdateCodeSignature`/`publisherName` default: https://www.electron.build/docs/win [secondary]
10. `gh api repos/cure53/DOMPurify/releases/latest` — 3.4.17, 2026-10-12 — accessed 2026-11-12 [verified]
11. https://github.com/cure53/DOMPurify/security/advisories (`gh api repos/cure53/DOMPurify/security-advisories`: 25 published in 2026), incl. GHSA-87xg-pxx2-7hvx (CVE-2026-47423, high, default-config `selectedcontent` re-clone, fixed 3.4.5), GHSA-r47g-fvhr-h676 (3.4.6), GHSA-rp9w-3fw7-7cwq (3.4.7); global DB GHSA-v2wj-7wpq-c8vv (CVE-2026-0540, fixed 3.3.2 / 2.5.9) — accessed 2026-11-12 [verified]
12. https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API — "Baseline 2026, Newly available… Since February 2026" — accessed 2026-11-12 [verified]
13. https://github.com/microsoft/WSL — `src/windows/common/WslClient.cpp` (exec mode re-parses the command line with `CommandLineToArgvW`) and `localization/strings/en-US/Resources.resw` (`--exec`: "without using the default Linux shell"); https://learn.microsoft.com/en-us/windows/wsl/basic-commands documents neither flag — accessed 2026-11-12 [verified]
14. https://docs.npmjs.com/trusted-publishers — OIDC trusted publishing, automatic provenance, npm CLI ≥ 11.5.1 / Node ≥ 22.14.0, "Require two-factor authentication and disallow tokens" (page edited 2026-10-06) — accessed 2026-11-12 [verified]
15. `gh api repos/zizmorcore/zizmor/releases/latest` (v1.32.0, 2026-11-02); `gh api repos/EmbarkStudios/cargo-deny/releases/latest` (0.20.2, 2026-07-09) — accessed 2026-11-12 [verified]
16. https://docs.github.com/en/rest/actions/artifacts#download-an-artifact — download needs authentication; observed: anonymous `GET /repos/cli/cli/actions/artifacts` → 200, anonymous `…/artifacts/<id>/zip` → 401 — accessed 2026-11-12 [verified]
17. GitHub docs: the `GITHUB_TOKEN` `permissions` keys (`actions` … `vulnerability-alerts`, no `workflows`), https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax; GitHub Apps' separate "Workflows" permission, https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps#repository-permissions-for-workflows — accessed 2026-11-12 [verified, derived]
18. Local harness source, `/Users/daniel/Work/devscene` at `a1d0e99` (read-only):
    - `cli/templates/claude/settings.autonomous.json`
    - the rendered `.claude/settings.autonomous.json`
    - `cli/templates/github/workflows/devscene-{trigger,control,run,resume}.yml`
    - `cli/templates/scripts/{remote-run.sh, autonomous-watcher.sh, autonomous-format-stream.sh, prompt-injection-screen.sh, lib/harness-run-lib.sh}`
    - `cli/src/generators/writeProtection.ts`
    - `cli/src/doctor/checks.ts` (`runPythonSelfCheck`, `probeRegistrySpec`)
    - `plugin/agents/prompt-injection-reviewer.md`
    - `plugin/instructions/mention_reading.md`
    - `plugin/commands/branch-answer.md`
    - `plugin/hooks/{hooks.json, git-trust-file-guard.sh}`
    - `docs/sandbox-record.md` §6
    - `stat` of `harness-runs/`

    Accessed 2026-11-12 [verified]
19. Cross-references: 07 §2/§2a/§4c/§4d (threat summary, controls, GitHub App, mode comparison), 05 §2/§5 (transport, contract), 04 §1/§2/§6–§8 (PATH, WSL quoting, signing, updaters), 03 (O-d unit, ≈ 27 O-d v1), 01 (versions).
20. https://www.electronjs.org/docs/latest/api/protocol — `protocol.handle` example confining paths with `path.relative` and rejecting `..`/absolute with a 400 — accessed 2026-11-12 [verified]
21. https://github.com/electron/fuses (`src/config.ts`: `GrantFileProtocolExtraPrivileges`, default on) and https://www.electronjs.org/docs/latest/tutorial/fuses ("If you aren't serving pages from `file://`, you should disable this fuse") — accessed 2026-11-12 [verified]
22. https://webkitgtk.org/security.html — WSA-2026-0001…0006 — accessed 2026-11-12 [verified]
