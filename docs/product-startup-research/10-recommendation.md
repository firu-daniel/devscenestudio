# 10 — Recommendation: framework, delivery mode and repo topology
> Status: reviewed · Date: 2026-11-12 · Area owner: synthesis agent · Review: [`reviews/10-recommendation.md`](reviews/10-recommendation.md)

This is the decision document for Issue #1 item 1 ("Product startup") and item 16 ("Licensing check"). It synthesises the nine reviewed area files, 01–09, and the review resolutions in `reviews/`. For the harness follow-ups (§8) it also maps them onto devscene issue #170; the security items not covered there are filed as devscene #344–#356. "See 04 §2" means section 2 of `04-os-integration-blockers.md`. Owner-days (O-d) are 03's unit: owner review, steering, testing and release time, with agent wall-clock time treated as free. Every O-d figure is an estimate, not a measurement.

The Issue's "Decisions taken" are treated as discussion points, not constraints. Where the research contradicts one, this file says so (§2, §9).

## TL;DR

- **Framework (default): Electron, with a TypeScript web UI and a TypeScript main process.** Tauri 2 is the close alternative. The spike (§5) validates the pick against measured flip conditions; it does not choose it. The decision rests on the evidence criteria, with security first:
  - **Security, the owner's main concern, is even once Electron's cadence is kept.** 08 §6.1 rates Electron "equal if the release cadence is kept": ship each upstream security release within 14 days (≈ 1.6 O-d/yr of Chromium bumps) and add a Linux update-signature hook. Tauri has a modest structural edge (a mandatory signed updater, a capabilities ACL, OS-patched webviews on macOS/Windows), but on Linux its webview is only as patched as the distro's WebKitGTK: 6 advisories in 2026, LTS distros lag upstream, and Trusted Types may be missing below 2.50 (07 TL;DR, 08 Risk 7). Electron's condition is under the owner's control; Tauri's Linux lag is not.
  - **Every other evidence criterion favours Electron:** consistent Linux rendering with bundled Chromium (04 §4); the widest updater coverage (AppImage, deb, rpm, pacman; 04 §8); the largest agent corpus and real-shell CDP QA in test builds (03 §3, 07 §1); a foundation-backed line with a published support policy and no pending migration, against Tauri's likely v2→v3 migration in 2027 (01 §3); Node-only DX with builds in seconds, against cold Rust builds of 3–8 min (07 §7); and ≈ 2 O-d less v1 effort (03 §6, 08 §4.2). 01 and 07 rank it first. Only download size and idle RAM favour Tauri, and 02 finds them not user-visible for this app apart from the download.

  **Flip to Tauri** if the owner cannot commit to Electron's release cadence, if the spike cannot close the Linux update-signature gap, or if download size or idle RAM becomes a product requirement (§1.2). Career value does not decide anything here: 03 rates the two equal, and Tauri's extra Rust exposure is a minor plus at most.
- **Delivery mode: a desktop shell for v1, with a web-first UI.** Build the UI as a web app behind an intent-level IPC interface, with a **browser mode** (IPC mocked or served from fixtures) so the harness's `web-playwright` QA agent can drive it on Linux runners (03 §2, 07 §1). A hosted remote-only web app is a later, optional add-on (07 §4c, 08 §6.1). A local web app is acceptable only as an opt-in developer mode. **No hosted UI + local connector** (08 §2f).
- **Repo topology: one cross-platform project (06 shape B).** Layers: `app/` (web UI, the renderer), `app/main/` (TS main process and preload: process transport, `gh` read-model, file watching, OS overrides as `process.platform` branches), `contract/` (types generated from the harness's JSON Schema), plus `general`. One version for all three OSes. Linux typecheck and tests on every PR, 3-OS signed builds on release tags (06 §3).
- **Native per platform is not worth it, even with agents.** It costs about 2.1–2.2× the owner's time for v1 and about 2.7× per later feature (03 §1). More decisively, the harness cannot build or test WinUI 3 in any run mode, can build SwiftUI only in a local Mac run, and has no native QA driver. Closing that gap would cost 48–82 O-d of harness work (06 §2.6).
- **The integration contract matters more than the framework.** No stack can import the harness's run logic: it is about 22,500 lines of per-repo bash (05 §1). Every stack calls a versioned `devscene runs … --json` contract (Issue item 7), directly on macOS/Linux and through `wsl.exe --exec` on Windows, with one long-lived `runs watch` stream inside WSL (05 §4, 04 §2). The Issue's premises that "Electron can reuse the CLI code directly" and "Tauri needs a Node sidecar" are both disproved (05 §3).
- **Security bar for v1 (§6):** a sanitiser pipeline with Trusted Types and a strict CSP, intent-only IPC, one argv builder, an OS-native confirmation modal for every start, answer and resume, a repo-trust gate, display-time secret masking, signed updates with key custody, and three CI security suites (for the desktop shell: an XSS corpus, an argv fuzz and a hostile-repo fixture). Estimated at about 5.5 O-d for Electron (6.0 for Tauri) (08 §4.2). **Harness findings H1 and H1′ (08 §5.2) block the answer and resume features** until they are fixed, or until 08 Risk 1's runtime measurement shows every write refused (they then drop to Info).
- **Anthropic terms: the design is within them** (09). The rule is "spawn the user's own unmodified `claude`; never touch credentials, never bundle Claude Code, never put Claude or Anthropic in a product name." Three narrow questions remain (09 "Open questions"). In each, the worst case is a change of credential type or plan, not a ban. Send the drafted email (09 "Draft email to Anthropic").
- **Money:** about US$99/yr if the app is open source (Apple Developer Program, with free Windows signing via SignPath and free public CI). About US$220–600/yr otherwise (up to ≈ 900 with Sentry Team), because a closed app needs Artifact Signing (≈ 120, if eligible) or an OV certificate (≈ 300–500) (§7). **Owner time:** about 7–8 O-d for the spike, then about 32.5 O-d for v1 on Electron (23–42 at ±30%), including security. About 4 O-d of the spike carries into v1 [inferred], so spike plus v1 is ≈ 36 O-d (§7). Harness-side contract work comes on top and is sized in the harness repo.
- **Owner decisions needed now (§4):** *answered on 2026-11-24, see §4.0; the list below is kept as originally written.*
  - the framework (D1: Electron, which commits you to its 14-day security-release cadence; Tauri only if you cannot commit to that);
  - the open-source licence;
  - the Windows signing route (which depends on your country and legal entity);
  - whether v1 ships answer/resume (gated on harness H1/H1′);
  - the commitment to build the harness contract first, with pause, local start and a global stop in the phase Studio v1 depends on (D6).

  Enrol in the Apple Developer Program now: notarization onboarding has stalled for weeks to months in 2026 (04 §6).

## Scope

This file covers the recommendation (framework, delivery mode, repo topology) and its reasoning chain; direct answers to the owner's questions; where the area files disagree and how that is resolved; the owner's decisions; a validation spike; the v1 minimum security bar; a cost summary; consolidated harness follow-ups; suggested updates to Issue #1; and what remains unverified.

It adds no new primary research. Facts come from 01–09 as reviewed, and from a read-only mapping onto devscene #170 for §8, with one exception: the state-label prefix was checked in the harness source (`cli/src/remote/githubActions.ts:136`, `STATE_LABEL_PREFIX = 'devscene: '`) to resolve a naming conflict (§2 row 9).

## Findings

### 1. The recommendation and its reasoning chain

#### 1.1 Why cross-platform, and why a webview stack

1. **The app is small and process- and file-bound.** Runtime performance does not separate the candidates. Time to a populated board is about 1 s in every stack, dominated by `gh` network calls (02 §4). Only download size (02 §9), the JVM's start without AOT (02 §8) and Linux WebKitGTK rendering (02 §6) are user-visible.
2. **Native ×3 costs 2.1–2.2× for v1 and about 2.7× per feature** (03 §1). The harness, which is the owner's agent workflow, cannot verify two of the three native codebases (03 §2, 06 §2.4). Every native-topology run on one OS parks at Run gates (06 §2.2). Security does not justify native either: a hardened webview shell gets close to native residual risk for about the same total effort (08 §4.4).
3. **Among cross-platform stacks, a web UI wins on the criteria the harness can measure:**
   - the harness's only implemented QA driver is `web-playwright`, so only a web UI is agent-QA-able today (03 §2, 07 §1);
   - one design system can span the product website, Studio and the sibling products (07 §4a);
   - TS has the largest agent corpus (03 §3).

   Flutter, Compose, Avalonia and Qt are viable but each lacks harness QA, and each has its own gaps: Compose has no AppImage, no first-party updater, no Linux accessibility and no Kotlin/Native desktop UI (02 §8, 04 §10, 07 §3); Flutter's desktop updater is stale and its Linux AT-SPI support is weak (04 §8, 07 §3). See 01's ranked shortlist.
4. **Among webview shells, Electron and Tauri 2 are the finalists.** Wails 3 has the same WebKitGTK exposure as Tauri, a stable line about two weeks old, a young updater, a GTK3 path announced for removal, and agents trained mostly on v2 (01 §3, 03 §3, 04 §4). Revisit it in 2027 if Go is preferred over Rust. Electrobun and Deno Desktop are too young (01 §2, 02 §3).

#### 1.2 Electron vs Tauri 2: the criteria that decide it

| Criterion | Weight for this owner | Electron | Tauri 2 | Source |
|---|---|---|---|---|
| Security, residual risk after MUSTs | **High** (stated main concern) | Low–medium as shipped: bundled Chromium you must ship within 14 days of each security release; Linux updates checked by sha512 only. 08 §6.1: "**equal if the release cadence is kept**" (≈ 0.25 O-d per bump, ≈ 1.6 O-d/yr), plus a Linux signature `verify` hook (08 §3.6) | **Low**: OS-patched WebView2/WKWebView, mandatory signed updater, capabilities ACL, isolation pattern. **But on Linux** WebKitGTK is patched only as fast as the distro ships it: 6 advisories so far in 2026, LTS distros lag upstream, and Trusted Types may be missing below webkit2gtk-4.1 2.50 | 08 §2a, §2b, §4.2, §4.4, §6.1, Risk 7; 07 TL;DR |
| Developer experience | Medium (07 weights it high, ×3) | **Node only; builds in seconds** (07 score 5) | Node + Rust + platform dev packages on every contributor machine; **cold Rust builds 3–8 min**, Rust edits recompile (07 score 3) | 07 §7, Scoring |
| Linux rendering consistency | Medium | **Bundled Chromium, consistent** | WebKitGTK: blank-window, flicker and Wayland "Error 71" class bugs, NVIDIA workarounds | 04 §4, 02 §6 |
| Linux auto-update coverage | Medium | **AppImage, deb, rpm, pacman** (but sha512-only) | AppImage only (deb users via the package manager); signature mandatory | 04 §8, 08 §3.6 |
| Line stability | Medium | **No pending migration**; 8-week major cadence | v3 in alpha; a v2→v3 migration likely in 2027 | 01 §3 |
| Agent effectiveness | Medium | **Largest corpus, stable APIs** | v1/v2 API confusion; a third generation coming | 03 §3 |
| Harness gates on Linux runners | Medium | **Nothing extra** | WebKitGTK dev packages via `depInstall`; `~/.cargo` under the sandbox untested | 06 §2.4, 06 Risks |
| Real-shell agent QA (beyond browser mode) | Low (browser mode is required anyway) | **CDP in test builds, all OSes** | WebDriver on Windows/Linux; macOS via a third-party plugin or a paid fork | 07 §1 |
| Bundle size and idle RAM | Low | ≈ 250–370 MB unpacked | **≈ 3–60 MB** on macOS/Windows (Linux AppImage 70 MB+ once WebKitGTK is bundled); RAM advantage gone on Windows | 02 §3, 04 §5 |
| Effort, v1 | Low (difference ≈ 2 O-d) | **1.0×** (27 O-d) + 5.5 security | ≈ 1.05× (28.4 O-d) + 6.0 security | 03 §6, 08 §4.2 |
| Recurring maintenance | Low | ≈ 1.6 O-d/yr of Chromium bumps | Low tracking, plus the one-off v3 migration | 08 §4.2 |
| Observability | Low | Official `@sentry/electron` | Official Rust + JS SDKs wired by hand | 07 §5 |
| Linux accessibility | Low (developer tool) | Chromium AX works | WebKitGTK/Orca fragile | 07 §3 |
| Career value | **Minor note; decides nothing** (the owner's interest is a mild wish) | TS (03 §6: ●●●) | TS + some Rust if the app-side layer is in Rust (03 §6: also ●●●; 03 §5 calls the Rust part moderate) | 03 §5, §6 |

**Reading.** Security comes first, so it is read first:
- **Security is even once Electron's cadence is kept.** 08 §6.1 rates Tauri the "security-first pick" and Electron "equal if the release cadence is kept". The cadence is a MUST in both shells (08 §4.1 row 24: ship within 14 days of upstream security releases), and for Electron it costs ≈ 0.25 O-d per bump, ≈ 1.6 O-d/yr (08 §4.2). Electron's other gap, Linux updates checked by sha512 only, is closed by a detached-signature `verify` hook (08 §3.6). Tauri's structural edge (a mandatory signed updater, a capabilities ACL, no Chromium to ship on macOS/Windows) is real but modest, and on Linux it runs the other way: WebKitGTK is patched only as fast as each distro ships it, and Trusted Types may be missing below 2.50 (07 TL;DR, 08 Risk 7). Electron's residual risk depends on a discipline the owner controls; Tauri's Linux residual depends on distro maintainers the owner does not control.
- **With security even, the other criteria decide, and they favour Electron:** Linux rendering reliability (bundled Chromium against WebKitGTK's blank-window, flicker and Wayland "Error 71" bugs), updater and packaging coverage, agent effectiveness and harness QA fit (CDP in test builds on every OS; Tauri's macOS path needs a third-party plugin or a paid fork), maturity and support (a published support policy, no pending v2→v3 migration), developer experience, and effort (≈ 2 O-d less for v1, though ≈ 1.6 O-d/yr more upkeep). 07's 15-point gap (99 vs 84) comes mostly from agent QA, DX and observability.
- **07's flip criterion does not reverse this.** It reads in full: "**Security weighted above everything** moves Tauri, with its ACL, above Electron, non-webview toolkits above both, and pushes the local web app and the hybrid down. Strict CSP plus sanitizing closes most of the webview gap; it does not close the listener gap." This file weights security first, not above everything: it holds Electron to 08's cadence condition rather than ranking by Tauri's ACL alone. Weighting security above everything would also favour non-webview toolkits, which lose on every other row.
- **Career value is a minor note.** 03 rates both ●●●; Tauri would add some Rust. The owner's interest in it is a mild wish, and every other criterion outweighs it.

**So Electron is the default, and the spike validates it.**

**Flip conditions for the Electron default.** Any one of them moves the pick to Tauri 2:
1. The owner cannot commit to shipping each Electron security release within 14 days and a new major at least every 24 weeks (the support window of the latest 3 majors, 01 §3). 08's equality condition then fails, and Tauri's lower residual risk wins on the main concern.
2. The spike cannot close the Linux update-integrity gap: a detached-signature `verify` hook on electron-updater's AppImage/deb path does not work, and electron-updater's own manifest signing is not yet stable (08 §6.1). Shipping Linux updates through the package manager only is the fallback before flipping.
3. Download size or idle RAM becomes a product requirement, for example on 8 GB machines (02 TL;DR: Electron ≈ 250–370 MB unpacked).

A revisit trigger rather than a flip: if Tauri 3 ships a stable line with a stable CEF runtime on Linux before Studio v1 freezes, its migration and Linux rendering penalties go away; re-run the comparison then (01 §3). Switching shells after the spike costs only the shell and the app-side layer, roughly 03's data and process rows (≈ 7 O-d) rewritten from TS to Rust [inferred], because the UI is web-first and the run logic lives in the harness contract.

#### 1.3 Why a desktop shell, not a web delivery mode

- Local runs are in v1 scope: Issue item 12 (inbox drop) and item 15 (watcher status). The hosted remote-only app fails that gate (07 §4d, "Gate: local runs"). Keeping them in v1 means the harness must ship `runs drop`, `runs pause`, a global-stop verb and `daemon status --json` before Studio v1 (D6 (a)).
- The local web app exposes a process-spawning socket. It is reachable by other OS users, by every Windows user through WSL `localhostForwarding`, and by hostile pages whenever a Host, Origin or token check regresses (08 §2d). It also needs Node plus a terminal-started server inside WSL, against a WSL distro that shuts down after 15 s idle (07 §4b).
- The hybrid connector turns one hosted XSS into process spawning on every connected machine (08 §2f).
- Because the UI is web-first, a hosted remote-only app can be added later from the same components (07 §4c) once its GitHub App, BFF and operations are justified (08 §6.1).

#### 1.4 Why one project (shape B)

- The whole tree typechecks and tests on a Linux runner. Overrides are `process.platform` branches in the TS main process, so they typecheck and unit-test on Linux (06 §1.7, §2.4; with Tauri they would live in Rust behind `#[cfg(target_os)]`).
- No harness changes are needed. Shapes A and C would need H1–H8 (06 §2.6). Per-PR CI cost is about 15× lower in a private repo, and zero in a public one (06 §1.2).
- Drift can only occur inside small overrides. In A, drift is the default (06 §1.6).
- Keep native Node modules out of the override layer where possible; if Tauri is ever chosen, avoid crates with C or Swift build scripts there, since they would break `cargo check --target …` from Linux (06 §1.7).

#### 1.5 The architecture in one picture

```
 web UI (TS; React or Svelte; one component library shared with the site later)
   │  intent-level IPC only: listRuns(), runDetail(b), startRun(issue), pauseRun(b) …
   │  browser mode: the same interface, served from fixtures, for harness QA and dev
 preload (contextBridge): intent verbs only; no Node in the renderer
 TS main process: argv builder → spawn | PATH probe | gh read-model | log tail | native confirm modal (dialog)
   │  Transport = Direct (macOS/Linux) | Wsl(distro) via `wsl.exe -d … --cd … --exec …`
 devscene runs … --json  (harness-owned contract; `runs watch` = NDJSON stream from inside WSL)
 gh (GitHub read-model, read-only; markers trusted only from github-actions[bot])
```

Sources: 05 §4, 07 §2a, 08 §1.2, §2a and §3.2.

### 2. Where the area files disagree, and how it is resolved

| # | Disagreement | Positions | Resolution |
|---|---|---|---|
| 1 | **Framework order** | 01: Electron, Tauri 2, Wails 3 ("close"). 03: a tie, Tauri for Rust exposure and Electron for agent-friendliness. 07 scoring: Electron 99, Tauri 84 of 115 (Tauri wins only on security). 08: Tauri the "security-first pick", Electron "equal if the release cadence is kept". | Default **Electron**, on the evidence with security first (§1.2). Security is even once Electron's 14-day cadence and a Linux signature hook are kept (08 §6.1), and Tauri's Linux webview lags with the distro; every other evidence row favours Electron. Career value is a minor note and decides nothing. 07's flip list reads in full: "**Security weighted above everything** moves Tauri, with its ACL, above Electron, non-webview toolkits above both, and pushes the local web app and the hybrid down. Strict CSP plus sanitizing closes most of the webview gap; it does not close the listener gap." This file weights security first but holds Electron to 08's cadence condition, so that criterion does not apply as stated. Flip conditions are in §1.2. |
| 2 | **Language of the app-side core** | 07: "a small Node core". 03, 06 and 08: Rust commands under Tauri, TS main process under Electron. | The core language follows the shell. 07's real point (a web UI behind an intent-level boundary, with a browser mode) holds in both shells. |
| 3 | **Windows transport** | 05: `wsl.exe` stdio. 07: a localhost HTTP transport to a core inside WSL as an alternative. | **stdio via `wsl.exe --exec`.** A listener adds 08 §2d's whole attack surface for no functional gain. |
| 4 | **Delivery mode** | 07's table puts hosted remote-only top (103) but says the table does not settle the mode. 08 ranks hosted below the shells and says it is worst in aggregate. | **Desktop shell for v1** (§1.3). Hosted remote-only later, read-mostly first. |
| 5 | **Electron vs Tauri updater** | 04: Electron's updater has the widest coverage. 08: Electron on Linux checks only the sha512 from the same manifest; Tauri signatures are mandatory. | Coverage favours Electron and integrity favours Tauri. With Electron as the default, a detached-signature `verify` hook on the Linux AppImage/deb path is a v1 MUST (08 §3.6, §6.1); if it cannot be made to work, update Linux through the package manager only (flip condition 2). |
| 6 | **Windows signing eligibility and price** | 01: Azure Artifact Signing open to organisations in 12 countries; OV from €49 (Certum, out of stock). 04: organisations only in US/CA/EU/UK with **3+ years of verifiable tax history**; OV US$300–500/yr. | Both cite Microsoft pages updated in October 2026; the stricter text (04) governs planning. A new company or an individual outside US/CA should budget for an OV certificate (US$300–500/yr, Microsoft's range, 04 §7; Certum's €25–€69 Open Source variants apply only if the app is open source), or use SignPath if the app is OSI open source (§4 D3). Confirm at enrolment. |
| 7 | **Issue #1 premises on integration** | Issue: Electron reuses the CLI code; Tauri needs a Node sidecar. | **Both disproved** (05 §1, §3). Integration is roughly neutral across stacks. |
| 8 | **"N natives = N × time"** | Owner hypothesis: 3×. | 2.1–2.2× for v1 and about 2.7× per feature (03 §1), plus 48–82 O-d of harness work for a verified agent loop (06 §2.6). Directionally right, numerically too high at v1, closer to right over the product's life. |
| 9 | **State-label prefix** | The Issue (item 5) and 08 §1.3/§3.12 say `sdlc-harness: <state>`; 05 says `devscene: <state>`. | Harness code: `STATE_LABEL_PREFIX = 'devscene: '` (`cli/src/remote/githubActions.ts:136`). Use **`devscene:`**; fix Issue item 5 (§9). 08's trust rule is unaffected. |

### 3. Answers to the owner's questions

#### 3.0 Are there credible cross-platform solutions in late 2026?

Yes.
- **Credible:** Electron, Tauri 2, Flutter, Compose Multiplatform, Avalonia and Qt (C++ or PySide6), plus Wails 3 (stable only since 2026-10-26).
- **Riskier:** Electrobun (young), Flet and Toga (Python, pre-1.0 maturity or a Flutter dependency), and the Rust-native toolkits (pre-1.0, more code for a board UI).
- **Out:** MAUI and React Native desktop (no Linux), Xamarin (end of life).

→ 01 TL;DR, Q1, ranked shortlist.

#### 3.1 Is cross-platform worth it versus native, given AI agents?

Yes. Agents compress *writing*; they compress much less of review in three languages, testing on three OSes, and owning three toolchains and release pipelines. The model gives 57–59 vs 27 O-d for v1 (2.1–2.2×) and about 2.7× per feature. The deciding fact is the harness: it runs on Linux, so it cannot verify WinUI at all, can verify SwiftUI only in local Mac runs, and has no native QA driver. Agents would write code the agent loop cannot check. → 03 §1–§2, 06 §2.4–§2.6.

Intermediate options cost less: ≈ 1.5× for SwiftUI on the Mac plus Tauri/Electron elsewhere, and ≈ 1.6× for native ×3 on the CLI core. They still need 33–63 O-d of harness work and leave Swift unverifiable in remote runs (03 §4, 06 §2.6). 03 calls the two-codebase split "the only native variant worth considering". Consider it only if a native Mac feel becomes a product requirement.

#### 3.2 Performance comparison

Native wins every micro-metric (≈ 3–15 MB, ≈ 30–70 MB RAM, < 0.2 s start). System webviews (Tauri, Wails) match native on size; Tauri idles at ≈ 88–109 MB on macOS and ≈ 94 MB on Linux, but ≈ 312 MB on Windows, where WebView2 erases the RAM gap. Electron is ≈ 250–370 MB unpacked and idles at ≈ 128–600 MB depending on how RAM is measured; public benchmarks disagree by 2–4×. None of this changes what the user sees, because the board waits about 1 s on `gh`. The only user-visible risks are download size, a non-AOT JVM start, and WebKitGTK rendering on Linux. → 02 TL;DR, §3, §9.

#### 3.3 Does Kotlin Multiplatform work?

Yes, but only as **Compose Multiplatform on the JVM**; there is no Kotlin/Native desktop UI (02 §8). It costs ≈ 60–130 MB, ≈ 100–150 MB RAM, and a 1.3–2 s start, or 0.4–0.65 s with the JDK 25 AOT cache (Compose 1.13, still beta). It works for this app, but its packaging story is the weakest: no AppImage, no built-in updater (Conveyor, US$45/month unless OSI open source), macOS file watching by polling (04 §10), no Linux accessibility (07 §3), and no harness QA driver (03 §3). Kotlin's career value is moderate (Android and JVM back-end); desktop Compose is niche (03 §5). Not recommended here. → 02 §8, 04 §8, 07 §3.

#### 3.4 Native-side blockers with a cross-platform framework

Mostly they are the same blockers a native app has:
- the macOS GUI `PATH` (probe a login shell);
- TCC prompts and notarization;
- SmartScreen and Smart App Control (signing is mandatory);
- `wsl.exe` quoting, UTF-16 output and latency;
- Windows watchers that likely miss `\\wsl$` events (secondary evidence);
- Flatpak and Snap confinement.

Framework-specific ones:
- Tauri/Wails: WebKitGTK rendering on Linux; AppImage-only updates on Linux.
- Wails: the GTK3 path is slated for removal, which would drop Ubuntu 22.04 and Debian 12.
- Compose: no AppImage or updater.
- Flutter: community plugins for tray, updates and installers.

None blocks WSL2 once WSL is treated as a remote host with one long-lived process inside it. → 04 TL;DR, §10. The flip conditions for the Electron default are in §1.2.

#### 3.5 Costs

No framework licence is needed for any finalist (01 §4a). The real recurring costs are signing and, if the repo is private, CI minutes (§7). Paid traps to avoid: Qt commercial and PyQt6 (GPL) licences, Avalonia's paid Hot Reload, Conveyor for Compose, CrabNebula's macOS WebDriver, Squish. → 01 §4, 04 Q6, 06 §1.2, 07 §6.

#### 3.6 Deprecation and momentum

- Deprecated or out: Xamarin (end of life), MAUI and React Native desktop (no Linux).
- In transition: Tauri (v3 alpha since 2026-09-13), Wails (v3 stable since 2026-10-26).
- Changing hands: Flutter desktop's stewardship moved to Canonical, a handover rather than a wind-down.
- Gaining investment: WinUI 3, Avalonia, Compose Multiplatform.
- Stale add-ons: the Tauri Stronghold plugin and Flutter `auto_updater`.
- Electron is not losing momentum; its cost is the 8-week Chromium treadmill.

→ 01 §3, Q7; 04 Q7.

#### 3.7 Monorepo of native apps vs one project with native overrides, under the harness

The config can express a monorepo of native apps (one layer per app), but the gates can't verify it. There is one repo-wide `commands.typecheck` and `commands.test`, every unit runs the whole-tree typecheck, remote runs are Linux-only, and WinUI is unverifiable in every run mode. An OS-switching wrapper that skips toolchains reports a false PASS, which breaks the harness's own "never report a pass for a gate that was not run" rule. Dispatch is one task per layer, run sequentially, so one feature becomes three or more sequential platform tasks. The parity reviewer checks business logic against one fixed reference, not sibling feature presence. Making native well supported needs 48–82 O-d of harness work. One project with runtime or `#[cfg]` overrides needs none of it. → 06 TL;DR, §2.1–§2.6.

#### 3.8 Security depth

Treat it as an app that can start an autonomous coding agent on the user's machine. The asset that matters most is the ability to start or continue a headless `claude` run, not a credential. The required depth is:
- a STRIDE model per mode;
- 29 controls, most of them MUST;
- about 5.5 O-d of v1 work for Electron (6.0 for Tauri; ≈ 20–22% on top of v1);
- three CI suites. For the desktop shell they are an XSS corpus, an argv fuzz test and a hostile-repo fixture (08 §4.3 #1, #2, #5), plus traversal and release assertions. 08's TL;DR names DNS-rebinding/CSRF/WebSocket as the third suite, but that one applies only to the local web modes (08 §4.3 #3).

Two app-side preconditions apply: native-modal confirmations and a repo-trust gate. Two harness findings block the answer and resume features (H1, H1′). → 08 TL;DR, §4.1–§4.3, §6.2.

#### 3.9 Anthropic terms

Within the terms, with three narrow open questions (09 grades in brackets):
- The subscriber's own `claude -p` (locally or with their own `setup-token` in their own CI) is explicitly permitted **[unambiguous]**.
- Spawning the unmodified binary matches the legal page's carve-out **[strong reading]**.
- Sustained, unattended use (several parallel runs) on a personal Max/Ultra plan is allowed but at risk, since limits "assume ordinary, individual usage" **[ask]** (email item b).
- Prohibited: offering Claude sign-in, reading or relaying tokens, bundling or proxying Claude Code, selling Claude usage, and Anthropic marks in names or logos.
- Team repos should use an API key, WIF or Team/Enterprise rather than one person's OAuth token.
- EEA/Swiss Pro/Max/Ultra users doing business work should use an API key or a Team plan, or get confirmation.
- Send the drafted email.

→ 09 "Not in doubt", F3, F4, F7, "Draft email".

#### 3.10 Career value

TypeScript is the strongest single bet. Rust is the best second language for growth, and Go the best for job count. 03 §6 rates Electron and Tauri equal (●●●); Tauri would add some Rust if the app-side layer were written in it. The owner's interest in career languages is a mild wish, so it does not affect the framework choice (§1.2). Kotlin's value is moderate (Android and JVM back-end; desktop Compose is niche). Swift, Dart and WinUI/GTK skills carry little transferable value. Python's value comes from the language, not from desktop GUIs. → 03 §5.

### 4. Decisions the owner must make

#### 4.0 Owner's decisions (2026-11-24)

The owner answered the table below on 2026-11-24. Like the rest of Issue #1, these are working decisions: new evidence can reopen any of them. The table after this subsection is kept as originally written, with the options and the reasoning.

| # | Decision | Notes |
|---|---|---|
| D1 | **Electron**, TS web UI and TS main process | Commits the project to shipping each Electron security release within 14 days. The spike (§5) still validates it against the flip conditions. |
| D2 | **Apache-2.0, public repo** on the owner's personal GitHub account | The repo went public on 2026-11-24, with `LICENSE` and `NOTICE` at the root. A licence that stops others selling Studio itself, such as PolyForm Shield or FSL, was considered and rejected: it isn't OSI open source and would lose free SignPath signing and the Sentry open-source sponsorship. |
| D3 | **SignPath Foundation** (follows from D2) | Apply before the first Windows release. |
| D4 | **Deferred.** No new Apple Developer account for now | v1 work goes ahead without one. Private pre-release macOS builds may be signed with Developer ID and notarized under an existing organisation account the owner holds, signed on the owner's machine and never in this repo's CI. TestFlight isn't used, because it needs a sandboxed Mac App Store build. Before the first public release, move to the publishing identity (a personal individual account), starting enrolment a few weeks ahead. Installs signed by the interim account need one manual reinstall. |
| D5 | **Yes, most likely** | Harness H1/H1′ are fixed in parallel and must land, or the 08 Risk 1 measurement must show every write refused, before answer/resume ships. |
| D6 | **Yes, option (a)** | The read side plus `runs pause`, `runs drop` and a global-stop verb in the harness phase Studio v1 depends on. |
| D7 | **Desktop shell only in v1** | |
| D8 | **AppImage + deb**, with the detached-signature update hook | |
| D9 | **Leaning:** each person's own subscription for local runs, on any plan including a Team seat. A repo's subscription token for remote runs only when its owner alone starts them, which the harness enforces with `DEVSCENE_RUN_ACTORS`. A Console API key or workload identity federation only when several people start remote runs. | This follows DevScene's `docs/team-accounts-research.md` (Summary, Option C, §6) and narrows this file's "API key for team repos". It is final once Anthropic has answered the 09 email. |
| D10 | **No tray or OS notifications in v1** | |
| D11 | **React** | Chosen on the owner's React experience. Both options were viable and no comparison was researched. |

**Repo setup:** the `dev` and `main` branch model and the `dev-protection` and `main-protection` rulesets are copied from the DevScene repo. `main` is the default branch. The publish flow, which regenerates `main` from `dev` without the harness adoption files, comes after the harness is installed (Issue #1 items 2–3).


| # | Question | Options and consequences | Recommendation |
|---|---|---|---|
| D1 | **Framework?** Decided now on the evidence, with security first (§1.2); the spike validates it. | **(a) Electron:** security equal to Tauri if you ship each security release within 14 days and a major at least every 24 weeks (≈ 1.6 O-d/yr) and add a Linux update-signature hook; consistent Linux rendering; widest updater coverage; largest agent corpus and CDP QA; no pending migration; best DX; ≈ 2 O-d less v1 effort. **(b) Tauri 2, app-side layer in Rust commands:** a modest structural security edge (mandatory signed updater, ACL, OS-patched webviews on macOS/Windows), smaller download; but Linux webview patching depends on the distro, WebKitGTK rendering risk, slower DX (cold Rust builds 3–8 min), a likely 2027 v3 migration, and agents need a version-pinning note. **(c) Tauri 2, app-side layer from JS via plugins:** the shell/fs plugin scopes widen the IPC surface (08 T2). Career value: equal (03 §6); not a factor. | **(a) Electron.** Commit to its release cadence now. Switch to (b) if a §1.2 flip condition fires. Avoid (c). |
| D2 | **Open source, and which licence?** | **Apache-2.0, public repo:** free SignPath Windows signing (no dual licensing, no proprietary components), free hosted CI runners on all three OSes, Sentry OSS sponsorship; saves about US$120–500/yr in signing, plus up to US$312 if Sentry Team would otherwise be needed (07 §6, which notes that the free tier likely suffices). Rules out a closed "pro" tier inside the same project (09 F8). **Closed:** pay for signing and private CI; Qt/PyQt licence questions return (irrelevant for Tauri/Electron). | Apache-2.0, public, matching the harness. |
| D3 | **Windows signing route?** (depends on your country and legal entity) | **SignPath Foundation:** free; needs D2 = OSI open source and verifiable CI builds; the publisher shown is SignPath Foundation. **Azure Artifact Signing:** ≈ US$120/yr; only US/CA individuals, or organisations with 3+ years of tax history. **OV certificate in a cloud HSM:** US$300–500/yr (Microsoft's range, 04 §7), renewed at least every 460 days; Certum's €25–€69 Open Source variants only for an open-source app. All of them still build SmartScreen reputation over time (04 §7). | SignPath if D2 is open source; otherwise whichever of the others you are eligible for. Decide before the first release. |
| D4 | **Apple account: individual or organisation?** | An individual enrols quickly. An organisation needs a D-U-N-S number and shows the company name. Notarization onboarding has stalled teams for weeks to months in 2026 (04 §6). | Enrol **now**, as whichever entity will publish; notarize a test build in week 1 of the spike. |
| D5 | **Does v1 include answer and resume?** | **Yes:** harness H1 + H1′ must be fixed and runtime-tested first, or a prompt-injected run can answer its own (or a sibling's) park, and the answer form is not a real human checkpoint (08 §6.2 item 5). **No (v1 = board, detail, local and remote start, pause, global stop):** ships sooner; answer/resume in v1.1 once H1/H1′ land. The v1 acts need harness verbs; see D6. | Ship v1 without answer/resume unless H1/H1′ are fixed, or the 08 Risk 1 runtime measurement shows every write refused (H1/H1′ then drop to Info). File H1/H1′ now (§8, S-1). |
| D6 | **Build the harness contract (`devscene runs … --json`, Issue item 7) before the app's data layer, and in what phases?** | 05 §5 phases it as v1 read-only, v1.1 pause/resume/answer, v1.2 drop/derive-branch/review. That does not fit Studio v1: local start (`drop`) would arrive two harness phases late and pause one phase late, and 05 has no global-stop verb at all, although 08 §6.2 item 5 makes a one-click global stop a release gate. **(a) Re-phase:** the phase Studio v1 depends on holds the read side (`capabilities`, `runs list/show/watch`, `doctor --json`, `repos --json`, `daemon status --json`) **plus** `runs pause`, `runs drop` (with `derive-branch` if Studio derives branch names) and a global-stop verb (`runs stop-all`, which writes `AUTONOMOUS_STOP` locally and wraps the existing remote `stop` dispatch). Then v1.1 resume/answer (gated on H1/H1′), v1.2 review. **(b) Cut v1:** remote start only (the Issue trigger label) plus read-only; local start and pause move to Studio v1.1. That weakens §1.3's "local runs are in v1 scope" argument for the desktop shell. **No contract:** the app parses `remote-run.sh` human output and raw registry JSON, which drifts and is acceptable only in a throwaway spike (05 Risks). Size: the read side is ≈ 1–1.5k lines **excluding `runs watch`**; `watch` and the act side are several thousand lines, to be sized in the harness repo (05 §5). | Yes, with **(a)**. Build the read side in parallel with the spike, then the three act verbs, with 08 §5.3's security requirements built in. If the act verbs slip, fall back to (b) rather than letting the app write markers itself. |
| D7 | **Delivery modes beyond the desktop shell?** | **Hosted remote-only, later:** zero install for no-local-setup teammates; adds a GitHub App, a BFF, server-side budgets, a privacy policy and incident response (≈ 8.5 O-d + operations, 08 §4.2). **Local web app:** opt-in developer mode only, behind every 08 §2d control. **Hybrid connector:** not in v1. | Desktop shell only in v1. Revisit hosted once no-local-setup users are real. |
| D8 | **Linux packaging and updates?** | **AppImage + deb:** electron-updater updates both (deb through a pkexec/sudo prompt), with the detached-signature `verify` hook, since its Linux path checks only the manifest's sha512 (04 §8, 08 §3.6). electron-builder's static AppImage runtime needs no `libfuse2` (04 §5). Optionally a signed apt repo later. Flatpak and Snap are not viable (04 §5). | AppImage + deb with the signature hook; build on the oldest supported glibc (Ubuntu 22.04). |
| D9 | **Which Claude credential does Studio's documentation steer to?** | Plan login for solo, own-machine use (permitted); API key, WIF or Team/Enterprise for team repos, heavy unattended use and EEA business use (09 F4, F7). | Both, as 09 says. Send the 09 email (items a–f) now; the answers may tighten the defaults. If you are EEA-resident, consider item (e) for your own development use too. |
| D10 | **Are tray and OS notifications v1 needs?** | Not in Issue #1. A desktop shell supports both either way. They matter only if a web-only mode is ever the sole deliverable (07 §4d). | Not in v1. Note: GNOME needs the AppIndicator extension for any tray (04 §9). |
| D11 | **UI library: React or Svelte?** (§1.5) | No area file compares them for this app. Both run in either shell and in browser mode. | Deferred: decide on spike Day 1 and record it in the spike write-up. |

### 5. Validation spike

**Goal:** validate the Electron default against the measured flip conditions (§1.2), prove the Windows/WSL transport, and prove that the harness can run gates and QA on the repo. The spike draws on 02 Risks, 03 Risks, 04 Risks, 05 Risks, 06 Risks, 07 Risks 1 and 5, and 08 Risks 6 and 7.

**What to build** (about 60% of the build work carries into v1, ≈ 4 O-d [inferred]):
- **Web UI:** a board with 300 fixture cards in three columns; a detail screen; a log tail with a 10k-line ring buffer and frame-batched appends; the §6 rendering pipeline (markdown-it with `html: false`, DOMPurify ≥ 3.4.17, Trusted Types, CSP, closed-palette ANSI parser); browser mode with fixture-backed IPC.
- **Electron shell:** a TS main process with the argv builder, branch validation and `--end-of-options`; a `PATH` probe; a `Direct | Wsl` transport; a `gh` read call; a log-tail stream from a child process; a **native start modal** (`dialog.showMessageBox` from the main process); a preload with intent verbs only, `contextIsolation`, `sandbox`, the fuse set and a confined `app://` handler; electron-builder packaging with electron-updater and a prototype Linux signature `verify` hook.
- **Thin Tauri shell** around the same UI, optional and about half a day: only if a flip condition looks likely, for comparison measurements.
- **A stand-in for `devscene runs watch --json`** (the harness verb does not exist yet): a small script inside WSL that emits a `snapshot`, then `run_updated` NDJSON from inotify, plus heartbeats, and exits when stdin closes.
- **CI seeds:** a 50-string XSS corpus run by Playwright in browser mode; a 10k-case argv fuzz with a mocked `wsl.exe` that applies `CommandLineToArgvW` on a Windows runner.

**OS matrix:**
- macOS 15 on Apple Silicon (the owner's M4), plus macOS 26 if available (TCC).
- Ubuntu 24.04 GNOME on Wayland, with an NVIDIA GPU if possible (proprietary driver ≥ 545).
- Ubuntu 22.04, the oldest glibc baseline (and WebKitGTK 4.1, if the Tauri comparison runs).
- Optionally, Fedora's latest KDE on Wayland.
- Windows 11 with WSL2 Ubuntu in the default NAT mode, plus one run in mirrored mode. Windows 10 22H2 if available (`\\wsl.localhost` auto-start differs).
- A GitHub `ubuntu-latest` runner for the harness's remote gates.

**Hardware needed.** The research confirms only the owner's M4 Mac (02). The plan also needs:
- a bare-metal Linux machine with an NVIDIA GPU on Wayland, since a VM is unlikely to reproduce GPU-driver rendering bugs (DMABUF/NVIDIA) [inferred];
- a Windows 11 machine with WSL2;
- optionally, a Windows 10 22H2 machine.

If the NVIDIA machine is missing, Day 3 runs in VMs or on Intel/AMD graphics, and the NVIDIA case stays an open rendering risk. If no Windows machine is available, Day 4 drops entirely. The WSL transport then stays unproven, which blocks the Windows release but not the framework decision. Without Windows 10, its `\\wsl.localhost` auto-start stays untested.

**Plan (≈ 7 owner-days, plus 0.5 optional; 7–8 O-d with Day 0 admin):**

| Day | Work | Measure or test (pass threshold) | Source |
|---|---|---|---|
| 0 (admin, in parallel, ≈ 0.5 O-d) | Apple Developer enrolment; Windows signing route (D3); notarize a hello-world Electron `.app` | Notarization accepted, with no `statusCode 7000` | 04 §6 |
| 1 (1.5 days) | Web UI and browser mode; Playwright QA on it; seed the XSS corpus; pick the UI library (D11) | `web-playwright` drives every screen; the corpus gives 0 dialogs, 0 off-origin requests and 0 CSP violations | 03 §2, 08 §4.3 #1 |
| 2 (1.5 days) | Electron main process and shell on macOS; native modal; fuses; packaging and updater | Fuses read back with `@electron/fuses read`; no debug port in the release config; installer size recorded (flip condition 3); RSS after 10 min idle; time to a populated board (≤ 1.5 s with live `gh`); CPU over 10 min with the window hidden (≈ 0%); a signed update round trip on macOS | 02 Risks, 03 Risks, 08 §4.3 #6, Risk 6 |
| 3 | Linux matrix: AppImage + deb; log tail at 1–2k lines/s; updater | No blank window or crash on first launch; smooth scrolling on Wayland (+ NVIDIA); AppImage runs on a clean 24.04 **without libfuse2**; an AppImage and a deb update succeed, and a tampered update is **refused by the signature hook** (flip condition 2); a quick Orca check | 02 §6, 04 §5, §8, 08 §3.6 |
| 4 | Windows + WSL2: transport and stream | Cold and warm `wsl.exe --exec` latency (target ≤ 0.2 s warm); first call with the VM stopped; the stream child survives sleep/resume, or reconnects with a fresh `snapshot` within 5 s after `wsl --shutdown` and after the 15 s idle timeout; pgid kill leaves no orphans; a 15-minute `\\wsl.localhost` watcher probe (FileSystemWatcher and `notify`) settles the watcher gap; UTF-16 and `WSL_UTF8=1` handling; the 10k-case argv fuzz with the mocked `wsl.exe` passes on a GitHub-hosted Windows runner | 02 §7, 04 §2 and Risks 2/8, 05 Risks, 07 Risk 5, 08 §4.3 #2 |
| 5 | Harness fit: `npx devscene init` on the spike repo, layers set by hand; one remote run on a Linux runner; CDP | `tsc` and the tests pass inside the sandbox; the `process.platform` overrides typecheck and unit-test on Linux; the QA phase drives browser mode; CDP attach for Playwright MCP and Chrome DevTools MCP to a test build works, including a WSL-resident harness against Windows-side Electron in NAT and mirrored modes | 06 §2.4, 07 §1, Risk 1 |
| 6 | macOS TCC and write-up | Spawning `git`/`devscene`/`node` in a repo under `~/Documents` prompts once and then works; decision memo against the §1.2 flip conditions, including the owner's cadence commitment (flip condition 1) | 04 Risk 5 |
| +0.5 | Optional, only if a flip condition looks likely | Thin Tauri comparison shell: installer size, RSS, WebKitGTK version (Trusted Types ≥ 2.50) and first-launch rendering on the Linux matrix | 02 §6, 04 §4, 08 Risk 7 |

**Outputs:** a measurements table; confirmation of Electron, or a switch to Tauri if a flip condition fired; a corrected v1 O-d estimate from the logged hours (03 Risks); and the WSL transport parameters for the harness contract.

**Not in the spike, harness-side:** the H1/H1′ runtime measurement (08 Risk 1) belongs in the devscene repo (§8, S-1).

### 6. v1 minimum security bar

From 08 §6.2, applied to the Electron default (Tauri equivalents in brackets), plus 09's terms invariants. Every item is a release gate.

1. **Rendering.** markdown-it (`html: false`) → DOMPurify ≥ 3.4.17 in default mode, auto-tracked with the floor raised on every advisory → Trusted Types policy. No remote images. Logs as text nodes through a closed-palette ANSI parser that drops OSC/DCS sequences. CSP `default-src 'none'; script-src 'self' …; require-trusted-types-for 'script'`. Bidi and invisible characters shown as glyphs in the confirmation and answer views. XSS corpus in CI. (08 §3.1)
2. **Privilege.** `contextIsolation`, `sandbox`, a preload with intent verbs only, sender-frame origin checks, the fuse set (including `GrantFileProtocolExtraPrivileges=false`), a confined `app://` handler. [Tauri: intent-level commands restricted by `AppManifest::commands`; no `shell`/`fs` plugin permissions; the isolation pattern on (08 §6.2 item 8 puts it in the minimum bar, although 08 §4.1 row 13 grades it S; this file follows the stricter reading).] (08 §2a–§2b, §6.1)
3. **Processes.** One argv builder. Branch regex plus `git check-ref-format --branch`. `--end-of-options` for git and `--` for gh, always with `--repo`. Free text only by stdin or a `0600` file. `wsl.exe -d … --cd … --exec`. Git hardening flags. Child-environment allowlist; never spawn `claude`. `devscene` resolved by absolute path from `$HOME`, never via `npx` in a repo. Argv fuzz in CI, including the mocked `wsl.exe`. (08 §3.2)
4. **Files.** A realpath-confined reader with `O_NOFOLLOW` and a validated `stateDir`. Registry paths are not trusted. On Windows, security-relevant reads happen inside WSL, never over `\\wsl$`. Traversal tests in CI. (08 §3.3)
5. **Human in the loop (precondition).** Every start (and later answer and resume) is confirmed in an **OS-native modal opened by the main process** [Tauri: the Rust core]. It shows provenance (author, association, labeller, `updated_at`) and the exact text. A non-member warning. No auto-start, no batch start. A one-click global stop, through the harness's global-stop verb (D6, §8 F-1). (08 §3.5, §3.10, §6.2 item 5)
6. **Repos (precondition).** Detected repos are untrusted until the user confirms each one. No `doctor`, `git` or `devscene` spawn in an untrusted repo. Process cwd outside the repo. Hostile-repo fixture in CI. (08 §3.11)
7. **GitHub state.** Progress comments trusted only from `github-actions[bot]` with the exact marker. Actions run state over labels. Branch-committed JSON schema-validated, numbers only. (08 §3.12)
8. **Secrets.** Display-time masking; never show `.stream.jsonl`; crash reports scrubbed; never read `**/.credentials.json` under `~/.claude` or any `CLAUDE_CONFIG_DIR`, including inside WSL, and exclude it from every watcher and diagnostics bundle. (08 §3.8, 09 F3)
9. **Release.** Signed builds. Updater key in a protected CI environment with required reviewers, plus an offline backup. Hardware keys or passkeys on GitHub, Apple, npm, the registrar and the host. Linux updates verified by the detached-signature hook. Supply chain: lockfile, `--ignore-scripts`, a 7-day dependency cooldown, SHA-pinned actions, zizmor [Tauri: plus `cargo-deny`]. No debug port in release builds (CI-asserted); fuses read back in CI. No custom URL scheme. **Ship within 14 days of upstream security releases**, and move to a supported Electron major at least every 24 weeks. (08 §3.6–§3.7, §4.1, §6.1)
10. **Anthropic invariants.** No Claude sign-in UI; never capture `claude setup-token` output or set secrets with values Studio has seen; never bundle, patch or proxy Claude Code; no Anthropic marks in names or logos; a non-affiliation line in the About box, README and website; before a remote dispatch, warn when the repo uses a personal `CLAUDE_CODE_OAUTH_TOKEN` and the current `gh` user is not its owner. (09 F3, F4, F5, checklist)
11. **Harness blockers.** H1 + H1′ before answer/resume ships, unless 08 Risk 1's measurement shows every write refused. H2 before Studio exposes any API-key configuration. H12 before auto-doctor runs on any repo; the trust gate (item 6) covers it in the meantime. (08 §6.2 item 5, §3.11)

Estimated effort: ≈ 5.5 O-d for Electron (3.9–7.2), ≈ 6.0 for Tauri (4.2–7.8) (08 §4.2), plus ≈ 1.6 O-d/yr of Chromium bumps for Electron.

### 7. Cost summary

**Money per year** (US$, rounded):

| Item | Open source, public repo (D2) | Closed source or private repo | Source |
|---|---|---|---|
| Apple Developer Program | 99 | 99 | 01 §4b |
| Windows signing | 0 (SignPath) | ≈ 120 (Artifact Signing, if eligible) or ≈ 300–500 (OV; Microsoft's range, 04 §7). Certum's €25–€69 Open Source variants do not apply to a closed app (01 §4b) | 01 §4b, 04 §7 |
| Linux signing (GPG) | 0 | 0 | 01 §4b |
| CI (GitHub-hosted runners) | 0 | Linux PR gate ≈ $0.05/PR; release ≈ $0.8–1.5 each; within the $12–18/month allowance at small scale | 06 §1.2 |
| Crash reporting (Sentry) | 0 (OSS sponsorship or the free tier) | 0 (free tier) to 312 (Team) | 07 §5 |
| Framework licences, updater | 0 | 0 | 01 §4a, 04 §8 |
| Hardware security keys (one-off) | 50–100 | 50–100 | 08 Q6 |
| **Total, recurring** | **≈ 99** | **≈ 220–600 (up to ≈ 900 with Sentry Team)** | |
| Later, hosted remote-only app | Free or hobby tiers at small scale, plus operator duties | same | 07 §4c |

Not costed here: the product website and domain (not researched), and legal advice on the trademark clearance (09 F5).

**Owner-days** (03's unit; point estimates, ±30%):

| Block | Electron (default) | Tauri 2 | Native ×3 (for comparison) | Source |
|---|---|---|---|---|
| Validation spike | ≈ 7–8 (≈ 4 of it carries into v1 [inferred]); +0.5 for the optional Tauri comparison | (shared) | — | §5 |
| App v1, functional (Issue items 2–17) | 27 | ≈ 28.4 | 57–59 | 03 §1, §6 |
| Security v1 | ≈ 5.5 | ≈ 6.0 | ≈ 5.75 | 08 §4.2 |
| **App v1 total** | **≈ 32.5 (23–42)** | **≈ 34 (24–45)** | **≈ 63–65** | |
| **Spike + v1, net of the carry-over** | **≈ 36** | ≈ 37 | — | |
| Harness work to make the topology verifiable | 0 | 0 (plus F-2, the Rust toolchain under the sandbox) | 48–82 | 06 §2.6 |
| Recurring | ≈ 1.6 O-d/yr of Chromium bumps (the security condition) | Low tracking, plus a v2→v3 migration once (unsized; expect a few O-d [inferred]) | three toolchains | 01 §3, 08 §4.2 |
| Per later feature | 1 unit | ≈ 1.1 units | ≈ 2.7 units | 03 §6 |

**Not included, harness-side:** the `devscene runs … --json` contract (read side ≈ 1–1.5k lines excluding `runs watch`; `watch` and the act side several thousand lines, to be sized in the harness repo; 05 §5). Under D6 (a), `pause`, `drop` and the global-stop verb move into the phase Studio v1 depends on, so more of that act side lands before Studio v1. Also not included: the security follow-ups in §8. The browser-mode IPC layer is a small extra in every webview option that 03 did not model (03 Risks).

### 8. Harness-owned follow-ups (suggested devscene issues)

The area files reuse IDs (06 H1–H8, 08 H1–H12, 09 H1–H9), so each item is tagged with its file. The list has two parts, which are not ranked against each other:
- **Part A, security findings,** ranked by severity. The severity is 08's where 08 grades the item. 09 assigns no severity to its harness items, so their rows carry **[10's grading]**.
- **Part B, features, contract work and documentation** that Studio depends on, ranked by priority for Studio. They carry no severity.

**Studio** marks items that gate a Studio feature. **Tracked in** maps each finding onto devscene #170 → "## 10. The remaining sandbox and gate items" and the issues it links (#309, #312, #146, #316–#319, #234, #241, #150), as read on 2026-11-12 at commit `a1d0e992`. #170 item 10 **fully covers none of them**: H1′, 06-H3 and the toolchain-cache caveat are partly covered, and the rest are not covered. The 13 security items not covered were filed on 2026-11-12 as **devscene #344–#356**, each worded as a proposal to re-verify against the code before fixing. The owner's spot-check confirmed the two load-bearing claims: the settings template's `allowWrite` covers the whole state folder and its `denyWrite` is empty (the rendered profile adds only `registry.json`), and `~/.claude/.credentials.json` is absent from `sandbox.credentials`.

**Step 0, when picking an item up:** the security rows are filed (devscene #344–#356). Before fixing one, re-read it against the code and against #170's sandbox series (#316–#319 and newer), which is moving; close or merge it if a newer issue already covers it. The F rows are not filed yet: search open issues first, and comment on an existing issue rather than filing a duplicate.

#### Part A: security findings (by severity)

| ID | Severity | Suggested issue | Merges | Tracked in | Studio |
|---|---|---|---|---|---|
| S-1 | **High** | **Sandboxed runs can write the control channel, sibling run copies and the main checkout.** First add the runtime measurement row (`docs/sandbox-verification.md`): inbox drop, own `answer_1.md`, a sibling `RESUME`, a `.claude/CLAUDE.md` append, `AUTONOMOUS_STOP` delete. **Contingency (08 Risk 1):** if every write is refused, H1/H1′ drop to Info and stop blocking answer/resume. Otherwise narrow `Edit(/{{repoRoot}}/**)`; deny the inbox, markers and answers, and sibling copies by exact path; or move the control channel outside the agent's write roots. | 08-H1, 08-H1′ | **Not fixed by #170.** H1: not covered. #319 keeps only today's protections, and under `srt` the state dir stays in `allowWrite`. H1′: partly covered by #318 Q2, but only for user-level `~/.claude`. Filed as devscene #344 (H1, with H8) and #345 (H1′). Feed the deny list into #318's design questions (Q1) so the `srt` settings carry it | **Blocks answer/resume** (D5) |
| S-2 | **High** (API-key users) | **No cost ceiling on task runs:** `RUN_MAX_BUDGET_USD` → `--max-budget-usd`, a `DAILY_RUN_CAP`, surfaced in `capabilities.budget`, and `runs drop` refusing with `error.code: "budget"`. | 08-H2, 08 §5.3 item 7 | Not covered (#312/#241 cover gate *time*, not spend). Filed as devscene #346 | Blocks API-key configuration in Studio |
| S-3 | Medium | **`doctor` applies a repo-controlled `.mcp.json` env overlay to a child process** (`LD_PRELOAD`, `PYTHONPATH`, `BASH_ENV`): allow-list the keys. | 08-H12 | Not covered. Filed as devscene #351 | Needed before auto-doctor (Issue item 9) |
| S-4 | Medium | **Logs world-readable and unredacted, locally and in the 400-day `harness-state` artifact:** `umask 077`, a redaction pass before writing `.log` and before `save`, `::add-mask::`, and a docs note that public repos publish run logs. | 08-H3, 08 §5.3 item 8 | Not covered (#309 goal 4 is adjacent: it scans commits, PRs and QA findings, not logs). Filed as devscene #347 | Studio's masking is display hygiene only |
| S-5 | Medium | **Pin the agent CLI and the plugin in secret-bearing jobs:** `@anthropic-ai/claude-code@X.Y.Z` with integrity and `DISABLE_AUTOUPDATER=1`, the plugin cloned by commit SHA, an `npm-shrinkwrap.json` for `devscene`. Keep installing from Anthropic's channel, never a mirror or image. | 08-H5, 09-H2 | Not covered (#146 pins only `srt`). Filed as devscene #349 | — |
| S-6 | Medium | **Trigger provenance omits the issue author:** add the author, `author_association` and `updated_at` to the snapshot footer; let the PI screen weight `NONE` authors; optionally refuse when the issue was edited after labelling. | 08-H6, 08 §5.3 item 3 | Not covered. Filed as devscene #350 | Feeds Studio's provenance display |
| S-7 | Medium [10's grading] | **Team credential guard:** warn (not note) when `CLAUDE_CODE_OAUTH_TOKEN` is set and `DEVSCENE_RUN_ACTORS` names more than one login; consider `init` refusing `*` with an OAuth token. | 09-H5 | Not covered. Filed as devscene #355 | Studio shows the same warning before dispatch |
| S-8 | Medium [10's grading] | **Deny `.credentials.json` to sandboxed commands and the `Read` tool** (under `~/.claude` and any `CLAUDE_CONFIG_DIR`), after measuring that the CLI's own auth still works. | 09-H6 | Not covered. #309 scopes itself to repo-local files, and #316's credential leg probes only today's list. **Fold into #309** (or #318 Q1's credential-denial mapping) (filed as devscene #356, which notes this option); add the path to #316's credential leg | — |
| S-9 | Medium | **Watchdog kills a registry pid without an identity check:** record the start time or pgid and verify before signalling. | 08-H4 | Not covered. Filed as devscene #348 | — |
| S-10 | Low–Medium | **The mention reader can compose an `answer` from third-party comments:** require the text verbatim from the commenter, or a confirm step. | 08-H7 | Not covered. Filed as devscene #352 | — |
| S-11 | Low | **The screen's SAFE record lives in a session-writable ledger:** move it to a session-write-denied file keyed by sha256. | 08-H8, 08 §5.3 item 4 | Not covered. Folded into devscene #344 with H1 | Studio shows screen verdicts from it |
| S-12 | Low | **Bash allow-list breadth:** `find -exec/-delete`, `sed e`, `awk system()`; add `git branch --delete/-f/--force` to the deny floor. | 08-H9 | Not covered (#318/#319 keep the deny floor as it is). Filed as devscene #353 | — |
| S-13 | Info | **Validate `scriptsDir` before writing to `$GITHUB_ENV`.** | 08-H11 | Not covered. Filed as devscene #354; #241's new gates workflow should reuse the helper | — |

#### Part B: features, contract work and documentation (by priority for Studio)

| ID | Item | Merges | Tracked in | Studio |
|---|---|---|---|---|
| F-1 | **`devscene runs … --json` contract, phased as in D6 (a).** The phase Studio v1 depends on holds `capabilities`, `runs list/show/watch`, `doctor --json`, `repos --json`, `daemon status --json`, plus `runs pause`, `runs drop` (with `derive-branch` if needed) and a global-stop verb (`runs stop-all`). Then v1.1 resume/answer (after S-1), v1.2 review. Include `"schema": 1` in `registry.json`, ISO-8601 timestamps with an offset, a repo-scripts version stamp, a JSON Schema in `schemas/`, contract tests, and the security requirements: in-CLI validation, no path echo outside roots, provenance and screen fields, `--expect-*` optimistic concurrency, an audited `actions.log`, budget, redaction, no env or raw doctor output, refusal on an unknown major. | 05 §5, 08 §5.3, 08-H10 (graded **Low** in 08) | Not covered; deferred in the #170 mapping until the contract is scheduled. D6 schedules it now, so file it now | **Blocks the data layer and every v1 act** |
| F-2 | **Rust toolchain under the sandbox:** no `CARGO_HOME` / `CARGO_TARGET_DIR` handling and no `~/.cargo` carve-out; document WebKitGTK dev packages in `depInstall` for Tauri adopters. **Only if D1 flips to Tauri.** | 06 Risks | Partly covered by #234 (sandboxed install and build), which leaves out gate-time tool-cache writes. The #170 mapping deferred it as relevant to shape A only; under Tauri it would also apply to shape B, because the gates would run `cargo check`. With Electron, nothing to file | Would gate Tauri in remote runs |
| F-3 | **Structured "points needing attention"** for the status digest (today it is prose distilled by Claude), and confirm that the app posting `@dev-scene` comments is a supported route for remote-only users. | 05 Risks | Not security; not filed. Search open issues before filing | Detail screen, remote actions |
| F-4 | **Non-affiliation sentence in the README;** avoid "Powered by Claude" badges. | 09-H7 | Not security; not filed | Studio does the same |
| F-5 | **Refresh `docs/remote-execution.md` §9 citations:** add Ultra, drop "and GitHub Actions" from the paused-change paragraph, add the 2026-10-07 notice, re-source the $20/$100/$200 figures. | 09-H1 | Not security; not filed | — |
| F-6 | **Document the terms invariants** as harness policy: no pre-built image with Claude Code inside, a manual token flow, never `--bare` with subscription auth, read the Software Directory Policy before any directory listing. | 09-H3, H4, H8, H9 | Guidance, nothing to fix today (09-H3, H4); H8/H9 not security; not filed | — |
| — | **Deferred:** per-layer gates, layer OS affinity with a "deferred" gate state, cross-OS gate jobs, a macOS runner, a sibling-parity reviewer, native QA drivers, multi-app `init`. **Only if a native topology is ever chosen.** | 06-H1–H8 | 06-H3 partly covered by #241 (Linux runners only); the rest not mapped | Not needed for shape B |

### 9. Suggested updates to Issue #1

**"Decisions taken"** (discussion points, now informed by research):
- Add: **Framework:** Electron with a TS web UI and a TS main process, chosen on the evidence with security first and validated by the spike; Tauri 2 if a flip condition fires, chiefly if the 14-day security-release cadence cannot be kept (10 §1.2, D1).
- Add: **Delivery:** a desktop shell in v1; the UI is web-first with a browser mode; hosted remote-only maybe later; no hybrid connector.
- Add: **Topology:** one cross-platform project with `process.platform` overrides in the main process; one version for all OSes.
- Amend **Platforms:** Windows talks to WSL2 as a remote host through `wsl.exe --exec` stdio and one long-lived in-distro stream. `\\wsl$` paths are for occasional non-security-relevant reads only, never for watching (04 §2, 08 §3.3).
- Amend **Data source:** add the trust rules (progress comment only from `github-actions[bot]`; Actions run state over labels; branch JSON untrusted) (08 §3.12).
- Add: **Security posture** = 08 §6.2 is the v1 bar.

**Task list:**
- **Item 1:** replace the candidate list. The "reuse the CLI directly" and "needs a Node sidecar" notes are disproved (05). Link this research, record the D1 decision now, and record the spike's confirmation or switch afterwards.
- **New item 1a, validation spike** (10 §5), ≈ 7–8 O-d, with an explicit go/no-go against flip conditions 1–3 and the hardware list.
- **Item 2:** layout `app/` (renderer), `app/main/` (main process and preload), `contract/`; the browser mode with mocked IPC is a v1 architecture requirement (03 §2).
- **Item 3:** expect the layers to be set by hand (`devscene config set layers …`); `commands.typecheck` is `tsc` and `commands.test` the TS tests; no extra system packages are needed on Linux runners (06 §2.4). Harness follow-up F-2 applies only if the framework flips to Tauri.
- **Item 4:** rewrite as in "Platforms" above; depends on `runs watch` (harness follow-up F-1).
- **Item 5:** fix the label prefix to `devscene: <state>` (harness `STATE_LABEL_PREFIX`). Fix the run titles too: Actions runs are titled `harness <action> <branch>`, with `<action>` one of `run`, `pause`, `warm`, `stop` (`devscene-run.yml:425`, `:430-438`). Add the 08 §3.12 trust rules.
- **Item 6:** treat run logs on public repos as public (08 H3, Risk 3); prefer the committed analytics summary for history.
- **Item 7:** promote from "open discussion" to a **dependency**; link harness follow-up F-1 with D6 (a)'s phases: Studio v1 needs the read side plus `runs pause`, `runs drop` and a global-stop verb; resume/answer follow in v1.1.
- **Item 8:** detected repos are **untrusted until confirmed** (08 §3.11).
- **Item 9:** run `doctor` only on trusted repos, via `doctor --json`; depends on harness follow-ups F-1 (`doctor --json`, `repos --json`) and S-3.
- **Item 10:** the terminal hand-off passes a fixed command with no interpolated repo text (08 §3.5); per-OS launchers in 04 §9.
- **Items 11–12:** the start confirmation is an **OS-native modal** with provenance and the exact text; a non-member warning; no batch start (08 §3.10). Local start (item 12, inbox drop) goes through `runs drop` and pause through `runs pause`, both in the harness phase Studio v1 depends on (D6 (a)); if they slip, v1 ships remote start only and local start moves to v1.1 (D6 (b)).
- **Item 15:** watcher status comes from `daemon status --json` (F-1).
- **Item 14:** answer/resume depend on harness follow-up S-1 (H1/H1′), or on its runtime measurement showing every write refused; `runs answer --expect-question-sha` (08 §3.4).
- **Item 16:** mark the research done (09). Follow-ups: send the Anthropic email; add the non-affiliation line; add the credential-file exclusions; add the pre-dispatch team-credential warning.
- **Item 17:** enrol with Apple now; decide the Windows route (D3); AppImage + deb through electron-updater with the Linux signature hook; signing-key custody; commit to the 14-day Electron security-release cadence; SignPath depends on the licence (D2).
- **New item, Security baseline and CI suites** (08 §4.3, §6.2).
- **New item, Licence and repo visibility** (D2): LICENSE, NOTICE, a third-party notices bundle.
- **New item, Harness follow-ups:** the security follow-ups are filed as devscene #344–#356 (§8); link them from Issue #1, and file the F rows when Studio work needs them.
- **Item 18:** no Anthropic restriction found on donations or a paid tier, provided no Claude usage is sold (09 F7). A paid tier inside the same project would lose SignPath eligibility.

## Risks and open questions

**What remains unverified:**
- **No benchmark of this app's workload.** All performance figures come from hello-world or other apps (02 Risks); the spike measures them.
- **WSL behaviour:**
  - the `wsl.exe` latency figure is a single unreproduced report;
  - the `\\wsl$` watcher gap rests on a 2019 bot-closed issue and forum reports, untested on WSL 3.0.x;
  - the long-lived child's behaviour across sleep, `wsl --shutdown` and idle timeout is untested;
  - Windows 10 auto-start through `\\wsl.localhost` differs from Windows 11.

  (02 §7, 04 Risks 2/8, 05 Risks)
- **Electron on Linux:** the detached-signature `verify` hook for electron-updater's AppImage/deb path is designed but unbuilt (08 §3.6); rendering on NVIDIA/Wayland is untested on this app's workload (02 §6).
- **Electron QA from WSL:** a WSL-resident harness cannot reach a Windows-side CDP port in NAT mode (07 §1, Risk 1); browser mode covers QA in the meantime.
- **If the pick flips to Tauri:** WebKitGTK rendering on the target distros and NVIDIA drivers, Trusted Types from 2.50 (secondary source), WebKitGTK n-day lag on LTS distros, the AppImage without libfuse2, and `~/.cargo` under the harness sandbox are all untested (04 §4, Risk 4; 06 Risks; 08 Risk 7).
- **Harness H1/H1′** are confirmed by settings analysis only; the runtime test is pending (08 Risk 1). If it shows every write refused, they drop to Info and answer/resume can ship in v1.
- **Harness act verbs for v1:** D6 (a) moves `pause`, `drop` and a global-stop verb into the harness phase Studio v1 depends on. Their size is unknown until sized in the harness repo; if they slip, v1 falls back to remote start only (D6 (b)).
- **#170 mapping** is a snapshot of 2026-11-12; the sandbox series may have moved (§8 Step 0).
- **Effort models** (03, 06, 08) are estimates, sensitive to one-sided review-cost errors (03 §1 sensitivity: 1.7–2.6×). The agent benchmarks behind 03 §3 are older than 12 months.
- **Tauri v3 timing** is unknown. There is no v2 end-of-life date and no stable date for CEF (01 §3). It matters only for the revisit trigger in §1.2.
- **Signing:** Artifact Signing eligibility conflicts between 01 and 04 (§2 row 6); Certum's €49 cloud product is out of stock; notarization delays are anecdotal (04 §6).
- **macOS TCC** for `devscene`/`node` children on macOS 26/27 (04 Risk 5).
- **Anthropic terms:** open asks (a)–(f); the US Consumer Terms text is secondary only; the terms changed at least four times in 2026, including a Usage Policy effective on the day of this research (09 Risks). Re-check quarterly and before any paid tier.
- **Trademark clearance** of "DevScene" has not been done (09 F5).
- **Whether the app may post `@dev-scene` comments** as a supported route for remote-only users is unconfirmed (05 Risks).
- **Hosted-mode unknowns** (artifact proxy, org-approval friction, privacy duties) matter only if D7 changes (07 Risk 6).

**Biggest risk to the recommendation:** the release discipline Electron's security depends on. 08 rates Electron equal to Tauri only if each security release ships within 14 days, every year the app lives (≈ 1.6 O-d/yr). If that discipline lapses, Electron's residual risk rises above Tauri's on the owner's main concern (flip condition 1). Decide the commitment now, and automate the bump (a scheduled dependency PR gated by the CI suites) so it costs review rather than effort [inferred]. Because the UI is web-first and the run logic lives in the harness contract, switching to Tauri later costs only the shell and the app-side layer: roughly 03's data and process rows, ≈ 7 O-d rewritten from TS to Rust [inferred].

## Sources

Area files in this folder, 01–09 all `Status: reviewed` and each with a PASS WITH FIXES review in `reviews/`:

1. `01-framework-landscape.md`: candidates, health, deprecation, licence and signing costs; `reviews/01-framework-landscape.md`
2. `02-performance.md`: bundle, RAM, start, rendering, spawn and WSL costs, Kotlin Multiplatform; `reviews/02-performance.md`
3. `03-native-vs-cross-effort.md`: the N-native cost model, harness gate facts, agent effectiveness, career value; `reviews/03-native-vs-cross-effort.md`
4. `04-os-integration-blockers.md`: process control, WSL2, file watching, webviews, packaging, signing, updaters; `reviews/04-os-integration-blockers.md`
5. `05-harness-integration.md`: where the run logic lives, integration shapes, the `runs --json` contract; `reviews/05-harness-integration.md`
6. `06-repo-topology-harness-fit.md`: shapes A/B/C, gates per run mode, CI cost, harness changes H1–H8; `reviews/06-repo-topology-harness-fit.md`
7. `07-additional-criteria.md`: agent QA, delivery modes, accessibility, code sharing, observability, licensing, DX, scoring; `reviews/07-additional-criteria.md`
8. `08-security.md`: threat models, controls, effort, CI suites, harness findings, the v1 bar; `reviews/08-security.md`
9. `09-anthropic-terms-licensing.md`: Anthropic terms, naming, redistribution, monetisation, Apache-2.0, the draft email; `reviews/09-anthropic-terms-licensing.md`
10. GitHub Issue #1, `firu-daniel/devscenestudio` (read 2026-11-12): decisions and the task list.
11. Harness source `/Users/daniel/Work/devscene`, `cli/src/remote/githubActions.ts:136` (`STATE_LABEL_PREFIX = 'devscene: '`), read 2026-11-12 [verified]; `cli/templates/github/workflows/devscene-run.yml:425, 430-438` (run titles), as checked in `reviews/10-recommendation.md`.
12. devscene issues #344–#356 (https://github.com/firu-daniel/devscene/issues/344 to /356), filed 2026-11-12 from the mapping of the 05/06/08/09 harness findings onto devscene #170 item 10 and its linked issues.
