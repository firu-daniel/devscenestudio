# 04 — OS integration and native-side blockers (incl. WSL2), per framework
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **No candidate hits a hard ❌ on the app's core job** of spawning `git`/`gh`/`claude`/`devscene`, streaming output and reading JSON and logs, on macOS, Linux or Windows→WSL2. The only ❌ in the matrix is a packaging gap: Compose has no AppImage. The real blockers sit at the edges: Linux webview rendering (Tauri, Wails), packaging formats, auto-update coverage (Tauri and Wails update Linux AppImage only in practice, Flutter and Compose have no first-party updater) and Flatpak/Snap confinement (it hurts every framework). **[verified]**, sources inline.
- **The hard problems don't depend on the framework.** The macOS GUI-app PATH, WSL quirks, file watching across `\\wsl$`, SmartScreen, notarization and terminal hand-off each need the same workaround in every framework. Picking a framework doesn't make any of them go away. **[inferred]**
- **Windows/WSL2: treat WSL as a remote host, not as a file share.** Run one long-lived process inside the distro that runs `git`/`gh`/`devscene` there, watches files with inotify there, and streams JSON lines over stdio. Microsoft rates Windows-side `\\wsl$` access as "slow (9P)… not for tight loops" [6] **[verified]**. Windows-side watchers (ReadDirectoryChangesW, so notify, chokidar, .NET FileSystemWatcher and Dart `watch`) are reported not to get events on `\\wsl$` [66][14][15] **[secondary; no Microsoft statement, unconfirmed on current WSL, see Risk 8]**. This design lets any framework do WSL, as long as it can spawn a process and read its stdout. Integration shape, sidecar and the `runs watch` NDJSON stream: see 05.
- **Webview on Linux is the main framework-specific risk.** Tauri v2 runs on WebKitGTK 4.1 and has documented blank-window, flicker and Wayland "Error 71" problems, with env-var workarounds [22]. Wails v3 defaults to GTK4/WebKitGTK 6.0. The opt-in `-tags gtk3` (WebKitGTK 4.1) path still ships in 3.1.0, but it is announced for removal. Once it goes, Ubuntu 22.04, Debian 12, Fedora ≤ 39 and RHEL 9 drop out [25]. Electron, Flutter, Compose, Avalonia and Qt draw their own UI and don't have this problem. Tauri v3 (alpha since 2026-09-13) adds an optional CEF/Chromium runtime, which would fix it, but it isn't production-ready [28]. **[verified]**
- **Auto-update without app stores**, from best to weakest coverage: **Electron** (electron-updater covers DMG/zip, NSIS, AppImage, deb, rpm, pacman [45]); **Avalonia/.NET, PySide6 and Rust** with **Velopack** (Windows, macOS, Linux AppImage only [48]); **Wails v3** (a new built-in updater, GA Oct 2026; on Linux AppImage or a user-writable binary only [27]); **Tauri** (signed updates, but Linux is AppImage only [47]); **Flutter** (community plugins, and the main one was last released in 2024 [52]); **Compose** (none built in, so you need **Conveyor**: free for OSI-licensed projects, **$45/month** otherwise [49]; on Linux it gives deb + apt repo, not AppImage [67]). **[verified]**
- **Flatpak isn't a good fit for any framework.** Each `git`/`gh`/`claude` call would go through `flatpak-spawn --host` with `--talk-name=org.freedesktop.Flatpak`, which effectively escapes the sandbox [31][32]. Snap classic confinement would likely be refused for this app [33]. Both are store channels anyway, which the brief excludes. **Ship AppImage plus deb (and rpm).** **[verified]**
- **macOS: run without the App Sandbox, with Hardened Runtime and notarization.** The Hardened Runtime doesn't restrict spawning other signed binaries such as `/opt/homebrew/bin/gh`. JS/.NET/JVM runtimes need `allow-jit` [34][41][68]. Flutter turns the sandbox on by default, so you have to turn it off [5]. Watch out for TCC "responsible process" prompts when repos live in `~/Documents` or `~/Desktop` [36][37]. Enrol in the Apple Developer Program early: new and some existing teams have been stuck at notarization error 7000 for weeks to months [39]. **[verified/secondary]**
- **Windows signing is mandatory, not optional.** EV certificates no longer bypass SmartScreen, and reputation builds up per file or publisher over time [42]. On Windows 11, Smart App Control "will block execution of unsigned files unless the file has a positive reputation" [42]. Azure Artifact Signing ($9.99/month) is the cheap route, but only organisations in US/CA/EU/UK **with three or more years of verifiable tax history** and *individuals in US/CA* are eligible [43]. A new company or a non-US/CA individual should budget for an OV certificate at $300–500/year [43]. **[verified]**

## Scope

This file covers the native-side integration needs of DevScene Studio and where each framework hits friction: process control, WSL2, file watching, webviews, Linux, macOS and Windows packaging, auto-update and desktop integration (tray, notifications, deep links, keychain, terminal hand-off).

Other files cover the rest:
- framework momentum, health and licence costs beyond signing and update tooling (01)
- performance, bundle size and memory (02)
- N-native cost and career value (03)
- harness integration contract, integration shape, CLI PATH discovery and sidecar sizes (05)
- repo topology and harness fit (06)
- additional criteria (07)

Version facts used here were checked on 2026-11-12:
- Electron 45.3.1 (latest stable)
- Tauri 2.12.5, with 3.0.0-alpha.6
- Wails 3.0.0 (2026-10-26) and 3.1.0 (2026-11-01) [26]
- Compose Multiplatform 1.12.2
- Avalonia 12.1.6
- Velopack 1.2.161
- Sparkle 2.10.1
- WSL 3.0.5

These come from `gh release list` on each repo **[verified]**.

## Findings

### 1. Process control

| Need | What it takes | Framework notes |
|---|---|---|
| Spawn with custom env and PATH | Every runtime can pass an env map: Node `child_process`, Rust `std::process`/`tokio::process`, Go `os/exec`, Dart `Process.start(environment:)`, JVM `ProcessBuilder`, .NET `ProcessStartInfo`, `QProcess`. | **Tauri:** the JS-side `shell` plugin is capability-gated. Each program and argument pattern has to be allow-listed in `capabilities/*.json`, and "by default all potentially dangerous plugin commands and scopes are blocked" [1]. **Workaround:** spawn from Rust `#[tauri::command]`s with `std::process`/`tokio::process`, which aren't gated, and expose only high-level commands to the UI. **[verified]** |
| **macOS GUI PATH** | An app launched from Finder or the Dock gets roughly `/usr/bin:/bin:/usr/sbin:/sbin`, without Homebrew (`/opt/homebrew/bin`), nvm, volta or `~/.local/bin` [2][4]. | Same fix everywhere: at startup run the user's interactive login shell (`$SHELL -ilc 'command -v devscene; command -v node; command -v gh; command -v git'`, or `'env'` to merge the whole PATH) with a timeout, cache the absolute paths, then add known fallbacks and per-tool path overrides in settings (same recipe as 05 §2). Ready-made helpers exist: `fix-path-env-rs` for Tauri/Rust [2], and `fix-path`/`shell-env` for Electron (the npm fix-path has had side-effect bugs) [3]. Flutter, Compose, Avalonia, Qt and Wails need about 20 lines of hand-written code. **[verified/secondary]** |
| Linux PATH | Apps launched from `.desktop` files get the session PATH. It usually has `~/.local/bin`, but nvm paths set in `.bashrc` are missing. | Same interactive login-shell probe (`-i` is needed, because nvm's init lives in `~/.bashrc`). **[inferred]** |
| Stream stdout/stderr | Every framework supports it. | Line-buffer and decode UTF-8. On Windows, `wsl.exe --list` writes UTF-16LE (see section 2). |
| Kill process trees | Unix: start the child in its own process group (`detached`/`setsid`/`Setpgid`) and signal `-pgid`. Windows: Job Objects or `taskkill /T /F`. | **JVM:** `ProcessHandle.descendants()` does it cleanly. **Dart/Flutter:** `Process.kill` "sends the `signal` to the process" and documents no process-group option [69], so you need a shell wrapper or `taskkill` **[inferred from Dart API]**. The harness has no per-run stop by design (Issue #1), so kill only matters for the app's own helpers. |
| Run the `devscene` Node CLI | Integration shape, sidecar and sizes: see 05 (call the user's installed `devscene`; no sidecar). Windows: always through `wsl.exe`. | **Electron:** if it ever runs JS out of process, `ELECTRON_RUN_AS_NODE` conflicts with the recommended `runAsNode` fuse being off, because `child_process.fork` then throws. Use `utilityProcess` instead [55]. **[verified]** |

### 2. WSL2 from Windows

**How to call it.** Use `wsl.exe -d <distro> --cd <linuxdir> -- <cmd> <args…>` or `wsl.exe -d <distro> -e <cmd>`. `-e`/`--exec` skips the Linux shell, so the program gets argv directly. Microsoft documents `wsl -d <distro> -- cmd` [6]. **[verified]**

Quirks to design for:

| Quirk | Detail | Mitigation |
|---|---|---|
| UTF-16 output | `wsl.exe --list/--status` writes UTF-16LE with no BOM [9]. | Set `WSL_UTF8=1` in the child env (opt-in since WSL 0.64.0 [9] **[verified]**) or decode UTF-16LE yourself. Use `wsl.exe -l -q` to enumerate distros. **[secondary]** |
| Quoting | Windows command-line to argv to bash quoting is inconsistent [59]. | Prefer `--exec prog arg1 arg2` with no shell. When you need a shell, use `-- bash -c '<script>'`, building the script from a fixed template and passing data through env or stdin, not string interpolation. Use `WSLENV` to pass env vars across [7]. **[secondary/inferred]** |
| Non-login shell PATH | `wsl.exe -- cmd` doesn't run `.profile` or `.bashrc`, so nvm-installed `node`, `devscene` and `claude` are missing. `bash -lc` doesn't fix it on a default setup: the nvm installer appends its init to `~/.bashrc`, and Ubuntu's default `~/.bashrc` returns early for non-interactive shells (05 §2). | Follow 05 §2: resolve once with an interactive login shell, `wsl.exe -d <distro> -- bash -ilc 'command -v node; command -v devscene'`, cache the absolute paths (user-overridable), then exec with `wsl.exe -d <distro> --cd <dir> --exec <abs-node> <abs-script> …` so steady-state calls don't depend on shell init files. **[secondary/inferred]** |
| Distro not running / not installed | `\\wsl$` doesn't resolve while the distro is stopped. `\\wsl.localhost` can auto-start it on Windows 11 [6]; the redirector starts it through `wslservice` [8]. WSL may also be missing entirely, so check `wsl --status` first [6]. | Run a doctor step: check that `wsl.exe` exists, `wsl --status` succeeds, the distro is listed, and a warm-up `wsl -d X -e true` works. **[verified]** |
| Startup latency | A cold VM boot plus distro start takes seconds. Warm calls cost each `wsl.exe` spawn round-trip. | Keep **one long-lived in-distro process** (`devscene runs watch --json`, see 05) instead of spawning `wsl.exe` per command. **[inferred; measure in a spike]** |
| Killing | If `wsl.exe` dies before its Linux child, `wslhost.exe` takes over the interop channel [10]. Orphaned Linux processes get re-parented to `/init` and keep running [11]. | The in-distro process runs children under `setsid` and kills them by pgid on request; `runs watch` exits when stdin closes (05 §5). Don't rely on killing `wsl.exe`. **[secondary]** |
| `git`/`gh` auth | Credentials live **inside** WSL (`~/.config/gh`, the git credential helper). Windows `gh.exe`/`git.exe` can't see them, and Windows `git.exe` over `\\wsl.localhost` is slow (1.5–3.8 s for trivial commands, against 0.09 s in WSL, in one report) [17]. | Always run `git`/`gh` inside WSL. **[secondary]** |
| WSL 3.0 | WSL 3.0.1 (2026-09-29) made WSL containers (WSLc) GA and ships an SDK NuGet package (`Microsoft.WSL.Containers`) [58]. | Nothing changes for `wsl.exe`. The SDK is .NET-only and container-oriented, so it isn't needed here. **[verified]** |

**File access.** `\\wsl$\<distro>\…` and `\\wsl.localhost\<distro>\…` are aliases served by the same `p9rdr.sys` redirector over a Plan 9 server on an hvsocket [8]. Neither prefix is faster than the other. Microsoft rates "Windows process reading Linux files (`\\wsl$\...`)" as **slow (9P)**: "use for occasional file access, not tight loops" [6]. Reading a handful of small JSON files (`registry.json`, `status.json`) is fine. Tailing logs and scanning many repos should happen inside WSL. **[verified]**

**File watching across the boundary.** Watching from the Windows side is probably a ❌ for every framework, but the evidence is secondary:
- microsoft/WSL#4581, "Unable to watch directory changes via `\\wsl$\` redirector": a `FindFirstChangeNotification` repro fails on `\\wsl$`. Opened 2019 and closed by an inactivity bot on 2024-02-01 with no fix [66].
- Directory Opus and Syncthing users report missing events or watcher errors on `\\wsl.localhost` / `\\wsl$` [14][15].
- No Microsoft doc states either support or non-support.

Plan on polling from the Windows side. **[secondary; not reproduced on WSL 3.0.x, see Risk 8]**

The reverse direction is a separate, documented gap: a Linux program under WSL2 watching `/mnt/c/...` "may not produce inotify events" for changes made by Windows applications [12] **[verified]**. That matters only if users keep repos on `/mnt/c`; the doctor should warn about it.

The workaround is the **VS Code model**: run a server inside WSL [16]. For DevScene Studio that is the harness's own `devscene runs watch --json`, invoked with the cached absolute paths from the PATH row above, which uses inotify on the distro's ext4 and streams NDJSON over stdout. Contract, events and failure modes: see 05 §2 and §5. Fallback until it exists: poll `status.json` and `registry.json` mtimes every 2–5 s over `\\wsl.localhost`. **[inferred]**

### 3. File watching (native)

| Framework | Library | macOS | Linux | Windows | Notes |
|---|---|---|---|---|---|
| Electron | chokidar 6.0 (2026-10-19), @parcel/watcher | FSEvents (via `fs.watch`) | inotify | RDCW | ✅ |
| Tauri | `notify` 8.x (9.0 rc.8) | FSEvents | inotify | RDCW | ✅. Has a PollWatcher fallback [12]. |
| Wails | `fsnotify` | **kqueue: one fd per file, no FSEvents** | inotify, **no recursion** | RDCW | ⚠️ [57]. Use `rjeczalik/notify` or a helper. |
| Flutter | `dart:io` `FileSystemEntity.watch` | FSEvents (recursive) | inotify, **recursive not supported** | RDCW, can overflow | ⚠️ [18] |
| Compose | `java.nio` WatchService | **polling, seconds of latency** (FSEvents impl JDK-8293067 unresolved) | inotify | RDCW | ⚠️ [20]. Use `io.methvin:directory-watcher`. |
| Avalonia | .NET `FileSystemWatcher` | FSEvents | inotify | RDCW | ✅ |
| Qt/PySide6 | `QFileSystemWatcher` / Python `watchdog` | FSEvents | inotify | RDCW | ⚠️ QFSW isn't recursive and has fd limits on BSD-style backends [19]. `watchdog` is fine. |
| Native | FSEvents / GFileMonitor / FileSystemWatcher | ✅ | ✅ | ✅ | ✅ |

**Linux inotify limits.** Since kernel 5.11, `max_user_watches` scales with RAM (about 1% of memory, clamped to 8192–1,048,576). `max_user_instances` stays at **128** per user [21]. That instance limit is the one usually hit when an IDE, Dropbox and several Electron apps run together. The app needs only a few dozen watches (registry, run folders, log files), so watch directories, not trees. **[secondary]**

### 4. Webview inconsistencies (Tauri, Wails; Electron for contrast)

- **Engines:** Tauri and Wails use WKWebView on macOS, WebView2 (Chromium, evergreen) on Windows and WebKitGTK on Linux [23]. Electron ships its own Chromium, so it renders the same everywhere. **[verified]**
- **WebKitGTK problems** documented by Tauri itself [22]:
  - blank or white windows
  - flicker on resize
  - crash on resize
  - `AcceleratedSurfaceDMABuf` framebuffer errors
  - Wayland `Error 71`
  - silent WebGL slowness

  The workarounds are, in order: enable kernel modesetting (an NVIDIA < 545 kernel parameter, not an env var), then `__NV_DISABLE_EXPLICIT_SYNC=1`, then `WEBKIT_DISABLE_DMABUF_RENDERER=1`, then `WEBKIT_DISABLE_COMPOSITING_MODE=1`. The last two cost rendering speed. A board UI doesn't need WebGL, so the impact is mostly the blank-window class of bug, which loses users at first launch. **[verified]**
- **AppImage plus WebKitGTK:** AppImages bundle the build host's Wayland, EGL and GTK libraries, which can produce blank windows with `EGL_BAD_PARAMETER` or Wayland crashes on other distros. One documented fix is to exclude the bundled `libwayland-*` [62]. **[secondary]**
- **Distro version spread:** Tauri v2 needs WebKitGTK **4.1** (GTK3) [24]. Wails v3 defaults to GTK4/**WebKitGTK 6.0**. Its legacy opt-in `-tags gtk3` (WebKit2GTK 4.1) path is described as "scheduled for removal in v3.1", but it **still ships in v3.1.0**: the v3.1.0 docs still document it, the v3.1.0 tree still contains the `gtk3` build-tagged files (for example `v3/internal/operatingsystem/webkit_linux_gtk3.go`), and the v3.1.0 release notes don't mention removing it [25][26]. Once it is removed, Ubuntu 22.04, Debian 12, Fedora ≤ 39 and RHEL 9 drop out. **[verified]**
- **WKWebView vs WebView2:** these differ in CSS and JS feature timing, and there's no WebDriver for WKWebView, so E2E tests can't run the same way on all three [63]. For a simple board UI this is ⚠️ test effort, not a blocker. **[secondary]**
- **WebView2 runtime:** built into Windows 10 (April 2018 update or later) and Windows 11. Tauri offers `downloadBootstrapper` (default, 0 MB), `embedBootstrapper` (~1.8 MB), `offlineInstaller` (~127 MB) and `fixedVersion` (~180 MB) [44]. Wails offers similar options. Not a blocker. **[verified]**
- **Tauri v3:** `tauri-runtime-cef` (Chromium, GTK4 on Linux) arrived in 3.0.0-alpha.0 on 2026-09-13 and is at alpha.6/7 [28]. It's worth tracking, but don't base a product on it in 2026. **[verified]**

### 5. Linux packaging

| Format | Status | Notes |
|---|---|---|
| **AppImage** | Recommended, with care | The new static **type2-runtime** needs no `libfuse2`, and electron-builder uses a "static AppImage runtime that does not depend on FUSE2" [29]. Older runtimes still need FUSE2, which Ubuntu 22.04 and later and Fedora Atomic no longer ship by default [30]. Since tauri-bundler 2.6 the bundler "pulls the latest AppImage linuxdeploy plugin… This should remove the libfuse requirement" [70]. Build on the **oldest glibc** you support, in practice Ubuntu 22.04 or Debian 12 [24]. Tauri: 2–6 MB grows to **70 MB+** once WebKitGTK is bundled, and there's no ARM cross-build [24]. **[verified/secondary]** |
| **deb / rpm** | Recommended | Native dependencies (`libwebkit2gtk-4.1-0` etc.) come from the distro, so there are no bundling problems. Electron, Tauri, Wails (via nfpm, and it signs too) and Compose all have first-party support [25][50]. Flutter, Avalonia and Qt need community or manual tooling **[inferred]**. |
| **Flatpak** | Not viable for this app | Every host binary call has to go through `flatpak-spawn --host`, which needs `--talk-name=org.freedesktop.Flatpak` and "allows commands to run outside the sandbox" [31][32]. Flathub lists it as a linter *warning*, not an error ("Warnings do not require an exception") [32]. Users would see a "can access full host system" label. It also breaks the app's environment model (PATH, env and cwd mapping). Flathub is also a store channel, which the brief excludes. **[verified]** |
| **Snap** | Not viable | Classic confinement needs a forum request and manual vetting. This app's reasons (it runs host `git`/`gh`, reads `~/.config/gh`) fall into categories the review process lists as unsupported ("dependent software only available on host", "access to dot files in $HOME", "management snaps") or as not justifying classic on their own (running arbitrary commands), and "if you can use interfaces for your app and it can function, classic will usually not be granted" [33]. Snap is also a store channel, which the brief excludes. **[verified]** |

### 6. macOS

- **Sandbox:** distribute *outside* the App Store, with **no App Sandbox**. A sandboxed parent passes its sandbox to its children, so `git` couldn't read arbitrary repos. Flutter enables the sandbox by default and you remove it in `Release.entitlements` [5]. Other frameworks leave it off by default. **[verified/inferred]**
- **Hardened Runtime and notarization:** required for notarization [34][35]. The hardened runtime doesn't stop the app spawning separately signed binaries such as Homebrew `gh`, Apple's `git` or the `claude` binary. Entitlements depend on the runtime:
  - **Electron:** `allow-jit` (and, on some versions, `allow-unsigned-executable-memory`) [34]
  - **.NET (Avalonia):** `allow-jit`; Microsoft lists four defaults [41]
  - **JVM (Compose):** `allow-jit` and related entitlements, set by hand in an entitlements plist per JetBrains' signing tutorial [68]; the plugin's `notarize*` tasks do the submission [50]
  - **Tauri, Wails, Flutter AOT, SwiftUI:** usually none

  **[verified/secondary]**
- **TCC:** when the app spawns `git` in `~/Documents` or `~/Desktop`, macOS attributes access to the app as the "responsible process" and prompts once [36]. If a launcher disclaims responsibility, the child gets EPERM [37]. A separately signed Node sidecar can become its own responsible process **[secondary]**. Document "grant Documents access" in onboarding. Don't disclaim. **[secondary]**
- **Gatekeeper:** macOS 15 removed the Control-click bypass. Unsigned apps now need System Settings → Privacy & Security → Open Anyway [38] (source from 2024, still current behaviour) **[secondary]**. Signing and notarization are effectively mandatory.
- **Account issues:** Apple Developer Program is $99/year, and notarization itself costs nothing extra [40]. Several 2026 forum threads report teams stuck at notarization `statusCode 7000` ("Team is not yet configured for notarization") for weeks to months: one team enrolled 2026-05-01 had every submission rejected for two months, another "across three calendar months" [39]. Apple DTS says the account holder can't fix it from the portal and must go through Developer Program Support [39]. So **enrol early, and notarize a test build in week 1**. **[secondary]**
- **Universal binaries:** supported by Electron (`--universal`), Tauri (`--target universal-apple-darwin`), Wails, Flutter (default) and Xcode. Compose/jpackage builds one architecture per JDK, so ship two DMGs or use Conveyor. **[inferred, standard tooling]**

### 7. Windows

- **SmartScreen:** "EV certificates no longer bypass SmartScreen. Years ago… this behavior no longer exists" (Microsoft gives no date). Reputation builds per file hash and publisher [42]. Expect warnings on the first releases whatever certificate you use. **[verified]**
- **Smart App Control (Windows 11):** "Smart App Control will block execution of unsigned files unless the file has a positive reputation", and its checks "apply to all executable files, not just those downloaded from the Internet" [42]. On SAC-enabled machines, unsigned means blocked, not warned. That covers the installer and any helper executable the app ships, so sign everything. **[verified]**
- **Signing options:**
  - **Azure Artifact Signing** (formerly Trusted Signing): Basic tier with 5,000 signatures a month, "Starts at $9.99/month" [42][43]. Public Trust eligibility: "Available to organizations in the USA, Canada, the European Union, and the United Kingdom, and to individual developers in the USA and Canada. **Organizations must have a verifiable tax history of three or more years**" [43]. A newly founded DevScene company won't qualify as an organisation, whatever its country. **[verified]**
  - Otherwise an OV certificate on a hardware token or cloud HSM, "$300–500/year" per Microsoft [43]. **[verified]**
- **Installer:**
  - NSIS (Electron, Tauri, Wails) or MSI (Tauri, but only buildable on Windows [44]; Compose via jpackage, Windows-only [50]).
  - MSIX is supported by Wails v3 and Electron, but it adds package identity and AppContainer-adjacent behaviour. Plain NSIS is simpler for a `wsl.exe`-spawning app.
  - Velopack's `Setup.exe` for .NET and Python. **[verified/inferred]**
- **WebView2:** see section 4. Not a blocker.

### 8. Auto-update (no app stores)

| Option | Platforms | Hosting | Notes |
|---|---|---|---|
| **electron-updater** | macOS DMG+zip (app must be signed), Windows NSIS, Linux **AppImage, deb, rpm, pacman** [45] | GitHub Releases, S3 or any static server (`latest*.yml`) | Most complete. deb/rpm/pacman installs go through pkexec/sudo with an auth prompt and skip the automatic install-at-startup path [45]. Electron's *built-in* `autoUpdater` has **no Linux support** [46]. |
| **Tauri updater** | macOS `.app.tar.gz`, Windows NSIS/MSI, Linux **AppImage only** [47] | Static JSON (GitHub Releases/S3) or a dynamic endpoint. Signatures are mandatory. | deb and rpm users update through their package manager or a self-hosted repo. |
| **Wails v3 updater** | macOS `.app` zip, Windows, Linux **AppImage or a user-writable binary** (not deb/rpm: it stages "beside the installed binary… so that directory must be writable"); `.dmg`, `.pkg` and `.msi` "are not supported in v1". Providers: GitHub Releases, keygen.sh, Sparkle appcast, Wails manifest [27] | Static | New in 3.0 (Oct 2026). Its github-provider asset URL was fixed in 3.1.0 [26]. ⚠️ young; AppImage-only in practice on Linux, like Tauri. |
| **Velopack** (v1.2.161) | Windows, macOS, Linux **AppImage only** [48] | Any static host or GitHub Releases | SDKs marked "Ready": C#, Rust, JS, C++, Python; Java, Swift and Go are "Planned", so no Wails path yet [48]. Covers Avalonia, PySide6 and WinUI 3. Flutter only through community `velopack_flutter` (0.3.3, 2026-10-19) [53]. |
| **Sparkle 2.10.1 / WinSparkle** | macOS / Windows | Static appcast | Native standard on macOS [51]. Flutter's `auto_updater` wraps both, but its pub.dev platform map lists only macOS and Windows, and its last release was 1.0.0 on 2024-10-27 (stale) [52]. |
| **Conveyor (Hydraulic)** | macOS, Windows, Linux **deb + apt repo / tarball** (no AppImage; rpm "planned"; the tarball doesn't auto-update) [67]. Cross-builds from any OS, JVM-aware | Static site | **Free for OSI-licensed open source. Standard $45/month (3 apps). Source tier by quote** [49]. Main path for Compose, which has no updater and no cross-build [50]. |

### 9. Tray, notifications, deep links, secure storage, terminal hand-off

Tray, notifications, deep links and secure storage are **low need** for this app: none is a core flow, auth stays in `gh`, and Issue #1 has no tray requirement. Terminal hand-off is the only one a core flow uses.

- **Tray (low need):** Electron, Tauri (`tray-icon` feature), Wails v3, Compose (`Tray`) and Qt (`QSystemTrayIcon`) have it built in. Avalonia's `TrayIcon` is "confirmed to work on Ubuntu", which means only some Linux distros [56]. Flutter needs community `tray_manager`. **GNOME has no tray without the AppIndicator extension**, whatever the framework. **[verified/inferred]**
- **Notifications (low need):** Electron, Tauri (plugin) and Wails v3 have built-in support [26]. Compose has a basic `TrayState.sendNotification`. Avalonia has none at OS level; you need the third-party `DesktopNotifications` [56]. Flutter needs plugins. **[verified/secondary]**
- **Deep links (low need):** not needed by the core flows, because auth goes through `gh`. Electron (`setAsDefaultProtocolClient`), the Tauri deep-link plugin and Wails custom protocols support them. Compose's `Desktop.setOpenURIHandler` is macOS-only. On Linux, scheme registration needs a `.desktop` `MimeType`, so an AppImage won't register a scheme until it's integrated. **[inferred]**
- **Secure storage (low need):** probably unnecessary, because GitHub auth stays in `gh`.
  - Electron's `safeStorage` uses Keychain, DPAPI or libsecret/kwallet. Linux can fall back to `basic_text`, which is effectively unencrypted. The synchronous API is deprecated in 45 and removed in Electron 46, which is at 46.0.0-alpha.10 today [54].
  - Tauri: `keyring` crate. Stronghold's last release was 2025-10-27 [61].
  - Others use community keyring wrappers.

  **[verified]**
- **Terminal hand-off** (for harness-analyze, Issue item 10) works the same way in every framework, by shelling out:
  - **macOS:** `open -a Terminal <dir>`. Scripting a command into Terminal or iTerm through AppleScript triggers the Automation (TCC) consent prompt.
  - **Linux:** there's no standard default terminal. Try `xdg-terminal-exec` [64], then `x-terminal-emulator` (Debian), then known terminals.
  - **Windows:** `wt.exe -- wsl.exe -d <distro> --cd <dir> -- bash -ilc '…'` [65] (interactive, so nvm's `~/.bashrc` init runs), with `wsl.exe` in a console window as the fallback.

  **[inferred/secondary]**

### 10. Blocker matrix

Legend: ✅ works with first-party or standard tooling · ⚠️ works with a workaround or extra work · ❌ blocker (no reasonable path inside the framework). Numbers refer to the Sources list. **[inf]** marks a non-✅ cell with no direct source: it is this file's inference from standard tooling, not a checked fact. "Universal" means the same issue and fix apply in every column.

**A. Runtime: processes, files, WSL, rendering**

| Concern | Electron | Tauri v2 | Wails v3 | Flutter | Compose MP | Avalonia | Qt/PySide6 | SwiftUI (mac) | GTK4 (Linux) | WinUI 3 (Win) |
|---|---|---|---|---|---|---|---|---|---|---|
| Spawn with env | ✅ | ⚠️ shell-plugin scopes, so use Rust commands [1] | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| macOS GUI PATH (universal) | ⚠️ [3] | ⚠️ [2] | ⚠️ [2] | ⚠️ [4] | ⚠️ [2] | ⚠️ [2] | ⚠️ [2] | ⚠️ [2] | n/a | n/a |
| Stream and kill tree | ✅ | ✅ | ✅ | ⚠️ no pgroup API [69] [inf] | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Drive `wsl.exe` (quirks universal) | ⚠️ [6][9] | ⚠️ [6][9] | ⚠️ [6][9] | ⚠️ [6][9] | ⚠️ [6][9] | ⚠️ [6][9] | ⚠️ [6][9] | n/a | n/a | ⚠️ [6][9] |
| Read files over `\\wsl$` (slow 9P) | ⚠️ [6] | ⚠️ [6] | ⚠️ [6] | ⚠️ [6] | ⚠️ [6] | ⚠️ [6] | ⚠️ [6] | n/a | n/a | ⚠️ [6] |
| Watch files over `\\wsl$` (stream from inside WSL; universal, secondary evidence) | ⚠️ [66][14][15] | ⚠️ [66][14][15] | ⚠️ [66][14][15] | ⚠️ [66][14][15] | ⚠️ [66][14][15] | ⚠️ [66][14][15] | ⚠️ [66][14][15] | n/a | n/a | ⚠️ [66][14][15] |
| Native file watching | ✅ | ✅ | ⚠️ kqueue fds, no recursion [57] | ⚠️ no recursion on Linux [18] | ⚠️ macOS polling [20] | ✅ | ⚠️ QFSW [19] (watchdog ✅) | ✅ | ✅ | ✅ |
| UI rendering consistency | ✅ | ⚠️ WebKitGTK [22][23] | ⚠️ WebKitGTK [22]; GTK3 path deprecated, LTS distros at risk [25] | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**B. Distribution and desktop integration**

| Concern | Electron | Tauri v2 | Wails v3 | Flutter | Compose MP | Avalonia | Qt/PySide6 | SwiftUI | GTK4 | WinUI 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| macOS no-sandbox, notarize, universal | ✅ (JIT entitlements) [34] | ✅ | ✅ | ⚠️ turn sandbox off [5] | ⚠️ one arch per build [inf], JIT entitlements [68] | ⚠️ manual codesign/Parcel, .NET entitlements [41] [inf for Parcel] | ⚠️ PyInstaller/Nuitka signing is manual [inf] | ✅ | n/a | n/a |
| Windows sign and installer (signing mandatory: SmartScreen/SAC universal [42]) | ✅ NSIS | ✅ NSIS/MSI [44] | ✅ NSIS/MSIX | ⚠️ no first-party installer [inf] | ⚠️ jpackage, Windows-host only [50] | ⚠️ via Velopack [48] | ⚠️ IFW/Inno, manual [inf] | n/a | n/a | ⚠️ Windows App SDK runtime or MSIX [inf] |
| Linux AppImage | ✅ static runtime [29] | ⚠️ glibc baseline, 70 MB, EGL/Wayland [24][62] | ⚠️ WebKitGTK [22]; GTK3 path deprecated, LTS distros at risk [25] | ⚠️ community tooling [inf] | ❌ no AppImage in the plugin or in Conveyor; hand-roll it with appimagetool [50][67] | ✅ Velopack [48] | ⚠️ linuxdeploy-qt [inf] | n/a | ⚠️ GTK4 AppImage is awkward; Flatpak is its native home [inf] | n/a |
| Linux deb/rpm | ✅ | ✅ | ✅ nfpm [25] | ⚠️ community [inf] | ✅ [50] | ⚠️ community [inf] | ⚠️ manual [inf] | n/a | ✅ | n/a |
| Flatpak / Snap (universal; store channels, out of scope) | ⚠️ [31][32][33] | ⚠️ [31][32][33] | ⚠️ [31][32][33] | ⚠️ [31][32][33] | ⚠️ [31][32][33] | ⚠️ [31][32][33] | ⚠️ [31][32][33] | n/a | ⚠️ [31][32] | n/a |
| Auto-update | ✅ all formats (deb/rpm with auth prompt) [45] | ⚠️ Linux AppImage only [47] | ⚠️ new (3.0); AppImage-only in practice on Linux [27] | ⚠️ stale/community [52][53] | ⚠️ none built in; Conveyor $45/month, deb/apt only on Linux [49][67] | ✅ Velopack [48] | ✅ Velopack (Python) [48] | ✅ Sparkle [51] | ⚠️ distro/Flatpak only [inf] | ✅ Velopack/App Installer [48] |
| Tray (low need; GNOME needs extension, universal) | ✅ | ✅ | ✅ | ⚠️ community plugin [inf] | ✅ | ⚠️ some distros [56] | ✅ | ✅ | ⚠️ AppIndicator [inf] | ✅ |
| Notifications (low need) | ✅ | ✅ | ✅ [26] | ⚠️ plugin [inf] | ⚠️ basic `TrayState.sendNotification` [inf] | ⚠️ third-party [56] | ⚠️ basic [inf] | ✅ | ✅ | ✅ |
| Secure storage (low need) | ⚠️ Linux `basic_text` fallback [54] | ⚠️ keyring crate; Stronghold stale [61] | ⚠️ community [inf] | ⚠️ community [inf] | ⚠️ community [inf] | ⚠️ community [inf] | ⚠️ QtKeychain [inf] | ✅ | ✅ | ✅ |
| Terminal hand-off (universal) | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ [64][65] | ⚠️ AppleScript TCC [inf] | ⚠️ [64] | ⚠️ [65] |

**Reading the matrix.** The only ❌ is Compose/AppImage. Conveyor gives Compose updates and cross-builds, but on Linux only through deb/apt; an AppImage would have to be hand-rolled around the jpackage app-image with `appimagetool`, or dropped in favour of deb/tarball. Every candidate needs the shared PATH, WSL and terminal workarounds. The columns differ on these:
- **Electron:** fewest ⚠️, at the cost of bundle size and memory (see 02).
- **Tauri:** Linux WebKitGTK, and AppImage-only updates on Linux.
- **Wails v3:** new updater that is AppImage-only in practice on Linux, Linux WebKitGTK, and a deprecated GTK3 path that puts LTS distros at risk once it is removed.
- **Flutter:** community plugins for tray, updater and installers.
- **Compose:** no AppImage, no updater, macOS file watching by polling, so it effectively requires Conveyor (deb/apt on Linux).
- **Avalonia/Qt:** packaging and signing are more manual, but Velopack covers updates.

## Answers to the owner's questions

- **Q5. Could native-side blockers come up with a cross-platform framework?**
  - Yes, but mostly ones that native apps share. The PATH probe, TCC and notarization, SmartScreen, Flatpak confinement, WSL quoting and latency, and file watching over `\\wsl$` hit SwiftUI, GTK4 and WinUI 3 as much as Electron.
  - The framework-specific blockers worth weighing are:
    - Linux WebKitGTK rendering (Tauri, Wails)
    - Wails v3's deprecated GTK3/WebKitGTK 4.1 path: still in 3.1.0, but once it is removed Ubuntu 22.04, Debian 12, Fedora ≤ 39 and RHEL 9 drop out [25]
    - the Tauri and Wails updaters skipping deb and rpm
    - Compose lacking AppImage (even with Conveyor) and an updater
    - Flutter relying on community plugins for tray, updates and installers
  - None of them blocks the WSL2 requirement once WSL is treated as a remote host with a long-lived in-distro process (`devscene runs watch --json`, see 05). That is the single most important architectural decision for Windows, and it doesn't depend on the framework.
- **Q6. Financial costs in this area:**
  - Apple Developer Program, $99/year (notarization costs nothing extra) [40].
  - Windows signing (mandatory, see §7): Azure Artifact Signing at $9.99/month if you're eligible (US/CA/EU/UK organisations with 3+ years of tax history, or US/CA individuals), otherwise an OV certificate at $300–500/year [42][43].
  - Conveyor: $45/month unless the app is OSI open source [49].
  - Velopack, electron-updater, the Tauri updater, the Wails updater and Sparkle are free.
  - Update hosting can be GitHub Releases at no cost, or any static host or CDN.
- **Q7 (touches this area):**
  - The **Tauri `stronghold` plugin** has had no release since 2025-10.
  - **Flutter `auto_updater`** has had no release since 2024-10.
  - **Wails v3's GTK3 path** is deprecated and slated for removal. As of v3.1.0 it hasn't been removed [25].
  - Flutter desktop's maintenance and roadmap moved to Canonical (Google I/O 2026), a handover rather than a wind-down [57b].

## Risks and open questions

1. **WSL streaming process.** 05 recommends the harness's own `devscene runs watch --json` (Issue item 7) over a bundled helper; the open WSL-side work is to spike it through `wsl.exe` with cold-start timing, pgid kill, VM idle shutdown and reconnect (see 05, Risks).
2. **Cold-start latency** of `wsl.exe` and of `\\wsl.localhost` auto-start on Windows 10 isn't measured. Microsoft says only Windows 11 auto-starts the distro through `wsl.localhost` [6].
3. **Artifact Signing eligibility** depends on the owner's country and the company's age. If the owner is an individual outside US/CA, or a company younger than 3 years, budget for an OV certificate at $300–500/year [43].
4. **AppImage runtime for Tauri:** since tauri-bundler 2.6 the AppImage "should" no longer need libfuse2 [70]. Verify on a clean Ubuntu 24.04 VM before relying on it.
5. **TCC behaviour** for the `devscene`/`node` child processes launched from the app on macOS 26/27 needs a real test. The forum reports are anecdotal [36][37].
6. **Wails v3 and Tauri v3/CEF maturity.** Both are weeks old (Wails 3.0 GA on 2026-10-26; Tauri CEF in alpha). Re-check in Q1 2027.
7. **Linux tray on GNOME:** decide whether the tray is a core feature. If it is, document the AppIndicator extension requirement.
8. **The `\\wsl$` watching gap is secondary evidence only**: one bot-closed 2019 issue and two user-forum reports [66][14][15], with no Microsoft statement and no test on WSL 3.0.x. A 15-minute test with `FileSystemWatcher`, notify or chokidar on `\\wsl.localhost` would settle it (05 asks for the same probe).

## Sources

1. https://v2.tauri.app/plugin/shell/ — Tauri shell plugin: capability scopes and allow-listed commands, blocked by default. Accessed 2026-11-12.
2. https://github.com/tauri-apps/fix-path-env-rs and https://v1.tauri.app/v1/guides/building/macos — fix PATH for GUI apps on macOS and Linux. Accessed 2026-11-12.
3. https://github.com/sindresorhus/fix-path/issues/11 — the npm fix-path package's side-effects in Electron. Accessed 2026-11-12 (old issue; flag).
4. https://github.com/tekartik/process_run.dart/issues/36 — Flutter `.app` loses the Homebrew PATH. Accessed 2026-11-12 (older than 12 months).
5. https://docs.flutter.dev/platform-integration/macos/building — Flutter macOS apps are sandboxed by default, entitlements, Hardened Runtime. Accessed 2026-11-12.
6. https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop — `wsl -d … --`; `\\wsl$` needs a running distro and `wsl.localhost` auto-starts it on Windows 11; 9P performance table (page dated 2026-07-16). Accessed 2026-11-12.
7. https://learn.microsoft.com/en-us/windows/wsl/filesystems — cross-filesystem performance, `WSLENV`. Accessed 2026-11-12.
8. https://wsl.dev/technical-documentation/plan9/ — `p9rdr.sys` serves both `\\wsl$` and `\\wsl.localhost` over Plan 9/hvsocket and auto-starts the distro. Accessed 2026-11-12.
9. https://github.com/microsoft/WSL/issues/4607 and https://github.com/microsoft/WSL/releases/tag/0.64.0 — UTF-16 output of `wsl --list`; 0.64.0 notes: "opt-in `WSL_UTF8=1` environment variable to force UTF8 encoding". Accessed 2026-11-12 (old; behaviour current).
10. https://wsl.dev/technical-documentation/boot-process/ — `wslhost.exe` takes over interop when `wsl.exe` exits early. Accessed 2026-11-12.
11. https://forum.cursor.com/t/agent-shell-commands-survive-after-cursor-closes-leaving-orphaned-high-cpu-processes-in-wsl/161340 — orphaned WSL processes re-parented to `/init`. Accessed 2026-11-12.
12. https://raw.githubusercontent.com/notify-rs/notify/main/notify/src/lib.rs ("Known Problems", lines 39–48; see also https://github.com/notify-rs/notify/issues/254) — NFS may emit no events; under WSL2, Linux inotify on `/mnt/c/...` may miss changes made by Windows apps (the reverse of Windows watching `\\wsl$`); PollWatcher fallback. Accessed 2026-11-12.
13. *(Withdrawn after review: https://github.com/zed-industries/zed/pull/22660 is about watching a missing or symlinked `settings.json` on Windows and says nothing about WSL. No longer cited.)*
14. https://resource.dopus.com/t/wsl2-file-system-changes-are-not-updated-automatically-have-to-press-f5-manually/53329 — no change notifications on `\\wsl.localhost`. Accessed 2026-11-12.
15. https://forum.syncthing.net/t/filesystem-watcher-errors-incorect-function/17756 — watcher errors on a `\\wsl$` folder. Accessed 2026-11-12.
16. https://code.visualstudio.com/docs/remote/wsl — VS Code Server runs inside WSL. Accessed 2026-11-12.
17. https://claudeissues.com/issue/98440-bug-windows-wsl-desktop-diff-panel-git-probes-still-leak-orphaned-git-exe-after and https://dev.to/aleixrodriala/i-built-the-vs-code-remote-wsl-extension-but-for-github-desktop-4pic — Windows git over 9P is slow. Accessed 2026-11-12.
18. https://api.dart.dev/stable/dart-io/FileSystemEntity/watch.html — Dart watch backends; no recursion on Linux; Windows overflow. Accessed 2026-11-12.
19. https://doc.qt.io/qt-6/qfilesystemwatcher.html — QFileSystemWatcher fd limits. Accessed 2026-11-12.
20. https://bugs.openjdk.org/browse/JDK-8293067 — macOS WatchService is polling; FSEvents implementation unresolved. Accessed 2026-11-12.
21. https://patchwork.kernel.org/comment/23714847/ and https://watchexec.github.io/docs/inotify-limits.html — inotify defaults since 5.11. Accessed 2026-11-12.
22. https://v2.tauri.app/develop/debug/linux-graphics/ — WebKitGTK blank, flicker and Error 71 problems and env-var workarounds (tauri#9394). Accessed 2026-11-12.
23. https://v2.tauri.app/reference/webview-versions/ — engine per OS. Accessed 2026-11-12.
24. https://v2.tauri.app/distribute/appimage/ — glibc baseline, WebKitGTK 4.1, 70 MB+, no ARM cross-build. Accessed 2026-11-12.
25. https://github.com/wailsapp/wails/blob/v3.1.0/docs/mpress/content/guides/build/linux.md — GTK4/WebKitGTK 6.0 default; legacy `-tags gtk3` (WebKit2GTK 4.1) path "scheduled for removal in v3.1" but still documented at the v3.1.0 tag, with the `*gtk3*` build-tagged files still in the v3.1.0 tree (`gh api repos/wailsapp/wails/git/trees/v3.1.0?recursive=1`); AppImage/deb/rpm via nfpm. Accessed 2026-11-12.
26. https://github.com/wailsapp/wails/releases/tag/v3.1.0 (and v3.0.0, published 2026-10-26) — tray, notifications, updater fixes. Accessed 2026-11-12.
27. https://github.com/wailsapp/wails/blob/v3.1.0/docs/mpress/content/guides/updater.md — Wails v3 updater providers; stages "beside the installed binary… so that directory must be writable"; AppImage via `$APPIMAGE`; `.dmg`/`.pkg`/`.msi` "not supported in v1". Accessed 2026-11-12.
28. https://github.com/tauri-apps/tauri/releases/tag/tauri-v3.0.0-alpha.0 — Tauri v3 alpha (2026-09-13) with the CEF runtime. Accessed 2026-11-12.
29. https://github.com/AppImage/type2-runtime and https://www.electron.build/docs/appimage — the static runtime needs no libfuse2; electron-builder uses a "static AppImage runtime that does not depend on FUSE2". Accessed 2026-11-12.
30. https://fedoraproject.org/wiki/Changes/AtomicDesktopDropFuse2 — distros dropping FUSE2. Accessed 2026-11-12.
31. https://www.man7.org/linux/man-pages/man1/flatpak-spawn.1.html — `flatpak-spawn --host` needs `org.freedesktop.Flatpak`. Accessed 2026-11-12.
32. https://docs.flathub.org/docs/for-app-authors/linter — `finish-args-flatpak-spawn-access` warning ("allows commands to run outside the sandbox"); "Warnings do not require an exception". Accessed 2026-11-12.
33. https://snapcraft.io/docs/reviewing-classic-confinement-snaps and https://forum.snapcraft.io/t/process-for-reviewing-classic-confinement-snaps/1460 — classic confinement review: supported and unsupported categories; "classic will usually not be granted" if strict confinement with interfaces works. Accessed 2026-11-12.
34. https://www.electron.build/docs/notarization — Hardened Runtime and Electron JIT entitlements. Accessed 2026-11-12.
35. https://developer.apple.com/documentation/security/hardened-runtime — what the hardened runtime restricts. Accessed 2026-11-12.
36. https://www.qt.io/blog/the-curious-case-of-the-responsible-process — TCC responsible-process attribution for children. Accessed 2026-11-12.
37. https://github.com/anthropics/claude-code/issues/64685 — disclaimed child gets EPERM on `~/Documents`. Accessed 2026-11-12.
38. https://appleinsider.com/articles/24/08/06/apple-removes-control-click-option-for-skipping-gatekeeper-in-macos-sequoia — Gatekeeper bypass change (2024; older than 12 months, behaviour current). Accessed 2026-11-12.
39. https://developer.apple.com/forums/thread/839181, https://developer.apple.com/forums/thread/837671 (team enrolled 2026-05-01, rejected for two months; DTS reply sends it to Program Support) and https://developer.apple.com/forums/thread/839636 ("across three calendar months") — 2026 notarization `statusCode 7000` delays **[secondary]**. Accessed 2026-11-12.
40. https://developer.apple.com/forums/thread/746992 — no extra fee for notarization; the $99 membership. Accessed 2026-11-12.
41. https://docs.avaloniaui.net/docs/deployment/macOS and https://learn.microsoft.com/dotnet/core/install/macos-notarization-issues — Avalonia and .NET notarization entitlements. Accessed 2026-11-12.
42. https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation and https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options — EV no longer bypasses SmartScreen (no date given); Smart App Control blocks unsigned files on Windows 11; Artifact Signing "Starts at $9.99/month" (page updated 2026-08-17). Accessed 2026-11-12.
43. https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview (updated 2026-10-12) — Artifact Signing Public Trust eligibility (US/CA/EU/UK organisations with "a verifiable tax history of three or more years"; US/CA individuals), "Basic: ~$10/month", OV certificate "$300–500/year"; and https://azure.microsoft.com/pricing/details/artifact-signing/ — tiers and quotas. Accessed 2026-11-12.
44. https://v2.tauri.app/distribute/windows-installer/ — WebView2 install modes and sizes; MSI only built on Windows. Accessed 2026-11-12.
45. https://github.com/electron-userland/electron-builder/blob/master/website/docs/features/auto-update.md — electron-updater targets; deb/rpm/pacman install via pkexec/sudo with an auth prompt (lines 222–229). Accessed 2026-11-12.
46. https://www.electronjs.org/docs/latest/api/auto-updater — the built-in autoUpdater has no Linux support. Accessed 2026-11-12.
47. https://v2.tauri.app/plugin/updater/ — Tauri updater artifacts per OS; Linux AppImage only. Accessed 2026-11-12.
48. https://docs.velopack.io/ and https://docs.velopack.io/packaging/operating-systems/linux — Velopack languages; Linux = AppImage. Accessed 2026-11-12.
49. https://hydraulic.dev/pricing.html — Conveyor: free for OSI, Standard $45/month, Source by quote. Accessed 2026-11-12.
50. https://kotlinlang.org/docs/multiplatform/compose-native-distribution.html — Compose formats (no AppImage), no cross-compile, notarize tasks, points to Conveyor. Accessed 2026-11-12.
51. https://github.com/sparkle-project/Sparkle/releases — Sparkle 2.10.1 (2026-10-25). Accessed 2026-11-12.
52. https://pub.dev/packages/auto_updater and https://github.com/leanflutter/auto_updater — latest 1.0.0 published 2024-10-27, platforms macOS and Windows only (stale). Accessed 2026-11-12.
53. https://pub.dev/packages/velopack_flutter — community Velopack bridge, 0.3.3 published 2026-10-19. Accessed 2026-11-12.
54. https://www.electronjs.org/docs/latest/api/safe-storage — safeStorage backends; `basic_text` fallback; sync API deprecated in 45.0.0, removed in Electron 46 (46.0.0-alpha.10 on 2026-11-12, `gh release list -R electron/electron`). Accessed 2026-11-12.
55. https://www.electronjs.org/docs/latest/tutorial/fuses — `runAsNode` fuse; `fork` throws when it's off; use `utilityProcess`. Accessed 2026-11-12.
56. https://docs.avaloniaui.net/docs/reference/controls/tray-icon and https://github.com/pr8x/DesktopNotifications — Avalonia tray Linux caveat; third-party notifications. Accessed 2026-11-12.
57. https://github.com/fsnotify/fsnotify — kqueue needs an fd per file, no FSEvents, no recursion, no events on network filesystems. Accessed 2026-11-12. (57b: https://www.omgubuntu.co.uk/2026/05/flutter-desktop-canonical-maintained — Canonical stewardship of Flutter desktop, **[secondary]**.)
58. https://github.com/microsoft/WSL/releases/tag/3.0.1 — WSL 3.0 / WSLc GA (2026-09-29). Accessed 2026-11-12.
59. https://github.com/microsoft/WSL/issues/1746 — inconsistent wsl.exe argument quoting (old; flag). Accessed 2026-11-12.
60. Release metadata via `gh release list` for electron/electron, tauri-apps/tauri, wailsapp/wails, JetBrains/compose-multiplatform, AvaloniaUI/Avalonia, velopack/velopack, paulmillr/chokidar, notify-rs/notify and microsoft/WSL. Accessed 2026-11-12.
61. https://v2.tauri.app/release/stronghold/all-versions/ — Stronghold plugin last release 2.3.1 (2025-10-27). Accessed 2026-11-12.
62. https://dev.to/fengzeng/fixing-wayland-crashes-in-tauri-appimage-linuxdeploy-gtk-issue-1381 — bundled Wayland libraries crash AppImages; exclusion fix **[secondary]**. Accessed 2026-11-12.
63. https://takazudo-zudo-tauri.pages.dev/pj/zudo-tauri/docs/frontend/playwright-engine-pitfall — no WKWebView WebDriver; engine differences **[secondary]**. Accessed 2026-11-12.
64. https://github.com/Vladimir-csp/xdg-terminal-exec — proposed default-terminal launcher spec for Linux **[secondary]**. Accessed 2026-11-12.
65. https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments — `wt.exe` command-line arguments. Accessed 2026-11-12.
66. https://github.com/microsoft/WSL/issues/4581 — "Unable to watch directory changes via `\\wsl$\` redirector": `FindFirstChangeNotification` repro fails; opened 2019, closed by an inactivity bot on 2024-02-01 with no fix **[secondary]**. Accessed 2026-11-12.
67. https://conveyor.hydraulic.dev/latest/package-formats/ — Conveyor Linux output: a deb inside an apt repository (updates via apt) and a plain tarball "which doesn't auto update"; RPM planned; AppImage not offered. Accessed 2026-11-12.
68. https://github.com/JetBrains/compose-multiplatform/blob/master/tutorials/Signing_and_notarization_on_macOS/README.md — Compose Desktop entitlements plist with `com.apple.security.cs.allow-jit`. Accessed 2026-11-12.
69. https://api.dart.dev/stable/dart-io/Process/kill.html — `Process.kill` "sends the `signal` to the process"; no process-group option documented. Accessed 2026-11-12.
70. https://github.com/tauri-apps/tauri/blob/tauri-v2.12.5/crates/tauri-bundler/CHANGELOG.md (2.6.0, PR #13913) — bundler pulls the latest linuxdeploy AppImage plugin; "This should remove the libfuse requirement". Accessed 2026-11-12.
