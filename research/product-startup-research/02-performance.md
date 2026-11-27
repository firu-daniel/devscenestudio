# 02 — Performance: cross-platform vs native
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **For this app, the differences that matter are bundle size and idle RAM. Runtime speed does not matter.** DevScene Studio waits on `gh` (≈0.5–0.6 s per network call, measured), `git` (≈8 ms) and the `devscene` CLI (≈70 ms start with a warm file cache, measured). Every candidate renders a 3-column board of a few hundred cards plus a log tail at 60 fps once the list is virtualized. Process I/O is the bottleneck in every stack, not the UI toolkit. [verified locally + inferred]
- **Download size splits the candidates into three groups.** System-webview and native-UI apps (Tauri, Wails, Electrobun on the system webview, Neutralino, Slint/egui/iced, SwiftUI/GTK4/WinUI 3) ship **≈1–20 MB**. Self-drawn runtimes (Flutter, Avalonia + NativeAOT, Compose on a jlink'd JRE, PySide6) and Deno Desktop, which uses the system webview but ships the Deno runtime (111 MB measured [2]), ship **≈20–150 MB**. Engines that bundle Chromium (Electron, Electrobun with CEF, and Tauri 3 with CEF, which is [inferred] and alpha only) ship **≈250–420 MB unpacked** (≈90–130 MB compressed installer, [inferred]). This is the clearest measurable gap. Users notice it once, at download and update time. [secondary: Elanis CI benchmark, Better Stack, Hopp]
- **Idle RAM.** A system-webview app (Tauri/Wails) uses ≈90–170 MB. Electron uses ≈130–600 MB (RSS sums; ≈80–110 MB by free-memory delta). A JVM Compose window uses ≈100–150 MB. Native and Rust-native toolkits use ≈20–60 MB. Every public benchmark measures RAM differently, and results disagree by 2–4×. One example: Elanis' CI puts Tauri on Windows *above* Electron. On a 16 GB dev machine that also runs `claude`, Node and an IDE, a 200 MB difference is **noise**. On 8 GB laptops it is a reputational issue, not a functional one. [secondary + inferred]
- **Cold start.** Electron and Tauri start in ≈0.2–0.6 s on Windows and Linux. Compose/JVM without AOT starts in ≈1.3–2.0 s. With the JDK 25 AOT cache (Compose Multiplatform 1.13, now in beta) that drops to ≈0.4–0.65 s. Flutter release builds are not measured in any trustworthy public source. Native apps start in under 0.2 s. In a board app that the user opens a few times a day, the only noticeable gap is the **non-AOT JVM's ~2 s**. [Compose figures verified: #5644; Electron/Tauri secondary: 1, 2; native secondary/inferred]
- **Idle CPU and battery depend on how the app is written, not on the framework.** The real risks are polling `gh` on a timer, which drains the GitHub rate limit and wakes the CPU, and watching `\\wsl$` paths from Windows, which does not work reliably. Any stack can idle at about 0% if it uses event-driven watchers with backoff. Electron apps that peg the CPU at idle (Claude Desktop, WhatsApp reports) are bugs in those apps. [secondary + inferred]
- **WSL2: performance is the same for every framework.** `wsl.exe --exec /bin/true` costs ≈0.1 s per spawn (a single third-party report, method not stated). Windows file watchers on `\\wsl$` / `\\wsl.localhost` paths are unreliable (WSL issue #4581, bot-closed without a fix; Zed's warning). Cross-OS file access over 9P is markedly slower than native, and Microsoft recommends against it; no trustworthy multiplier exists for Windows→`\\wsl$` reads. The fix is architectural and works in every framework: keep **one long-lived process inside WSL** (for example a `devscene runs watch --json` stream), not one `wsl.exe` per poll. [secondary + inferred]
- **Kotlin Multiplatform works, but only as JVM desktop.** Compose Multiplatform for desktop runs **only on the JVM** (verified in the docs). JetBrains has no Kotlin/Native desktop UI target on its roadmap (verified, roadmap of Aug 2026). The cost is a bundle of ≈60–130 MB with a jlink'd JRE, idle RAM of ≈100–150 MB, and a start of ≈1.3–2 s, or ≈0.4–0.65 s with AOT. That is roughly on par with Electron and worse than Tauri. It is fine for this app. GraalVM native-image (through the third-party Nucleus plugin) claims ≈0.2 s and ≈30 MB for a hello-world, but it is not officially supported. [Compose JVM-only, roadmap, start times verified; bundle and RAM secondary; Nucleus vendor]
- **Bottom line:** performance does **not** decide between Electron, Tauri, Wails, Compose/JVM, Flutter or Avalonia for this app. It argues only (a) mildly against Electron and Electrobun-with-CEF on download size and "bloat" perception, and (b) against using a JVM without the AOT cache. On Windows (WebView2) and Linux (WebKitGTK, where CEF may be needed) the gap between system-webview stacks and Electron narrows. Choose on dev effort (03), OS integration (04), CLI-code reuse and career value.

## Scope

This file covers measured or estimated bundle size, RAM, cold start, idle CPU and battery, list and log rendering, and the cost of spawning and streaming child processes (including through `wsl.exe`). It also covers Kotlin Multiplatform, Compose Multiplatform, Kotlin/Native and GraalVM in detail.
Deferred: dev effort and the "N native codebases" cost (see 03), OS-integration blockers such as WSL path handling, signing and tray (see 04), licences and money, momentum and deprecation, and career value (other files). Version and momentum facts appear here only where they change a performance number.

## Findings

### 1. Versions current on 2026-11-12 (checked via GitHub releases)

| Framework | Current stable (pre-release) | Note for perf |
|---|---|---|
| Electron | 45.3.1 (46 alpha) | Chromium bundled in every app [verified] |
| Tauri | 2.12.5, 2026-10-21 (3.0.0-alpha.6; `tauri-runtime-cef` 3.0.0-alpha.7) | Tauri 3 (alpha since 2026-09-13, no stable date) can bundle Chromium (CEF), which removes the size advantage when used. GitHub's "Latest" badge sits on the alpha [verified: releases] |
| Wails | v2.17.1 / **v3.1.0** (released 2026-11-01) | System webview [verified] |
| Electrobun | 2.0.6 (2.0.7-beta.12) | System webview by default on all three OSes, CEF opt-in per platform (`bundleCEF`) [verified: releases + docs] |
| Compose Multiplatform | 1.12.2 (1.13.0-beta02 adds AppCDS/AOT) | JVM only on desktop [verified] |
| Flutter | 3.50 | Skia/Impeller self-drawn [verified: archive page] |
| Avalonia | 12.1.6 | Skia self-drawn, NativeAOT supported [verified] |
| Slint | 1.18.1 | Native-compiled, small RAM [verified: releases] |

### 2. Benchmarks found and how far to trust them

| Source | Who / when | Setup | Trust |
|---|---|---|---|
| Elanis `web-to-desktop-framework-comparison` [1] | Open-source repo. Re-run on GitHub CI, last update 11/2026 | Empty app. Electron, Tauri, NW.js, Wails, NodeGui, Neutralino, Flutter, MAUI. Win/macOS/Linux | **Medium for size, low for RAM and start.** It runs on CI VMs without a GPU. Tauri's ≈30 s Linux start is clearly a headless WebKitGTK artifact. The RAM method (sum of processes, or the free-memory delta) double-counts shared pages. Flutter has release numbers on Windows only (Debug elsewhere). No versions are pinned. |
| Better Stack: Tauri vs Electron vs Deno Desktop vs Electrobun [2] | Blog, ≈mid-2026 (mentions Deno 2.9) | The same screen-recorder app built in 4 stacks. macOS. Median of 10 launches. Idle RAM from Activity Monitor | **Medium.** A real app, not hello-world. One OS, versions not stated. Electrobun was forced onto CEF. |
| Hopp: Tauri vs Electron [3] | Blog, 2025-07 | Demo app, MacBook Pro, N=1, 6 windows | **Low–medium.** Older than 12 months, single run. |
| JetBrains PR #5644 (Compose AppCDS/AOT) [4] | JetBrains engineer, 2026-07 | A small demo app. M1 Ultra and Dell Precision. Cold and hot start, split by phase | **High** for Compose start-time deltas. The baseline app is small. |
| Nucleus README [5] | Third-party plugin author, 2026 | Hello-world Compose on GraalVM native-image, Windows 11 | **Low** (vendor claim, hello-world) |
| Electrobun site and docs [6] | Vendor | ≈1 MB hello-world on the system webview; no start or RAM figures | **Low** (marketing, hello-world) |
| Own measurements (this file) | 2026-11-12, Apple M4, macOS 15 (Darwin 24.6), Node 22.23, gh 2.100, git 2.50 | Spawn cost, gh latency, devscene CLI start, RSS of installed apps | **High for this machine**, macOS only |

**A hello-world is not representative** on any of these measures except bundle size. RAM grows with a JS framework (React/Svelte), router, state library, fonts and icons. For Electron that adds about +30–80 MB to the renderer [inferred]. A JVM's RAM is set mostly by heap sizing (`-Xmx`), not by the UI. No benchmark found covers a list of several hundred items or a log tail.

### 3. Comparison table (best available numbers; ranges reflect disagreement between sources)

Sizes are unpacked app bundles unless marked "installer". RAM is the sum of the app's processes at idle with one window.

| Stack | Bundle (unpacked) | Idle RAM, small UI | Cold start (release) | Idle CPU | Sources / confidence |
|---|---|---|---|---|---|
| **Electron** | 244–373 MB (≈270 MB macOS arm64, ≈290 Linux, ≈370 Win in CI) | 128 MB (Better Stack, macOS) to ≈280–600 MB (CI sums); GitHub Desktop (Electron 44) idles at **≈170–210 MB RSS across 4 processes** on my M4 (two snapshots) | 0.19–0.43 s (CI), 0.27 s (Better Stack) | ≈0% if written well. Chromium throttles background timers | [1][2][3] [secondary]; own [verified locally] |
| **Electrobun** | ≈1 MB hello-world claimed (vendor, system webview). **418 MB** with CEF | No vendor or independent system-webview figure. 208 MB with CEF | No system-webview figure. 773 ms with CEF | No data | [2][6] [secondary / vendor] |
| **Deno Desktop** (Deno 2.9+, system webview) | 111 MB (real app, macOS; ships the Deno runtime) | 98 MB | 242 ms | No data | [2] [secondary]; maturity and dev effort: see 01 and 03 |
| **Tauri 2** (system webview) | 3–8.6 MB hello-world. 57 MB real app | 88–109 MB macOS. ≈94 MB Linux. ≈312 MB Windows (CI; WebView2 shares processes with Edge, which makes RSS sums noisy) | 0.31 s macOS (Better Stack). 0.6 s Windows (CI) | ≈0% | [1][2][3] [secondary] |
| **Wails v2/v3** | ≈8–11 MB | ≈92–101 MB macOS. ≈330–360 MB Win/Linux (CI, noisy) | 0.26–0.57 s Win/Linux (CI) | ≈0% | [1] [secondary] |
| **Neutralino** | ≈2–3 MB | High and inconsistent in CI | ≈0.35 s Linux | — | [1] |
| **Flutter desktop** | ≈25 MB Windows (CI). Expect ≈40–60 MB on macOS [inferred] | Windows release (CI): ≈377 MB RSS sum, ≈86 MB free-memory delta (same caveats as the other CI rows). No macOS/Linux release figure | Release ≈2.0 s on Windows in CI. Possibly inflated by software rendering on the GPU-less VM [inferred], but Electron, Tauri and Wails start in 0.2–0.7 s on the same VMs | ≈0% when idle (draws only on change) | [1] [secondary / inferred] |
| **Compose Multiplatform (JVM)** | ≈60–130 MB with a jlink'd JRE. ≈200–300 MB with `includeAllModules` [anecdotal forum] | ≈100–150 MB for hello-world (JVM + Skia). More if `-Xmx` is not capped | **1.36 s Win / 2.0 s macOS** without AOT. **0.65 s Win / 0.42 s macOS** with JDK 25 AOT | ≈0% at idle. JIT warm-up costs some CPU in the first seconds | [4] [verified]; forum [secondary] |
| **Compose + GraalVM native-image** (Nucleus) | Single binary, size unstated (≈50–80 MB [inferred]) | ≈30 MB hello-world (vendor). No real-app figure | ≈0.2 s hello-world (vendor) | — | [5] [vendor] |
| **Avalonia 12** (NativeAOT) | ≈18 MB (community template), ≈30–60 MB realistic [inferred] | ≈20 MB claimed (template) | Sub-second. NativeAOT is 2–4× faster than JIT .NET [secondary] | ≈0% | [7] [secondary] |
| **Qt / PySide6** | 30–120 MB with PyInstaller onedir. C++ Qt Widgets ≈15–40 MB [inferred] | ≈40–80 MB for PySide6 [inferred]. C++ Qt ≈20–40 MB [inferred] | onedir ≈1–2 s; onefile ≈5 s (one report) | ≈0% | [8] [secondary / inferred] |
| **Slint / iced / egui** | ≈5–20 MB [inferred] | ≈20–60 MB with wgpu/GL [inferred; Xilem issue cites ≈50 MB as typical for wgpu Rust GUIs] | <0.3 s [inferred] | egui repaints only on input or animation, so it idles at zero [secondary] | [9][10] |
| **Native** (SwiftUI/AppKit, GTK4, WinUI 3) | macOS Notes.app is 15 MB. A SwiftUI app is ≈3–15 MB [inferred]. WinUI 3 self-contained ≈50–150 MB, framework-dependent small [inferred] | ≈30–70 MB (Notes.app idles at 61 MB on my M4) | 0.1–0.2 s (WinUI 3 NativeAOT empty window ≈0.09–0.18 s, one informal test) | Lowest; App Nap etc. are automatic | own [verified locally]; [11] [secondary] |

How to read the RAM column: on macOS, RSS summed over Chromium or WebKit helper processes over-counts shared memory. The CI "free-memory delta" table in [1] (release builds) gives Electron ≈80–110 MB and Tauri ≈14–190 MB: 76 MB macOS, 14 MB Linux (unreliable, as that build takes 30 s to start), and **187 MB on Windows, higher than Electron's 110 MB**. On macOS and Linux Tauri uses less, by roughly 1.5×. On Windows, WebView2 removes the advantage. **The 10× claims are not supported.** [secondary + inferred]

### 4. Cold start: what the user experiences

- Below ≈0.5 s an app feels instant. From 1 to 2 s users notice it but accept it for an app they open a few times a day. [inferred]
- **For this app, the first data on screen is gated by `gh`, not by the framework.** One `gh issue list` took 0.59–0.63 s and `gh api rate_limit` took 0.52–0.55 s on my machine (Wi-Fi, EU). A board needs issues, PRs, Actions runs and labels, which is 3–6 calls. Run in parallel that is ≈0.6–1.0 s, run serially ≈2–4 s. **The time to a populated board is ≈1 s in every stack, and that is dominated by the network.** [verified locally + inferred]
- The JVM without AOT adds ≈1–1.5 s before the window appears. That is the only startup gap a user would plausibly notice. Shipping with `aot { mode = AotMode.AotPrebuild }` (Compose 1.13+, JDK 25) removes most of it [4].

### 5. Idle CPU, battery, polling and file watchers

- **No framework idles badly by itself.** Chromium throttles timers in hidden windows, macOS App Nap throttles background apps, and Flutter, Compose, egui and native toolkits redraw only on change [12][10]. The well-known Electron offenders (Claude Desktop renderer at 60–80% idle CPU, WhatsApp at 10–15% in the background) are app bugs: busy loops, animations left running, unbounded DOM growth [12]. [secondary]
- **This app's own design decides its energy cost** [inferred]:
  - Polling GitHub: at 5 s per repo × 4 endpoints that is ≈2,900 requests/hour, which exceeds the 5,000/h authenticated REST limit with two repos (`gh issue list` / `gh pr list` use GraphQL, which has its own separate 5,000-point budget). Use ETags and conditional requests (a 304 does not count against the limit), back off to 30–60 s when idle or unfocused, and poll fast only for runs that are In Progress.
  - Local file watching: use FSEvents on macOS and inotify on Linux (one watcher per run folder; the cost is negligible). Debounce the tail of `run.log`.
  - Animations: a spinning "running" badge on 50 cards keeps the compositor awake in **every** framework. Prefer a static badge, or pause animations when the window is unfocused.
- **The cost of Electron's extra processes at idle** is ≈0% CPU and a few idle wake-ups per second. Measured differences in battery life between a well-written Electron app and a native app with the window hidden are within noise [inferred; no controlled 2025–2026 study found].

### 6. Board of a few hundred cards plus a streaming log tail

- **A few hundred cards does not need virtualization in any stack.** That is about 300 × 10–20 DOM nodes, or 3–6k nodes. Browsers lay that out in a few ms. Compose `LazyColumn`, Flutter `ListView.builder`, Avalonia `VirtualizingStackPanel` and SwiftUI `LazyVStack` all virtualize anyway. [inferred]
- **The log tail is the only rendering-sensitive part, and it is easy.** Rules that hold in every stack [inferred]:
  - Keep a ring buffer (for example 5–10k lines) and virtualize the view: a `<pre>` per visible window or a virtual list in web stacks, a `LazyColumn` of `Text` in Compose/Flutter.
  - Batch appends per animation frame (16 ms), not per stdout chunk.
  - Monospaced text in a single style. Do not run regex or ANSI parsing on every render; parse once on ingest.
  - A web view easily handles 1–2k appended lines/s with batching. Without virtualization and with per-line DOM inserts, the trouble starts at tens of thousands of nodes. That is a coding mistake that any stack can make.
- **Linux WebKitGTK is the weak spot for Tauri and Wails.** There are open, site-specific scrolling bugs in 2026 (slow scrollbar drag after resize on a long article page, WebKit #305290, Jan 2026; stutter on a carousel in WebKitGTK 2.50.5, #310814) plus the documented NVIDIA/DMABUF problems that Tauri works around with env vars [13]. [secondary] Neither bug involves a virtualized monospace list, but a log tail is the kind of view that could expose such bugs, which makes this the **one place where the choice of rendering engine could become user-visible** for this app [inferred]. Tauri 3 (alpha since 2026-09, no stable date) adds an optional CEF runtime. If it ships stable, it is a possible fix, but it brings Electron-sized bundles [verified: releases]. Electrobun's own docs recommend CEF on Linux for consistent behaviour [6].

### 7. Spawning child processes and streaming stdout

Own measurements (Apple M4, macOS, Node 22.23 `spawnSync`, median of 10–20 runs):

| Child | Median | p90 |
|---|---|---|
| `/usr/bin/true` | 1.0 ms | 1.2 ms |
| `git --version` | 8.1 ms | 15.7 ms |
| `git status --porcelain` (this repo) | 8.7 ms | 9.1 ms |
| `gh --version` | 31 ms | 33 ms |
| `node -e 0` | 37 ms | 40 ms |
| `node devscene/cli/dist/cli.js --version` (v0.6.12) | ≈70–80 ms | — |
| `gh api rate_limit` (network) | 520–550 ms | — |
| `gh issue list --limit 50 --json …` (network) | 590–630 ms | — |
| Stream 200k log lines (14.6 MB) from a child's stdout | 16 ms total (≈900 MB/s) | — |

- **The framework's spawn overhead is noise.** Node, Rust, Go, the JVM and .NET all call `posix_spawn`/`fork+exec` or `CreateProcess`. The ≈1 ms floor is OS cost. The tens to hundreds of ms are the child's own start-up (Go `gh`, Node CLI) and the network. Reports of Node spawn costing 30–50 ms [14] come from large-heap `fork` cases that a small UI process does not hit. [verified locally + secondary]
- **Stream throughput is far above any log rate the app will see.** A `run.log` grows at roughly KB/s. [verified locally]
- **The JVM side** (`ProcessBuilder`) and **.NET** (`Process`) behave alike. One small JVM gotcha: stdout and stderr must be drained on separate threads or coroutines, or the child blocks once its pipe buffer fills. [inferred, standard behaviour]
- **Through `wsl.exe` on Windows:**
  - Each `wsl.exe --exec …` call costs about **0.1 s** with the distro already running. `bash -i -c exit` costs ≈0.35 s. Those come from a single, unreproduced report in Codex issue #26149 (Ubuntu 26.04, June 2026; method, repeat count and Windows/WSL version not stated) [15] [secondary]. If the WSL VM is stopped, the first call boots it, which takes several seconds [inferred, commonly reported].
  - Windows-side **file watchers on `\\wsl$` / `\\wsl.localhost` do not deliver change events reliably** (WSL #4581, from 2019 and bot-closed in 2024 without a fix; Zed logs "ReadDirectoryChangesW … may occur on network filesystems and WSL paths"; Directory Opus users must refresh by hand) [16]. Cross-OS file access over 9P is markedly slower than native access, and Microsoft recommends against it for performance [17]. No trustworthy multiplier was found for Windows→`\\wsl$` reads, so measure it in the WSL spike. [secondary + inferred]
  - **Implication [inferred]:** a naive Windows design (poll `\\wsl$\…\status.json` every second, plus a `wsl.exe git …` per card) costs ≈0.1 s × N spawns per refresh and may miss changes. The efficient design keeps **one long-lived child inside WSL** (`wsl.exe -d <distro> --exec devscene runs watch --json` or similar; see Issue item 7). That child uses inotify natively and streams NDJSON over stdout. The cost is then paid once, at about 0.1–0.4 s. The design is identical in Electron, Tauri, Compose, Flutter or native WinUI. **No framework has a performance advantage here.** What matters is how easily the code reuses the Node CLI (see 03 and 04).

### 8. Kotlin Multiplatform, specifically

**What the names mean** [verified: kotlinlang docs]
- **Kotlin Multiplatform (KMP)** shares *Kotlin logic* across targets (JVM, Android, iOS/macOS/Linux/Windows native, JS/Wasm). It says nothing about the UI.
- **Compose Multiplatform (CMP)** is JetBrains' *shared UI* built on KMP. On desktop it ships **only for the JVM** target. The packaging docs say "Compose for desktop runs on the JVM", and the August 2026 Kotlin roadmap lists no Kotlin/Native desktop UI item [18][19]. Third-party projects (for example "compose-native", desktop-native experiments) are not production options.
- **Kotlin/Native for desktop** exists for *non-UI* code: `macosArm64` is Tier 1, `linuxX64` Tier 2, **`mingwX64` Tier 3 (no CI or binary-compatibility guarantee)**, and `macosX64` has been **deprecated since Kotlin 2.3.20** [20]. You could build a Kotlin/Native CLI or core and pair it with a native UI on each platform. You cannot build a Compose desktop app on Kotlin/Native.

**JVM desktop costs** [verified where cited]
- Packaging uses `jpackage` (JDK 17+) plus `jlink`, producing `.dmg/.pkg`, `.msi/.exe` and `.deb/.rpm`. Modules must be listed by hand (`suggestModules` helps). ProGuard is built in. **No cross-compiling**: each OS must build its own installer [18]. There is no AppImage output (jpackage's `app-image` type is a plain app folder, not the Linux AppImage format). Alternatives for AppImage, cross-building and update: Nucleus (MIT; lists AppImage, Flatpak and Snap among 18 formats) or Conveyor (JetBrains docs point to it; paid for closed source); see 04.
- Size: a jlink'd JRE (java.base + desktop + a few modules) is ≈40–60 MB, plus Skiko/Skia natives ≈15–25 MB per OS, plus the app. That gives **≈60–130 MB unpacked, ≈40–70 MB compressed** [inferred; forum reports of 61.6 MB download / 128 MB installed for a JVM build, and 216→307 MB when adding crypto modules carelessly].
- Start-up (JetBrains PR #5644, small demo app, merged 2026-07-17, ships in **Compose 1.13**, beta now; JDK 25 AOT cache = JEPs 483/514/515) [4]:

| | macOS M1 Ultra, cold | Windows Dell Precision, cold |
|---|---|---|
| No AOT | 2,017 ms | 1,356 ms |
| AppCDS prebuild (JDK 21+) | 526 ms | 828 ms |
| **AOT prebuild (JDK 25, JEPs 483/514/515)** | **424 ms** | **650 ms** |

  Caveats: these come from a "training run" at build time, so the CI runner needs a display. The archive also grows the bundle. On Windows the "relocated" case (install path differs from build path) gains less: 919 ms with AOT, 1,217 ms with AppCDS.
- RAM: ≈100–150 MB for a hello-world (JVM heap + metaspace + Skia surfaces) [secondary, forum]. Set `-Xmx256m` and `-XX:+UseSerialGC` or G1 with small regions to keep it bounded [inferred].
- **GraalVM native-image:** not officially supported by JetBrains. The third-party **Nucleus** plugin (441★, active 2026-11) automates reachability metadata. Its README claims ≈0.2 s cold start and ≈30 MB RAM for a hello-world on Windows 11, and gives no real-app figures [5]. Expect AWT/Skiko edge cases, long and RAM-heavy builds, and no cross-compilation [inferred]. Treat it as an optimization to add later, not as the plan of record. [vendor / secondary]

**Does KMP "work" for DevScene Studio?** Yes, as **Compose Multiplatform on the JVM**. Performance lands roughly at Electron level: a smaller bundle (≈60–130 MB vs ≈250–370 MB), similar RAM, and a slightly slower start that is acceptable with AOT. It is clearly behind Tauri, Wails and native on size and RAM. Neither gap is decision-relevant for this app. Three things weigh more than the numbers: (a) it cannot reuse the Node `devscene` CLI code in-process and must shell out to it, just as Tauri does; (b) Linux packaging lacks AppImage out of the box; (c) the Windows→WSL design is the same as everywhere else. These belong to 03 and 04.

### 9. Where performance is decision-relevant, and where it is noise

| Factor | Relevant? | Why |
|---|---|---|
| Download / install size | **Mildly relevant** | ≈10 MB vs ≈100 MB compressed is visible on the product site and in the auto-update payload. It also feeds the "Electron bloat" perception among the developer audience. It does not change function. |
| Idle RAM | Mostly noise (relevant but small: on Windows, WebView2 removes Tauri/Wails' advantage; on Linux, WebKitGTK may push Tauri, Wails or Electrobun toward CEF) | The audience runs dev machines that already host `claude`, Node and IDEs. 100–250 MB extra is <2% of 16 GB. |
| Cold start | Noise, except JVM without AOT | The network-bound first paint (≈1 s) dominates. Ship JVM with AOT if Compose is chosen. |
| Idle CPU / battery | Depends on the app's design, not the framework | Polling strategy and animations dominate. |
| List and log rendering | Noise, except WebKitGTK on Linux | All stacks are fast enough. The Linux system webview is the only known rendering risk. |
| Spawn and stream cost | Noise | The OS floor is ≈1 ms. Children and the network take 10–600 ms in every stack. |
| WSL2 process and file I/O | **Relevant, but the same for every framework** | It is an architecture choice (a long-lived in-WSL process), not a framework choice. |

## Answers to the owner's questions

**Q4. Performance: cross-platform vs native, and does Kotlin Multiplatform work?**
- Native apps (SwiftUI, GTK4, WinUI 3) win every micro-metric: ≈3–15 MB, ≈30–70 MB RAM, <0.2 s start. System-webview frameworks (Tauri, Wails, Electrobun) come within ≈2× of native on RAM and match it on size. Chromium-bundling Electron is an order of magnitude or more bigger on disk and ≈2–4× on RAM. JVM Compose sits between. **For a board app that waits on `gh`, `git` and `devscene`, none of these gaps changes what the user experiences**, except download size, JVM start without AOT, and possibly WebKitGTK rendering quirks on Linux.
- **Kotlin Multiplatform works**, as Compose Multiplatform on the JVM: ≈60–130 MB bundle, ≈100–150 MB RAM, ≈0.4–0.65 s start with JDK 25 AOT (Compose 1.13), or ≈1.4–2 s without. Kotlin/Native has no desktop UI path, and its Windows target is Tier 3. GraalVM native-image works only through a third-party plugin.

**Q1 (performance angle only).** Every listed framework is credible on performance for this app. Electrobun's small-size claim holds only with the system webview. Its tested CEF build was the heaviest of all (418 MB, 773 ms) [2]. Deno Desktop (Deno 2.9, June 2026) is a credible TypeScript newcomer on performance (111 MB, 242 ms, 98 MB [2]).

## Risks and open questions

- **No benchmark covers this app's workload** (hundreds of cards, a live log tail, a polling loop). Recommendation: before committing, build a 1-day spike in the top 2 candidates. Measure an installer under 120 MB, RSS after 10 minutes idle, time to the first populated board, and CPU over 10 minutes with the window hidden. Do this on macOS, Ubuntu/Wayland with an NVIDIA GPU if possible, and Windows + WSL2. [inferred]
- **Tauri and Wails on Linux:** WebKitGTK scrolling and compositing bugs, plus NVIDIA issues [13]. Check that the log view scrolls smoothly on Wayland + NVIDIA, or plan for Tauri 3 + CEF *only if it has reached stable by then*, which costs the size advantage.
- **Windows RAM figures for WebView2** are ambiguous because the runtime is shared with Edge. Real-world Tauri/Wails RAM on Windows may be closer to Electron than the macOS numbers suggest [1].
- **Compose AOT is in beta (1.13).** Confirm it in a stable release before relying on it, and check the "relocated install path" penalty on Windows [4].
- **WSL2:** confirm in a spike that `wsl.exe` cost is ≈0.1 s on the target machines, how long the first-call VM boot takes, and whether a long-lived `wsl.exe` child survives sleep/resume and `wsl --shutdown`. See 04 for the integration side.
- **Flutter desktop release-mode numbers** exist only from Windows CI [1]. If Flutter stays a finalist, include it in the 1-day spike, since it is the one stack whose release start time on CI is slow and unexplained.
- **Source age:** Hopp [3] is from 2025-07 and WSL #4581 [16] from 2019, both older than 12 months. Most of the JVM RAM forum reports date from 2021–2023 and are flagged as such.

## Sources

1. https://github.com/Elanis/web-to-desktop-framework-comparison — CI benchmark of empty apps: size, RAM, start time. Electron/Tauri/Wails/Flutter rows updated 11/2026. Methodology caveats — accessed 2026-11-12
2. https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/ — the same real app in 4 stacks (Tauri, Electron, Deno Desktop, Electrobun) on macOS: size, start, idle RAM (updated 2026-07-20) — accessed 2026-11-12
3. https://dev.to/gethopp/tauri-vs-electron-performance-bundle-size-and-the-real-trade-offs-1el4 — Tauri 8.6 MiB vs Electron 244 MiB; 172 vs 409 MB RAM with 6 windows (2025-07, N=1) — accessed 2026-11-12
4. https://github.com/JetBrains/compose-multiplatform/pull/5644 — AppCDS/AOT modes and start-time tables. Merged 2026-07-17. In CHANGELOG under 1.13.0-alpha01 — accessed 2026-11-12
5. https://github.com/NucleusFramework/Nucleus — GraalVM native-image and AOT packaging for Compose. Hello-world ≈0.2 s / ≈30 MB claim (Windows 11); 18 package formats incl. AppImage — accessed 2026-11-12
6. https://electrobun.dev/electrobun/ and https://docs.electrobun.dev/electrobun/apis/bundling-cef (old blackboard.sh/electrobun/docs URLs redirect here) — ≈1 MB hello-world claim; system webview default, CEF opt-in per platform, CEF recommended on Linux — accessed 2026-11-12
7. https://docs.avaloniaui.net/docs/deployment/native-aot and https://github.com/lixinyang123/AvaloniaAOT — Avalonia NativeAOT start-up benefit; ≈18 MB / ≈20 MB template claim — accessed 2026-11-12
8. https://www.pythonguis.com/faq/packaged-installer-file-sizes/ and https://dev.to/kerfiq/pyside6-vs-electron-why-i-shipped-a-118-mb-windows-desktop-tool-not-a-250-mb-cross-platform-one-2gfl — PyQt/PySide6 bundle sizes; onefile vs onedir start-up — accessed 2026-11-12
9. https://github.com/linebender/xilem/issues/918 — wgpu Rust GUI RAM, "typically around 50MB" — accessed 2026-11-12
10. https://docs.rs/crate/egui/0.37.0 — egui repaints only on interaction or animation — accessed 2026-11-12
11. https://zenn.dev/suusanex/articles/f642d91df412c9?locale=en — WinUI 3 NativeAOT empty window ≈0.09–0.18 s (informal) — accessed 2026-11-12
12. https://developer.apple.com/library/content/documentation/Performance/Conceptual/power_efficiency_guidelines_osx/AppNap.html ; https://claudeissues.com/issue/32020-claude-desktop-app-renderer-process-consumes-80-of-total-cpu-even-when-idle ; https://hyperdisk.raynersw.com/blog/too-many-mac-apps-are-being-built-with-electron — App Nap; Electron idle-CPU anecdotes — accessed 2026-11-12
13. https://v2.tauri.app/develop/debug/linux-graphics/ ; https://bugs.webkit.org/show_bug.cgi?id=305290 ; https://bugs.webkit.org/show_bug.cgi?id=310814 — WebKitGTK/NVIDIA workaround; 2026 scrolling bugs — accessed 2026-11-12
14. https://maxmcd.com/posts/process-per-request-performance/ — Node spawn cost ≈30 ms in a large-process context — accessed 2026-11-12
15. https://github.com/openai/codex/issues/26149 — `wsl.exe --exec /bin/true` ≈0.1 s; `bash -i -c exit` ≈0.35 s (June 2026; single report, method not stated) — accessed 2026-11-12
16. https://github.com/microsoft/WSL/issues/4581 ; https://git.secluded.site/zed/commit/d3fc00d5a0f6e493bfe1ac4a8f231a59f408626c ; https://resource.dopus.com/t/wsl2-file-system-changes-are-not-updated-automatically-have-to-press-f5-manually/53329 — watchers on `\\wsl$` are unreliable (WSL #4581: 2019, bot-closed 2024-02-01 without a fix) — accessed 2026-11-12
17. https://learn.microsoft.com/en-us/windows/wsl/filesystems (updated 2026-06-02) and https://github.com/microsoft/WSL/issues/4197 (open since 2019) — cross-OS file access is slower; Microsoft recommends against it; no multiplier given — accessed 2026-11-12
18. https://kotlinlang.org/docs/multiplatform/compose-native-distribution.html — jpackage/jlink, JDK 17+, manual modules, ProGuard, no cross-compiling, "runs on the JVM" (page dated 2026-08-25) — accessed 2026-11-12
19. https://kotlinlang.org/docs/roadmap.html — roadmap of Aug 2026; no Kotlin/Native desktop UI item — accessed 2026-11-12
20. https://kotlinlang.org/docs/native-target-support.html — macosArm64 Tier 1, linuxX64 Tier 2, mingwX64 Tier 3, macosX64 deprecated in 2.3.20 — accessed 2026-11-12
21. GitHub releases via `gh release list`: electron/electron (45.3.1), tauri-apps/tauri (2.12.5; 3.0.0-alpha.6 with tauri-runtime-cef 3.0.0-alpha.7), wailsapp/wails (v3.1.0), blackboardsh/electrobun (2.0.6; 2.0.7-beta.12), denoland/deno (v2.9.0, 2026-06-25, `deno desktop`), AvaloniaUI/Avalonia (12.1.6), slint-ui/slint (1.18.1), JetBrains/compose-multiplatform (1.12.2; 1.13.0-beta02); https://docs.flutter.dev/release/archive (Flutter 3.50) — accessed 2026-11-12
22. Own measurements, 2026-11-12: Apple M4, macOS (Darwin 24.6), Node 22.23.2, git 2.50.1, gh 2.100.0, devscene CLI 0.6.12. Spawn and stream timings via a Node `spawnSync`/`spawn` script; RSS via `ps` (GitHub Desktop on Electron 44.9.1 idles at ≈170–210 MB over 4 processes in two snapshots; Notes.app at 58–61 MB; Notes.app bundle 15 MB)
