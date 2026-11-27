# Review — 07-additional-criteria.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The per-criterion research (§1–§7) is mostly accurate. Most of the load-bearing facts check out live:
- WSL `localhostForwarding` defaults to on, and NAT is the default networking mode.
- MDN allows PWA install from localhost.
- The Playwright MCP `--cdp-endpoint` and Chrome DevTools MCP `--browserUrl` flags exist.
- Playwright's Electron support is experimental (v21+).
- macOS has no WKWebView WebDriver, and CrabNebula needs a paid key on macOS.
- The Compose 1.12 MCP server is experimental, and so is the Dart MCP server.
- Compose has no Linux accessibility, and Ubuntu flags Flutter's AT-SPI issues.
- The Flutter web FAQ and the Compose Wasm Beta status are as quoted.
- The Sentry SDK list and its OSS plan are as stated.
- The arrayref date is right, Avalonia's hot reload is paid, and the `gh` plaintext fallback exists.

A few details are stale or wrong: WebKitGTK now has 6 advisories in 2026, Avalonia DevTools has a free tier, the arrayref mechanism is described wrongly, and WinAppDriver had a 2021 pre-release. These are should-fix items.

**The headline recommendation is the problem.** It is not a problem because it departs from Issue #1. The owner has clarified that Issue #1's decisions are initial discussion points that the research may overturn. It is a problem because its case on the merits is one-sided:
- It rests on two wrong claims about the harness: that the `devscene daemon` runs once per machine and could host the server (M2), and that npm lockstep removes the skew 05 describes (M5).
- It ignores the WSL instance idle shutdown (M4).
- It assumes every Studio user has Node, but Issue #1 identifies users with no local setup, and the harness supports non-Node repos (M3).
- **Its security analysis is one table cell.** Security is the owner's main concern with this option. A process-spawning HTTP server on localhost has a larger attack surface than any desktop shell, and 07 does not work it through (M7).
- **It does not assess a hosted, deployed web app at all** (M8). That is the obvious fourth delivery mode, and it fits Issue #1's remote-default, `gh`-first data model.

The scoring table puts the local web app 1 point ahead of Electron (36 vs 35). That lead disappears once three things are corrected: the self-referential criterion 8, the security score, and the omitted distribution and lifecycle axes. The file needs a reframe and two new sections (M7 security, M8 hosted web app), not a rewrite. The verdict is PASS WITH FIXES.

## Must fix

**M1. TL;DR bullet 1 and §4b verdict: the recommendation is stated as a conclusion, but the comparison behind it is incomplete.**
- **Problem.** The owner has clarified that Issue #1's decisions (desktop app, signed bundles, `wsl.exe`/`\\wsl$`) are initial discussion points. Departing from them is therefore **not** a finding in itself, and 07 is right to put the local web app on the table. The problem is that the TL;DR states "build browser-first" as a recommendation on a comparison that is missing four things:
  - **Security**, the owner's main concern. 07 gives the local server one table cell (M7).
  - **Lifecycle on Windows**: idle shutdown (M4) and the daemon claim (M2).
  - **Users without Node** (M3).
  - **The hosted web app option**, which 07 does not assess at all (M8).

  07's own §4b lists the benefits of the local web app: no signing, QA on the real UI, and one server. Its costs are understated: an always-on listener, a token flow, auto-update, and OS hand-offs (S9).
- **Fix.** Reword TL;DR bullet 1 and the §4b verdict to separate the architecture finding, which is well supported, from the delivery-mode choice, which is still open. Suggested text:
  > "**A web-first architecture is the strongest finding:** build the UI as a web app that talks HTTP/WebSocket to a small Node core. That core is the 04 WSL helper and the 05 contract client. The same UI can then ship in up to four delivery modes: (1) a desktop shell, Electron or Tauri; (2) a local web app (`devscene-studio serve`); (3) a hosted web app with GitHub sign-in (§4c), limited to what GitHub holds; (4) a hosted UI plus an optional local connector. The modes trade off security (§2, §4b), lifecycle on Windows/WSL, install friction for users without Node, signing cost and auto-update. The table in §4d compares them. The choice between them is the owner's; the research default is to build web-first so that the choice can be deferred."

  This keeps every real benefit 07 found (QA on the real UI, one server implemented once, Electron vs Tauri deferred) without presenting the delivery mode as decided.

**M2. §4b "Lifecycle" row and §8.6: "hosted by the existing `devscene daemon` (launchd/systemd), which already runs per machine (05)" is wrong.**
- **Problem.** The harness daemon is **per repository**, not per machine. Its only program is that repo's bash watcher. Studio's server is cross-repo (Issue item 8's repo dropdown), so it cannot be "hosted by" any one repo's watcher unit.
- **Evidence (local harness source).** The launchd label is `com.devscene.watcher.<slug>` and the systemd unit is `harness-watcher@<slug>.service`, where the slug comes from the repo path. "A second repository on the same machine installs a watcher of its own." The daemon runs `<repoRoot>/<scriptsDir>/autonomous-watcher.sh` (`/Users/daniel/Work/devscene/docs/cli.md` §9; `cli/src/daemon/backend.ts` header). On systemd the CLI only *prints* the `systemctl --user` commands ("launchd is driven; systemd is instructed"). Users with no local setup have no daemon at all.
- **Fix.** Replace the row text with:
  > "Someone must start and keep alive a machine-level server. The harness daemon cannot host it: it is per repo and runs the repo's bash watcher (`devscene/docs/cli.md` §9). Options: start on demand from a terminal or shortcut, or add a new machine-level unit (`devscene studio install`), which is new harness scope (Issue item 7 territory). On systemd hosts the CLI only prints the enable commands."

  Correct §8.6 to match.

**M3. §4b "Users" row: "Harness users are developers who already ran `npx devscene init`. The friction is minimal." The premise is false for part of the audience.**
- **Problem.** This is a merits point, not a constraint point. Issue #1 identifies the audience: it says `git`/`gh` is the primary source "because some users (team members whose repo someone else set up) have no local plugin, watcher or logs". Item 8 also names "users with no local setup". Those users ran no `init`, so they may not have Node at all. The harness supports non-Node repos: `cli/src/detect/presets.ts` includes `python-package`, `rust-cargo`, `dotnet`, `jvm`, `flutter`, `apple-native`, `php-composer` and `ruby-bundler`. Issue #1 also puts the To Do column in GitHub Issues "so the whole team sees them", which hints at less technical board users.

  For these users, the local web app needs all of the following, where a DMG/AppImage double-click needs none:
  - Node ≥ 20 and npm (inside WSL on Windows, plus `gh` there).
  - A global npm install or `npx` from a terminal.
  - A long-lived process kept running, and a bookmarked tokenized URL.

  05's "every harness user already has Node" is about users who adopted the harness, not about every Studio user.
- **Fix.**
  - Replace the "Users" row with: "**Harness adopters** have Node. **No-local-setup team users (Issue #1) may not**: the harness supports Python, Rust, .NET, JVM and other repos. For them the local web app adds Node plus npm plus a terminal-started server, against a double-click install. That is acceptable for developers and a real barrier for non-Node teams and non-developer board users. [inferred]"
  - Add this as a flip criterion: "If no-local-setup users are a v1 audience, the local web app cannot be the sole deliverable. That audience is exactly the one a hosted web app (M8) serves with zero install."

**M4. TL;DR bullet 1, §4b "Windows/WSL" row: "No `\\wsl$` and no `wsl.exe` from Windows at all" omits the WSL idle shutdown and the start-up problem.**
- **Problem.** The networking claim itself is correct. Microsoft's networking page says that in NAT mode you can reach a Linux server "from a Windows app (like your Edge or Chrome internet browser) using `localhost`". `localhostForwarding` defaults to `true` and covers "ports bound to wildcard or localhost". It "is ignored when networkingMode=mirrored", but mirrored mode gives two-way localhost on its own. NAT is still the default. The missing part is **lifecycle**:
  - `.wslconfig` `[general] instanceIdleTimeout` defaults to **15000 ms**: "the number of milliseconds that a distro is idle, before it is shut down".
  - Community reports say systemd services do not keep the instance alive. Only processes attached to a WSL session do.
  - So something on Windows has to start the server inside WSL (a `wsl.exe` shortcut or terminal) and keep a session attached. Otherwise users must set `instanceIdleTimeout=-1`.

  A desktop shell that holds a `wsl.exe -e <core>` child gets keep-alive for free. A bare browser tab cannot.
- **Evidence.**
  - https://learn.microsoft.com/en-us/windows/wsl/networking (updated 2026-06-02).
  - https://learn.microsoft.com/en-us/windows/wsl/wsl-config (updated 2026-10-16): `localhostForwarding`, `networkingMode` default `NAT`, `instanceIdleTimeout` 15000.
  - [secondary] https://learn.microsoft.com/en-us/answers/questions/1192206/wsl2-cant-run-in-the-background-after-enabling-sys and https://guidov.github.io/2024/09/15/wsl2-keep-alive.
- **Fix.** Replace the clause with:
  > "The Windows browser reaches the WSL-hosted server on `localhost` in both NAT (default; `localhostForwarding=true`) and mirrored mode [verified, 22, wsl-config]. Starting the server still needs `wsl.exe` or a WSL terminal. WSL shuts an idle distro down after 15 s (`instanceIdleTimeout`), and systemd services reportedly don't count as activity [secondary], so the server needs an attached session or a `.wslconfig` change. A desktop shell holding a `wsl.exe` child avoids both problems."

  Add the wsl-config page to Sources. Also note in §1: the reverse direction fails in NAT mode, because a harness QA agent inside WSL cannot reach a Windows-side CDP port on `localhost`. So the "Tauri on Windows via WebView2 CDP" and "Electron CDP attach" paths do **not** work for a WSL-resident harness without mirrored mode. Correct §1's Tauri and Electron rows and the takeaway to match.

**M5. §4b "Packaging" row and §8.2: "lockstep with the `devscene` CLI … removes the contract-skew problem 05 describes" is wrong.**
- **Problem.** The skew 05 describes is between the CLI version and the **per-repo rendered bash scripts** ("The run logic is installed per repo, so its version is per repo"; `registry.json` has no schema field). Shipping Studio in lockstep with a globally installed CLI does nothing for repos rendered by older `init` versions. It also adds its own skew: the global `devscene` may differ from the version each repo pins (`DEVSCENE_CLI_VERSION` in workflows).
- **Fix.** Replace with:
  > "Releasing alongside the CLI removes app↔CLI skew only. It does not remove the CLI↔per-repo-scripts skew from 05, which still needs the `schema` field and the repo-scripts version stamp 05 asks for."

  Lower criterion 8's local-web-app score to match (see M6).

**M6. Scoring table: the ranking is not justified as presented.**
- **The weights are shown but unused.** The sum is unweighted. Applying them (high=3, med=2) gives local web app 90 vs Electron 87. Dropping criterion 8 gives 80 vs 79. The whole lead comes from criterion 1 (5 vs 4) and criterion 8.
- **Criterion 8 is self-referential.** Its sub-criteria were written in §8 to name the local web app as the winner (8.2, 8.3, 8.5). 8.2 is wrong (M5). 8.3 "remote/headless hosts" is uncited. Remote harness runs on GitHub are already read through `gh` by any delivery mode, and a hosted web app (M8) serves that case better.
- **Security is mis-scored.** The local web app gets 3, equal to Electron. But it opens a network listener reachable by every local process, by other OS users, and (on Windows) by every Windows process through localhost forwarding. Any website is a CSRF or DNS-rebinding attacker. Electron with no listener has none of this exposure. A score of 2 is more defensible.
- **The table excludes the axes where the local web app's case is decided.** Signing, distribution and auto-update are TL;DR arguments *for* it. Lifecycle, users without Node and OS hand-offs are arguments *against* it. None of them is in the table.
- **Licensing double-counts DX and contradicts the text.** Qt scores 3 although §6 says LGPL is "fine for an open-source app" and PySide6 is LGPL. Avalonia scores 4 for paid *tooling*, which criterion 7 already penalises.
- **Fix.**
  - Either apply the weights and show the weighted totals, or drop the "(high/med)" labels.
  - Remove criterion 8 from the total, or re-score it without 8.2 and 8.3.
  - Add rows for "Distribution/signing/updates" and "Lifecycle and no-setup users", or say explicitly that the table cannot rank the local web app against shells.
  - Add a **Hosted web app** column (M8). It scores high on criteria 1 (QA at a URL), 4 (shares the site's stack and domain), 5 and 7, and has its own security row.
  - Change the sentence under the table to: "The local web app and Electron are tied within noise on these criteria. The delivery-mode choice turns on security (§2, §4b), users without Node, and how much of the product must work without a local harness. This table does not settle it."

**M7. §2 "Local web app" column and §4b "Security" row: the security analysis of a process-spawning localhost server is far too thin for the owner's main concern.**
- **Problem.** 07 covers the local web app's security in one §2 table cell ("per-launch secret token, a Host-header allowlist and an Origin check … bind to `127.0.0.1` only") and one §4b row. It then scores it the same as Electron (M6). It does not analyse the attack surface, the token flow, WebSockets, WSL forwarding, or how XSS chains into process spawning. The owner names security as the main concern with this option, so this is required coverage, not polish.
- **Evidence.**
  - [verified] https://learn.microsoft.com/en-us/windows/wsl/wsl-config: `localhostForwarding` covers "ports bound to wildcard or localhost". `networkingMode=mirrored` exists.
  - [verified] https://learn.microsoft.com/en-us/windows/wsl/networking: mirrored mode benefit "Connect to WSL directly from your local area network (LAN)"; Hyper-V firewall rules govern inbound traffic.
  - [verified] https://developer.chrome.com/blog/local-network-access: Chrome 142's Local Network Access prompt gates *public-site → loopback* requests. Localhost-to-localhost is "not yet" covered, and WebSocket/WebTransport/WebRTC connections "are not yet gated".
  - [secondary] source 23 (DNS rebinding).
- **Fix.** Add a new §4b-sec subsection, "Threat model of the local server". Suggested text, which the fix agent may tighten:

  > **What the server is.** An HTTP plus WebSocket API that can create GitHub Issues, dispatch workflows, drop prompts into the inbox (which starts a headless `claude` run), pause and resume runs, and write park answers. Anyone who can call it can make the user's machine run an agent on a prompt of their choosing. Treat it as a **remote-code-execution-equivalent endpoint**: it is more privileged than an Electron preload, because it is reachable over a socket. [inferred]
  >
  > **Who can reach it.** A `127.0.0.1` bind keeps the LAN out, but not the following [inferred unless tagged]:
  > - **Other local processes of the same user.** These include any compromised npm postinstall, a browser extension, or another tool. No token design fully stops same-user malware: it can read the token file. Accept this as residual risk, as every desktop app does.
  > - **Other OS users on the same host** (shared Linux boxes, multi-user Macs). TCP loopback has no per-user ACL, so the token is the only barrier. Store it in a `0600` file under `$XDG_STATE_HOME`/`~/Library/Application Support`, never in argv or environment variables visible in `ps`.
  > - **On Windows, the whole Windows side.** With `localhostForwarding=true` (the default) any Windows process, and any other signed-in Windows user, reaches the WSL server on `localhost:PORT` [verified, wsl-config]. All WSL2 distros share one VM network, so other distros (for example Docker Desktop's) reach it too [secondary].
  > - **Mirrored mode can expose it to the LAN.** In mirrored mode WSL shares Windows' interfaces, and Microsoft lists "connect to WSL directly from your LAN" as a feature. A server bound to `0.0.0.0` (a common mistake, and the docs' own Flask example) is then reachable from the LAN wherever the Hyper-V firewall allows inbound traffic [verified, networking]. **Rule: bind `127.0.0.1` only, refuse to start on any other address, and check this in a test.**
  > - **Any web page the user visits**, through CSRF, DNS rebinding and cross-site WebSocket hijacking (below).
  >
  > **Required controls** [inferred, standard practice]:
  > 1. **Host-header allowlist** (`127.0.0.1:PORT`, `localhost:PORT`), with exact match. This defeats DNS rebinding, where `evil.com` re-resolves to `127.0.0.1` and becomes same-origin with the server.
  > 2. **Origin check on every state-changing request and on every WebSocket upgrade.** WebSocket handshakes are not subject to CORS, and Chrome's Local Network Access does not yet gate WebSockets [verified, chrome LNA]. Reject a missing or `null` Origin on writes. Send no `Access-Control-Allow-Origin` header.
  > 3. **A per-install secret of 128 bits or more** that every API call must present in a **custom header** (`X-Studio-Token`). A custom header forces a CORS preflight that the server refuses, so a plain cross-site form POST cannot carry it. Put the token in the launch URL's **fragment** (`#t=…`), not the query string, so it stays out of server logs, history sync and `Referer`. Have the page exchange it once for an `HttpOnly; SameSite=Strict` cookie scoped to the port. This also fixes the PWA `start_url` problem (S7). On Windows, the server inside WSL opens the browser with the token through `wslview`/`explorer.exe` interop or prints the URL.
  > 4. **Local Network Access is a bonus, not a control.** Chrome 142+ prompts before a public site can reach loopback. It does not cover Firefox or Safari, WebSockets, or localhost-to-localhost requests [verified, chrome LNA].
  >
  > **The process-spawning layer.** This is the same rule as Electron's IPC, with less margin for error because the layer is network-reachable:
  > - Expose **intent-level endpoints only**: `POST /runs/{branch}/pause`, never `/exec`.
  > - Spawn with argv arrays, never a shell. Put `--` before every user-supplied ref. Validate branch names with `git check-ref-format` and repo paths against the detected-repo list.
  > - Require an explicit UI confirmation for run-starting and inbox-drop actions, and enforce it server-side with a short-lived per-action nonce.
  > - Rate-limit act endpoints, and append every act to an audit log.
  > - Never return environment variables, tokens or file contents outside the run directories.
  >
  > **XSS from GitHub content and logs.** Issue bodies, PR comments, clarification files and `run.log` lines (which echo model and tool output) are attacker-controlled. In the local web app, an XSS runs *in the server's own origin*, with the session cookie, so **XSS equals full API access equals process spawning**. Host, Origin and token checks do not help, because the request is same-origin. The required defences are:
  > - Render markdown with an allowlist sanitizer (DOMPurify) and no raw HTML.
  > - Render log tails as text nodes, with a safe ANSI parser.
  > - Set a strict CSP (`default-src 'self'; script-src 'self'`, no inline script, `connect-src 'self'`) and use Trusted Types where supported.
  > - Allow only `https:` URLs in links, with `rel="noopener noreferrer"`.
  > - Add a CI test that renders a payload corpus (script tags, `javascript:` links, SVG `onload`, ANSI and OSC-8 hyperlinks).
  >
  > **Net assessment.** With these controls the local web app can be about as safe as Electron. Without them it is clearly worse, and the controls are easy to get subtly wrong: Host checks with ports, WebSocket origins, token leaks through the query string. Score security 2 by default, or 3 only if CI carries the rebinding, CSRF, WebSocket-hijack and XSS tests (Risk 4). Electron and Tauri have no listener, so only the XSS chain applies to them.

  Also expand Risk 4 into a named CI test list: Host `evil.com:PORT`, cross-origin POST, cross-origin WebSocket upgrade, `Origin: null`, token in query rejected, bind address equal to `127.0.0.1`, and the XSS payload corpus.

**M8. Missing coverage: 07 does not assess a hosted, deployed web app (not on localhost) as a delivery mode.**
- **Problem.** 07 compares desktop bundles with a local web app and stops there. A hosted web app at an https URL, with GitHub sign-in, is a credible fourth mode. Issue #1 makes remote the repo default and makes `gh`/GitHub the primary data source, specifically for users with no local setup. It also plans a product web site that lists all products. The owner neither favours nor rejects this mode, but the comparison is incomplete without it.
- **Evidence.**
  - [verified] https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps: "In general, GitHub Apps are preferred over OAuth apps"; GitHub Apps have targeted permissions and access chosen repositories; an OAuth app has access to all of the user's accessible resources, and issue/PR access needs the broad `repo` scope.
  - [verified] https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens: user access tokens expire after 8 hours; refresh tokens last 6 months; expiry is on by default.
  - The harness's own skills show remote runs can be paused, resumed and answered by "a pause dispatch sent straight to GitHub" and by sending "the answers as the resume dispatch itself" (`devscene:branch-pause`, `devscene:branch-answer` skill descriptions).
- **Fix.** Add a §4c, "Hosted web app", and a §4d comparison of the four modes. Suggested text:

  > **4c. Hosted web app (e.g. `studio.<product-domain>`).**
  >
  > **Sign-in and tokens.**
  > - Use a **GitHub App**, not an OAuth App. A GitHub App gets fine-grained permissions (Issues RW, Pull requests R, Actions RW for dispatch, Contents R for committed analytics, Metadata R). It is installed on the repos the user chooses, and its user tokens expire after 8 hours, with 6-month refresh tokens [verified]. An OAuth App would need the `repo` scope, which grants access to all of the user's private repos [verified].
  > - The token exchange needs the app's client secret, so some server-side component is required. There are two storage models:
  >   - (a) **No server-side token store.** A thin backend-for-frontend does the exchange and keeps the tokens in an encrypted, `HttpOnly`, `SameSite=Lax` session cookie. A server breach then exposes only in-flight sessions.
  >   - (b) **A server-side encrypted token store.** This is needed only for background work such as notifications or polling. It makes the service a high-value target that holds write access to many users' repos.
  >   Prefer (a). [inferred]
  > - Org-owned repos need an org admin to approve the GitHub App installation. That is friction for team adoption, but it is also an audit trail.
  >
  > **Multi-tenant isolation.**
  > - Every GitHub call uses the *requesting user's* token, never an installation token shared across users.
  > - Any cache is keyed by user and repo, and private-repo data is never served from a shared cache.
  > - No cross-tenant aggregation.
  > - XSS from issue text acts with the user's GitHub permissions (it could create issues or dispatch workflows), but it cannot spawn local processes. The same CSP and sanitizer rules from §4b-sec apply.
  > - The operator (the owner) becomes a processor of private-repo data, which brings a privacy policy and data-handling obligations, including GDPR for EU users. [inferred]
  >
  > **Cost.**
  > - A static SPA plus a small serverless function for the token exchange and the artifact proxy.
  > - Typically within the free or hobby tiers of mainstream serverless hosts at small scale, plus the domain the product site needs anyway.
  > - No signing certificates and no notarization. [inferred: re-check the chosen host's pricing]
  > - GitHub's per-user rate limit applies per signed-in user.
  >
  > **What it can do with GitHub data only.**
  > - The To Do column, from Issues.
  > - Start remote runs through the Issue trigger.
  > - In Progress and Done, from Actions runs titled `harness run <branch>`, `devscene:` labels, progress comments and PR merge state.
  > - Session detail, from `status.json`, `run.log` and clarification files in the `harness-state` artifact. Artifact zips redirect to blob storage, so a backend proxy is likely needed [inferred].
  > - Analytics, from the committed `run_analytics/`/`branch_statistics/`.
  > - Pause, resume and answer **remote** runs by dispatch.
  > - Detect repos carrying the harness workflows.
  >
  > This covers Issue #1's remote-default flow and its no-local-setup users completely, with zero install on every OS, Windows included, with no WSL.
  >
  > **What it cannot reach without a local agent.** The local `registry.json`, local logs, the autonomous inbox (starting **local** runs), watcher and daemon status and `daemon install`, `devscene doctor`, WSL, and folder-based repo detection.
  >
  > **Resulting shapes.**
  > - **(i) Remote-only scope.** Hosted, local runs out of scope. This is the simplest and safest shape.
  > - **(ii) Hybrid.** A hosted UI plus an optional local connector, which is the §4b Node server running in API-only mode.
  >   - It reintroduces every §4b-sec issue.
  >   - Worse, the connector must now accept cross-origin calls from the hosted origin (a CORS allowlist), so an **XSS on the hosted site becomes a path to local process spawning on every connected machine**.
  >   - It triggers Chrome's Local Network Access prompt (public origin → loopback) [verified].
  >   - Its behaviour in Safari and Firefox needs a spike.
  >   - If chosen, act verbs on the connector should require a local confirmation (a pairing code, or a native notification), not just a token sent by the hosted page.
  > - **(iii) Desktop or local app for local runs, hosted app for remote runs.** The same web UI in both.
  >
  > **Fit with the product web site.** It can share the site's stack, design system and domain (§4a), with one sign-in across sibling products. Serve it from a **separate subdomain** from the marketing site, so that cookies and any XSS stay isolated from site content. Donations and "download" links sit next to it naturally.

  Add a **§4d table** with the four modes as columns: desktop shell, local web app, hosted (remote-only), and hosted plus connector. Give it these rows:
  - Install friction (Node / none / download).
  - Signing cost.
  - Auto-update.
  - Attack surface: listener, multi-tenant store, XSS reach.
  - Local runs.
  - Remote runs.
  - Windows/WSL lifecycle.
  - Agent QA.
  - Offline use.
  - Data-processor obligations.

  Add flip criteria:
  - "If local runs are not a v1 requirement, a hosted remote-only app removes signing, WSL and Node-install friction entirely."
  - "If they are, the hybrid connector carries the highest security burden of all modes."

## Should fix

**S1. TL;DR bullet 3 and §2 table: the WebKitGTK advisory count is stale.** The file says 5 advisories (WSA-2026-0001…0005). WebKitGTK has since published **WSA-2026-0006 (2026-09-29)**, so 2026 has 6 so far. The current stable is 2.54.2 (2026-10-23). Evidence: https://webkitgtk.org/security.html. Fix: change "5 advisories … (WSA-2026-0001…0005)" to "6 advisories so far in 2026 (WSA-2026-0001…0006, latest 2026-09-29)" in TL;DR bullet 3 and §2. Update source 16.

**S2. §2 table "Supply chain", crates.io row: "compromised through a build-time proc-macro typosquat … about 1.5 h window" misstates the mechanism.**
- **Problem.** The Rust blog describes a likely **compromised maintainer account or machine**. `arrayref` was republished to depend on the malicious crate `proc-macro1`, whose **build script** downloaded a payload. The blog does not call it a typosquat.
- **Scope and windows.** Three legitimate crates were affected (`arrayref@0.3.10`, `internment@0.8.7`, `append-only-vec@0.1.9`). Their versions were live for 86, 90 and 107 minutes respectively.
- **Evidence.** https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/
- **Fix.** "crates.io: on 2026-08-20 `arrayref`, `internment` and `append-only-vec` were republished from a likely compromised account to depend on `proc-macro1`, whose build script fetched a payload. Each bad version was live for 86–107 min [verified, 15]."

**S3. §1 Avalonia/DX rows, §6, §7: "Avalonia (paid hot reload and devtools)" and "DevTools paid tier" are partly wrong.** Avalonia's hot-reload page says Hot Reload "has no free Community edition, unlike DevTools, Parcel, and the IDE extensions". So DevTools *has* a free Community edition. Hot Reload is only in Plus and above. Evidence: https://avaloniaui.net/hot-reload. Fix: "Avalonia's official Hot Reload is paid (Plus and above; HotAvalonia is a free MIT alternative). DevTools has a free Community edition."

**S4. §1 "Native ×3" row and Risk 6: WinAppDriver's status can be verified from the primary source.** The GitHub API gives:
- Last stable release: `v1.2.1`, 2020-11-05.
- Last pre-release: `v1.2.99` (1.3 RC1), **2021-07-01**.
- The repo is not archived; its last push was 2025-04-14.

Evidence: `gh api repos/microsoft/WinAppDriver/releases`. Fix: "WinAppDriver: last stable release 2020-11-05, last pre-release 2021-07 (1.3 RC1). Effectively unmaintained [verified]". Downgrade Risk 6 to cover only NovaWindows.

**S5. §3 Qt row: the citation does not support the claim.** The Qt 6 row cites "[secondary, 18]", but the Ubuntu accessibility-stack page (source 18) does not mention Qt. It mentions only GTK3/GTK4 and says other toolkits "must ensure it implements the AT-SPI D-Bus interfaces". Fix: cite Qt's own accessibility docs (https://doc.qt.io/qt-6/accessible.html), or mark the row [inferred]. Also, the Ubuntu doc's wording is "Flutter engine has compatibility issues with AT-SPI", which supports the Flutter row as [verified].

**S6. TL;DR bullet 6 and §5: "It has none for Tauri, Wails or Avalonia" overstates the gap, and the Observability scores follow from that.** Sentry has first-party **Rust**, **Go**, **.NET** and **JavaScript** SDKs. What is missing is a framework-specific *integration guide* for Tauri, Wails and Avalonia, not an SDK. Avalonia, which is in the same position, scores 3, but Tauri and Wails score 2. Evidence: https://docs.sentry.io/platforms/ lists .NET, Go, Rust, JavaScript and Native, with no Tauri, Wails or Avalonia guide. Fix: "No framework-specific guide for Tauri, Wails or Avalonia. Each wires the official language SDKs (Rust plus JS, Go plus JS, .NET) by hand." Score Tauri, Wails and Avalonia consistently (all 3, or all 2).

**S7. TL;DR bullet 1 and §4b "Tray" row: the PWA claim needs browser-by-browser precision.**
- **What MDN confirms.** Installable PWAs may be served "from a local development environment using `localhost` or `127.0.0.1` — with or without a port number". A service worker is not required. On macOS Sonoma and later, "Safari supports Add to Dock … for any web app with or without a manifest file". "Firefox does not support installing PWAs using a manifest file."
- **Gaps.** MDN does not test Safari's Add to Dock on `http://localhost`. On Linux, users whose default browser is Firefox get no install path.
- **Separate design problem.** A `?token=…` in the URL conflicts with the manifest `start_url` and with Safari web apps' separate website-data store. The token has to move to a cookie or be re-entered.
- **Evidence.** https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
- **Fix.** "Chrome and Edge install from `http://localhost`/`127.0.0.1` [verified, 24]. Safari 17+ Add to Dock works for any web page [verified, 24], but is untested on localhost. Firefox desktop cannot install PWAs. The auth token must survive install (cookie, not query string)." Keep Risk 3, but narrow it to Safari-on-localhost.

**S8. §2 "Practical controls" and TL;DR bullet 3 vs bullet 1: the security section and the distribution choice point in opposite directions.**
- **Problem.** 07 calls npm "the largest surface" (Mini Shai-Hulud stole publish tokens to push malicious versions). The headline then makes npm the app's own distribution channel ("Updates come through npm"). It also needs the user to `npm i -g` a package with install-time scripts in its dependency tree.
- **Fix.** Add one line to §4b "Security": "Distributing via npm puts Studio itself in the npm blast radius. Publish with trusted publishing and provenance, ship with zero install scripts, and pin a minimal dependency set." Also note that `npm i -g` packages don't auto-update. Issue #1 item 17 requires auto-update, so the server would need an "update available" notice.

**S9. §4b and §8: hand-offs the browser cannot do are missing from the comparison.** Issue #1 needs these:
- Item 8: a "point to a folder" fallback. A browser file picker gives no absolute path, so the server must render its own directory browser.
- Item 10: a possible "hand-off to the terminal" for harness-analyze.
- Item 15: `devscene daemon install` in a privileged context.

A desktop shell has native dialogs and `shell.openPath`/terminal launch. A local web app inside WSL can only reach Windows through interop executables (`wt.exe`, `explorer.exe`). Fix: add a §4b row, "OS hand-offs (folder picker, open terminal/editor)", with Desktop "native" and Local web app "server-side reimplementation; WSL interop on Windows". Add the same item to §8.

**S10. §1 table and takeaway: the Electron/Tauri CDP rows need the WSL caveat and a security caveat.**
- **Electron CDP is a test-build-only path.** Playwright notes that Electron launch needs the `nodeCliInspect` fuse not set to `false`. A shipped build that leaves `--remote-debugging-port` reachable lets any local process drive the privileged app. Evidence: https://playwright.dev/docs/api/class-electron.
- **The harness cannot reach these ports on Windows.** The harness runs only inside WSL (05). A Windows-side Electron or WebView2 CDP port bound to `127.0.0.1` is not reachable from WSL in NAT mode (wsl-config / networking pages above).
- **Fix.** "CDP attach (Electron everywhere, Tauri on Windows) is for debug/test builds only. On Windows it needs mirrored networking for a WSL-resident harness to connect."

**S11. §7 "Harness tie-in": "Only the local web app and Electron … can also be QA-driven there" contradicts 03 and the §1 table.** 03 makes a mocked browser mode a v1 requirement. In that mode Tauri and Wails UIs *are* QA-driven by the harness on a Linux runner. Electron's real shell on a headless runner also needs Xvfb. Fix: "Every web-tech option can be QA-driven on the Linux runners in browser mode (03). The local web app and Electron (with Xvfb) can also be driven unmocked."

**S12. §6: the US$600–900/yr open-source saving needs to show its arithmetic, and its parts are stack-dependent.** Live figures:

| Item | Annual cost | Notes |
|---|---|---|
| Sentry Team | ~$312/yr ($26/mo annual) | The free Developer tier, 5k errors/month and 1 user, likely suffices for a small app, so this is not a real saving |
| Conveyor Standard | $540/yr ($45/mo) | Only if Compose is chosen |
| OV certificate | $300–500/yr | Per 04 |
| Azure Artifact Signing | ~$120/yr | Alternative to OV, where eligible |
| macOS runner minutes | — | 06 gives private-repo rates |

So the saving is about $420–810 for Electron/Tauri (OV or Azure, plus Sentry Team if needed) and about $960–1,350 with Conveyor. For the local web app it is about $0–312, because there is nothing to sign.

Evidence: https://sentry.io/pricing/ and https://hydraulic.dev/pricing.html. Fix: replace "about US$600–900/yr" with a small table per stack, mark it [inferred], and cite the prices.

**S13. TL;DR bullet 1: "The 04 'long-lived helper inside WSL' and the 05 JSON contract both become this server" conflates layers.** 05's contract is a harness CLI verb (`devscene runs … --json`) that lives in the harness repo. The server would be a *client* of it, as §4b's own verdict correctly says ("the 05 contract client"). Fix: "…the 04 WSL helper and the 05 contract *client* become this server."

**S14. §2 `gh` token: the claim can now be [verified], and "silently" is unsupported.** The `gh auth login` manual says the token goes to "the system credential store", and that gh falls back to a plain-text file when "a credential store is not found or there is an issue using it". `--insecure-storage` forces plain text. Evidence: https://cli.github.com/manual/gh_auth_login. Fix: cite the manual as [verified]. Drop "silently" unless it is checked, because gh may print a notice. Keep the WSL note, which matters: most WSL distros have no Secret Service, so plaintext is the norm there.

## Nice to have

**N1. §2 Supply chain, Mini Shai-Hulud figures.** The wave counts vary widely between sources:
- About 170 packages / 400+ versions (mid-May).
- 1,055 versions / 502 packages (a later Socket/Endor tally).
- More than 2,200 components (Sonatype, which also dates a wave to 2026-08-04).

Give a range and cite Sonatype (https://www.sonatype.com/blog/mini-shai-hulud-npm-attack-more-than-2200-components-impacted) alongside CSA, rather than single figures. The tag [secondary] is correct.

**N2. §4a.** The Flutter FAQ itself recommends **Jaspr** (Dart, DOM-based, SEO-friendly) for sites, and notes that flutter.dev and dart.dev migrated to it. That weakens "never with the website" slightly for Flutter: the language is shared, but the components are not. One line would keep the argument honest. Source: https://docs.flutter.dev/platform-integration/web/faq.

**N3. §1 Dart MCP row.** The README does not state desktop support. `launch_app` is disabled by default and must be enabled via the `flutter` or `flutter_app_lifecycle` category. Add "desktop support not documented". Source: https://github.com/dart-lang/ai/tree/main/pkgs/dart_mcp_server.

**N4. Source 30.** 06 verified GitHub's runner pricing live: public repos are free, and private repos get a dollar allowance. Cross-reference 06 instead of the [secondary] tag.

**N5. Consistency with 01–06.** The TL;DR should state in one line how 07 relates to the other areas:
- 01 shortlists Electron, Tauri and Wails.
- 03 recommends Tauri or Electron, with a browser mode as a v1 requirement.
- 05 recommends the `wsl.exe` stdio transport.
- 06 recommends (B).

07's web-first architecture is compatible with all of them: it is 03's browser mode made first-class, served over HTTP rather than mocked. Only "local web app as the sole deliverable" conflicts with them. Saying this lets the synthesis reconcile the files rather than pick between them. A localhost-HTTP transport from a Windows shell to a core inside WSL is also a real alternative to 05's stdio-over-`wsl.exe`, and could be flagged for 04/05.

**N6. Risk 1.** Make the 30-minute CDP spike also test a harness running inside WSL against a Windows-side Electron (see M4/S10). That is the configuration that matters on Windows.

## Review resolution

Resolved 2026-11-12 by the fix agent. Factual corrections were re-verified live (wsl-config, WSL networking, Chrome LNA, webkitgtk.org/security.html, the Rust arrayref post, avaloniaui.net/hot-reload, gh auth login manual, Sentry pricing and platforms, MDN PWA page, Flutter web FAQ, Dart MCP README, Playwright Electron page, GitHub Apps docs, Sonatype, Qt accessibility page) or against `/Users/daniel/Work/devscene` (`docs/cli.md` §9, `cli/src/daemon/backend.ts`, `cli/src/detect/presets.ts`) and `gh api repos/microsoft/WinAppDriver/releases`. Every check matched the review; nothing was rejected.

| ID | Resolution |
|---|---|
| M1 | Applied. TL;DR and §4 now separate "web-first UI architecture (well supported)" from "delivery-mode choice (owner's)": desktop shell, local web app, hosted (remote-only), hosted + connector, and combinations. |
| M2 | Applied. §4b Lifecycle row and §8.6 now say the daemon is per repo and cannot host the server; options listed; systemd "instructed" noted. |
| M3 | Applied. §4b Users row rewritten (non-Node presets verified in `presets.ts`); no-local-setup flip criterion added to §4d. |
| M4 | Applied. §4b Windows/WSL row covers `localhostForwarding`, mirrored mode and the 15 s `instanceIdleTimeout` (verified); systemd keep-alive kept [secondary]. §1 Electron/Tauri/Wails rows and takeaway note the NAT reverse-direction problem; wsl-config added as source 42. |
| M5 | Applied. §4b Packaging row and §8.2 now say only app↔CLI skew is removed; CLI↔per-repo-scripts skew remains. |
| M6 | Applied. Weights applied (high 3, med 2, low 1; /115). Criterion 8 redefined as low-weight 8.4/8.5/8.7 only (8.1 counted in security; 8.2, 8.3 dropped). Rows added for distribution/signing/updates and install/lifecycle/no-setup/operations. Hosted (remote-only) and Hosted + connector columns added. Security: local web app 2, hybrid 1, hosted 3. Licensing: Qt 4, Avalonia 5. Results: hosted 103, Electron 99, local web app 92, hybrid 86, Tauri 84. Sentence under the table states the table does not settle the delivery mode; gates for local runs and tray added. |
| M7 | Partially applied. Per owner guidance (08 will go deep), the review's long threat model was condensed into §2a: a threat-summary table per delivery mode (privileged surface, who can reach it, XSS reach, obligations, relative burden) plus the required controls (bind, Host allowlist, Origin incl. WebSocket, fragment token → cookie, nonces, rate limits, audit log, sanitizer/CSP/Trusted Types, argv spawning) and the CI test list. Narrative detail (e.g. per-attacker prose) is left for 08. |
| M8 | Applied, concisely. §4c (GitHub App vs OAuth App, token storage, cost, GitHub-only reach, what it cannot reach, resulting shapes, subdomain) and §4d (four-mode table with all requested rows plus tray and OS hand-offs; flip criteria). Multi-tenant isolation rules moved into §2a. |
| S1 | Applied (6 advisories, latest 2026-09-29, stable 2.54.2; source 16 updated). |
| S2 | Applied (likely compromised account, `proc-macro1` build script, 86–107 min). |
| S3 | Applied (§6, §7, TL;DR: official Hot Reload paid; DevTools free Community edition). |
| S4 | Applied (dates verified via `gh api`; source 51); Risk 6 narrowed to NovaWindows (now Risk 8). |
| S5 | Applied. Qt's page only says it uses platform-specific APIs, so the Qt row cites it (source 50) and marks AT-SPI [inferred]; Flutter row quotes Ubuntu and stays [verified]. |
| S6 | Applied. TL;DR and §5 reworded; Tauri, Wails and Avalonia all score 3. |
| S7 | Applied. Browser-by-browser PWA text; token moves to fragment → cookie; Risk 3 narrowed to Safari on localhost. |
| S8 | Applied. npm blast-radius line in §4b Security row; no-auto-update note in Packaging row; npm-as-channel noted in §2 table. |
| S9 | Applied. §4b "OS hand-offs" row, §8.8, and a §4d row. |
| S10 | Applied. §1 rows: CDP is debug/test builds only; `nodeCliInspect` fuse noted; mirrored networking needed for a WSL harness. |
| S11 | Applied. §7 Harness tie-in and §1 takeaway rewritten. |
| S12 | Applied. §6 has a cost table with prices verified (Sentry Team $26/mo annual, Developer free 5k/1 user; Conveyor $45/mo) and per-stack savings. |
| S13 | Applied ("05 contract client"). |
| S14 | Applied. Cited the gh manual as [verified, 46]; "silently" dropped; WSL plaintext note kept. |
| N1 | Applied (range of tallies; Sonatype added as source 49). |
| N2 | Applied (§4a Jaspr line; verified). |
| N3 | Applied (§1 Dart MCP row; verified). |
| N4 | Applied (source 30 and §6 cross-reference 06). |
| N5 | Applied (TL;DR bullet on relation to 01–06, incl. localhost-HTTP transport note for 04/05). |
| N6 | Applied (Risk 1 now includes the WSL-harness → Windows-Electron case, NAT and mirrored). |
