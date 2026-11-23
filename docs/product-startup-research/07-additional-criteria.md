# 07 — Additional decision criteria
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **Two separate findings: a well-supported UI architecture, and a delivery-mode choice that is the owner's.**
  - **Architecture (well supported):** build the UI as a **web app** that talks HTTP/WebSocket (or IPC) to a small **Node core**. The core is the 04 WSL helper and the 05 contract *client*, implemented once. Agent QA, the shared design system and DX all point here (§1, §4a, §7). [inferred]
  - **Delivery mode (open):** the same UI can ship as (1) a **desktop shell** (Electron or Tauri), (2) a **local web app** (`devscene-studio serve` on `127.0.0.1`, inside WSL on Windows), (3) a **hosted web app** with GitHub sign-in, remote runs only, or (4) a **hosted UI plus a local connector**. Combinations work too, for example a desktop shell for local runs and the hosted app for remote runs. The modes trade off security, Windows/WSL lifecycle, install friction for users without Node, signing cost and auto-update. §4d compares them and lists the criteria that flip the choice. Building web-first lets the owner defer the choice. [inferred]
- **How this relates to 01–06:** 01 shortlists Electron, Tauri and Wails; 03 recommends Tauri or Electron with a browser mode as a v1 requirement; 05 recommends a `wsl.exe` stdio transport; 06 recommends (B). The web-first architecture is compatible with all of them: it is 03's browser mode made first-class. Only "local web app as the *sole* deliverable" conflicts with them. A localhost-HTTP transport from a Windows shell to a core inside WSL is also an alternative to 05's stdio, worth a note in 04/05. [inferred]
- **Agent-drivable UI testing ranks web-tech highest.** The harness QA agent only has Playwright MCP and Chrome DevTools MCP. Both can attach to an existing CDP endpoint (`--cdp-endpoint`, `--browserUrl`) [verified, 3, 4]. A local or hosted web app is a native fit. Electron (`--remote-debugging-port`) and Tauri on Windows (WebView2 CDP [verified, 5]) work only in **debug/test builds**, and on Windows a WSL-resident harness cannot reach a Windows-side CDP port in NAT mode [verified, 22]. Every web-tech option can be QA-driven in browser mode on the Linux runners (03). Apple still ships **no WebDriver for WKWebView** [verified, 1]. Compose 1.12 has an experimental MCP server [verified, 8] and Dart has one too [verified, 7], but neither plugs into the harness's `web-playwright` driver.
- **Security is the owner's main concern; each mode has a different threat profile (§2a).** All webview and browser modes share one chain: **attacker-controlled GitHub text → XSS → privileged action**. What that privileged action is differs: IPC to a process spawner (desktop shell), a network-reachable process-spawning API (local web app), the user's GitHub permissions (hosted), or both of the last two (hybrid). The local web app and the hybrid connector carry the largest local attack surface; the hosted app adds a multi-tenant service. Area 08 goes deep; this file keeps a threat summary per mode and the required controls. Supply chain: 2026 hit both **npm** (Mini Shai-Hulud waves) [secondary, 14] and **crates.io** (arrayref, 2026-08-20) [verified, 15].
- **Embedded runtime patching:** Electron carries its own Chromium and is only as patched as your last release. WebView2 is evergreen and WKWebView updates with macOS. WebKitGTK has published **6 advisories so far in 2026** (WSA-2026-0001…0006, latest 2026-09-29), and LTS distros lag upstream [verified, 16]. For an app that loads no remote web content, XSS hygiene matters more than runtime patch lag. [inferred]
- **Accessibility splits the field on Linux.** Compose Desktop has **no Linux accessibility** [verified, 17]. Ubuntu flags Flutter's AT-SPI issues [verified, 18]. Avalonia claims full AT-SPI2 support [verified, 19]; Qt 6 and GTK4 expose platform accessibility APIs [inferred]. Web stacks inherit browser or webview accessibility. i18n is low-weight here.
- **Code sharing argues strongly for web-tech UI.** Flutter's FAQ says Flutter web is not suited to text-rich static sites [verified, 20] (it recommends Jaspr or HTML for those), and Compose for Web (Wasm) is **Beta** [verified, 21]. Only a web UI spans the site, Studio and the sibling apps with one component library. All web-tech modes qualify, and the hosted app can also share the site's domain and sign-in. [inferred]
- **Observability:** Sentry has first-party SDKs and guides for Electron, Flutter, Compose Multiplatform, Qt and .NET. Tauri, Wails and Avalonia have **no framework guide**, but each wires the official Rust/Go/.NET plus JS SDKs by hand [verified, 25]. Sentry's free Developer tier (5k errors/month, 1 user) likely suffices; OSS projects get a sponsored plan [verified, 27, 45].
- **Licensing: open-sourcing (Apache-2.0, like the harness) saves real money**: roughly US$420–810/yr for Electron/Tauri, ~US$960–1,350 with Conveyor, ~US$0–312 for the web modes (§6) [inferred]. Qt (PyQt is GPL) and Avalonia (paid official Hot Reload; DevTools has a free tier) are the only friction points.
- **Scoring (§ Scoring):** with the weights applied and distribution and lifecycle included, the hosted app (remote-only), Electron and the local web app land within noise of each other at the top (103, 99, 92 of 115), with Tauri next (84). **The table does not decide the delivery mode**: two gates (local runs, tray/notifications) and the security weighting do.

## Scope

**Covered here:** criteria not covered in 01–05: agent-drivable UI testing, the security model (decision level; depth in 08), accessibility and i18n, code sharing with the web site and siblings, the four delivery modes (local web app, hosted web app, hosted + connector, desktop shell), observability, licensing of the app itself, developer experience, plus a few additions (§8).

**Deferred:**
- Framework health and costs: 01.
- Bundle size, RAM and start time: 02.
- Native vs cross-platform effort and career value: 03.
- OS-integration blockers, signing mechanics, updaters and WSL plumbing: 04.
- Harness contract and CLI reuse: 05.
- Repo topology and harness fit: 06.
- **Full threat model, security architecture and security test plan: 08.**

Where a point touches those files, this one cross-references them rather than repeating it.

## Findings

### 1. Automated UI testing an AI agent can drive

**Why it matters:** the harness QA phase (`devscene:qa-tester`, variant `web-playwright`) can call only `mcp__playwright__*` and `mcp__chrome-devtools__*` tools. It navigates to a `base_url` (see 03). So the real question per stack is whether these two MCPs can reach the UI, and if not, whether some other agent-usable tool exists.

| Stack | Harness MCPs reach the **real app**? | Framework test kit | Agent can screenshot + inspect? | Notes |
|---|---|---|---|---|
| **Local web app** | **Yes, natively.** It is a web page at `base_url`. | Playwright / Vitest | Yes: DOM snapshot, screenshot, console, network | Zero adaptation. The QA agent tests the shipped product, not a mock. [inferred] |
| **Hosted web app** | **Yes, natively**, against a preview deployment or a local dev server. | Playwright / Vitest | Yes | GitHub sign-in needs a test account or a mocked auth path in QA. [inferred] |
| **Electron** | **Yes, via CDP, in debug/test builds only.** Launch with `--remote-debugging-port`, then Playwright MCP `--cdp-endpoint` [3] or Chrome DevTools MCP `--browserUrl` [4]. Neither MCP documents Electron officially. A shipped build must not expose the port: any local process could drive the privileged app. **On Windows a WSL-resident harness cannot reach a Windows-side `127.0.0.1` port in NAT mode** (the default); it needs mirrored networking [verified, 22, 42]. | Playwright `_electron` (experimental, Electron ≥ 21; needs the `nodeCliInspect` fuse not set to `false`) [verified, 2] | Yes (renderer). The main process needs a separate Node inspector. | Community Electron MCP servers exist, all third-party [secondary, 6]. [inferred for MCP attach] |
| **Tauri 2** | **Windows only, via WebView2 CDP, debug/test builds only** (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=…`) [verified, 5]. Same WSL caveat as Electron: needs mirrored networking for a harness inside WSL. **No on macOS or Linux.** | `tauri-driver` WebDriver on Windows and Linux. macOS through `@wdio/tauri-service` with the embedded `tauri-plugin-wdio-webdriver`, or CrabNebula's fork (**paid API key on macOS**) [verified, 1]. Docs updated 2026-06-29. | Through WebDriver, yes. Through the harness MCPs, in browser mode with mocked IPC (03). | **WKWebView WebDriver: still none from Apple** [verified, 1]. Community crates (`tauri-plugin-webdriver`, `tauri-wd`) fill the gap [secondary]. |
| **Wails 3** | No CDP on macOS or Linux; WebView2 CDP on Windows applies in principle, with the same WSL caveat [inferred]. | Official guide: Playwright **against the dev server** on port 9245 [verified, 9]. That is not the native shell. | Browser mode only. | Real-shell testing is left to AT-SPI or xdotool [secondary, 9]. |
| **Flutter** | No. | `integration_test` runs on macOS, Windows and Linux (Linux needs an X server in CI) [verified, 7a] | **Dart MCP server** (experimental): `launch_app` (off by default; enable the `flutter_app_lifecycle` category), `widget_inspector`, `flutter_driver_command`, `hot_reload`, `get_runtime_errors`. Desktop support is not documented [verified, 7] | A second MCP to register. It would need a new harness QA variant. |
| **Compose MP** | No. | `runComposeUiTest` / JUnit4 desktop rule (marked experimental in docs) [verified, 10] | **Compose Hot Reload MCP** (experimental, CMP 1.12): screenshots, semantics tree, click and input, logs [verified, 8] | The strongest non-web agent story. Still needs a new QA variant. |
| **Avalonia** | No. | **Avalonia.Headless** (xUnit/NUnit). Real Skia rendering with `CaptureRenderedFrame()`, plus keyboard, mouse and drag-drop simulation [verified, 13] | Through tests, yes. No agent MCP. | Excellent for CI. Appium is suggested for real windows. |
| **Qt / PySide6** | No. | Qt Test / QtQuickTest (free). **Squish** is quote-only, with third-party figures of about €6.3k–9.6k per licence [secondary, 36]. | Community MCPs (qt-mcp for PySide6, qtPilot, qt-commander). Qt's official MCP covers docs and QML preview, not runtime [secondary, 37] | |
| **Native ×3** | No. | XCUITest (macOS). **WinAppDriver: last stable release 2020-11-05, last pre-release 2021-07 (1.3 RC1); effectively unmaintained** [verified, 51]; Appium's Windows driver points to NovaWindows as a replacement [secondary, 38]. AT-SPI with dogtail on Linux. | OS accessibility-tree MCPs (kwin-mcp, linux-desktop-mcp, Cua) are third-party [secondary, 39] | Three test stacks, two of which can't run on the harness's Linux-only remote runners (03). |

**Takeaway:** every web-tech option can be QA-driven on the Linux runners in browser mode (03). The local and hosted web apps are QA-driven exactly as they ship. Electron (with Xvfb on a headless runner) can also be driven unmocked through CDP on all three OSes in test builds, but on Windows only if the WSL-resident harness uses mirrored networking. Tauri and Wails need the mocked browser mode except on Windows, with the same caveat. [inferred]

### 2. Security model (decision level; full threat model in 08)

**Threat model specific to this app** [inferred]:
- (a) The app renders **attacker-influenced text**: GitHub issue titles and bodies, PR comments, clarification files, and `run.log` lines that may echo model or tool output.
- (b) The privileged side spawns `git`, `gh`, `claude` and `devscene` with arguments, and drops files into the inbox. A dropped prompt starts a headless `claude` run, so **any path to an act verb is equivalent to running an agent on the user's machine** on a prompt of the attacker's choosing.
- (c) It must never touch Claude credentials and must handle the `gh` token minimally.

So the dangerous chain is **XSS in the rendered content → privileged call → process spawn**. The secondary chain is **argument injection** into `git` or `gh` (for example, a branch name that starts with `-`).

| Concern | Electron | Tauri 2 | Wails 3 | Flutter / Compose / Avalonia / Qt / native | Local web app |
|---|---|---|---|---|---|
| IPC exposure | Safe defaults: `contextIsolation` since 12, `sandbox` since 20, `nodeIntegration` off; a 20-item checklist; fuses [verified, 11]. Exposure is whatever the preload `contextBridge` exposes. | **Capabilities ACL**: permissions per window label, remote origins off by default, platform-scoped. Caveat: all *app* commands are allowed for every window unless `AppManifest::commands` restricts them [verified, 12]. | Bound Go methods are callable from JS. No ACL layer comparable to Tauri's [inferred]. | No webview, so no XSS-to-IPC class; text widgets don't execute markup [inferred]. | The HTTP/WebSocket API **is** the privilege boundary, and it is network-reachable (§2a). |
| Mitigation pattern | Strict CSP, sanitize markdown (DOMPurify), expose **intent-level** IPC (`pauseRun(branch)`), never `spawn(cmd,args)` | Same, plus capabilities | Same | Validate arguments | Same as webview, plus the listener controls in §2a |
| Embedded runtime CVEs | Bundles Chromium. Electron supports the latest 3 majors; only the latest minor of each gets fixes [verified, 31]. **You** must ship updates. | OS webview: WebView2 is evergreen. WKWebView follows macOS. **WebKitGTK** has published 6 advisories so far in 2026 (WSA-2026-0001…0006, latest 2026-09-29; stable 2.54.2), and LTS distros trail upstream by weeks to months [verified, 16]. | Same as Tauri (WebKitGTK 6.0 on Linux) | Skia/JVM/.NET runtimes have a smaller attack surface for local-only UIs | The user's browser, updated by the user, usually the best patched [inferred] |
| Supply chain | npm: 2026 Mini Shai-Hulud worm waves (Apr–Aug). Tallies vary widely by source and date: from ~170 packages / 400+ versions (mid-May) to 1,055 versions / 502 packages, and Sonatype's 2,225 component versions with a wave on 2026-08-04 [secondary, 14, 49] | npm (frontend) **plus** crates.io: on 2026-08-20 `arrayref`, `internment` and `append-only-vec` were republished from a likely compromised account to depend on `proc-macro1`, whose build script fetched a payload. Each bad version was live for 86–107 min [verified, 15] | npm + Go modules (the checksum DB and no install scripts make Go the most conservative) [inferred] | pub / Maven Central / NuGet / pip: smaller fan-out, same account-takeover class [inferred] | npm (same as Electron), **and npm is also the app's own distribution channel** (§4b) |

**Practical controls, whatever the stack** [inferred]:
- Lockfiles and `npm ci --ignore-scripts` where possible.
- Pin GitHub Actions by SHA.
- Use Dependabot with a cooldown.
- Keep the dependency count low; a 3-column board does not need a UI kit with 1,000 transitive deps.

**`gh` token handling** [verified + inferred]:
- `gh auth login` stores the token in "the system credential store"; when "a credential store is not found or there is an issue using it", gh falls back to a plain-text file, and `--insecure-storage` forces plain text [verified, 46]. Most WSL distros have no Secret Service, so plain text is the norm there [inferred].
- Recommended rule for the local modes: **the app never reads or stores the token.** It shells out to `gh` (`gh api …`, `gh issue …`) inside the right environment, which is WSL on Windows (see 04).
- If a direct REST client is ever needed, call `gh auth token` per process, keep the token in memory on the privileged side only, never send it to the renderer, and never log it.
- **Claude credentials:**
  - Never read `~/.claude*` or the Keychain item.
  - Spawn `claude` only through the harness scripts, with an environment allowlist.
  - Redact `ANTHROPIC_*`/`GH_TOKEN`-looking strings from any log tail or crash report before display or upload.

#### 2a. Threat summary per delivery mode, and required controls

| | Desktop shell (Electron/Tauri) | Local web app | Hosted web app (remote-only) | Hosted UI + local connector |
|---|---|---|---|---|
| **Privileged surface** | In-process IPC; no listener | An HTTP + WebSocket API that spawns processes: an **RCE-equivalent endpoint** reachable over a socket | A multi-tenant service holding users' GitHub sessions; no local process spawning | Both: the hosted service **and** a local spawning API that accepts cross-origin calls from the hosted origin |
| **Who can reach it** | Only the app's own renderer (plus any debug port left open) | Same-user processes (residual, as for every desktop app); **other OS users** on the host (loopback has no per-user ACL); on Windows **every Windows process and user** via `localhostForwarding` (default on) and other WSL2 distros [verified, 42; secondary]; the **LAN** in mirrored mode if bound to `0.0.0.0` [verified, 22]; **any web page** via CSRF, DNS rebinding and cross-site WebSocket hijacking | The internet (it is a public site); a breach of the operator exposes in-flight sessions or, with a token store, write access to many users' repos | Everything in both columns. **An XSS on the hosted site becomes local process spawning on every connected machine.** |
| **What an XSS from GitHub text reaches** | The preload/IPC API | The full API, same-origin, with the session cookie: Host, Origin and token checks do not help | The user's GitHub permissions (create issues, dispatch workflows) | The user's GitHub permissions plus local spawning |
| **Extra obligations** | Code signing keys; shipping Chromium/runtime updates | Token lifecycle; npm publishing hygiene | Privacy policy, data-processor duties (GDPR for EU users), incident response, uptime | All of the hosted ones, plus the connector's |
| **Relative burden** [inferred] | Lowest of the local modes | High; can approach Electron only with every control below and CI tests for them | Medium; different in kind (service security, not local RCE) | **Highest** |

**Required controls** [inferred, standard practice unless tagged]. 08 will specify and test them.
- **All web-tech modes:** markdown through an allowlist sanitizer (DOMPurify), no raw HTML; log tails as text nodes with a safe ANSI parser; strict CSP (`default-src 'self'; script-src 'self'`, no inline script) and Trusted Types where supported; only `https:` links with `rel="noopener noreferrer"`; **intent-level** actions only (`pauseRun(branch)`, never `exec`); spawn with argv arrays and no shell, `--` before user-supplied refs, branch names validated with `git check-ref-format`, repo paths checked against the detected-repo list; a CI test that renders an XSS payload corpus (script tags, `javascript:` links, SVG `onload`, ANSI and OSC-8 hyperlinks).
- **Local web app, and the connector:**
  - Bind `127.0.0.1` only; refuse any other address; test it.
  - Exact-match **Host-header allowlist** (`127.0.0.1:PORT`, `localhost:PORT`) against DNS rebinding [secondary, 23].
  - **Origin check on every state-changing request and every WebSocket upgrade**; reject a missing or `null` Origin on writes. WebSocket handshakes are not subject to CORS, and Chrome's Local Network Access (Chrome 142+) does not yet gate WebSockets or localhost-to-localhost requests, and does not exist in Firefox or Safari, so it is a bonus, not a control [verified, 43].
  - A **≥ 128-bit per-install secret** in a `0600` file (never argv or environment), presented in a custom header so cross-site forms cannot carry it; passed in the launch URL **fragment**, then exchanged once for an `HttpOnly; SameSite=Strict` cookie (this also survives PWA install, §4b).
  - Server-side confirmation nonces for run-starting and inbox-drop actions; rate limits and an audit log on act endpoints; never return environment variables, tokens or files outside the run directories.
  - CI tests: Host `evil.com:PORT`, cross-origin POST, cross-origin WebSocket upgrade, `Origin: null`, token in query string rejected, bind address equal to `127.0.0.1`, plus the XSS corpus.
- **Connector only:** an exact CORS allowlist for the hosted origin, and act verbs confirmed **locally** (pairing code or native notification), not by a token the hosted page sends.
- **Hosted:** a **GitHub App**, not an OAuth App (§4c); every GitHub call uses the requesting user's token; caches keyed by user and repo; no shared caches for private data; serve from a subdomain separate from the marketing site.
- **Desktop shell:** Electron's checklist and fuses [verified, 11] or Tauri capabilities [verified, 12]; no remote-debugging port in release builds.

### 3. Accessibility and i18n

| Stack | macOS (VoiceOver) | Windows (Narrator/NVDA) | Linux (Orca / AT-SPI) | Source |
|---|---|---|---|---|
| Electron | Good (Chromium AX) | Good (UIA) | Works. Chromium enables AX on demand; some setups need `ACCESSIBILITY_ENABLED=1` [secondary] | [40] |
| Tauri / Wails | Good (WKWebView) | Good (WebView2) | **Fragile.** WebKitGTK has a history of Orca regressions and needs GNOME 46+ for web content inspection [secondary] | [41] |
| Flutter | Good | Good | **Known AT-SPI problems.** Ubuntu docs say the "Flutter engine has compatibility issues with AT-SPI", and Orca can't read the Flutter installer's dropdowns | [verified, 18] |
| Compose MP | Full | Via Java Access Bridge (`jdk.accessibility`) | **Not supported** (official) | [verified, 17] |
| Avalonia | Supported | Supported | **AT-SPI2 "full support"**, automatic when D-Bus and an AT service are present | [verified, 19] |
| Qt 6 | Good | Good | AT-SPI bridge. Qt's docs say only that it "use[s] platform-specific APIs" [verified, 50]; the AT-SPI claim is [inferred] | [50] |
| Native | Best | Best | GTK4 is AT-SPI-native | [inferred] |
| Local / hosted web app | The user's browser AX, generally best-in-class | | | [inferred] |

**Weight for this product:** moderate. It is a developer tool. Keyboard navigation of the board (move cards, open details) matters more than full screen-reader parity. The Compose and Flutter Linux gaps are still a reputational risk for an open-source tool. [inferred]

**i18n:** every stack has mature tooling: ICU/FormatJS/i18next, ARB/intl, Compose resources, resx, Qt Linguist, String Catalogs. Studio mirrors an English-only harness whose prompts, labels and logs are English, so **i18n should not weigh on the choice**. Keep strings in a catalog from day 1 so the option stays cheap. [inferred]

### 4. Code sharing, and the delivery modes

**4a. One design system across the site, Studio and N siblings.**
- The product website must be crawlable HTML. Flutter's FAQ says Flutter web is not suited to "static websites with text-rich flow-based content" and recommends either Jaspr (Dart, DOM-based) or plain HTML for those; flutter.dev and dart.dev themselves migrated to Jaspr [verified, 20]. Compose for Web (Wasm) is Beta [verified, 21] and canvas-rendered.
- A shared component library across site and apps is therefore realistic only with a **web UI**: React or Svelte components, design tokens (CSS variables), and Storybook, published as an internal package and consumed by the Next/Astro site and by every Studio-like app.
- With 5+ planned products (ragscene, langscene, tracescene, scenewise), this is a **strong argument for web-tech UI**: brand consistency, a single place to fix accessibility, and agents reusing one component vocabulary.
- Non-web stacks could share a design system *among desktop apps* (all Compose, or all Flutter). With Flutter the website could share the *language* through Jaspr, but not the components. [inferred]

**4b. Local web app.** Weighed as a real option, not only as a fallback.

| Aspect | Desktop bundle (Electron/Tauri) | Local web app (`npx devscene-studio` → `http://127.0.0.1:PORT/#t=…`) |
|---|---|---|
| Signing / notarization | Apple US$99/yr, Windows signing (see 01/04) | **None.** It ships as an npm package. |
| Windows/WSL | `wsl.exe` transport, helper inside WSL (04). A shell holding a `wsl.exe -e <core>` child keeps the distro alive. | **Server runs inside WSL.** The Windows browser reaches it on `localhost` in both NAT (default; `localhostForwarding=true`) and mirrored mode [verified, 22, 42]. Starting the server still needs `wsl.exe` or a WSL terminal. WSL shuts an idle distro down after 15 s (`instanceIdleTimeout` = 15000 ms) [verified, 42], and systemd services reportedly don't count as activity [secondary, 44], so the server needs an attached session or a `.wslconfig` change. |
| Packaging / updater | DMG, NSIS/MSI, AppImage/deb, plus updater (04) | `npm i -g` / `npx`. Global npm packages don't auto-update; Issue #1 item 17 requires auto-update, so the server needs an "update available" notice. Releasing alongside the CLI removes **app↔CLI** skew only. It does not remove the **CLI↔per-repo-scripts** skew from 05, which still needs the `schema` field and the repo-scripts version stamp 05 asks for. |
| Agent QA | Browser mode with mocks (03), or CDP attach in test builds | **The real product, as-is.** |
| Remote machines | No | **Yes:** SSH port-forward or Codespaces port forwarding to a remote Linux dev box running the harness. [inferred] (Remote runs *on GitHub* are read through `gh` by every mode.) |
| Tray, background notifications, dock | Yes | **No tray.** Web Notifications work only while a tab or service worker is alive. PWA install: Chrome and Edge install from `http://localhost`/`127.0.0.1` [verified, 24]. Safari 17+ "Add to Dock" works for any web page [verified, 24] but is untested on localhost. Firefox desktop cannot install PWAs [verified, 24]. The auth token must survive install (cookie, not query string). |
| OS hand-offs (folder picker, open terminal/editor) | Native dialogs, `shell.openPath`, terminal launch | Server-side reimplementation: a browser file picker gives no absolute path, so the server renders its own directory browser (Issue item 8); terminal hand-off (item 10) and `devscene daemon install` (item 15) need server-side launching, and on Windows WSL interop (`wt.exe`, `explorer.exe`). [inferred] |
| Lifecycle | App launch | Someone must start and keep alive a machine-level server. The harness daemon cannot host it: it is **per repo** (launchd `com.devscene.watcher.<slug>`, systemd `harness-watcher@<slug>.service`) and runs that repo's bash watcher [verified, 52]. Options: start on demand from a terminal or shortcut, or add a new machine-level unit (`devscene studio install`), which is new harness scope (Issue item 7 territory). On systemd hosts the CLI only prints the enable commands [verified, 52]. |
| Security | IPC hardening (§2) | Network-reachable spawning API: see §2a. Distributing via npm also puts Studio itself in the npm blast radius: publish with trusted publishing and provenance, ship with zero install scripts, and pin a minimal dependency set. |
| Users | Anyone (double-click install) | **Harness adopters** have Node. **No-local-setup team users (Issue #1) may not**: the harness supports Python, Rust, .NET, JVM, PHP, Ruby and other repos (`cli/src/detect/presets.ts`) [verified, local repo]. For them the local web app adds Node plus npm plus a terminal-started server (inside WSL on Windows, with `gh` there), against a double-click install. Acceptable for developers; a real barrier for non-Node teams and non-developer board users. [inferred] |

**4c. Hosted web app (e.g. `studio.<product-domain>`).** Weighed as a real option.

- **Sign-in and tokens.**
  - Use a **GitHub App**, not an OAuth App. GitHub says "In general, GitHub Apps are preferred over OAuth apps": a GitHub App gets fine-grained permissions (here Issues RW, Pull requests R, Actions RW for dispatch, Contents R for committed analytics, Metadata R) on the repositories the user chooses. An OAuth App gets all of the user's accessible resources, and issue/PR access needs the broad `repo` scope [verified, 47]. GitHub App user tokens expire after 8 hours with 6-month refresh tokens, on by default [verified, 48].
  - The token exchange needs the app's client secret, so a server-side component is required. Prefer **no server-side token store**: a thin backend-for-frontend does the exchange and keeps tokens in an encrypted `HttpOnly` session cookie. A server-side store is needed only for background work (notifications, polling) and makes the service a high-value target. [inferred]
  - Org-owned repos need an org admin to approve the installation: friction for team adoption, but also an audit trail. [inferred]
- **Multi-tenant isolation:** see §2a. The operator (the owner) becomes a processor of private-repo data. [inferred]
- **Cost:** a static SPA plus a small serverless function for the token exchange and an artifact proxy; typically within free or hobby tiers at small scale, plus the domain the product site needs anyway. No signing certificates, no notarization. GitHub's per-user rate limit applies per signed-in user. [inferred: re-check the chosen host's pricing]
- **What it can do with GitHub data only:** the To Do column (Issues); start remote runs through the Issue trigger; In Progress and Done from Actions runs titled `harness run <branch>`, `devscene:` labels, progress comments and PR state; session detail from `status.json`, `run.log` and clarification files in the `harness-state` artifact (artifact zips redirect to blob storage, so a backend proxy is likely needed [inferred]); analytics from the committed `run_analytics/`/`branch_statistics/`; pause, resume and answer **remote** runs by dispatch (the harness's `branch-pause` and `branch-answer` skills already do this for runs on GitHub) [verified, local plugin]; detect repos carrying the harness workflows. This covers Issue #1's remote-default flow and its no-local-setup users, with zero install on every OS and no WSL.
- **What it cannot reach without a local agent:** the local `registry.json`, local logs, the autonomous inbox (starting **local** runs), watcher and daemon status and `daemon install`, `devscene doctor`, WSL, and folder-based repo detection.
- **Resulting shapes:** (i) **remote-only**: simplest and safest; (ii) **hosted UI + local connector** (the §4b Node server in API-only mode): reintroduces every §2a local-listener issue, adds the hosted-XSS-to-local-spawn path, triggers Chrome's Local Network Access prompt (public origin → loopback) [verified, 43], and needs a Safari/Firefox spike; (iii) **desktop shell or local app for local runs, hosted app for remote runs**, with the same web UI in both.
- **Fit with the product web site:** it can share the site's stack, design system, domain and sign-in across sibling products. Serve it from a **separate subdomain** from the marketing site so cookies and any XSS stay isolated. [inferred]

**4d. Comparison of the four delivery modes** [inferred unless tagged]

| | Desktop shell (Electron/Tauri) | Local web app | Hosted web app (remote-only) | Hosted UI + local connector |
|---|---|---|---|---|
| Install friction | Download and double-click | Node ≥ 20 + npm + terminal-started server (in WSL on Windows) | **None** (a URL and GitHub sign-in) | None for remote; Node + connector for local |
| Signing cost | Apple US$99/yr + Windows signing (free via SignPath if OSS, 01) | None | None | None |
| Auto-update | Updater per 04 (electron-updater the most complete) | No; "update available" notice only | **Instant** (deploy) | UI instant; connector via npm, manual |
| Attack surface | No listener; XSS → IPC | Local spawning listener; XSS → full API | Multi-tenant service; XSS → user's GitHub permissions | **Both**, plus hosted-XSS → local spawn |
| Local runs | Yes | Yes | **No** | Yes |
| Remote runs | Yes (via `gh`) | Yes (via `gh`) | Yes | Yes |
| Windows/WSL lifecycle | Shell holds a `wsl.exe` child: keep-alive for free | Server must be started in WSL and kept attached (15 s idle shutdown) [verified, 42] | n/a | Same as local web app |
| Agent QA | Browser mode (03); CDP in test builds | Real product | Real product (preview deploys) | Real product (UI); connector by API tests |
| Offline use | Yes (local data) | Yes (local data) | No | Partly |
| Tray / OS notifications | Yes | No (PWA partial) | No (web push possible) | No |
| OS hand-offs (folder picker, terminal) | Native | Server-side reimplementation | n/a | Server-side reimplementation |
| Data-processor obligations | None | None | **Yes** (privacy policy, GDPR) | Yes |

**Criteria that flip the delivery-mode choice:**
- **Are local runs a v1 requirement?** If not, a hosted remote-only app removes signing, WSL and Node-install friction entirely, at the price of running a service and its data-handling duties.
- **If local runs are required**, the hybrid connector carries the highest security burden of all modes; a desktop shell for local runs (optionally with the hosted app for remote runs) carries the lowest.
- **Are no-local-setup users a v1 audience?** If so, the local web app cannot be the sole deliverable. That audience is exactly the one the hosted app serves with zero install (or a desktop shell with a double-click).
- **Are tray and background notifications v1 needs?** Issue #1 does not list them. If they are, only the desktop shell delivers them.
- **How much weight does security get?** At the top of the list (the owner's stated concern), the desktop shell and the hosted remote-only app are the lower-risk modes; the local web app is acceptable only with every §2a control and its CI tests; the hybrid is the hardest to secure.
- **Is the owner willing to operate a service?** A hosted app means uptime, incident response and privacy obligations that no local mode has.

### 5. Observability: crash reporting and opt-in telemetry

| Stack | Sentry SDK [verified, 25] | Native crash capture | Notes |
|---|---|---|---|
| Electron | **Official `@sentry/electron`** | Yes (Crashpad minidumps) | One SDK covers main and renderer |
| Tauri | No Tauri guide; the official **Rust** and **JavaScript** SDKs are wired by hand. Community `tauri-plugin-sentry` is "experimental"; it merges Rust and JS breadcrumbs [secondary, 26] | Through `sentry-rust-minidump`; official Rust SDK minidumps need ≥ 0.49.3 [secondary, 26] | Maintenance risk in the plugin |
| Wails | No Wails guide; official **Go** SDK plus `@sentry/browser` wired by hand | Go panics only | [inferred] |
| Flutter | **Official** | Yes (desktop via the native SDK) [secondary] | |
| Compose MP | **Official** Compose Multiplatform guide | JVM exceptions; JVM crash logs are manual | |
| Avalonia | No Avalonia guide; official **.NET** SDK wired by hand | Managed exceptions | |
| Qt | **Official** sentry-native Qt guide | Yes | |
| Native ×3 | Cocoa, .NET WinUI, native/GTK: three integrations | Yes | Triple the setup |
| Local / hosted web app | `@sentry/node` (or serverless) + `@sentry/browser` | n/a (no native layer) | Simplest |

- **Cost:** Sentry Developer is free (5k errors/month, 1 user), and the Team plan is US$26/month billed annually [verified, 45]. **Open-source sponsorship: 5M errors/month** for OSI-licensed projects [verified, 27]. Self-hostable alternative: GlitchTip, which speaks the Sentry protocol [inferred].
- **Telemetry:** make it **opt-in** with a first-run dialog. Aptabase (MIT SDKs, AGPL server, EU hosting, no device identifiers, 20k events/month free) has Tauri, Electron, Flutter, Swift and C++ SDKs [verified, 28]. Never send repo names, branch names, issue text or paths. Scrub crash reports of `$HOME` paths and tokens (§2).

### 6. Licensing of the app itself

- **Recommended: Apache-2.0 (or MIT), matching the harness** (`devscene` is Apache-2.0 and already ships a `funding.json`) [verified, local repo]. Open source unlocks:
  - **SignPath Foundation** free Windows signing (conditions in 01).
  - **Conveyor** free for OSI-licensed projects, otherwise **$45/month** [verified, 29]. Relevant if Compose is chosen (04).
  - **Sentry's** sponsored plan [verified, 27].
  - Free GitHub-hosted runners, including macOS and Windows, for **public** repos (verified live in 06). Notarization builds need a macOS runner in every desktop stack.
- **Rough annual value against a closed-source build** [inferred, prices from 29, 45 and 04]:

  | Item | Annual cost if closed source | Applies to |
  |---|---|---|
  | Sentry Team | ~US$312 ($26/mo annual); the free Developer tier likely suffices, so this may not be a real saving | All |
  | Conveyor Standard | US$540 ($45/mo) | Compose only |
  | OV code-signing certificate | US$300–500 (per 04) | Desktop stacks |
  | Azure Artifact Signing | ~US$120, where eligible (alternative to OV) | Desktop stacks |
  | macOS runner minutes | Private-repo rates (06) | Desktop stacks |

  So the saving is about **US$420–810/yr for Electron/Tauri**, about **US$960–1,350/yr with Conveyor**, and about **US$0–312/yr for the local or hosted web app**, which have nothing to sign.
- **Framework licence interaction:**
  - Electron, Tauri, Wails, Flutter, Compose and Avalonia core are permissive. No issue.
  - **Qt LGPLv3:** fine for an open-source app (dynamic linking and relinkability are trivially met when source is public). **PyQt6 is GPL**; PySide6 is LGPL (01).
  - **Slint** is GPLv3 or royalty-free with attribution; it was dropped in 01 anyway.
  - Avalonia's paid tiers affect **developer tooling** (official Hot Reload), not the shipped app; DevTools has a free Community edition [verified, 35].
- **SignPath restriction:** SignPath requires **no dual licensing** (01). An "open core plus paid edition" plan for Studio would lose it.
- **Donations (Issue item 18):** GitHub Sponsors, Open Collective and Stripe links are independent of the framework and licence. Open source is the model donations work best with, and the harness already advertises funding. Rendering the link means an `openExternal` / `shell.open` allowlist in Electron or Tauri; in the web modes it is a plain `<a target=_blank rel="noopener noreferrer">`. [inferred]

### 7. Developer experience

| Stack | Toolchain a contributor installs | UI hot reload | Debugging | Build time (indicative) |
|---|---|---|---|---|
| **Local web app** | **Node only** (already required by the harness for adopters) | Vite HMR | Browser DevTools + Node inspector | Seconds |
| **Hosted web app** | Node only, plus a deploy target and a GitHub App for dev | Vite HMR | Browser DevTools + serverless logs | Seconds; deploy minutes |
| **Electron** | Node only | Vite HMR (renderer); main-process restart | Chrome DevTools, Node inspector | Seconds; packaging minutes |
| **Tauri 2** | Node + **Rust** + platform deps (MSVC Build Tools/WebView2; Xcode CLT; WebKitGTK-4.1 dev libs) | Frontend HMR; **Rust edits recompile** | DevTools + rust-analyzer/lldb | **Cold 3–8 min**, then seconds to tens of seconds; Windows `target/` watcher pitfalls [secondary, 33] |
| **Wails 3** | Node + **Go** + GTK4/WebKitGTK 6.0 dev libs on Linux (04) | Frontend HMR; Go rebuild is fast | DevTools + Delve | Go builds fast [inferred] |
| **Flutter** | Flutter SDK (GBs) + Xcode / VS C++ / clang-cmake-GTK | **Stateful hot reload, best in class** | Dart DevTools | Moderate |
| **Compose MP** | JDK + Gradle (+ IntelliJ) | **Compose Hot Reload, stable since CMP 1.10, bundled and on by default** [verified, 34] | IntelliJ | Gradle: slowest inner loop of the cross-platform options [inferred] |
| **Avalonia** | .NET SDK | **Official Hot Reload is paid** (Plus and above); HotAvalonia is MIT and free [verified, 35] | Rider/VS; DevTools has a free Community edition [verified, 35] | Fast |
| **Qt / PySide6** | `pip install PySide6` (easy) / Qt online installer + C++ toolchain | QML live preview; PySide restart | Qt Creator | Deployment (pyside6-deploy/Nuitka) is the pain point [inferred] |
| **Native ×3** | Xcode (Mac only) + VS (Windows only) + GTK toolchain | SwiftUI Previews, XAML Hot Reload | Three debuggers | Three pipelines (03) |

**Harness tie-in:** the harness's remote runs are Linux-only (03). Every web-tech option, Flutter, Compose and Avalonia can typecheck and test there. Every web-tech option can also be **QA-driven** there in browser mode (03). The local and hosted web apps and Electron (with Xvfb) can be driven unmocked. [inferred]

### 8. Additional decision-relevant criteria

| # | Criterion | Why it matters (one line) | Who it favours |
|---|---|---|---|
| 8.1 | **Rendering untrusted GitHub content** | Issue and PR text, plus logs, are attacker-controlled; webviews and browsers turn that into an XSS-to-privileged-action risk (§2a). Scored under criterion 2. | Native toolkits, and Tauri (ACL); web-tech stacks need CSP and sanitizing |
| 8.2 | **Version skew with the harness** | 05's skew is between the CLI and the per-repo rendered scripts; no delivery mode removes it. Releasing alongside the CLI removes only app↔CLI skew. Not scored. | Neutral |
| 8.3 | **Remote / headless harness hosts** | A remote Linux dev box running the harness locally is reachable by an HTTP UI through port forwarding; remote runs on GitHub are read through `gh` by every mode. Uncited; not scored. [inferred] | Local web app (dev boxes); hosted app (GitHub runs) |
| 8.4 | **Contributor pool for an OSS repo** | Outside contributors are likelier in TS than in Rust, Kotlin, C# or Swift (career and corpus data in 03). | TS stacks |
| 8.5 | **Deep links** | "Open this run in Studio" from a PR comment or a notification needs either a custom URL scheme (signing-sensitive on macOS) or a plain http(s) URL. | Hosted (a real https URL), local web app; desktop needs protocol registration |
| 8.6 | **Single-instance and background lifecycle** | Tray and auto-start need a desktop shell; the local web app needs a new machine-level unit or a manually started server (§4b). | Desktop shells; hosted needs none |
| 8.7 | **CI build matrix** | Notarized macOS and signed Windows artefacts need native runners in every desktop stack; it weighs against native ×3 and favours a public repo. | Web modes (no artefacts); desktop stacks roughly equal; native last |
| 8.8 | **OS hand-offs** | Folder picker with absolute paths (Issue item 8), terminal hand-off (item 10), `devscene daemon install` (item 15). | Desktop shells (native); local web app reimplements server-side; hosted cannot |

## Answers to the owner's questions

- **Q1/Q2 (cross-platform credible, worth it):** the extra criteria reinforce one cross-platform **web-tech** UI. Agent QA fits the harness's existing driver, one design system spans the website and siblings, and Sentry, Playwright and npm tooling are mature. They also widen the delivery options beyond the brief: the same UI can ship as a desktop shell, a local web app, a hosted web app, or a hosted UI with a local connector (§4d). Which one is the owner's call; the security weighting, the local-runs requirement and the no-local-setup audience decide it.
- **Q5 (native-side blockers):** see §1 (no WKWebView WebDriver; Tauri real-shell QA is Windows-only through the harness MCPs and needs mirrored networking for a harness in WSL), §3 (Compose has no Linux accessibility; Flutter's AT-SPI is weak) and §4b (WSL idle shutdown for any server inside WSL).
- **Q6 (financial costs):** see §1 (Squish is quote-only, about €6–10k; CrabNebula's macOS WebDriver is paid), §5 (Sentry free tier and OSS sponsorship; Aptabase free tier), §6 (open-sourcing saves about US$420–810/yr for Electron/Tauri; Avalonia's official Hot Reload is paid) and §4c (a hosted app adds hosting costs, typically within free tiers at small scale, and no signing).

## Risks and open questions

1. **The CDP attach path for Electron is inferred, not demonstrated.** Neither Playwright MCP nor Chrome DevTools MCP documents Electron. Do a 30-minute spike: launch Electron with `--remote-debugging-port=9222`, then point both MCPs at it. Also test a harness running **inside WSL** against a **Windows-side** Electron, with NAT and with mirrored networking: that is the configuration that matters on Windows.
2. **Tray and notification requirements, and the local-runs requirement,** decide the delivery mode (§4d). Issue #1 does not list tray or notifications. Confirm both before treating them as v1 needs.
3. **PWA install of the local web app in Safari:** "Add to Dock" on `http://localhost` is untested [verified for Chrome/Edge, 24].
4. **Localhost server hardening** is easy to get wrong (Host checks with ports, WebSocket origins, token leaks). It needs the CI test list in §2a. 08 owns the full plan.
5. **WSL lifecycle for a server inside WSL:** the claim that systemd services do not count as activity for `instanceIdleTimeout` is secondary [44]; verify on a current WSL build.
6. **Hosted app unknowns:** artifact download through a proxy, org-approval friction for the GitHub App, and the operator's privacy obligations. A hybrid connector also needs a Safari/Firefox spike for public-origin → loopback calls.
7. **Experimental agent tooling everywhere:** the Compose Hot Reload MCP, the Dart MCP server, Playwright `_electron` and `tauri-plugin-wdio-webdriver` are all pre-stable. Re-check them at implementation time.
8. **NovaWindows status** rests on secondary sources [38]. It matters only for the native-Windows option, which 03 already discourages.
9. The GitHub Actions self-hosted fee was postponed, according to secondary sources only [30]. Public-repo hosted runners remain free (06).

### Scoring (1 = poor, 5 = excellent, for *this* app)

Weights: high = 3, med = 2, low = 1. The weighted total is out of 115.

| Criterion (weight) | Hosted (remote-only) | Hosted + connector | Local web app | Electron | Tauri 2 | Wails 3 | Flutter | Compose MP | Avalonia | Qt/PySide6 | Native ×3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Agent-drivable UI testing (3) | 5 | 5 | 5 | 4 | 3 | 3 | 3 | 3 | 3 | 2 | 1 |
| 2. Security model (3) | 3 | 1 | 2 | 3 | 4 | 3 | 4 | 4 | 4 | 4 | 4 |
| 3. Accessibility (2) | 4 | 4 | 4 | 4 | 3 | 3 | 2 | 2 | 4 | 4 | 5 |
| 4. Code sharing: site + siblings (3) | 5 | 5 | 5 | 5 | 5 | 5 | 2 | 2 | 1 | 1 | 1 |
| 5. Observability (2) | 4 | 4 | 4 | 5 | 3 | 3 | 4 | 4 | 3 | 4 | 3 |
| 6. Licensing / OSS fit (2) | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 5 |
| 7. Developer experience (3) | 5 | 4 | 5 | 5 | 3 | 3 | 4 | 3 | 3 | 2 | 1 |
| 8. Other: contributors, deep links, CI (8.4, 8.5, 8.7) (1) | 5 | 5 | 5 | 4 | 3 | 3 | 3 | 3 | 3 | 3 | 1 |
| 9. Distribution, signing, updates (2) | 5 | 3 | 3 | 4 | 3 | 3 | 2 | 2 | 3 | 3 | 2 |
| 10. Install, lifecycle, no-setup users, operations (2) | 4 | 2 | 2 | 4 | 4 | 4 | 4 | 4 | 4 | 3 | 4 |
| **Weighted total (/115)** | **103** | 86 | 92 | **99** | 84 | 81 | 76 | 73 | 74 | 66 | 60 |
| **Gate: local runs** | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Gate: tray / OS notifications** | ✗ | ✗ | ✗ (PWA partial) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**How the scores were set** [inferred]:
- Criterion 2: the local web app scores 2 by default (a network-reachable spawning API, §2a); it rises to 3 only if CI carries the rebinding, CSRF, WebSocket-hijack and XSS tests. The hosted app scores 3 (no local spawning, but a multi-tenant service holding users' GitHub sessions). The hybrid scores 1 (both surfaces, plus hosted-XSS → local spawn).
- Criterion 5: Tauri, Wails and Avalonia all score 3 (official language SDKs, no framework guide).
- Criterion 6: Qt is 4 (LGPL is fine for an OSS app; only PyQt is GPL). Avalonia is 5 (its paid tooling is counted under criterion 7, not here).
- Criterion 8 no longer includes 8.1 (counted in 2), 8.2 (no mode removes the skew) or 8.3 (uncited), so it no longer favours one mode by construction.
- Criterion 9 follows 04's updater coverage (electron-updater the most complete; Compose needs Conveyor; Flutter's updater is stale); the local web app gets no signing cost but no auto-update and an npm distribution channel.
- Criterion 10 covers double-click install, Windows/WSL keep-alive, users without Node, and operating a service. The hosted app loses a point for its operator obligations.

**Reading the table.** The hosted (remote-only) app, Electron and the local web app are within noise of each other on these criteria (a one-point change in one high-weight row moves a total by 3). **This table does not settle the delivery mode.** That turns on the two gates (local runs, tray/notifications), on how heavily security is weighted (§2a), on users without Node, and on how much of the product must work without a local harness (§4d). Among desktop shells, Electron leads Tauri mainly on agent QA, DX and update coverage; Tauri leads on security. Read the table with 01–05: it does not include bundle size (02), effort (03), OS blockers (04) or the integration contract (05).

**Criteria that could flip the framework order:**
- **Tray and background notifications as a hard v1 requirement** take all web-only modes out as the *sole* deliverable. Electron then leads Tauri on these criteria. The web-first architecture still holds, with a shell around it.
- **Local runs not required in v1** make the hosted remote-only app the simplest option on every row except security-of-a-service and operator duties.
- **Mandatory real-shell agent QA on macOS** widens Electron's lead over Tauri and Wails. Tauri's macOS path depends on a third-party embedded plugin or a paid fork.
- **Linux screen-reader support as a requirement** removes Compose (officially unsupported) and Flutter (known AT-SPI failures), and lifts Avalonia, Qt and native.
- **Security weighted above everything** moves Tauri, with its ACL, above Electron, non-webview toolkits above both, and pushes the local web app and the hybrid down. Strict CSP plus sanitizing closes most of the webview gap; it does not close the listener gap.
- **Closed-source licensing** removes the free SignPath, Conveyor, Sentry and runner benefits. It also makes Qt's LGPL obligations and Avalonia's paid tooling bite. It does not change the order at the top.
- **Dropping the shared design system with the website and siblings** lets Flutter and Compose gain up to 9 weighted points on criterion 4. Even then they stay behind on agent QA and DX.

## Sources

1. https://v2.tauri.app/develop/tests/webdriver/: tauri-driver Windows/Linux only; macOS via `@wdio/tauri-service` embedded server; CrabNebula fork needs a paid key on macOS; "Last updated Jun 29, 2026". Accessed 2026-11-12.
2. https://playwright.dev/docs/api/class-electron: Electron automation experimental, v21+; `electronApp.evaluate` runs in the main process; `nodeCliInspect` fuse must not be `false`. Accessed 2026-11-12.
3. https://github.com/microsoft/playwright-mcp: `--cdp-endpoint`, `--extension`; no Electron mention. Accessed 2026-11-12.
4. https://raw.githubusercontent.com/ChromeDevTools/chrome-devtools-mcp/main/docs/configuration.md: `--browserUrl`, `--wsEndpoint`, `--autoConnect`; Chrome-only official support. Accessed 2026-11-12.
5. https://playwright.dev/docs/webview2: Playwright `connectOverCDP` to WebView2 via `--remote-debugging-port`. Accessed 2026-11-12.
6. https://glama.ai/mcp/servers/aj47/electron-native-mcp: example third-party Electron MCP (CDP; macOS-only) [secondary]. Accessed 2026-11-12.
7. https://github.com/dart-lang/ai/tree/main/pkgs/dart_mcp_server: Dart/Flutter MCP tools (widget_inspector, flutter_driver_command, hot_reload, launch_app off by default via `flutter_app_lifecycle`); desktop support not documented; "WIP… experimental". Accessed 2026-11-12. 7a. https://docs.flutter.dev/testing/integration-tests: integration_test on macOS/Windows/Linux; Linux needs X. Accessed 2026-11-12.
8. https://kotlinlang.org/docs/multiplatform/whats-new-compose-112.html: experimental Compose Hot Reload MCP server (screenshots, semantic tree, clicks and input, logs); page dated 2026-10-15. Accessed 2026-11-12.
9. https://v3.wails.io/guides/e2e-testing: Playwright against the Wails dev server (port 9245); https://git.mirv.top/verstak/verstak-desktop/src/branch/main/docs/GUI_TESTING.md, mocked bindings skip WebKitGTK [secondary]. Accessed 2026-11-12.
10. https://kotlinlang.org/docs/multiplatform/compose-desktop-ui-testing.html: `uiTestJUnit4`, `runComposeUiTest`; experimental. Accessed 2026-11-12.
11. https://www.electronjs.org/docs/latest/tutorial/security: contextIsolation default since 12, sandbox since 20, nodeIntegration off; 20-item checklist; fuses. Accessed 2026-11-12.
12. https://v2.tauri.app/security/capabilities/: per-window capabilities, remote URLs off by default, platform scoping, `AppManifest::commands` caveat. Accessed 2026-11-12.
13. https://docs.avaloniaui.net/docs/concepts/headless/: Avalonia.Headless with xUnit/NUnit, Skia `CaptureRenderedFrame`, input simulation. Accessed 2026-11-12.
14. https://labs.cloudsecurityalliance.org/research/csa-research-note-mini-shai-hulud-multi-ecosystem-supply-cha/ and https://thenewstack.io/npm-supply-chain-worm-attack/: 2026 Mini Shai-Hulud npm waves [secondary]. Accessed 2026-11-12.
15. https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/: crates.io compromise, 2026-08-20; likely compromised author account or machine; `proc-macro1` build script; 86/90/107-minute windows. Accessed 2026-11-12.
16. https://webkitgtk.org/security.html (WSA-2026-0001…0006, latest 2026-09-29; stable 2.54.2, 2026-10-23); https://linuxsecurity.com/advisories/ubuntu/webkitgtk-ubuntu-8237-1; https://errata.tuxcare.com/els_os/almalinux9.2esu/CLSA-2026-1777544437.html: WebKitGTK 2026 advisories and distro lag. Accessed 2026-11-12.
17. https://kotlinlang.org/docs/multiplatform/compose-desktop-accessibility.html: macOS full, Windows via Java Access Bridge, Linux unsupported. Accessed 2026-11-12.
18. https://documentation.ubuntu.com/desktop/en/latest/explanation/accessibility-stack and https://discourse.ubuntu.com/t/accessibility-flutter-based-ubuntu-25-10-installer-dropdown-menus-are-not-readable-by-orca-manual-disk-partitioning/73970: Flutter AT-SPI issues; GTK3/GTK4 bridges. Accessed 2026-11-12.
19. https://docs.avaloniaui.net/docs/app-development/accessibility and https://docs.avaloniaui.net/docs/platform-specific-guides/linux: AT-SPI2 full support. Accessed 2026-11-12.
20. https://docs.flutter.dev/platform-integration/web/faq: Flutter web not suitable for text-rich static sites; recommends Jaspr or HTML; flutter.dev and dart.dev migrated to Jaspr. Accessed 2026-11-12.
21. https://kotlinlang.org/docs/multiplatform/supported-platforms.html: Compose web (Wasm) Beta; desktop Stable. Accessed 2026-11-12.
22. https://learn.microsoft.com/en-us/windows/wsl/networking: Windows reaches WSL servers via `localhost` (NAT default); WSL reaches Windows only via the host IP in NAT mode; mirrored mode adds two-way localhost and "Connect to WSL directly from your local area network (LAN)"; Hyper-V firewall (page updated 2026-06-02). Accessed 2026-11-12.
23. https://github.blog/security/application-security/dns-rebinding-attacks-explained-the-lookup-is-coming-from-inside-the-house/: DNS rebinding against localhost services; Host and Origin checks [secondary]. Accessed 2026-11-12.
24. https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable: PWAs installable from HTTPS or localhost/127.0.0.1; service worker not required; Safari 17+ Add to Dock for any web app; Firefox does not support installing PWAs. Accessed 2026-11-12.
25. https://docs.sentry.io/platforms/: platform list (JavaScript incl. Electron, Rust, Go, .NET, Native incl. Qt, Flutter, Compose MP); no Tauri, Wails or Avalonia guide. Accessed 2026-11-12.
26. https://lib.rs/crates/tauri-plugin-sentry and https://docs.sentry.io/platforms/rust/native-crash-reporting/: community Tauri plugin (experimental); Rust minidumps ≥ 0.49.3 [secondary]. Accessed 2026-11-12.
27. https://sentry.io/for/open-source: OSS sponsorship (5M errors/month, permissive licence). Accessed 2026-11-12.
28. https://aptabase.com/: SDKs (Tauri, Electron, Flutter, Swift, C++), MIT SDKs and AGPL server, 20k events/month free. Accessed 2026-11-12.
29. https://hydraulic.dev/pricing.html: Conveyor free for OSI-licensed projects, $45/month Standard. Accessed 2026-11-12.
30. https://resources.github.com/actions/2026-pricing-changes-for-github-actions/ and https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/: self-hosted fee postponed (secondary reports; announcement older than 12 months). Public-repo runner pricing verified live in 06. Accessed 2026-11-12.
31. https://www.electronjs.org/docs/latest/tutorial/electron-timelines: 3 supported majors; only the latest minor of each gets fixes. Accessed 2026-11-12.
32. (Superseded by 46.) https://github.com/cli/cli/pull/7023 (older than 12 months): gh keyring storage with plaintext fallback [secondary]. Accessed 2026-11-12.
33. https://dev.to/ahonn/how-to-make-your-tauri-dev-faster-2en1 and https://tech-insider.org/tauri-tutorial-cross-platform-rust-app-2026/: Tauri cold build and rebuild times [secondary]. Accessed 2026-11-12.
34. https://kotlinlang.org/docs/multiplatform/compose-hot-reload.html and https://blog.jetbrains.com/kotlin/2026/01/compose-multiplatform-1-10-0/: Compose Hot Reload stable, bundled. Accessed 2026-11-12.
35. https://avaloniaui.net/hot-reload and https://nuget.org/packages/HotAvalonia: "Unlike DevTools, Parcel and the IDE extensions, Hot Reload has no free Community edition"; Plus and above; HotAvalonia MIT. Accessed 2026-11-12.
36. https://www.qt.io/quality-assurance/licensing and https://us.fitgap.com/products/squish-gui-tester: Squish quote-only; third-party price figures [secondary]. Accessed 2026-11-12.
37. https://doc.qt.io/agentictools/mcp/ and https://glama.ai/mcp/servers/@0xCarbon/qt-mcp: Qt official MCP (docs, QML preview); community runtime MCPs [secondary]. Accessed 2026-11-12.
38. https://github.com/appium/appium-windows-driver and https://learn.microsoft.com/en-us/answers/questions/1455246/is-the-tool-winappdriver-dead-or-not: NovaWindows suggested as WinAppDriver replacement [secondary]. Accessed 2026-11-12.
39. https://glama.ai/mcp/servers/isac322/kwin-mcp and https://cua.ai/blog/inside-linux-computer-use: AT-SPI-based agent MCPs [secondary]. Accessed 2026-11-12.
40. https://chromium.googlesource.com/chromium/src/+/HEAD/docs/accessibility/overview.md: Chromium AX enabled on demand [verified]; Linux `ACCESSIBILITY_ENABLED` note [secondary]. Accessed 2026-11-12.
41. https://mail.gnome.org/archives/orca-list/2022-May/msg00046.html (older than 12 months) and https://events.gnome.org/event/209/contributions/756: WebKitGTK and Orca regressions; GNOME 46 improvements [secondary]. Accessed 2026-11-12.
42. https://learn.microsoft.com/en-us/windows/wsl/wsl-config (updated 2026-10-16): `localhostForwarding` default `true` ("ports bound to wildcard or localhost"), ignored when `networkingMode=mirrored`; `networkingMode` default `NAT`; `[general] instanceIdleTimeout` default 15000 ms, -1 disables. Accessed 2026-11-12.
43. https://developer.chrome.com/blog/local-network-access: Local Network Access prompt ships in Chrome 142; WebSockets not yet gated; localhost-to-localhost not yet covered. Accessed 2026-11-12.
44. https://learn.microsoft.com/en-us/answers/questions/1192206/wsl2-cant-run-in-the-background-after-enabling-sys and https://guidov.github.io/2024/09/15/wsl2-keep-alive: systemd services do not keep a WSL instance alive [secondary]. Accessed 2026-11-12.
45. https://sentry.io/pricing/: Developer free (5,000 errors/month, 1 user); Team US$26/month billed annually. Accessed 2026-11-12.
46. https://cli.github.com/manual/gh_auth_login: token in the system credential store; plain-text fallback when none is found or usable; `--insecure-storage`. Accessed 2026-11-12.
47. https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps: GitHub Apps preferred; fine-grained permissions on chosen repos; OAuth apps get all accessible resources; broad `repo` scope. Accessed 2026-11-12.
48. https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens: user tokens expire after 8 hours, refresh tokens after 6 months; expiry on unless opted out. Accessed 2026-11-12.
49. https://www.sonatype.com/blog/mini-shai-hulud-npm-attack-more-than-2200-components-impacted: 2,225 component versions (snapshot); wave on 2026-08-04 in keyv/cacheable [secondary]. Accessed 2026-11-12.
50. https://doc.qt.io/qt-6/accessible.html: Qt "does use platform-specific APIs" to expose accessibility; does not name AT-SPI. Accessed 2026-11-12.
51. `gh api repos/microsoft/WinAppDriver/releases` and `gh api repos/microsoft/WinAppDriver`: last stable v1.2.1 (2020-11-05), last pre-release v1.2.99 (2021-07-01); not archived; last push 2025-04-14. Accessed 2026-11-12.
52. Local harness source `/Users/daniel/Work/devscene`: `docs/cli.md` §9 (daemon identity is the repository; launchd `com.devscene.watcher.<slug>`, systemd `harness-watcher@<slug>.service`; "launchd is driven; systemd is instructed"); `cli/src/daemon/backend.ts` header; `cli/src/detect/presets.ts` (non-Node presets). Accessed 2026-11-12.
