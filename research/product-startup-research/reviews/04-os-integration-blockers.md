# Review — 04-os-integration-blockers.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The main conclusions hold up when re-checked live. The hard problems (GUI PATH, WSL, SmartScreen, notarization) don't depend on the framework. Windows should treat WSL as a remote host with an in-distro process that streams JSON. Linux webview and packaging/update coverage are where the frameworks really differ. Most load-bearing facts check out, including:
- Tauri's WebKitGTK page and its AppImage-only updater
- `auto_updater`, last released 2024-10-27, with no Linux support
- Flutter's sandbox on by default
- Conveyor at $45/month
- Velopack's AppImage-only Linux support
- EV no longer bypassing SmartScreen
- 9P being "slow… not for tight loops"
- the JIT entitlements
- `flatpak-spawn` and the Snap classic review
- `WSL_UTF8`

Four errors need fixing:
1. The Wails v3.1 GTK3 claim.
2. Conveyor being offered as the fix for Compose AppImage.
3. Artifact Signing eligibility leaves out the 3-year rule for organisations.
4. Two of the four sources for "can't watch `\\wsl$` from Windows" don't say that.

Beyond that, several matrix cells cite the wrong source or none, the scope cross-references point at the wrong files, and the WSL-PATH advice contradicts 05.

## Must fix

**M1. Wails v3.1 does not drop GTK3, Ubuntu 22.04, Debian 12 or RHEL 9.**
- **Location:** TL;DR bullet 5 ("Wails v3.1 now *requires* GTK4/WebKitGTK 6.0, which drops Ubuntu 22.04, Debian 12 and RHEL 9"); §4 "Distro version spread"; matrix A "UI rendering" and B "Linux AppImage" Wails cells; Q5 ("Wails v3 dropping WebKitGTK 4.1"); Q7 ("Wails v3's GTK3 path has been removed"); Reading the matrix ("WebKitGTK 6 drops LTS distros").
- **Problem:** The file's own source [25], read at tag `v3.1.0`, still says: "A legacy GTK3 / WebKit2GTK 4.1 path is still available for distributions that don't yet ship WebKitGTK 6.0 (Ubuntu 22.04 LTS, Debian 12, Fedora ≤ 39, RHEL 9.x). The legacy path is opt-in via a build tag and is scheduled for removal in v3.1." The v3.1.0 source tree still ships the `gtk3` build-tagged files, for example `v3/internal/operatingsystem/webkit_linux_gtk3.go` with `//go:build linux && cgo && gtk3 …`. Those files are also still on `master`. The v3.1.0 release notes say nothing about removing GTK3. The v3.0.0 notes say only "legacy GTK3 stack is still available with `-tags gtk3` until v3.1". Removal was announced, but it did not ship in 3.1.0.
- **Evidence:**
  - `gh api repos/wailsapp/wails/contents/docs/mpress/content/guides/build/linux.md?ref=v3.1.0` (lines 109–146)
  - `gh api repos/wailsapp/wails/git/trees/v3.1.0?recursive=1`, which lists 10 `*gtk3*` files
  - https://github.com/wailsapp/wails/releases/tag/v3.1.0
- **Fix:**
  - **TL;DR:** "Wails v3 defaults to GTK4/WebKitGTK 6.0. The opt-in `-tags gtk3` (WebKitGTK 4.1) path still ships in 3.1.0, but it is announced for removal. Once it goes, Ubuntu 22.04, Debian 12, Fedora ≤ 39 and RHEL 9 drop out [25]."
  - **Matrix cells:** "⚠️ WebKitGTK [22]; GTK3 path deprecated, LTS distros at risk [25]".
  - **Q7:** "Wails v3's GTK3 path is deprecated and slated for removal. As of v3.1.0 it hasn't been removed."

**M2. Conveyor doesn't produce AppImages (or rpm), so it isn't "the fix" for the Compose/AppImage ❌.**
- **Location:** Matrix B, Compose "Linux AppImage" ("❌ unsupported by plugin, so Conveyor"); "Reading the matrix" ("that one has a paid or free-for-OSS fix in Conveyor"); §8 Conveyor row ("All three"); TL;DR bullet 6.
- **Problem:** On Linux, Conveyor produces a `.deb` that installs an apt repository (that's how it updates) and a plain tarball that doesn't update. RPM is listed as "planned". AppImage isn't mentioned at all. So on Linux, Conveyor gives Compose deb plus an apt repo, not AppImage. The ❌ stays a ❌ for AppImage. The real fix is to wrap the jpackage app-image with `appimagetool` by hand, or to accept deb/tarball only.
- **Evidence:** https://conveyor.hydraulic.dev/latest/package-formats/ ("Future versions of Conveyor are planned to support: RPMs…"; the tarball is not auto-updated). The pricing at https://hydraulic.dev/pricing.html is confirmed: free for OSI licences, Standard $45/month with 3 apps, Source by quote.
- **Fix:**
  - **Compose AppImage cell:** "❌ no AppImage in the plugin or in Conveyor. Hand-roll it with appimagetool [50]."
  - **§8 Conveyor row, Platforms:** "macOS, Windows, Linux **deb + apt repo / tarball** (no AppImage, rpm planned)".
  - **Reading the matrix:** "The only ❌ is Compose/AppImage. Conveyor gives Compose updates and cross-builds, but on Linux only through deb/apt."

**M3. Artifact Signing eligibility leaves out the rule that matters for a new company, and the price has a primary source.**
- **Location:** §7 "Signing options"; TL;DR bullet 9; Q6; Risk 3.
- **Problem:** Microsoft's MSIX signing page says Public Trust is "Available to organizations in the USA, Canada, the European Union, and the United Kingdom, and to individual developers in the USA and Canada. **Organizations must have a verifiable tax history of three or more years.**" A newly founded DevScene company won't qualify as an organisation, whatever its country. The file also relies on an AI-generated Q&A answer [43] for eligibility, and says the price "doesn't render". Two Microsoft pages state the price: "Starts at $9.99/month" (SmartScreen page) and "Basic: ~$10/month", with OV "$300–500/year" (MSIX page).
- **Evidence:**
  - https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview (updated 2026-10-12)
  - https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation (updated 2026-08-17)
- **Fix:**
  - Replace the Q&A citation in [43] with these two pages.
  - Add the 3-year tax-history rule to §7, the TL;DR and Risk 3: "If the owner is an individual outside US/CA, or a company younger than 3 years, budget for an OV certificate at $300–500/year."
  - Change "historically about $9.99" to "$9.99/month (Microsoft Learn) [42]". Mark it **[verified]**.

**M4. The evidence for "Windows-side watchers get no events on `\\wsl$`" is mis-cited.**
- **Location:** TL;DR bullet 3 ("[12][13][14][15]"); §2 "File watching across the boundary" bullets 1–2; matrix A "Watch files over `\\wsl$`", whose cells cite [12] and [13].
- **Problem:**
  - **[12] notify-rs** describes the *opposite* direction. Its "Known problems" text reads: "In Linux programs running under WSL, RecommendedWatcher uses inotify. On WSL2, changes made by Windows applications to files on Windows filesystems (such as `/mnt/c/...`) may not produce inotify events." That is Linux watching `/mnt/c`, not Windows watching `\\wsl$`.
  - **[13] Zed PR #22660** adds parent-directory and symlink watching for `settings.json`. It doesn't mention ReadDirectoryChangesW, network filesystems or WSL.
  - That leaves two user-forum reports, [14] and [15], plus microsoft/WSL#4581 ("Unable to watch directory changes via `\\wsl$\` redirector", opened 2019 and closed by a bot on 2024-02-01 with no fix), which 05 cites. The conclusion is still plausible, and the helper-in-WSL design doesn't depend on it, but the stated evidence is wrong.
- **Evidence:**
  - https://raw.githubusercontent.com/notify-rs/notify/main/notify/src/lib.rs (lines 39–48)
  - https://github.com/zed-industries/zed/pull/22660
  - `gh issue view 4581 -R microsoft/WSL`
- **Fix:**
  - Drop [12] and [13] from this claim and from the watch-over-`\\wsl$` matrix row. Cite microsoft/WSL#4581, [14] and [15], tagged **[secondary]**.
  - Keep [12] only for its real point: in the reverse direction (Linux watching `/mnt/c`), inotify misses Windows-side changes. That matters if users keep repos on `/mnt/c`, so it's worth one line.
  - Keep Risk 8, the 15-minute probe. It is now the only thing that can upgrade this claim.

## Should fix

**S1. The WSL nvm/PATH advice contradicts 05 and would break on a default nvm install.**
- **Location:** §2 "Non-login shell PATH" and the helper command `wsl.exe -d X -- bash -lc 'node ~/.devscene/studio-helper.js'`.
- **Problem:** The nvm installer appends its init to `~/.bashrc`, and Ubuntu's default `~/.bashrc` returns early for non-interactive shells. So `bash -lc` does *not* find nvm's `node` on the default setup. The file treats `-i` as an edge case ("if the user's nvm init lives only in `.bashrc`"), but that is the default case. 05 §2 gets this right.
- **Fix:** Use 05's recipe:
  1. Resolve the paths once with `wsl.exe -d <distro> -- bash -ilc 'command -v node; command -v devscene'`.
  2. Cache them.
  3. Exec with `wsl.exe -d <distro> --cd <dir> --exec <abs-node> <abs-script> …`.

  Give the helper example the same shape.

**S2. The Wails v3 updater has the same Linux deb/rpm gap as Tauri, which the matrix doesn't show.**
- **Location:** §8 Wails row ("macOS, Windows, Linux binary swap"); matrix B auto-update cell.
- **Problem:** The updater stages "in a `wails-update-*` directory beside the installed binary… so that directory must be writable". It handles AppImage through `$APPIMAGE`. `.dmg`, `.pkg` and `.msi` are "not supported in v1", so you ship a `.zip` instead. A deb or rpm install under `/usr` isn't user-writable, so in practice Linux self-update means AppImage (or a user-local install), just as with Tauri. By contrast, electron-updater handles deb, rpm and pacman through pkexec with an auth prompt.
- **Evidence:**
  - `gh api repos/wailsapp/wails/contents/docs/mpress/content/guides/updater.md?ref=v3.1.0` (lines 68–70, 280)
  - https://github.com/electron-userland/electron-builder/blob/master/website/docs/features/auto-update.md (lines 22, 222–229)
- **Fix:** Wails row: "macOS `.app` zip, Windows, Linux AppImage or a user-writable binary (not deb/rpm); no dmg/msi in v1". Cell: "⚠️ new (3.0); AppImage-only in practice on Linux [27]". Optionally, note the pkexec prompt in the electron-updater row.

**S3. Several non-✅ matrix cells have no source, or cite one that doesn't support them.**
- **Wrong source:**
  - Flutter "Stream and kill tree ⚠️ no pgroup API [18]": [18] is the Dart `watch` doc. Cite `dart:io` `Process.kill`, or mark the cell [inferred] as §1 already does.
  - Qt/PySide6 "PyInstaller/Nuitka signing is manual [41]": [41] covers Avalonia and .NET.
  - WinUI 3 "Windows App SDK runtime or MSIX [42]": [42] is the SmartScreen page.
  - GTK4 "AppImage is awkward; Flatpak is its native home [31]": [31] is the `flatpak-spawn` man page.
  - Compose "JIT [50]" (§6 and matrix B): the KMP distribution page lists only `notarize*` tasks and says nothing about entitlements. Cite the Compose signing/notarization tutorial instead.
- **No source:**
  - Flutter: Windows installer, AppImage, deb, tray, notifications
  - Avalonia: deb, "Parcel"
  - Qt: deb, notifications
  - Compose: notifications
  - Secure storage for Wails, Flutter, Compose and Avalonia
  - GTK4: auto-update
  - Tauri "⚠️ glibc baseline" ([24] does cover this; fine)
- **Fix:** Add a source for each, or tag the cell [inferred] in the matrix.

**S4. The scope cross-references point at the wrong files.**
- **Location:** Scope ("framework momentum… (01/02)", "performance (03)", "career value and N-native cost (05/06)", "see the cost area"); Reading the matrix ("bundle size and memory (see 03)").
- **Problem:** The actual files are:
  - 01: landscape, health, deprecation and **costs**
  - 02: performance
  - 03: native-vs-cross effort **and career value**
  - 05: harness integration
  - There is no 06.
- **Fix:**
  - "momentum and licence costs (01)"
  - "performance, bundle size and memory (02)"
  - "N-native cost and career value (03)"
  - "harness integration contract (05)"

**S5. Snap classic is likely to be refused for this app, not just slow.**
- **Location:** §5 Snap row.
- **Problem:** Snapcraft's review criteria list "dependent software only available on host", "management snaps", "access to dot files in $HOME" (the `gh` config lives there) and "running arbitrary command" as unsupported reasons or reasons that need strong justification. They also say classic "will usually not be granted" if strict confinement with interfaces can work. The "IDEs have precedent" framing overstates the odds. Snap and Flathub are also store channels, which the brief excludes.
- **Evidence:** https://forum.snapcraft.io/t/process-for-reviewing-classic-confinement-snaps/1460
- **Fix:** "Not viable. Classic needs vetting, and this app's reasons (it runs host `git`/`gh`, reads `~/.config/gh`) fall into categories the store usually rejects. Snap and Flathub are also store channels, which the brief excludes." The Flathub sentence ("still subject to manual permission review") is also loose: the linter page says "Warnings do not require an exception".

**S6. The notarization 7000 claim is right but under-sourced.**
- **Location:** §6 "Account issues".
- **Problem:** [39] is one thread reporting "11+ days" since 2026-07-09. The file says "several… for weeks". More threads confirm the claim is real and widespread:
  - https://developer.apple.com/forums/thread/837671 ("persistent for 2 months")
  - https://developer.apple.com/forums/thread/839636 ("unresolved across three calendar months")
  - https://developer.apple.com/forums/thread/851685 ("since June 2026")
  - https://developer.apple.com/forums/thread/837536 (new team)

  Some reports come from established teams that hit it suddenly, not only new teams. A moderator says the error is an account matter for Developer Programs Support.
- **Fix:** Cite 2–3 of these threads, and say "new and some existing teams, weeks to months". Keep the "enrol early" advice and add "and notarize a test build in week 1".

**S7. Windows 11 Smart App Control is missing.**
- **Location:** §7 Windows.
- **Problem:** The SmartScreen page the file already cites says: "On Windows 11 devices, the Smart App Control feature may supersede SmartScreen… Smart App Control will block execution of unsigned files unless the file has a positive reputation." That turns "unsigned means a warning" into "unsigned means blocked" on SAC-enabled machines. It also affects the Windows app's own helpers and installer.
- **Evidence:** https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation
- **Fix:** Add one bullet, and make signing mandatory on Windows in the TL;DR.

**S8. The "since 2024" date for the EV/SmartScreen change has no source.**
- **Location:** TL;DR bullet 9 and §7.
- **Problem:** The Microsoft page [42] says "Years ago… this behavior no longer exists" and gives no year. The claim is [verified]; the date is not.
- **Fix:** Drop "(since 2024)", or cite a dated source for it and tag that part [secondary].

**S9. Risk 4 (the Tauri AppImage runtime) can mostly be answered.**
- **Problem:** The tauri-bundler 2.6.0 changelog says: "The bundler now pulls the latest AppImage linuxdeploy plugin instead of using the built-in one. This should remove the libfuse requirement." ([#13913](https://github.com/tauri-apps/tauri/pull/13913)).
- **Evidence:** `crates/tauri-bundler/CHANGELOG.md` at `tauri-v2.12.5`
- **Fix:** Cite it in §5 and Risk 4: "since tauri-bundler 2.6 the AppImage should not need libfuse2. Verify on a clean Ubuntu 24.04 VM." electron-builder's static FUSE-free runtime is confirmed: https://www.electron.build/docs/appimage ("static AppImage runtime that does not depend on FUSE2").

**S10. Some confidence tags can be raised or should be sharpened.**
- **Raise:** `WSL_UTF8=1` is in the primary WSL 0.64.0 release notes ("opt-in `WSL_UTF8=1` environment variable to force UTF8 encoding"), so tag that row [verified]. "Only the value `1` works" is still unsourced.
- **Sharpen:** Electron `safeStorage`. The doc says the sync methods are "deprecated" in 45.0.0 and "will be removed in Electron 46". 46 is at alpha.10, so write "is removed in 46 (alpha today)". "A bare `-c` is rejected" (§2 Quoting) has no source.

## Nice to have

**N1. Content that overlaps 05 could become cross-references.**
- **Duplicated material:**
  - TL;DR bullet 4 ("weakens Electron's in-process reuse")
  - §1 row "Run the `devscene` Node CLI" (Node sidecar "about 40–90 MB")
  - The §2 paragraph on the VS Code model / helper
  - Risk 1 (helper versus `devscene runs watch --json`)
- **Problems:**
  - 05 covers these in depth, with harness evidence. 05 shows that the run logic is ~22.5k lines of bash, so even macOS/Linux reuse is weak, not just Windows.
  - The sidecar sizes disagree (40–90 MB here, 57–93 MB in 05).
  - The recommendations also differ: 04 leans toward a bundled `studio-helper.js`, while 05 recommends `devscene runs watch --json`.
- **Fix:** Cut these to one line: "Integration shape, sidecar and the `runs watch` NDJSON stream: see 05." Keep 04's WSL-specific mechanics: quirks table, kill/pgid, cold start, 9P. 04 is the better home for the macOS GUI-PATH probe, so 05 could shrink its copy to a pointer.

**N2. Tray, notifications, deep links and secure storage are low-relevance for this app.**
- **Problem:** §9 and four matrix rows give these as much weight as the core rows, but none is a core flow. Auth stays in `gh`, and Issue #1 has no tray requirement.
- **Fix:** Collapse them into one "nice-to-have integrations" row, or mark them "(low need)" as the secure-storage row already does. That keeps the matrix focused on spawn, WSL, Linux rendering, packaging and update.

**N3. Velopack facts are confirmed but could be cited more precisely.**
- **Checked:** Velopack's coverage is confirmed. Linux is AppImage only ("it simply creates an `.AppImage` file"), with pkexec elevation for privileged folders. The SDKs C#, Rust, JS, C++ and Python are "Ready"; Java, Swift and Go are "Planned". `velopack_flutter` 0.3.3 was published 2026-10-19 (pub.dev).
- **Fix:** Note "Go: planned", which is relevant if Wails users consider Velopack. Cite the pub.dev version for [53].

**N4. Flutter `auto_updater` is confirmed and could be cited more strongly.**
- **Checked:** On pub.dev the latest version is 1.0.0, published 2024-10-27, with only `macos` and `windows` in its platform map. The repo was last pushed 2025-03-29 and isn't archived.
- **Fix:** Cite pub.dev (`https://pub.dev/packages/auto_updater`) alongside GitHub.

**N5. Other items checked and found correct (no change needed).**
- **Releases:**
  - Electron 45.3.1
  - Tauri 2.12.5 (2026-10-21); 3.0.0-alpha.6 (2026-11-06), with `tauri-runtime-cef` alpha.0 on 2026-09-13
  - Wails 3.0.0 (2026-10-26) and 3.1.0 (2026-11-01)
  - CMP 1.12.2
  - Avalonia 12.1.6
  - Velopack 1.2.161
  - Sparkle 2.10.1
  - WSL 3.0.5; WSL containers GA in 3.0.1 (2026-09-29)
- **Tauri:**
  - The WebKitGTK page lists blank window, flicker, crash on resize, DMABuf and Wayland "Error 71", with workarounds in order. Kernel modesetting comes first, which the file omits; it's an NVIDIA <545 kernel parameter, not an env var.
  - The updater: "On Linux… AppImage", and signatures "cannot be disabled".
  - The AppImage page gives the 2–6 MB → 70+ MB growth and the no-ARM-cross-build limit.
- **Compose:** The plugin has no AppImage and no cross-compile, and JetBrains points to Conveyor. JDK-8293067 is still "Open".
- **macOS:** Flutter's "configured by default to be signed, and sandboxed with App Sandbox" is confirmed.
- **Electron:**
  - `allow-jit` is the only default entitlement; `allow-unsigned-executable-memory` is "Legacy Electron only".
  - The `runAsNode` fuse: "With this fuse disabled, child_process.fork throws."
- **.NET:** Four default entitlements.
- **Linux file watching:**
  - Dart `watch`: "Recursive watching is not supported" on Linux; RDCW overflow ends the stream.
  - fsnotify: kqueue uses one fd per file; no NFS/SMB notifications.
- **Flathub:** `finish-args-flatpak-spawn-access` is a warning ("allows commands to run outside the sandbox").
- **Canonical stewardship of Flutter desktop:** announced at Google I/O 2026 (OMG! Ubuntu, 2026-06-01).
- **Microsoft WSL interop page (2026-07-16):** `wsl -d … --`; `\\wsl$` needs a running distro; `wsl.localhost` auto-starts on Windows 11; 9P is "slow… not for tight loops".

**N6. The TL;DR could flag the matrix's single ❌ up front.**
- **Problem:** "No candidate hits a hard ❌" sits awkwardly next to the matrix's one ❌.
- **Fix:** "…on the app's core job. The only ❌ in the matrix is a packaging gap (Compose has no AppImage)."

## Review resolution

Fixes applied to `04-os-integration-blockers.md` on 2026-11-12; status set to `reviewed`. Each factual correction was re-checked live before applying it.

- **M1 — applied.** Re-checked: the v3.1.0 `linux.md` still documents the opt-in `-tags gtk3` path, the v3.1.0 tree still has the `*gtk3*` files, and the v3.1.0 notes don't mention removing it. Fixed in the TL;DR, §4, matrix A (UI rendering), matrix B (AppImage), Reading the matrix, Q5, Q7 and source [25].
- **M2 — applied.** Re-checked on Conveyor's package-formats page: Linux output is a deb with an apt repo, plus a tarball that doesn't auto-update. RPM is "planned" and AppImage isn't mentioned. Fixed in the Compose AppImage cell (appimagetool), the §8 Conveyor row, the auto-update cell, Reading the matrix, the TL;DR and Q5. Added source [67].
- **M3 — applied.** Re-checked: the MSIX signing page (updated 2026-10-12) states the 3-year tax-history rule, "~$10/month" and OV "$300–500/year". The SmartScreen page states "Starts at $9.99/month". The AI-generated Q&A citation in [43] is replaced. Fixed in the TL;DR, §7, Q6 and Risk 3, tagged [verified].
- **M4 — applied.** Re-checked: notify's lib.rs covers Linux inotify on `/mnt/c`, and Zed #22660 covers a missing or symlinked `settings.json`. Neither is about WSL. The claim now rests on microsoft/WSL#4581 (new [66]) plus [14] and [15], tagged [secondary] and marked unconfirmed on WSL 3.0.x. [12] is kept only for the reverse-direction line about `/mnt/c`. [13] is withdrawn. Risk 8 is kept and sharpened.
- **S1 — applied.** §2 now follows 05 §2: resolve with `bash -ilc`, cache the absolute paths, then `--exec <abs-node> <abs-script>`. The `bash -lc 'node ~/.devscene/studio-helper.js'` example is removed. The Linux PATH row and the `wt.exe` hand-off now use `-i`.
- **S2 — applied.** Re-checked the Wails updater doc (writable staging directory, `$APPIMAGE`, no dmg/pkg/msi in v1) and the electron-builder pkexec lines. Updated the §8 Wails and electron-updater rows, the matrix cell, the TL;DR and Q5.
- **S3 — applied.** Wrong sources fixed: Flutter kill now cites `Process.kill` [69] and is tagged [inf]. Qt/PySide6 signing, WinUI 3 and GTK4 AppImage are now [inf]. Compose JIT cites JetBrains' signing tutorial [68], which is re-checked and has `allow-jit`. Unsourced non-✅ cells are tagged [inf], and the legend explains the tag.
- **S4 — applied.** Scope now reads 01 momentum/costs, 02 performance/bundle size/memory, 03 N-native cost/career, 05 harness integration, 06 repo topology and harness fit, and 07 additional criteria. "See 03" in Reading the matrix is now "see 02".
- **S5 — applied.** Re-checked the Snapcraft criteria. One nuance: "running arbitrary commands" appears under criteria that "might require classic" and that may not justify classic on their own. It is not on the unsupported list, and the text now says so. The store-channel point is added. Flathub's "Warnings do not require an exception" was re-checked and is now quoted.
- **S6 — applied.** Re-checked threads 837671 (two months, team enrolled 2026-05-01, DTS reply) and 839636 ("across three calendar months"), and added them to [39]. The text now says "weeks to months", and "notarize a test build in week 1" is added. It is also mentioned in the TL;DR.
- **S7 — applied.** Re-checked the SAC text on the SmartScreen page. Added a §7 bullet. The TL;DR now says Windows signing is mandatory.
- **S8 — applied.** "Since 2024" is dropped. The text now quotes "Years ago…" and notes that Microsoft gives no date.
- **S9 — applied.** Re-checked the 2.6.0 changelog entry (#13913) at `tauri-v2.12.5`. It is cited as [70] in §5 and Risk 4, with the clean-VM verification step. electron-builder's FUSE-free runtime is added to §5 and [29].
- **S10 — applied.** `WSL_UTF8=1` is re-checked in the 0.64.0 notes and tagged [verified]. The unsourced claims "only the value `1` works" and "a bare `-c` is rejected" are removed. safeStorage now reads "deprecated in 45, removed in 46 (46.0.0-alpha.10 today)", with the release list re-checked.
- **N1 — partially applied.** The overlap is cut to cross-references: the TL;DR bullet on Electron in-process reuse is removed, the §1 sidecar row (the 40–90 MB figure) points to 05, the §2 VS Code/helper paragraph and Risk 1 now point to `devscene runs watch --json` in 05, and "helper" wording is replaced throughout. The macOS GUI-PATH probe stays in 04, aligned with 05's `-ilc` recipe. Shrinking 05's copy is not applied, because this pass may edit only 04 and this review.
- **N2 — partially applied.** Tray, notifications, deep links and secure storage are marked "(low need)" in §9 and in the matrix row labels, but they are not collapsed into one row. Separate rows keep each cell's source and [inf] tag visible.
- **N3 — applied.** Go/Java/Swift "Planned" is added to the Velopack row (no Wails path yet). The `velopack_flutter` 0.3.3 date (2026-10-19) is re-checked on pub.dev and cited in [53].
- **N4 — applied.** pub.dev was re-checked: 1.0.0, 2024-10-27, macOS and Windows only. It is cited in [52] and in the §8 Sparkle row.
- **N5 — applied where it called for a change.** Tauri's first workaround, kernel modesetting (an NVIDIA < 545 kernel parameter), is added to §4. The other items needed no change.
- **N6 — applied.** The TL;DR now flags the single ❌ as a packaging gap (Compose has no AppImage).
