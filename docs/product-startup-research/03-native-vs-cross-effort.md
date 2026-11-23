# 03 — Native-per-platform vs cross-platform: effort with AI agents, maintenance, and career value
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **"N platforms = N × time" is wrong in both directions.** With agents writing the code, three fully native apps cost about **2.1–2.2× the owner's time** of one cross-platform app for v1 (57–59 vs 27 owner-days) and about **2.6–2.8× (≈ 2.7×) per feature after that** (model and derivation in §1; a ±30% error in any one row group gives 1.9–2.4× for v1, except a one-sided review-cost error, which gives 1.7–2.6×). It is less than 3× because some work exists in every option: packaging, signing, WSL interop and QA on three real machines. It is much more than "agents make it free" because the owner's time goes into review, three toolchains, three release pipelines and parity checking, and agents speed those up much less than they speed up writing. The harness's review and parity agents could pull the v1 ratio toward ≈ 1.9–2.0× at best (§1). **[inferred]**
- **The decisive finding comes from the harness, not from the frameworks.** DevScene remote runs execute **only on Linux runners** ("Not supported: macOS and Windows GitHub-hosted runners", `devscene/docs/remote-execution.md` §8), and on Windows the harness itself lives in WSL2. So **no harness run can compile or test WinUI 3 code**, and a SwiftUI target only builds in a local run on a Mac. A native-per-platform repo would leave the harness's typecheck/test gates blind to two of three codebases inside the agent's fix loop (ordinary per-OS CI would still catch build breaks after a push). TS (Electron/Tauri), Rust, Kotlin/Compose, Dart/Flutter and C#/Avalonia all build and test on a Linux runner. **[verified, local repo]**
- **Harness adoption is also worse for native.** `devscene init` picks *one* preset per repo, keeps a single `commands.typecheck`/`commands.test`, has **no GTK/meson/Vala preset**, and its nested-app detection is advisory only (it never creates layers, and stays silent when it finds more than one child app). Its only implemented QA driver is `web-playwright`; the mobile drivers are stubs and there is no native-desktop driver. A webview UI (Electron, Tauri, Wails) is the only kind the harness's QA agent can drive today, provided the UI has a **browser mode** whose IPC layer is mocked or served over HTTP: the QA agent drives a browser at the dev server's `base_url` and never launches the desktop shell. Make that browser mode a v1 architecture requirement. **[verified, local repo]**
- **Agent effectiveness favours mainstream, typed, slow-moving stacks.** The training-data and benchmark evidence ranks TS/JS, Java/Kotlin, Python and Rust well. Swift is underserved: 3 of 35 code benchmarks include it, and 41 of 44 (2024-era) models score lower on Swift than on Python (SwiftEval, Jan 2025, older than 12 months). Fast-moving UI APIs are a known failure mode: SwiftUI `ObservableObject` vs `@Observable`, Tauri v1 vs v2 (and **Tauri v3 is now in alpha**), and **Wails v3 went stable only on 2026-10-26**, so most model knowledge is v2. GTK4/libadwaita and WinUI 3 have small corpora. **[verified / secondary]**
- **Agents cannot see native UIs, with one exception.** Xcode 26.3 lets Claude and Codex capture SwiftUI Previews, macOS only **[secondary]**. GTK and WinUI have no first-party preview or inspection tooling for agents (generic UI Automation / computer-use agents exist). Webview UIs can be driven by Playwright: Electron support is experimental, and Tauri uses WebDriver, on macOS only through the WebdriverIO embedded server. **[verified]**
- **The hybrid "shared core + thin native UIs" exists already for this app.** The core is the `devscene` CLI with a `devscene runs … --json` verb (Issue item 7). It is Node, already present on every harness machine, and on Windows it runs inside WSL. That cuts native ×3 to about 1.6× (44 vs 27 owner-days), but the harness-gate and QA-driver problems above remain. A Rust core via UniFFI would duplicate run logic the harness owns (per 05, per-repo bash behind the planned JSON verb). **[inferred]**
- **Career value: TypeScript first, then Rust and Go.** TypeScript is #1 on GitHub (Octoverse 2025, older than 12 months) and used by 43.8% in SO 2026. TS, Rust and Go form the top-growth group of JetBrains' 2025 Language Promise Index (the post gives no numeric ranks; one secondary report ranks Python #3 and Go #4). Rust is the most admired in SO 2025 (72%), and 67.4% admired with 18% usage in SO 2026. Go is back in the TIOBE top 10 (Nov 2026) and in 5% of US postings. Swift (5.9%), Dart (4.9%) and Kotlin outside Android carry little transferable value. Role pay differs little (SO 2026 global medians, USD: desktop $80.0k, about 6% below back-end $85.3k and above full-stack $79.6k), so career value comes mainly from the language. **[verified / secondary]**
- **Recommendation:** use one cross-platform codebase with a TypeScript UI. Choose **Tauri v2** if the owner wants real Rust exposure and accepts v2→v3 churn plus agent version confusion; the Rust exposure comes from putting the app-side layer in Rust commands (the `gh` read-model, the process transport including `wsl.exe`, log tailing, file watching), which every option needs anyway. Choose **Electron** if agent-friendliness and having one language across the harness CLI, the app and the JSON contract types matter most. (Per 05, the run logic is per-repo bash, so there is no direct code reuse.) Either way, local run logic stays in the harness behind its JSON verb, so sibling products can reuse the pattern. Do not go fully native. A **two-codebase** split (native SwiftUI on macOS plus one cross-platform build for Linux and Windows) is the only native variant worth considering, and only if a native Mac feel is a product requirement. **[inferred]**

## Scope

This file covers the effort, maintenance and agent-effectiveness comparison of native-per-platform and cross-platform builds for DevScene Studio, plus career value by language. Raw runtime performance and Kotlin Multiplatform performance are in **02**. OS-level blockers (WSL file and process access from each runtime, WebView2/WebKitGTK quirks, notarization specifics) are in **04**. Licence and money costs are in the other files. Framework momentum appears here only where it changes agent effectiveness, such as version churn.

## Findings

### 1. The "N × time" claim, tested with a cost model

**Unit:** owner-days (O-d) for v1, meaning the scope of Issue #1 items 2–17. Agents write about 90% of the code. Owner time is review, steering, configuration, real-machine testing and release work. Agent wall-clock time is treated as nearly free, but its *output* still has to be reviewed. The figures are relative estimates, not quotes. **[inferred]**

| Work item | Cross-platform, one codebase (Electron/Tauri) | Native ×3 (SwiftUI / GTK4 / WinUI 3) | Native ×3 + shared core (CLI JSON verb) | 2 codebases (SwiftUI mac + one cross build for Linux/Win) | Why the multiplier is what it is |
|---|---|---|---|---|---|
| Data layer (git/gh/JSON read-model, log tail, folder watch) | 3 | 9 (+2 parity checks) | 3 + 1.5 glue | 6 | Pure logic. Shared code is reviewed once. Three languages mean three reviews and three sets of edge-case bugs (encoding, JSON nulls, path separators). |
| Process + WSL interop (`wsl.exe`, `\\wsl.localhost\…`) | 4 | 4.5 | 3.5 | 4 | **Windows-only in every option.** Native does not remove it. A shared core running *inside* WSL removes most of the path translation. |
| UI (board, cards, detail, answer form, dropdown, doctor icons) | 5 | 15 → ~17 (two unfamiliar stacks) | 12 | 9 | Roughly N×. Each toolkit has its own list, drag-drop, form and async-state idioms, and agents are weakest exactly here (§3). |
| Packaging, signing, notarization, auto-update | 5 | 7.5 | 7.5 | 6.5 | Per-OS in **all** options: an Apple ID and notarization, a Windows cert, Linux AppImage/deb. Cross frameworks bundle one updater (Tauri updater, electron-updater). Native needs Sparkle, a Windows updater (MSIX/Velopack-class) and a self-built Linux path. |
| CI matrix | 2 | 4 | 4 | 3 | One build definition on three runners, versus three build systems (xcodebuild, meson/flatpak, MSBuild). |
| Automated tests | 2 | 5 | 3.5 | 3.5 | Core unit tests are written once. UI tests per stack: XCUITest, none practical for GTK, WinAppDriver-class tools for WinUI. |
| QA on three real machines | 4.5 | 6 | 5.5 | 5 | **Three OSes in all options.** Native adds distinct bug populations per OS. |
| Docs + harness adoption | 1.5 | 4 | 3.5 | 3 | One `harness.config.json` and conventions set, versus three repos or a layerless monorepo (§2). |
| **v1 total** | **27** | **57–59** | **44** | **40** | Native ×3: 55 with UI at 15, plus 2 parity checks = 57; with UI at 17 = 59. |
| **Ratio to cross** | 1.0× | **≈ 2.1–2.2×** (2.11–2.19) | ≈ 1.6× (1.63) | ≈ 1.5× (1.48) | |
| **Each later feature** (one UI screen + logic) | 1 unit | ≈ 2.6–2.8 units (≈ 2.7) | ≈ 1.9 units | ≈ 1.7 units | UI and QA dominate a feature, and both repeat per codebase. Derivation below. **[inferred]** |

**Row-level assumptions.** Agents write about 90% of the code. Owner review time scales with diff size × the owner's unfamiliarity with the language. Agent wall-clock time is free. The cost of building `devscene runs … --json` in the harness (05 sizes the read side at about 1–1.5k lines, more for the act side) is **excluded from every column**: it is harness-side work, common to all options. In the shared-core column, packaging and CI equal plain native ×3: the CLI is installed by the user, so nothing extra is bundled or signed, and the CLI-version handshake test sits in the "Automated tests" row. (An earlier draft had 8 and 4.5 here with no reason given; corrected.) **[inferred]**

**Derivation of the per-feature ratios [inferred].** A later feature in the cross-platform build is split as UI 0.45, logic 0.15, tests 0.15 and QA 0.25 of one unit ("UI and QA dominate"). Each share is multiplied by that row's v1 ratio from the table above:

| Feature share (cross = 1 unit) | Native ×3 row ratio | Shared-core row ratio | 2-codebase row ratio |
|---|---|---|---|
| UI 0.45 | 15/5–17/5 = 3.0–3.4 → 1.35–1.53 | 12/5 = 2.4 → 1.08 | 9/5 = 1.8 → 0.81 |
| Logic 0.15 | 11/3 = 3.67 (incl. parity) → 0.55 | 4.5/3 = 1.5 → 0.23 | 6/3 = 2.0 → 0.30 |
| Tests 0.15 | 5/2 = 2.5 → 0.38 | 3.5/2 = 1.75 → 0.26 | 3.5/2 = 1.75 → 0.26 |
| QA 0.25 | 6/4.5 = 1.33 → 0.33 | 5.5/4.5 = 1.22 → 0.31 | 5/4.5 = 1.11 → 0.28 |
| **Per-feature ratio** | **2.6–2.8** | **≈ 1.9** | **≈ 1.65 → 1.7** |

A UI-heavier mix (UI 0.5, logic 0.2, tests 0.1, QA 0.2) gives 2.75–2.95, 1.9 and 1.7, so the ordering does not depend on the mix.

**Sensitivity of the v1 ratio (native ×3 vs cross) to ±30% in one row group [inferred]:**

| Row group changed | Same change in every column | Native column only | Cross column only |
|---|---|---|---|
| UI ±30% | 2.06–2.25× | 1.94–2.37× | 2.00–2.31× |
| Review (code rows: data, process, UI, tests) ±30% | 2.03–2.25× | 1.72–2.60× | 1.83–2.59× |
| Packaging ±30% | 2.08–2.23× | 2.03–2.27× | 2.00–2.31× |

A shared estimating error barely moves the ratio (2.0–2.3×). A one-sided error in review cost moves it to 1.7–2.6×: still well under 3× and well above the 1.6× of the shared-core variant.

How to read it:
- The owner's claim is **directionally right and numerically too high** at v1 (about 2.1–2.2× rather than 3×). It is closer to right over the product's life, because each feature costs about 2.7×. Feature drift accumulates. The usual failure mode is "Mac got it, Linux next sprint, Windows never". The Issue's rule that the app "adds no features the harness does not have" makes parity a hard requirement, which makes drift a bug rather than a choice. **[inferred]**
- Agents compress *writing*. They compress much less the three things that dominate here: **reviewing** diffs in three languages, **testing on three OSes**, and **owning three toolchains** (Xcode/notarytool, Visual Studio/Windows App SDK on its own semver cadence — WinAppSDK 2.0 shipped 2026-04-29 and 2.6.5 on 2026-11-02 [12] — and GNOME's six-monthly GTK/libadwaita cycle, with GTK 4.22 and libadwaita 1.9 in the 2026 cycle [13][14]). **[verified/inferred]**
- **Counter-argument.** The harness ships review agents (`branch-reviewer`, `skeptic-reviewer`, `layer-reviewer`) and a parity phase whose `business-parity-reviewer` checks code against a reference implementation (`plugin/agents/`, `phases.parity` in `harness.config.json`) [28]. Porting an already-reviewed SwiftUI feature to GTK/WinUI is close to the best case for agents: translation with a spec and a reference. That could cut native UI cost toward ≈ 12 O-d and parity checks toward zero, a v1 ratio of ≈ 1.9–2.0×. The limits: these reviewers are read-only, the parity reviewer checks business logic rather than UI behaviour, and no harness run can compile or run gates for WinUI, or for SwiftUI in remote runs (§2). Owner review stays the backstop, so the effect is real but smaller than "×N disappears". **[verified agents / inferred effect]**
- **The human bottleneck becomes:** (1) review throughput in the owner's weakest language, (2) machine access: a Mac is required for notarization and SwiftUI, Windows for WinUI builds and signing, and Linux for GTK, and (3) release-day coordination of three pipelines. In the cross-platform option the bottleneck is (2) only, for QA. **[inferred]**

### 2. What the DevScene harness does with each option (verified in `/Users/daniel/Work/devscene`)

| Fact | Evidence | Consequence |
|---|---|---|
| Remote runs execute on Linux only. macOS and Windows hosted runners are "Not supported". | `docs/remote-execution.md` §8 (`runs-on: ${{ vars.DEVSCENE_RUNNER \|\| 'ubuntu-latest' }}`) | A remote run cannot compile SwiftUI (needs macOS/Xcode) or WinUI 3 (needs Windows). The typecheck/test gates for those codebases cannot run in the agent's fix loop. Ordinary CI on `macos-latest`/`windows-latest` would still catch build breaks after a push, outside that loop. Remote is the app's intended repo default (Issue #1); in the harness itself `local` is still the default and remote is opt-in (`ROADMAP.md` "Cloud / CI execution"). A local run on a Mac (Seatbelt sandbox) can build SwiftUI. |
| On Windows the harness runs inside WSL2. | Issue #1 "Platforms" | Even a *local* run on the owner's Windows box is Linux-side, so WinUI 3 builds are out of reach of any harness run. |
| One preset per repo. Presets: `monorepo`, `layered-clean-arch`, `python-package`, `api-service`, `flutter`, `android-gradle`, `jvm`, `dotnet`, `apple-native`, `rust-cargo`, `ruby-bundler`, `php-composer`, `cmake-cpp`, `flat`. | `cli/src/config/model.ts` `DETECTION_PRESET_NAMES` | There is no GTK/meson/Vala preset. A GTK4 app in C/Vala falls to `flat`. gtk-rs falls to `rust-cargo`, and PyGObject to `python-package`. |
| Single `commands.typecheck` / `commands.test`. Command families are tried in a fixed order (python, go, dart, android, maven, gradle, dotnet, apple-native, cargo, …, npm, cmake), and the first hit wins, except that `SIGNAL_COMMAND_FAMILY` hoists the family of the matched preset signal to the front. | `cli/src/detect/presets.ts` `COMMAND_FAMILIES`, `SIGNAL_COMMAND_FAMILY`. Repo's own `harness.config.json` | In a polyglot repo, init wires one stack's gates. The other two need hand-written wrapper scripts that cannot all run on one OS. |
| `monorepo` is "layerless by design". Nested-app detection is advisory only ("nothing is derived from what it finds. No preset, no layer …"): it prints an `--app-dir` hint, and returns nothing when more than one child dir holds an app. | `cli/src/detect/presets.ts` `LAYERLESS_BY_DESIGN_PRESETS`. `cli/src/detect/nestedApplication.ts` | A `mac/ linux/ windows/` layout gets no layer profile from detection. The working path is the `monorepo` preset with hand-split layers and wrapper scripts, which is how the harness's own repo is configured (`monorepo`, layers `cli`/`plugin`/`general`, `commands.typecheck: bash scripts/typecheck.sh`). So the real obstacle is **which OS the gates run on**, not the preset machinery. |
| QA driver: only `web-playwright` is implemented. `mobile-maestro` and `mobile-mcp` are declared stubs. | `plugin/agents/qa-tester*.md` | The harness's interactive QA phase can drive a webview UI served in a browser (Electron/Tauri/Wails dev server) but not a SwiftUI, GTK or WinUI window. The qa-tester navigates to `base_url` (served by `commands.devServer`) and never starts the app, so outside the desktop shell there is no Tauri `invoke`, Electron preload API or Wails binding. Harness QA therefore needs a browser mode with a mocked or HTTP-backed IPC layer, in all three webview options. |

These facts turn "agents write most of the code" from roughly true into **false for two of three native codebases, inside the agent's own loop**. The harness is the owner's agent workflow, and it cannot verify that code; ordinary per-OS CI can only report breaks after the fact. **[verified + inferred]**

### 3. Agent effectiveness by language and framework

**Benchmarks by language (repo-level issue resolution):**

| Benchmark | Python | Java | TS/JS | Go | Rust | C/C++ | Notes |
|---|---|---|---|---|---|---|---|
| SWE-bench Multilingual (SWE-agent + Claude 3.7 Sonnet, 2025-05) [6][6b] | n/a | 53.5% | 34.9% | 31.0% | **58.1%** | 28.6% | 300 tasks across 9 languages and 42 repos, about 33 per language. Small samples. The primary page confirms Rust highest and C/C++ lowest; the per-language figures are from the author's post [6b]. **Older than 12 months.** |
| Multi-SWE-bench (GPT-4o row) [4][5] | n/a¹ | 11.7% | 2.2% | 2.8% | 5.9% | 7.0% | 2025 paper. The best agent on Rust was about 12%. **Older than 12 months.** |
| SWE-PolyBench third-party run [7] | 36.3% | 33.3% | TS 35.0% / JS 30.0% | — | — | — | Agent and model not named. **[secondary]** |
| Kotlin SWE-style benchmark (JetBrains, 2026-07) [8] | — | — | — | — | — | — | Claude Code + Opus 4.7: 85.7% (90/105). **[secondary, not confirmed at primary]** |
| SwiftEval (MacPaw, FORGE 2025) [9] | baseline | — | — | — | — | — | 3 of 35 code benchmarks include Swift at all (stated on the page). 41/44 models score lower on Swift than on Python HumanEval (derived by counting the Δ column; only GPT-3.5 Turbo and CodeLlama 13B/34B score higher). 2024-era models, paper Jan 2025. **Older than 12 months.** |

¹ The GPT-4o Python figure, 36.2%, is from the original SWE-bench, a different benchmark, so it is not comparable across this row.

Reading: no current benchmark covers *UI frameworks*. The language-level signal is (a) TS, Java/Kotlin, Python and Rust are well served, (b) Swift is under-measured and under-served, and (c) Dart and C# have little public agent data. Rust's strict compiler appears to help agents iterate: it scored highest in SWE-bench Multilingual. GitHub's Octoverse says typed languages "make agent-assisted coding more reliable" and cites a 2025 arXiv study in which 94% of LLM compilation errors were type-check failures [10] (the 94% figure is **[secondary]**; the Octoverse post dates from 2025-10-28, updated 2026-02-28, so it is older than 12 months). **[verified/secondary]**

**Framework-level weak spots (where agents demonstrably go wrong):**

| Stack | Corpus size (relative) | Known agent failure modes | Can the agent see the UI? |
|---|---|---|---|
| Electron (TS/React) | Very large | Few. The main-vs-renderer IPC and security defaults (contextIsolation) are sometimes wrong. An 8-week major cadence with 3 supported majors [11] means steady dependency churn, but APIs are stable. | Yes. Playwright `_electron` (experimental, Electron ≥ 21) [15], or the renderer in a browser for the harness's `web-playwright` QA, provided the preload/IPC layer is mocked or served over HTTP in browser mode (§2). |
| Tauri v2 (TS + Rust) | Large TS, medium Rust, small Tauri-v2-specific | Mixing v1 and v2: `allowlist` vs capabilities, `@tauri-apps/api/tauri` vs `/core`, fs moved to plugins. This is widely documented, and community "knowledge patch" skills exist to fix it [16][17]. **Tauri v3 is in alpha** (`tauri-v3.0.0-alpha.6`, 2026-11-06, with a CEF runtime crate) next to 2.12.5 (2026-10-21) [18], so a third API generation is coming. | Yes, via WebDriver. `tauri-driver` supports only Windows and Linux. macOS needs the WebdriverIO embedded server or the paid CrabNebula fork [19]. The frontend also runs in a browser for Playwright, provided `invoke` is mocked or served over HTTP in browser mode (§2). |
| Wails (TS + Go) | Large TS, large Go, small Wails | **v3.0.0 went stable 2026-10-26** and v3.1.0 on 2026-11-01, while v2.17.x continues [18b]. Most model knowledge is v2, so expect Tauri-style version confusion for at least a year. | Yes. The frontend is a web page; harness QA needs the Wails bindings mocked in browser mode (§2). |
| Flutter (Dart) | Medium. Dart is 4.9% usage in SO 2026. | Mostly OK for widgets. Desktop-specific plugins (process, tray, file watching) are thinner. | Partly: `integration_test` and golden screenshots. No harness driver. |
| Compose Multiplatform desktop (Kotlin) | Large Kotlin, small Compose-desktop | Android-Compose idioms leak into desktop. The desktop APIs (window, tray, file dialogs) are a small share of the corpus. CMP 1.12.2 stable and 1.13 in beta [18c]. | Compose UI test framework. No harness driver. |
| SwiftUI/AppKit (macOS) | Medium, Apple-only | Superseded APIs: `ObservableObject` vs `@Observable`, `NavigationView`, `foregroundColor`. Swift 6 concurrency errors. Practitioners report models default to older idioms [20]. macOS-specific SwiftUI is a small slice of a mostly-iOS corpus. | **Yes, in Xcode 26.3+**: Claude Agent/Codex capture Previews over MCP, on macOS 26 only [21] **[secondary]**. This is the one native UI with first-party agent preview tooling. |
| GTK4/libadwaita (C/Vala/Rust/Python) | Small | GTK3→4 API breaks (event controllers, `GtkFileChooser` deprecations). A six-monthly libadwaita widget churn, e.g. 1.8 replaced `GtkShortcutsWindow` with `AdwShortcutsDialog` [14]. gtk4-rs bindings at 0.11.x [18d]. | No first-party preview/inspection tooling for agents. AT-SPI automation and generic computer-use agents only. |
| WinUI 3 (C#/XAML) | Small for WinUI 3 specifically, large for C#/WPF | Agents mix up UWP, WPF and WinUI XAML namespaces and APIs. Windows App SDK went from 1.x to 2.x semver in 2026 [12]. | No first-party preview/inspection tooling for agents (UI Automation–based MCP servers and computer-use agents exist). It also **cannot build on Linux**, so it is invisible to every harness run (§2). |

### 4. Hybrid options

| Hybrid | How | Fit for this app | Cost (from §1) |
|---|---|---|---|
| **CLI-as-core + thin UIs** | Each UI spawns `devscene runs … --json` (Issue item 7). On Windows this is `wsl.exe devscene …`. The core is the harness's own Node/TS. | Best fit. Node is already a harness prerequisite, and it works for any UI tech, including a cross-platform one. The logic stays in the harness (the Issue's stated goal). Versions can still differ per repo until `registry.json` gets a schema field (see 05). Users with no local harness setup are served by an app-side, read-only GitHub read-model through `gh` (05 shape d), which every option needs anyway. | Native ×3 drops to ≈ 1.6× (44/27). Cross-platform also benefits. |
| Rust core + UniFFI | One Rust crate, with generated Swift/Kotlin/Python bindings (UniFFI [22]) and C# via NordSecurity's `uniffi-bindgen-cs` (v0.12.0, 2026-11-09, 191 stars) [23]. The GTK UI in gtk-rs uses the crate directly. | Technically sound, and the most career-relevant core. If it re-implements local run logic (registry parsing, branch derivation, pause/resume), it **duplicates** what the harness owns (per-repo bash behind `devscene runs --json`, per 05), which is the drift Issue item 7 wants to avoid. Limited to the app-side layer (`gh` read-model, transport, watching), it does not. The C# binding is a small third-party project. | ≈ 1.7× plus a parity burden against the harness **[inferred, judgement, not a §1 output]**. |
| Go core as sidecar/daemon over IPC | A local daemon with a JSON-RPC socket. Native UIs are clients. | Workable, but it adds a third runtime to ship and sign per OS. Same duplication problem as Rust. | ≈ 1.75× **[inferred, judgement]**. |
| Kotlin core (KMP) + native UIs | Shared KMP module exported to Swift. JVM for Linux/Windows UIs. | Strong for mobile, awkward for desktop GTK/WinUI clients. See 02 for KMP itself. | ≈ 1.8× **[inferred, judgement]**. |
| **Two targets: native macOS + Linux build reused on Windows via WSLg** | Ship the Linux build (GTK or any Linux bundle) *inside* WSL2. WSLg gives it Start-menu entries, taskbar pinning and alt-tab on Win10 19044+/Win11 [24]. | Removes `wsl.exe` and `\\wsl$` interop entirely, because the app runs next to the harness. It **conflicts with the Issue's distribution plan**: there is no signed Windows bundle, install happens inside a distro, and it depends on the vGPU driver. Cross-ref 04. | ≈ 1.3–1.5× **[inferred]**: the §1 2-codebase column (40) minus most of the Windows interop row (4 → ~1) and some Windows packaging (6.5 → ~5) is ≈ 36, or 1.33×; WSLg install, docs and QA uncertainty make the upper end 1.5×. |
| Native macOS + one cross build for Linux/Windows | SwiftUI on Mac. Tauri/Electron for the rest. | Only if Mac-native feel is a product requirement. Two UI stacks, two release pipelines. The SwiftUI part is still invisible to remote harness runs. | ≈ 1.5× (§1 2-codebase column, 40/27). |

### 5. Career value

**Market data (late 2026):**

| Language | SO 2026 used / admired / desired [2] | TIOBE rank, Nov 2026 [3] | US job-posting share, Jan 2025–Mar 2026 [25] | JetBrains Promise Index 2025 [26] (top-growth group; ranks [secondary] [26c]) | Other |
|---|---|---|---|---|---|
| TypeScript | 43.8% / 53.0% / 27.5% | 41 (TIOBE counts search hits, so TS is undercounted) | 8% (plus JavaScript 19%) | **top group** (#1 [secondary]) | **#1 on GitHub by monthly contributors**, 2.64M, +66.6% YoY [10] |
| Python | 58.0% / 50.6% / 33.4% | 1 | **46%** | not named in the primary's top group (#3 [secondary]) | #1 for AI repos [10] |
| Rust | 18.0% / **67.4%** / 26.3% | 11 (left the top 10 in Nov 2026) | not in the top 10 (< 5%) | **top group** (#2 [secondary]) | Most admired in SO 2025 (72%) [1]. RedMonk Jan 2026 about #20 [27] |
| Go | 16.5% / 49.5% / 17.7% | **10** (back into the top 10) | 5% | **top group** (#4 [secondary]) | Only predicted grower that actually grew (JetBrains migration study, 2026-08) [26b] |
| Kotlin | 10.8% / 43.1% / 9.4% | 33 | not in the top 10 | — | Java→Kotlin is the third-largest migration flow [26b] |
| Swift | 5.9% / 48.5% / 5.3% | 18 | not in the top 10 | — | Apple-only GUI value |
| C# | 27.1% / 50.0% / 16.5% | 5 | 9% | — | +22% contributors YoY on GitHub [10] |
| C++ | 24.3% / 45.8% / 15.8% | 4 | 11% | — | |
| Dart | 4.9% / 42.3% / 4.1% | 20 | not in the top 10 | — | Almost entirely Flutter |

Role pay (SO 2026, global medians, USD): back-end $85.3k, mobile $84.3k, **desktop/enterprise $80.0k** (n = 559), full-stack $79.6k, front-end $70.3k [2b]. Role pay differs little: desktop is about 6% below back-end and above full-stack. Career value comes mainly from the *language*, not from desktop-GUI toolkit skill. **[verified]**

**Does the framework give transferable exposure?**

| Option | What the owner actually writes | Transferable? |
|---|---|---|
| Electron | TS/React (UI) and Node (main process) | **High.** It is the same skill as web front-end and Node back-end work, and the same language as the harness CLI. |
| Tauri v2 | About 80–90% TS frontend. Rust in `src-tauri` for commands, process spawning and file watching. | **High (TS) + moderate (Rust)** if the app-side layer lives in Rust commands: the `gh` read-model, the `devscene`/`wsl.exe` process transport, log tailing and file watching. That layer exists in every option (05), and it does not conflict with Issue item 7: only local run logic (registry parsing, branch derivation, pause/resume) belongs to the harness CLI. No Node sidecar is needed (05). Rust exposure is low if that layer is done from JS through `tauri-plugin-shell`/`plugin-fs`. |
| Wails v3 | Mostly TS frontend, with Go bindings | High (TS) + moderate (Go, which is the more in-demand back-end language). |
| Compose MP desktop | Kotlin end to end | Moderate. Kotlin's market is Android and JVM back-end. Desktop Compose is niche. |
| Flutter | Dart end to end | Low outside Flutter mobile. |
| SwiftUI / WinUI 3 / GTK4 | Swift / C# XAML / C, Vala, Rust or Python | Low per stack (platform-locked GUI skills). C# has a broad market, but WinUI in particular does not. |
| Python GUI (PySide6, Toga, Flet) | Python | Python is the top language, but desktop-GUI Python is a niche. The value comes from Python, not from the GUI. |

**Sibling products** (ragscene, langscene, tracescene, scenewise) are, by their names, RAG, LLM and tracing tools. Those ecosystems are Python- and TS-centric. A TS UI shell with a JSON-CLI core is the pattern most likely to carry over. **[inferred]**

### 6. Recommendation matrix

Scale: ●●● good · ●● medium · ● poor. Effort is v1 owner-days relative to cross-platform (§1). Ratios marked † are §1 model outputs. All other ratios are judgement calls **[inferred]**, not model outputs; their basis is given below the table.

| Option | Effort (v1) | Maintenance per feature | Agent-friendliness (corpus, API stability, harness gates + QA) | Career value | Reuse for sibling products |
|---|---|---|---|---|---|
| **Electron (TS)** | ●●● 1.0× † | ●●● 1× † | ●●● Largest corpus. Linux-buildable. `web-playwright` QA works with a browser mode (§2). | ●●● TS | ●●● Same language as the harness CLI |
| **Tauri v2 (TS + Rust)** | ●●● ≈ 1.05× | ●●● ≈ 1.1× (v3 migration ahead) | ●● v1/v2 confusion, v3 alpha. Linux-buildable. Web QA works with a browser mode (§2). | ●●● TS + Rust | ●●● |
| Wails v3 (TS + Go) | ●●● ≈ 1.05× | ●● ≈ 1.1× (v3 is two weeks old) | ●● Agents know v2. Web QA works with a browser mode (§2). | ●●● TS + Go | ●● |
| Compose MP desktop (Kotlin) | ●● ≈ 1.2× | ●● ≈ 1.2× | ●● Kotlin good, desktop Compose thin. No harness QA. | ●● | ●● |
| Flutter desktop (Dart) | ●● ≈ 1.2× | ●● ≈ 1.2× | ●● Medium corpus. No harness QA. | ● | ● |
| Avalonia (C#) | ●● ≈ 1.2× | ●● ≈ 1.2× | ●● Builds on Linux. No harness QA. | ●● | ● |
| Native ×3 + CLI core | ● ≈ 1.6× † | ● ≈ 1.9× † | ● WinUI unbuildable by the harness, SwiftUI local-only, GTK has no preset | ● | ● |
| Native mac + Linux build on Windows via WSLg | ●● ≈ 1.3–1.5× (§4) | ●● ≈ 1.7× | ● (SwiftUI part) / ●● | ● | ● |
| Native mac + Tauri/Electron for Linux+Win | ●● ≈ 1.5× † | ●● ≈ 1.7× † | ●● | ●● | ●● |
| **Fully native ×3** | ● ≈ 2.1–2.2× † | ● ≈ 2.6–2.8× (≈ 2.7×) † | ● | ● | ● |

Basis of the judgement ratios **[inferred]**:
- **Tauri / Wails ≈ 1.05× v1.** The data and process rows (7 O-d) move to Rust/Go, which the owner reviews more slowly: +20% on 7 O-d ≈ +1.4 O-d, giving 28.4/27 ≈ 1.05×. Per feature ≈ 1.1×: the same review premium on the logic share, plus an allowance for the v2→v3 (Tauri) or v2-trained-agent (Wails) churn.
- **Compose / Flutter / Avalonia ≈ 1.2×.** The UI row is in a less familiar, non-web toolkit with a thinner desktop corpus: +50% on 5 O-d = +2.5. No harness QA driver means about +1 O-d of manual QA. (27 + 3.5)/27 ≈ 1.13×, rounded up to ≈ 1.2× for thinner desktop plugins (process, tray, file watching). The same premiums on a feature give ≈ 1.2×.
- **WSLg per feature ≈ 1.7×.** It has the same two UI codebases as the 2-codebase column; removing the Windows interop affects v1, not a typical feature.

**Pick:** Tauri v2 or Electron, with local run logic behind `devscene runs … --json` and the app-side layer (the `gh` read-model, the process transport including `wsl.exe`, log tailing, file watching) in the app. The tie-break still holds after the 05 correction, with a narrower Electron side: Electron no longer reuses harness code (per 05, integration is roughly neutral), so its advantages are agent-friendliness, the largest corpus, the most stable APIs and one language across the CLI, the app and the contract types. Tauri's career advantage is now cleaner: the Rust app-side layer is needed in every option and conflicts with nothing in Issue item 7. 02 (performance and bundle size) and 04 (WSL process and file access from Rust vs Node) should break the tie.

## Answers to the owner's questions

- **Q2 — Is cross-platform worth it versus native? Is "N natives = N × time" right?** Cross-platform is worth it. Three native apps cost about 2.1–2.2× the owner's time for v1 (57–59 vs 27 owner-days) and about 2.6–2.8× (≈ 2.7×) per later feature, not 3× and not "free with agents". The harness's review and parity agents could pull v1 toward ≈ 1.9–2.0× at best. The deciding factor is that the owner's own agent workflow, the DevScene harness, runs on Linux. It cannot build or test WinUI 3 at all, can build SwiftUI only in a local Mac run, has no GTK preset, and has no QA driver for any native window. With native, agents write code that the harness cannot verify, so the owner becomes the compiler, the tester and the release engineer for three stacks. (§1, §2)
- **Q3 — Career value.** TypeScript is the strongest single bet: #1 on GitHub, in JetBrains' top-growth group, and transferable to web and back-end work. Rust is the best second language for growth and prestige (most admired, in JetBrains' top-growth group). Go is the best second language for job count (5% of US postings, TIOBE top 10). Tauri gives TS plus some Rust and Wails gives TS plus some Go, but only if the owner puts real logic on the Rust or Go side. The natural place is the app-side layer: the `gh` read-model, the process transport including `wsl.exe`, log tailing and file watching. That layer exists in every option and does not conflict with the harness CLI, which keeps only the local run logic. Swift, Dart and WinUI/GTK skills are platform-locked. Python is valuable as a language but weak for desktop GUIs. (§5)
- **Q7 — Momentum, from the agent angle only.** Tauri v3 is in alpha and Wails v3 just shipped. Both bring a period in which agents emit last-generation APIs. Plan for an AGENTS.md or conventions note that pins the major version. (§3)

## Risks and open questions

- The cost model is an informed estimate, not measured data. Its v1 ratio stays at 1.9–2.4× under a ±30% change in any one row group, and at 1.7–2.6× if review cost is misjudged on one side only (sensitivity table, §1). The absolute O-d values are not robust. Validate by timing a spike: build one screen (the board) in the cross-platform pick and log owner hours.
- Benchmarks by language are mostly from 2025 and use older models (Claude 3.7, GPT-4o). **They are older than 12 months.** The direction (Swift weaker, Rust and Java strong, C/C++ weakest) is consistent, but magnitudes on 2026 models are unknown. No benchmark measures UI-framework code.
- The harness could add macOS/Windows remote runners or a desktop QA driver later. That would weaken §2. Checked 2026-11-12: `ROADMAP.md` plans no macOS/Windows runner and no desktop QA driver. Only mobile QA drivers are open.
- Per 05, the GitHub-side read-model lives in the app in any case, for users with no local setup. The open choice is only its language (TS vs Rust).
- Under Tauri, the owner must decide explicitly whether the app-side layer (the `gh` read-model, the process transport, log tailing, file watching) is written as Rust commands, which gives the career value, or from JS through Tauri plugins, which is faster for agents. Either way, local run logic stays in the harness CLI.
- The webview options need a browser mode with a mocked or HTTP-backed IPC layer for harness QA (§2). It is a v1 architecture requirement and adds a little cost to all three equally; §1 does not model it.
- TIOBE's November 2026 ratings, as fetched, look low for C# (3.39%) compared with prior months. Only ranks are used here.
- No 2026 JetBrains Developer Ecosystem results were found. Its 2025 report and the 2026-08 migration post are used instead.

## Sources

1. https://survey.stackoverflow.co/2025/technology/ — Rust most admired 72% (2025) — accessed 2026-11-12
2. https://survey.stackoverflow.co/2026/technology/data — 2026 usage/admired/desired by language (n = 14,099 for this question) — accessed 2026-11-12
   2b. https://survey.stackoverflow.co/2026/work/data — median salary by developer role — accessed 2026-11-12
   2c. https://stackoverflow.blog/2026/10/06/the-results-of-the-2026-developer-survey-are-here/ — survey released 2026-10-06; Claude Code 66% among agent users — accessed 2026-11-12
3. https://www.tiobe.com/tiobe-index/ — November 2026 ranks (Go #10, Rust #11, Swift #18, Dart #20, Kotlin #33, TS #41) — accessed 2026-11-12
4. https://arxiv.org/pdf/2504.02605 — Multi-SWE-bench per-language resolved rates (2025, >12 months old) — accessed 2026-11-12
5. https://neurips.cc/media/neurips-2025/Slides/121692.pdf — best agent about 12% on Rust in Multi-SWE-bench — accessed 2026-11-12
6. https://www.swebench.com/multilingual.html — SWE-bench Multilingual primary page: 300 tasks, 9 languages, 42 repos; Claude 3.7 Sonnet + SWE-agent 43%; Rust highest, C/C++ lowest (2025, >12 months old) — accessed 2026-11-12
   6b. https://kabirk.com/multilingual — SWE-bench Multilingual per-language rates, 2025-05-06 (>12 months old) — accessed 2026-11-12
7. https://github.com/EuniAI/Polybench-experiment — third-party SWE-PolyBench per-language run [secondary] — accessed 2026-11-12
8. https://yage.ai/share/jetbrains-kotlin-benchmark-reframe-en-20260727.html — JetBrains Kotlin agentic benchmark figures [secondary] — accessed 2026-11-12
9. https://research.macpaw.com/projects/swifteval — SwiftEval: Swift vs Python gap (41/44 derived from the Δ column), benchmark coverage (Jan 2025, >12 months old) — accessed 2026-11-12
10. https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/ — TS #1, typed languages and agents, the 94% type-error figure (GitHub citing a 2025 arXiv paper, [secondary]), C# growth (2025-10-28, updated 2026-02-28, >12 months old) — accessed 2026-11-12
11. https://www.electronjs.org/docs/latest/tutorial/electron-timelines — 8-week majors, 3 supported — accessed 2026-11-12
12. https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/release-notes/windows-app-sdk-2-0 — WinAppSDK 2.0.1 on 2026-04-29, 2.6.5 on 2026-11-02 — accessed 2026-11-12
13. https://phoronix.com/news/gtk-4.22-released — GTK 4.22 released [secondary] — accessed 2026-11-12
14. https://en.linuxadictos.com/Libadwaita-1-is-ready-for-Gnome-8-with-a-new-shortcut-dialog-and-CSS-support..html — libadwaita 1.8 replaces GtkShortcutsWindow [secondary] — accessed 2026-11-12
15. https://playwright.dev/docs/api/class-electron — Playwright Electron support experimental, v21+ — accessed 2026-11-12
16. https://scour.ing/@matmat/p/https://dev.to/aierastack/why-boring-tech-might-be-better-for-ai-coding-agents-3mle — agents mixing Tauri v1/v2 [secondary] — accessed 2026-11-12
17. https://skills.sh/openaec-foundation/tauri-2-claude-skill-package/tauri-impl-migration — common v1 imports generated for v2 [secondary] — accessed 2026-11-12
18. https://github.com/tauri-apps/tauri/releases — tauri-v3.0.0-alpha.6 (2026-11-06), v2.12.5 (2026-10-21) — accessed 2026-11-12 (gh api)
    18b. https://github.com/wailsapp/wails/releases — v3.0.0 (2026-10-26), v3.1.0 and v2.17.1 (2026-11-01) — accessed 2026-11-12
    18c. https://github.com/JetBrains/compose-multiplatform/releases — 1.12.2 stable, 1.13.0-beta02 (2026-11-04) — accessed 2026-11-12
    18d. https://github.com/gtk-rs/gtk4-rs/releases — 0.11.5 (2026-09-20) — accessed 2026-11-12
19. https://v2.tauri.app/develop/tests/webdriver/ — tauri-driver Windows/Linux only; macOS via WebdriverIO embedded server or paid fork — accessed 2026-11-12
20. https://cocoawithlove.com/blog/llms-twelve-months-later.html and https://tessl.io/registry/dpearson2699/swift-ios-skills/files/skills/swiftui-patterns/references/deprecated-migration.md — LLMs default to superseded SwiftUI idioms [secondary] — accessed 2026-11-12
21. https://infoq.com/news/2026/02/xcode-26-3-agentic-coding — Xcode 26.3 agents, MCP, Preview capture, macOS 26 only [secondary] — accessed 2026-11-12
22. https://github.com/mozilla/uniffi-rs — UniFFI active (pushed 2026-11-09) — accessed 2026-11-12
23. https://github.com/NordSecurity/uniffi-bindgen-cs — C# bindings v0.12.0 (2026-11-09), 191 stars — accessed 2026-11-12
24. https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps — WSLg Start menu, taskbar, requirements (updated 2026-06-02) — accessed 2026-11-12
25. https://oxylabs.io/press-area/most-in-demand-programming-languages — US posting shares, about 800k postings, Jan 2025–Mar 2026 — accessed 2026-11-12
26. https://blog.jetbrains.com/research/2025/10/state-of-developer-ecosystem-2025/ — Language Promise Index: "TypeScript, Rust, and Go boast the highest perceived growth potential", no numeric ranks (2025, about 13 months old) — accessed 2026-11-12
    26c. https://awsinsider.net/articles/2025/10/20/aws-swamps-gcp-azure-among-developers-in-ecosystem-report.aspx — numeric Promise Index ranks TS 1, Rust 2, Python 3, Go 4, C++ 5 [secondary] — accessed 2026-11-12 (via review)
    26b. https://blog.jetbrains.com/research/2026/08/programming-language-migration/ — Go the only predicted grower that grew; Java→Kotlin flow — accessed 2026-11-12
27. https://redmonk.com/sogrady/2026/04/14/language-rankings-1-26/ — RedMonk Jan 2026 ranking — accessed 2026-11-12
28. Local: `/Users/daniel/Work/devscene/docs/remote-execution.md` §8; `cli/src/config/model.ts` (`DETECTION_PRESET_NAMES`); `cli/src/detect/presets.ts` (`COMMAND_FAMILIES`, `LAYERLESS_BY_DESIGN_PRESETS`); `cli/src/detect/nestedApplication.ts`; `plugin/agents/qa-tester*.md`; `plugin/agents/business-parity-reviewer.md`, `branch-reviewer.md`, `skeptic-reviewer.md`; `harness.config.json`; `ROADMAP.md` ("Cloud / CI execution", "Mobile QA drivers") — harness runner, preset, QA-driver, review-agent and roadmap facts — read 2026-11-12
29. Local: `docs/product-startup-research/05-harness-integration.md` (reviewed) — run logic is per-repo bash, no CLI library, no Node sidecar, app-side `gh` read-model, Windows via WSL — read 2026-11-12
