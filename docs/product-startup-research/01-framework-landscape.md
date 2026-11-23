# 01 — Framework landscape, health, deprecation and costs
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **There are many credible cross-platform options for macOS, Linux and Windows in late 2026.** Six of them have official Linux support, a stable release in the last six weeks and full-time paid maintainers: Electron, Tauri, Flutter, Compose Multiplatform, Avalonia and Qt. Wails v3 became stable on 2026-10-26 and joins them, with the caveat that it was stable for only about two weeks at the time of writing.
- **Electron (v45.3.1, 2026-11-12) is the lowest-risk choice for this app.** It has an 8-week major cadence, the team supports the latest 3 majors, it is under the OpenJS Foundation, it is MIT licensed, and it costs nothing. The cost is that a team must upgrade it every 8 weeks, or within about 24 weeks at most, to stay on a supported Chromium. It shares the harness's language (TypeScript), so the types for a future `devscene runs … --json` contract are native. It cannot import the run logic, which lives in per-repo bash scripts, and on Windows it must call the CLI through `wsl.exe` like any other stack (see 05).
- **Tauri 2 is healthy (2.12.5, 2026-10-21), but v3 is in alpha (alpha.6, 2026-11-06).** The v3 alpha adds a CEF (Chromium) runtime option and makes GTK3/GTK4 opt-in. In alpha.0 the default wry runtime still enables GTK3 (WebKitGTK); only the CEF runtime moves to GTK4 and Chromium [verified, 6]. A small app started on v2 now will probably face a v2→v3 migration within about a year. Its Linux webview, WebKitGTK, is still the weakest link: Tauri's own docs carry a "Linux graphics issues" page.
- **Flutter desktop is not deprecated.** At I/O 2026 (Flutter 3.44 post, 2026-05-20), Google named Canonical "lead maintainer and Strategic Steward for Flutter Desktop". Canonical leads the desktop roadmap and maintains the Linux, Windows and macOS embedders [verified, 40]. Reading this as reduced first-party Google investment in desktop is an inference [inferred]; it is not abandonment. Flutter 3.50 (2026-11-11) supports Windows, macOS and Linux (Debian and Ubuntu LTS) officially.
- **MAUI ships no Linux support from Microsoft,** even in .NET 11 / MAUI 11.0.0, released 2026-11-10. Linux is available only through Avalonia's MAUI backend (preview, March 2026) or community GTK backends. **Drop MAUI.** Xamarin reached end of support on 2024-05-01.
- **Compose Multiplatform desktop (JVM) is "Stable"** (1.12.2, 2026-10-15), Apache-2.0 and free. Kotlin Multiplatform therefore works for desktop. It runs on the JVM and draws through Skia, so it is not native widgets.
- **The only framework licence costs come from Qt, Slint and Avalonia, and none is forced for an MIT/open app:**
  - **Qt** is LGPLv3 (free with relinking obligations) or commercial (Small Business about €546 / US$618 a year per developer, for companies under €1M revenue). PySide6 is LGPL. PyQt6 is GPL unless you buy a commercial licence.
  - **Slint** is free for proprietary desktop apps under its Royalty-free License 2.0, **on condition that the app discloses that it uses Slint** (otherwise a Commercial licence is needed).
  - **Avalonia's** core is MIT. Its paid tiers are optional tooling and controls (Plus €299/yr, Pro €899/yr per seat). XPF is enterprise-priced (from €9,500).
- **Signing costs the same whatever the framework:**
  - **Apple:** Developer Program US$99/yr, which includes Developer ID and notarization.
  - **Windows, Azure Artifact Signing:** US$9.99/month (Basic), **but individual developers must be in the US or Canada**. Organizations qualify in the EU, UK and several other countries.
  - **Windows, other routes:** a cloud OV certificate (for example Certum Open Source in the cloud, from €49, listed as out of stock on 2026-11-12), or SignPath Foundation, free for OSI-licensed open-source projects.
  - **Linux:** free.
- **Recommended shortlist:**
  - **Viable, in order:** Electron, Tauri 2, Wails 3. Harness integration is equal across stacks (see 05), so the order rests on maturity, Linux rendering (bundled Chromium versus WebKitGTK), the updater and packaging ecosystem and line stability. Electron and Tauri are close.
  - **Viable with caveats:** Flutter, Compose Multiplatform, Avalonia, Qt/PySide6, Electrobun, and native per-platform.
  - **Dropped:** MAUI, React Native desktop (no Linux), Neutralino, Toga, pywebview, Flet, egui/iced/gpui/Fyne/Gio/Slint for this product (see the ranking).

## Scope

This file covers, for each candidate: language, rendering model, per-OS support (especially Linux), latest stable version and date, cadence, backing, momentum, deprecation and support risk, and financial costs including code signing. It does not cover:
- harness integration and WSL process driving, which matter for every framework (see 05), and OS integration blockers (see 04);
- performance benchmarks (see 02);
- career value;
- the native-versus-cross-platform cost model, beyond a framework-health view (see 03);
- packaging and auto-update mechanics (see the distribution area).

GitHub numbers are a snapshot taken through `gh api` on 2026-11-12. Contributor counts are GitHub's contributor count including anonymous contributors, so they are approximate. Star *trend* was not measured; only current totals are given.

## Findings

### 1. Master table — what each candidate is

| Candidate | Language(s) | Rendering model | macOS | Windows | Linux (status) |
|---|---|---|---|---|---|
| **Electron** | TS/JS (Node main process) | Bundled Chromium | Official | Official | Official (x64, arm64) |
| **Tauri 2** | Rust core + any web front-end | System webview (WKWebView / WebView2 / WebKitGTK). v3 alpha adds an optional bundled CEF runtime [verified, 6] | Official | Official | Official, but WebKitGTK quality varies by GPU/driver [verified, 8] |
| **Wails 3** | Go + web front-end | System webview. Linux uses GTK4 + WebKitGTK 6.0 by default [verified, 10] | Official | Official (amd64/arm64) | Official (amd64/arm64) |
| **Flutter** | Dart | Own renderer (Impeller/Skia) | Official, 12–27; Intel Macs are being phased out (Tahoe 26 is the last Intel release, macOS 27 requires Apple Silicon) [verified, 11] | Official, 10/11 | Official, Debian 10–13 and Ubuntu LTS only (20.04–24.04). Canonical now leads desktop [verified, 11, 40] |
| **Compose Multiplatform** | Kotlin (JVM) | Own renderer (Skia via Skiko) | Stable | Stable | Stable (JVM desktop target) [verified, 14] |
| **Avalonia 12** | C#/.NET | Own renderer (Skia) | Official | Official | Official. 12.1 added Wayland [secondary, 17] |
| **.NET MAUI** | C#/.NET | Native widgets (WinUI / Mac Catalyst) | Mac Catalyst | Official | **None from Microsoft.** Avalonia backend in preview, plus community GTK backends [secondary, 18, 19] |
| **Uno Platform** (newcomer check) | C#/.NET | Skia renderer or native | Official | Official | Official (Skia/X11) [inferred from repo; not deeply verified] |
| **Qt 6 (C++ / PySide6 / PyQt6)** | C++, Python, QML | Own widget/QML renderer with native styling | Official | Official | Official, first-class (Qt is Linux-native) |
| **Toga / BeeWare** | Python | Native widgets (Cocoa / WinForms / GTK). A Qt backend is in progress | Official | Official | Official via GTK, but widget coverage is uneven [secondary, 23] |
| **Flet** | Python | Flutter renderer | Official | Official | Official (1.0, 2026-09-15) [secondary, 24] |
| **pywebview** | Python | System webview | Yes | Yes | Yes, through GTK or Qt webviews |
| **Slint** | Rust, C++, JS, Python + `.slint` DSL | Own renderer (femtovg/Skia/software) | Yes | Yes | Yes |
| **iced** | Rust | Own renderer (wgpu) | Yes | Yes | Yes |
| **egui** | Rust | Immediate-mode, own renderer | Yes | Yes | Yes |
| **gpui** (Zed) | Rust | Own GPU renderer (Metal/Vulkan/DX) | Yes | Yes (newer) | Yes. crates.io `gpui` 0.2.2 (2025-10-22) is the latest published release. Zed vendors gpui in-tree and changes it weekly without bumping the version [verified, 26] |
| **Dioxus** | Rust | Desktop uses the system webview (wry); native renderer experimental | Yes | Yes | Yes (WebKitGTK) |
| **Fyne** | Go | Own renderer (OpenGL) | Yes | Yes | Yes |
| **Gio** | Go | Immediate-mode, own renderer | Yes | Yes | Yes |
| **React Native Windows / macOS** | TS/JS | Native widgets | Microsoft-maintained `react-native-macos` | Microsoft-maintained | **None** |
| **Neutralino.js** | JS + small C++ host | System webview | Yes | Yes | Yes |
| **Electrobun** | TS on Bun (+ Zig/C++ host) | System webview by default, optional bundled CEF | Official | Official (x64) | Official on Ubuntu; other distros community-supported [secondary, 27] |
| **Native per platform** | Swift (SwiftUI/AppKit), C# (WinUI 3/WPF), C/Rust/Python/Vala (GTK4/libadwaita) | Native | — | — | — |

### 2. Health — latest stable, cadence, backing, momentum (snapshot 2026-11-12)

| Candidate | Latest stable (date) | Cadence | Backing | Stars / contributors | Notes and notable apps |
|---|---|---|---|---|---|
| Electron | **v45.3.1** (2026-11-12). v45.0.0 on 2026-10-21 shipped Chromium 156, Node 24.22 | New major every **8 weeks**. The team supports the latest 3 majors; today v43, v44 and v45 all received patches on 2026-11-12 (v43.8.9, v44.11.2, v45.3.1) [verified, 1, 2] | OpenJS Foundation; Microsoft, Slack/Salesforce and others contribute | 123.9k / ~1,645 | VS Code, Slack, Discord, Claude desktop, GitHub Desktop. Very large ecosystem (electron-builder, electron-updater). |
| Tauri | **v2.12.5** (2026-10-21). v2.12.0 on 2026-09-26. **v3.0.0-alpha.6** on 2026-11-06 (alpha.0 on 2026-09-13) [verified, 4, 5] | Frequent patches, about one minor per quarter | Tauri Programme within the Commons Conservancy (NL) plus CrabNebula (commercial partner) | 112.8k / ~624 | v3 is in active alpha. Breaking changes so far: runtime selected in code, wry/CEF runtimes, GTK3/GTK4 feature-gated, MSRV 1.95 [verified, 6] |
| Wails | **v3.0.0** (2026-10-26), **v3.1.0** (2026-11-01). v2.17.1 (2026-11-01, the same day as v3.1.0) still maintained [verified, 9, 10] | Nightly v3.x pre-releases; fast minors | Community project led by Lea Anthony; sponsor-funded, no company behind it [inferred] | 37.1k / ~490 | v3 spent from January 2023 to October 2026 in alpha and beta. "v2 isn't going away … critical updates" [verified, 10]. The legacy GTK3 path (`-tags gtk3`) was announced as available only "until v3.1", which has shipped; this matters on distros without WebKitGTK 6.0 [verified, 10] |
| Flutter | **3.50.0** (2026-11-11), Dart 3.14 [verified, 3] | About quarterly stable releases with frequent hotfixes | Google. **Canonical named "lead maintainer and Strategic Steward for Flutter Desktop" at I/O 2026** [verified, 40; secondary, 12] | 181.2k / ~2,470 | Google desktop apps are few. Ubuntu's installer and several Canonical tools use it. Layoffs in 2024 [secondary, 13]. |
| Compose Multiplatform | **1.12.2** (2026-10-15). 1.12.0 on 2026-08-25; 1.13.0-beta02 on 2026-11-04 [verified, 4] | About 2 feature releases a year plus patches | JetBrains (commercial, profitable, privately held) | 19.5k / ~186 (the repo holds only part of the code) | JetBrains Toolbox App; JetBrains' own Kotlin Multiplatform push. 1.12 added a desktop window/dialog v2 API and an MCP server for agents [secondary, 15] |
| Avalonia | **12.1.6** (2026-11-09). 12.0.0 on 2026-04-07, 12.1.0 on 2026-07-09 [verified, 4] | About 2 minors a year with frequent patches | AvaloniaUI OÜ (commercial). Works with Microsoft's MAUI team on the Linux backend [secondary, 18] | 31.8k / ~745 | JetBrains Rider's UI parts, Unity tools, many enterprise line-of-business apps. Its WebView is being open-sourced [secondary, 17] |
| .NET MAUI | **11.0.10** (2026-11-11). 11.0.0 on 2026-11-10 with .NET 11 [verified, 4] | Follows .NET's yearly November release | Microsoft | 23.3k | No Linux. A secondary source says Microsoft calls Linux "not planned" [secondary, 19] |
| Qt | **6.12 LTS** (6.12.0, 2026-09-30); standard support until 2031-09-30 [verified, 20] | Two minors a year; an LTS roughly every 3–4 minors (6.2, 6.5, 6.8, 6.12). LTS patch releases are commercial-only (for example "Qt 6.8.8 (LTS, commercial only)"); open-source users get the regular patch releases [verified, 20] | The Qt Company (listed on Nasdaq Helsinki) plus the Qt Project | n/a (Gerrit) | KDE, OBS, Telegram desktop, VLC (partly), Autodesk tools |
| Toga | **v0.5.7** (2026-10-01) | Monthly-ish | Anaconda employs 2 BeeWare core members [secondary, 23] | 5.4k | Pre-1.0. A planned Anaconda web-backend collaboration fell through (Feb 2025) |
| Flet | **v1.1.2** (2026-11-06). 1.0 on 2026-09-15 [verified, 4; secondary, 24] | Fast | Small company (Appveyor's founder) | 17.5k | Python on Flutter. Inherits Flutter desktop's risk plus its own. |
| pywebview | **6.2.1** (2026-04-15) | Slow | One maintainer | 6.2k | Last release about 7 months old |
| Slint | **v1.18.1** (2026-09-21) | About quarterly | SixtyFPS GmbH (commercial) | 24.6k / ~321 | Embedded focus; desktop is secondary |
| iced | **0.14.0** (2025-12-07, **about 11 months old**) | Slow releases, pre-1.0; master is active (commits on 2026-11-11 and 2026-11-12) [verified, 4] | Volunteer-led; System76 COSMIC uses a fork | 32.0k | Breaking changes each minor |
| egui | **0.37.0** (2026-10-15) | About quarterly, pre-1.0 | Rerun.io | 32.2k | Developer tools; immediate-mode look |
| gpui | No stable standalone; crates.io 0.2.2 (2025-10-22) is the latest published release [verified, 26] | Tied to Zed | Zed Industries (VC-funded) | Zed 94.8k; gpui-component 20.5k (v0.9.1, 2026-11-09) | Zed and a few agent-tool apps |
| Dioxus | **v0.7.10** (2026-07-30) | Pre-1.0 | DioxusLabs (VC-funded) | 39.7k | Desktop is a webview, like Tauri |
| Fyne | **v2.8.2** (2026-10-12) | Steady | Fyne Labs plus community | 28.8k / ~800 | Non-native look |
| Gio | No GitHub releases (tags on sourcehut) | Slow | One lead maintainer | 2.3k | Niche |
| React Native Windows | **0.85.0** (2026-10-20); macOS **0.83.0** (2026-09-30) [verified, 4] | Follows RN about quarterly | Microsoft (Office uses it) | 17.4k / 4.4k | No Linux, so it fails the brief |
| Neutralino.js | **v6.10.0** (2026-10-06) | Steady | Small community | 8.7k | Minimal API surface |
| Electrobun | **v2.0.6** (2026-11-04) [verified, 4] | Very fast; v1 to v2 within 2026 | Blackboard (a small studio) | 13.0k / ~40 | Young; few production apps |
| WinUI 3 / Windows App SDK | **WASDK 2.6.5** (2026-11-03). WASDK 2.0 stable April 2026 [verified, 4; secondary, 28] | Monthly-ish | Microsoft. WinUI was open-sourced and moved to GitHub development in 2026 [secondary, 28] | 8.6k (microsoft-ui-xaml) | Renewed investment: Build 2026 push for native Windows apps, new TableView/Chart controls [secondary, 28] |
| WPF | **v10.0.15** (2026-11-10) | Follows .NET | Microsoft | 7.8k | Maintenance and modernization; Windows only |
| SwiftUI / AppKit | macOS 27 SDK (WWDC 2026) | Yearly | Apple | — | Apple is unifying SwiftUI, AppKit and UIKit. AppKit is not deprecated and the two interoperate [secondary, 29] |
| GTK4 / libadwaita | **GTK 4.24.1** (2026-10-01); 4.25.0 dev (2026-11-06) [verified, 30] | 6-monthly, with GNOME | GNOME Foundation plus Red Hat/Canonical/Endless contributors | — | Linux-first; macOS and Windows ports exist but are second-class |

### 3. Deprecation and support risk

| Item checked | Finding | Risk for DevScene Studio |
|---|---|---|
| **Flutter desktop at Google** | At Google I/O 2026, Google made Canonical "lead maintainer" and "strategic steward" of Flutter desktop, across all three OSes, and Canonical now leads the desktop roadmap and maintains the Linux, Windows and macOS embedders [verified, 40]. Google calls this an "expanded partnership"; OMG! Ubuntu's "handing stewardship" framing is secondary [secondary, 12]. Google still ships desktop features (multi-window, tooltips). This follows the 2024 Flutter/Dart layoffs [secondary, 13]. | **Medium.** Not deprecated. Reading the move as Google shifting desktop out of its core focus is an inference [inferred]. Canonical is Linux-first. macOS and Windows parity could lag. |
| **MAUI and Linux** | MAUI 11.0.0 shipped 2026-11-10 with no Linux target. Linux exists only through Avalonia's MAUI backend (first preview March 2026) [secondary, 18] or community GTK4/Skia backends [secondary, 19]. | **Disqualifying**: Linux is a hard requirement. |
| **Xamarin** | End of support 2024-05-01 (Microsoft). | Irrelevant; do not use. |
| **Compose Multiplatform desktop** | "Stable" for KMP core and Compose on Desktop (JVM) [verified, 14]. That page is from Sept 2025; 1.12.x shipped in 2026. JetBrains publishes no desktop-specific roadmap; its marketing focus is mobile (Android and iOS). | **Low–medium.** Stable and used by JetBrains itself, but desktop is the third priority after Android and iOS [inferred]. |
| **Wails v3** | Stable since 2026-10-26 after about 3.5 years of alpha and beta. v3.1.0 already out. v2 still gets critical fixes [verified, 9, 10]. | **Medium.** Very young stable line, and a bus factor tied to its lead maintainer. A security note: the 3.0.0 release says one advisory, GHSA-2p5f-2gx8-mh8m, is only partly fixed [verified, 9]. On Linux, same-origin child frames are not blocked, so don't embed untrusted same-origin content. |
| **Tauri v2** | v2 active (2.12.x). v3 alpha since 2026-09-13 [verified, 5]. No official v3 roadmap or v2 end-of-life date found. | **Low–medium.** A v2→v3 migration is likely in 2027. In alpha.0 the default wry runtime still enables GTK3 (WebKitGTK); only choosing the CEF runtime moves to GTK4 and Chromium [verified, 6]. CEF is therefore the Linux escape hatch, at the cost of losing Tauri's small bundle size. |
| **React Native desktop** | Microsoft maintains Windows (0.85) and macOS (0.83); there is no Linux. Meta does not prioritize desktop [secondary, 22]. | **Disqualifying** (no Linux). |
| **Qt licensing** | No 2026 licence-model change found. Open source remains LGPLv3/GPLv3; some add-ons are GPLv3/commercial only. The EU Cyber Resilience Act applies to Qt-based products, Community or commercial edition alike (reporting duties from 2026-09-11, full requirements from 2027-12-11) [secondary, 20]. | **Low** for an LGPL desktop app with dynamic linking. |
| **Electron's Chromium cadence** | A new major every 8 weeks; only the latest 3 majors are supported, about 24 weeks of support for each major [verified, 1]. | **Low technical risk; an ongoing chore.** You must budget an upgrade at least twice a year, and in practice a Dependabot/Renovate bump every 8 weeks. Falling behind means unpatched Chromium. |
| **AppKit vs SwiftUI** | WWDC 2026: Apple is unifying SwiftUI, AppKit and UIKit around a common foundation, and sessions cover using SwiftUI *with* AppKit [secondary, 29]. AppKit is not deprecated. | Low for a native-mac path. SwiftUI-first, with AppKit escape hatches. |
| **WinUI 3 / Windows App SDK** | Investment is up, not down: WASDK 2.0 (April 2026), WinUI fully open-sourced with development on GitHub (2026), new controls [secondary, 28]. | Low. Note, though, that a native Windows app here would mostly drive `wsl.exe`. |
| **Toga / BeeWare** | Still pre-1.0, and staffing depends on Anaconda (2 people). | Medium–high for a product. |
| **iced** | No release in about 11 months (0.14.0, 2025-12-07), though master is active (commits in November 2026) [verified, 4]; pre-1.0. | Medium. The risk is unpredictable release timing, not abandonment. |
| **gpui** | No stable standalone release; the API follows Zed's needs. | High for third-party products. |
| **pywebview** | One maintainer; last release April 2026. | Medium. |

### 4. Financial costs

#### 4a. Framework licences and paid tooling

| Candidate | Licence | What costs money (optional or required) |
|---|---|---|
| Electron, Tauri, Wails, Flutter, Fyne, Gio, iced, egui, Dioxus, Neutralino, Electrobun, React Native | MIT / Apache-2.0 / BSD | Nothing required. CrabNebula Cloud (Tauri distribution and updates) is optional and paid [inferred]. |
| **Compose Multiplatform / Kotlin** | Apache-2.0 | Nothing required. Since 2025.3 IntelliJ IDEA is one unified product whose free tier keeps all former Community features for commercial use [secondary, 31]. Android Studio and Fleet are free. **JetBrains terms do not touch shipped apps.** |
| **Avalonia** | MIT core | Optional per-seat tooling: **Plus €299/yr** (VS/VS Code tooling, DevTools, Hot Reload), **Pro €899/yr** (premium controls), **Enterprise from €21,000/yr**. **XPF** (WPF on macOS and Linux) is enterprise-priced, from €9,500 perpetual for an internal licence [unverified: the cited XPF pricing page returned 404 on 2026-11-12], "priced to be out of reach for individuals" [verified, 16; secondary, 17]. None of this is needed for this app. |
| **Qt (C++)** | LGPLv3 / GPLv3 / commercial | **LGPLv3 obligations (for an open or closed app):** provide a re-linking mechanism for the Qt libraries (link dynamically, or provide object files) so users can change, re-link and run the modified binary [verified, 41]; ship the LGPL text and Qt's source, or a written offer for it; state that Qt is used; do not forbid the reverse engineering needed to debug those modifications [inferred, standard LGPLv3 reading]. Your own code can stay closed. Qt gives no legal advice; LGPLv3's "Installation Information" duty applies to consumer devices, not to a desktop download. Some modules (for example Qt Charts, Qt Graphs, Qt Quick 3D and Qt Virtual Keyboard) are **GPLv3 or commercial only** [verified, 42]. **Commercial:** Qt for Small Business **€546 / US$618 per developer per year**, for companies with ≤ €1M annual revenue and/or funding, max 3 licences, 12-month term [verified, 21]. The full Application Development licence costs much more and is quote-based. |
| **PySide6** | LGPLv3 / GPLv2 / GPLv3 (Qt Company); PyPI 6.12.0 lists `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` [verified, 32] | The same LGPL obligations as above. Free for closed apps. |
| **PyQt6** | GPLv3 or commercial (Riverbank); PyPI 6.12.0 lists `GPL-3.0-only` [verified, 32] | A closed app needs a commercial licence, which grants "the right for a single developer"; Riverbank publishes no price on that page [verified, 32]. An open app must be GPL-compatible. |
| **Slint** | GPLv3 / Royalty-free / commercial | **Free for proprietary desktop apps** under the Royalty-free License 2.0 (`LicenseRef-Slint-Royalty-free-2.0`, which also covers proprietary mobile and web apps), **on condition that the app discloses that it uses Slint** (`AboutSlint` widget or badge). Without disclosure, a Commercial licence is needed. Embedded use always needs the Commercial licence [verified, 25]. Paid plans add support [verified, 33]. |
| **MAUI / WinUI / WPF** | MIT | Free. Visual Studio Community is free for individuals and small teams [inferred, standard terms]. |
| **Uno Platform** | Apache-2.0 | Optional paid "Studio" tooling [inferred]. |
| **Native macOS (Swift)** | — | Xcode is free; you need a Mac for builds and CI (GitHub macOS runners cost extra on private repos) [inferred]. |

#### 4b. Code signing and notarization (the same whatever the framework)

| Platform | Option | Cost | Eligibility and notes |
|---|---|---|---|
| macOS | Apple Developer Program, which gives a Developer ID certificate plus notarization | **US$99/yr** [verified, 34] | An individual or sole proprietor can enroll; an organization needs a D-U-N-S number and a website. Without it, Gatekeeper blocks downloaded apps. |
| Windows | **Azure Artifact Signing** (renamed from Trusted Signing) | **Basic US$9.99/month**, 5,000 signatures, then $0.005 each; Premium US$99.99/month for 100,000 signatures [verified, 35]. Needs a paid Azure subscription; free and trial subscriptions are rejected; billing is not pro-rated [verified, 36] | Public Trust is available to **organizations** in the US, Canada, EU, UK, Australia, New Zealand, Japan, South Korea, Singapore, Switzerland, Norway and Israel. **Individual developers must be located in the US or Canada** [verified, 37]. Identity verification takes 1–20 business days. No EV certificates. SmartScreen reputation still builds over time [verified, 36]. |
| Windows | Commercial OV code-signing certificate (Certum, SSL.com, Sectigo…) | For example, **Certum Open Source Code Signing in the cloud from €49** (listed as out of stock on 2026-11-12; the card-based Open Source variant is €25 with existing cryptoCertum hardware, or €69 with a card set); standard certificates cost more [verified, 38] | Individuals are accepted. Since 2023 the keys must sit on hardware or a cloud HSM. **CA/B Forum Code Signing BRs cap publicly trusted code-signing certificates at 460 days from 2026-03-01 (CSC-31) [secondary, 43]. Certum applies 459 days from 2026-02-27** [verified, 38]. Plan for yearly renewal and CI integration with the cloud HSM. |
| Windows | **SignPath Foundation** | **Free** | For OSI-licensed open-source projects only, with no dual licensing. The certificate names SignPath Foundation as publisher. MFA is mandatory for all team members, and builds must be verifiable automated CI builds from the project's source repository (terms page is marked draft) [verified, 39]. |
| Linux | GPG-signed deb/AppImage, signed apt repository | Free | No gatekeeper equivalent. |

Budget for a solo developer: about **US$99/yr (Apple) + US$120/yr (Artifact Signing, if eligible) or about €50–€300/yr (an OV certificate) or free (SignPath, if open source)**, so about **US$150–400/yr in total**, the same for every framework.

## Answers to the owner's questions

**Q1. Are there credible cross-platform solutions in late 2026?** Yes.
- **Credible for this app** (official Linux, an active release in the last 6 weeks, a funded team): **Electron, Tauri 2, Flutter, Compose Multiplatform, Avalonia, Qt (C++ or PySide6)**, plus **Wails 3**, which has been stable only since 2026-10-26.
- **Credible but riskier:** Electrobun (young), Flet and Toga (Python; pre-1.0 maturity or a dependency on Flutter), and the Rust-native toolkits (pre-1.0, more code for a board UI).

**Q6. Financial costs.**
- **No framework requires a licence fee for this app.** Qt needs care: the LGPL is fine if you link dynamically and honour the relinking obligations, and the commercial licence starts at about €546/developer/yr for small businesses. PyQt6 needs a commercial licence if the app is closed. Slint is free for proprietary desktop apps if you show Slint attribution. Avalonia's paid tiers are optional.
- **Signing is the real recurring cost:**
  - Apple: US$99/yr.
  - Windows: Azure Artifact Signing at US$9.99/month, if you sign as a US/Canadian individual or as an eligible organization; otherwise an OV certificate (from about €49/yr, though Certum's €49 cloud product is listed as out of stock on 2026-11-12), or SignPath if the app is OSI open source.
  - Linux: free.

**Q7. Is anything deprecated, or losing support or momentum?**
- **Deprecated or end of life:** Xamarin.
- **No Linux, so out:** MAUI and React Native desktop.
- **Possibly losing first-party investment:** Flutter desktop (Canonical named lead maintainer and steward [verified, 40]; reduced Google investment is an inference).
- **In a transition:** Tauri (v3 alpha) and Wails (v3 just stable).
- **Slow releases:** iced (no release in about 11 months, though master is active, so the risk is release timing, not abandonment), and pywebview (one maintainer, last release April 2026).
- **Gaining investment:** WinUI 3 / Windows App SDK (open-sourced, WASDK 2.x), Avalonia (12.x, MAUI backend deal), and Compose Multiplatform (steady releases).
- **Electron is not losing momentum.** Its "risk" is the mandatory 8-week Chromium treadmill.

**Q4, partial: does Kotlin Multiplatform work for desktop?** Yes. KMP core and Compose Multiplatform for Desktop (JVM) are both marked **Stable** by JetBrains [verified, 14]. The app runs on a bundled JVM with a Skia-drawn UI, so it is not native widgets. The performance comparison belongs in the performance area.

## Risks and open questions

- **Artifact Signing eligibility is the biggest cost and logistics trap.** An individual outside the US or Canada cannot use it. They must sign as an organization (EU, UK and others are eligible; this needs a legal entity), buy an OV cloud certificate, or use SignPath if the app is OSI open source. The owner's location and legal entity decide which route applies.
- **Tauri v3's timing is unknown.** No official roadmap or v2 end-of-life date was found. Starting on v2 now probably means one migration later.
- **Wails v3 is two weeks old as a stable release.** Watch the security advisory flagged in its release notes (partly fixed; same-origin child frames on Linux), and its 3.x churn.
- **Flutter desktop under Canonical:** watch whether macOS and Windows desktop fixes keep pace in 2027 releases.
- **The Compose stability source** (kotlinlang supported-platforms page) is dated 2025-09-10, more than 12 months old. Releases since then are consistent with it, but it was not re-confirmed by a 2026 statement.
- **Unverified prices:** the exact PyQt6 commercial price, the Avalonia XPF price (its pricing page returns 404), and Qt's full Application Development price were not visible on the live pages.
- **Uno Platform (7.0.32, 2026-11-11, 10.1k stars)** is a credible .NET newcomer with Linux support. It was not researched in depth; it is the alternative to Avalonia if .NET is ever preferred.
- **Star trends** (growth rate) were not measured; only current totals are given.

## Ranked shortlist

**Viable** (healthy, official Linux, free, fits a process- and file-driving board app):

Harness integration does not separate these candidates. Every stack calls the same `devscene … --json` process contract, directly on macOS/Linux and through `wsl.exe` on Windows; no stack can import the run logic, and none needs a bundled CLI or Node sidecar (see 05). The order below therefore rests only on maturity, support policy, licensing, Linux status and the updater and packaging ecosystem.

1. **Electron.** The most mature option: foundation-backed, MIT, free, with a published support policy (latest 3 majors, all patched on 2026-11-12) [verified, 1, 2]. On Linux it ships its own Chromium, so rendering does not depend on the distro's WebKitGTK, which is the weak spot of both system-webview options [verified, 8]. Its updater and packaging ecosystem is the deepest: electron-builder's auto-update covers macOS, Windows and Linux AppImage, DEB, Pacman and RPM [verified, 44]. It has no pending architecture migration. It is the same language as the harness CLI (TS contract types), a minor tie-breaker only, since any stack can generate those types from a JSON Schema (see 05). The caveats are bundle size and the 8-week upgrade chore.
2. **Tauri 2.** Healthy, MIT/Apache-2.0, small bundles, with an official updater plugin (on Linux it updates the AppImage) and official AppImage/deb/RPM bundling [verified, 45]. It ranks below Electron on Linux status (WebKitGTK quality varies by GPU and driver, and v3 keeps GTK3/WebKitGTK as the default runtime) and on stability of the line (v3 in alpha, a v2→v3 migration likely in 2027). The two are close; if bundle size or memory matters more than Linux rendering consistency (see 02), Tauri moves to first.
3. **Wails 3.** Go, small and system-webview based. Caveats: a stable line only about two weeks old, a small sponsor-funded core team, a partly fixed security advisory, and the same WebKitGTK dependency on Linux, with the GTK3 fallback now past its announced cutoff.

**Viable with caveats:**
4. **Compose Multiplatform.** Stable, free, and JetBrains-backed. It brings a JVM runtime and desktop is JetBrains' third priority.
5. **Flutter.** Mature renderer with official Linux support, but Canonical is now lead maintainer and steward of desktop (Intel Macs also being phased out).
6. **Avalonia 12.** Mature, MIT and funded. It ties the product to .NET; paid tiers are optional.
7. **Qt 6 / PySide6.** The most mature native-feeling toolkit. LGPL obligations apply; the commercial licence is costly; C++ or Python packaging adds friction.
8. **Electrobun.** TypeScript plus a system webview with low overhead, but young (~40 contributors) with fast churn.
9. **Native per platform (SwiftUI + GTK4 + WinUI 3).** All three are well funded and none is deprecated. The cost is N codebases (see the cost-model area).

**Dropped:**
- **.NET MAUI:** no Microsoft Linux target, even in MAUI 11.
- **Xamarin:** end of life since 2024-05-01.
- **React Native Windows/macOS:** no Linux.
- **Neutralino.js:** a thin API and small community; Tauri or Wails do the same job better.
- **pywebview:** one maintainer, slow releases; a weaker Tauri equivalent.
- **Toga/BeeWare:** pre-1.0 with uneven widgets; staffing depends on Anaconda.
- **Flet:** Flutter's desktop risk plus a young 1.x on top.
- **Slint:** embedded-first; a DSL with little desktop ecosystem for a board-style app (free proprietary use also requires visible Slint attribution).
- **iced:** pre-1.0, no release in about 11 months (master is active; release timing is unpredictable).
- **egui:** an immediate-mode developer-tool look, poor for a product UI.
- **gpui:** no stable standalone release; the published crate (0.2.2) is about 13 months old and Zed's in-tree copy tracks Zed's internals.
- **Dioxus:** the same webview model as Tauri but pre-1.0.
- **Fyne / Gio:** non-native look, small ecosystems; Wails is a better Go option.
- **Uno Platform:** not researched in depth; consider it only if .NET is chosen, against Avalonia.

## Sources

1. https://www.electronjs.org/docs/latest/tutorial/electron-timelines — 8-week cadence, latest 3 majors supported — accessed 2026-11-12
2. https://github.com/electron/electron/releases/tag/v45.0.0 (via `gh api`) — v45.0.0 2026-10-21, Chromium 156.0.8078.48, Node 24.22.0; v45.3.1 2026-11-12; v44 2026-08-25, v43 2026-06-30 — accessed 2026-11-12
3. https://storage.googleapis.com/flutter_infra_release/releases/releases_macos.json — Flutter 3.50.0 stable 2026-11-11, Dart 3.14 — accessed 2026-11-12
4. GitHub REST API (`gh api repos/<owner>/<repo>` and `/releases`) for every repository named in §2 — stars, latest release tag and date, contributor counts — accessed 2026-11-12
5. https://github.com/tauri-apps/tauri/releases — tauri-v2.12.5 (2026-10-21), v2.12.0 (2026-09-26), v3.0.0-alpha.0 (2026-09-13), alpha.6 (2026-11-06) — accessed 2026-11-12
6. https://github.com/tauri-apps/tauri/releases/tag/tauri-v3.0.0-alpha.0 — runtime selection, CEF runtime, GTK3/GTK4 opt-in, MSRV 1.95 — accessed 2026-11-12
7. https://v2.tauri.app/ (docs) — Tauri v2 docs — accessed 2026-11-12
8. https://v2.tauri.app/develop/debug/linux-graphics/ — official WebKitGTK/GPU issues page — accessed 2026-11-12
9. https://github.com/wailsapp/wails/releases/tag/v3.0.0 (via `gh api`) — GHSA-2p5f-2gx8-mh8m "only partly fixed"; Linux same-origin child-frame limitation; v3.1.0 and v2.17.1 both 2026-11-01 — accessed 2026-11-12
10. https://github.com/wailsapp/wails/releases/tag/v3.0.0 — v3.0.0 2026-10-26; GTK4/WebKitGTK 6.0; v2 keeps critical updates; Go 1.26 — accessed 2026-11-12
11. https://docs.flutter.dev/reference/supported-platforms — Flutter 3.50 desktop support matrix (updated 2026-11-11) — accessed 2026-11-12
12. https://www.omgubuntu.co.uk/2026/05/flutter-desktop-canonical-maintained — secondary report and "handing stewardship" framing of the Canonical move — accessed 2026-11-12
13. https://techcrunch.com/2024/04/29/google-lays-off-staff-from-flutter-dart-python-weeks-before-its-developer-conference — 2024 Flutter/Dart layoffs — accessed 2026-11-12 [older than 12 months]
14. https://kotlinlang.org/docs/multiplatform/supported-platforms.html — KMP and Compose Desktop (JVM) Stable — accessed 2026-11-12 [page dated 2025-09-10, older than 12 months]
15. https://www.infoworld.com/article/4216661/compose-multiplatform-1-12-0-welcomes-coding-agents-with-mcp-server.html and https://kotlinlang.org/docs/multiplatform/whats-new-compose-112.html — CMP 1.12.0 feature notes, window API v2, Skia m150 — accessed 2026-11-12
16. https://avaloniaui.net/pricing — Free/Plus €299/Pro €899/Enterprise from €21,000 — accessed 2026-11-12
17. https://avaloniaui.net/blog/avalonia-12 , https://avaloniaui.net/blog/release-12-1 , https://avaloniaui.net/xpf/pricing/internal (404 on 2026-11-12) , https://avaloniaui.net/handbook/pricing-principles — Avalonia 12/12.1 (Wayland), XPF €9,500 internal (unverified), XPF not aimed at individuals — accessed 2026-11-12
18. https://avaloniaui.net/blog/net-maui-is-coming-to-linux-and-the-browser-powered-by-avalonia , https://www.theregister.com/2026/03/23/maui_linux_avalonia — Avalonia MAUI backend preview March 2026 — accessed 2026-11-12
19. https://byteiota.com/net-maui-linux-support-two-paths-forward-in-2026/ , https://phoronix.com/news/microsoft-dotnet-maui-gtk4 — "not planned" claim; community GTK4 backend — accessed 2026-11-12
20. https://www.qt.io/blog/qt-6.12-beta-1-released , https://doc.qt.io/qt-6/qt-releases.html (Qt 6.12.0 supported to 2031-09-30; "Qt 6.8.8 (LTS, commercial only)") , https://www.phoronix.com/news/Qt-6.12-LTS-Released , https://www.qt.io/software-insights/qt-open-source-and-commercial-licensing-towards-cra-in-industrial-automation — Qt 6.12 LTS timing, support to 2031, CRA dates — accessed 2026-11-12
21. https://www.qt.io/development/qt-for-small-business (the old /qt-for-small-business URL redirects here) , https://www.qt.io/pricing — Small Business €546/US$618 a year, ≤ €1M revenue and/or funding, max 3 licences, 12-month term — accessed 2026-11-12
22. https://devblogs.microsoft.com/react-native/react-native-windows-v0-85-is-here/ — RNW 0.85; Microsoft maintenance — accessed 2026-11-12
23. https://beeware.org/news/buzz/page/2/ , https://beeware.org/news/buzz/2025/february-2025-status-update/ — Toga 2026 activity, Anaconda staffing, web-backend setback — accessed 2026-11-12
24. https://flet.dev/blog , https://www.marktechpost.com/2026/09/20/flet-1-0-released-build-production-web-desktop-and-mobile-apps-in-python-only/ — Flet 1.0 (2026-09-15) — accessed 2026-11-12
25. https://github.com/slint-ui/slint/blob/master/LICENSE.md (via `gh api`) — Slint triple licence; Royalty-free License 2.0 covers proprietary desktop, mobile and web on condition of disclosure; embedded needs Commercial — accessed 2026-11-12
26. https://crates.io/api/v1/crates/gpui/versions , https://github.com/zed-industries/zed/blob/main/crates/gpui/Cargo.toml — gpui 0.2.2 published 2025-10-22; in-tree version still 0.2.2, `publish = true`; Zed v1.28.1 2026-11-11 — accessed 2026-11-12
27. https://blackboard.sh/electrobun/docs/guides/compatability , https://framework.blackboard.sh/electrobun/guides/changelog/v2-x/ — Electrobun platform status — accessed 2026-11-12
28. https://www.thurrott.com/dev/340841/microsoft-moves-winui-wasdk-development-to-github , https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/release-notes/windows-app-sdk-2-0 , https://www.windowslatest.com/2026/10/31/one-reason-windows-11-has-so-many-web-apps-winui-still-lacked-basic-features-and-thats-finally-changing/ , https://www.windowscentral.com/software-apps/microsoft-drives-developers-toward-native-windows-apps-at-build-2026 — WinUI open-sourcing, WASDK 2.x, Build 2026 — accessed 2026-11-12
29. https://developer.apple.com/wwdc26/guides/macos/ , https://mjtsai.com/blog/2026/06/19/swiftui-in-appleos-27 — WWDC26 SwiftUI/AppKit/UIKit unification — accessed 2026-11-12
30. https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgtk/repository/tags — GTK 4.24.1 (2026-10-01), 4.25.0 (2026-11-06) — accessed 2026-11-12
31. https://www.jetbrains.com/help/idea/intellij-idea-single-distribution.html — unified IntelliJ IDEA; free tier keeps Community features for commercial use — accessed 2026-11-12
32. https://pypi.org/project/PySide6/ , https://pypi.org/project/PyQt6/ , https://www.riverbankcomputing.com/commercial/pyqt — PyPI licence metadata for 6.12.0; PyQt GPLv3 or commercial, "the right for a single developer" — accessed 2026-11-12
33. https://slint.dev/pricing — Slint plans (Royalty-free, Startup & Individual, Small Enterprise, Enterprise, GPLv3) — accessed 2026-11-12
34. https://developer.apple.com/programs/enroll/ — US$99/yr; individual vs organization; D-U-N-S — accessed 2026-11-12
35. https://azure.microsoft.com/en-us/products/artifact-signing , https://prices.azure.com/api/retail/prices (Basic 9.99, Premium 99.99, overage 0.005) , https://www.devclass.com/security/2026/01/14/code-signing-windows-apps-may-be-easier-and-more-secure-with-new-azure-artifact-service/4079554 — Basic US$9.99/month, 5,000 signatures, $0.005 overage; Premium US$99.99/month, 100,000 signatures; GA January 2026 — accessed 2026-11-12
36. https://learn.microsoft.com/en-us/azure/artifact-signing/faq — paid subscription required, no pro-rating, no EV, SmartScreen reputation (updated 2026-10-27) — accessed 2026-11-12
37. https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart — eligible countries; individuals US/Canada only; 1–20 business days (updated 2026-10-08) — accessed 2026-11-12
38. https://shop.certum.eu/open-source-code-signing-on-simplysign.html , https://shop.certum.eu/code-signing.html — Certum Open Source cloud from €49 (out of stock), card variants €25/€69; 459-day max validity from 2026-02-27 — accessed 2026-11-12
39. https://signpath.org/terms , https://about.signpath.io/product/open-source — SignPath Foundation free OSS signing conditions (OSI licence without dual licensing, MFA, verifiable builds; page marked draft) — accessed 2026-11-12
40. https://flutter.dev/blog/whats-new-in-flutter-3-44 — Google's Flutter 3.44 post (2026-05-20): Canonical "lead maintainer and Strategic Steward for Flutter Desktop", leads the desktop roadmap, maintains Linux, Windows and macOS embedders — accessed 2026-11-12
41. https://www.qt.io/development/open-source-lgpl-obligations , https://www.qt.io/download-open-source — Qt's LGPL obligations (re-linking mechanism; user must be able to run the re-linked binary) — accessed 2026-11-12
42. https://doc.qt.io/qt-6/qtcharts-index.html , https://doc.qt.io/qt-6/qtgraphs-index.html , https://doc.qt.io/qt-6/qtquick3d-index.html , https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html — module pages marked "Commercial or GPLv3" — accessed 2026-11-12
43. https://www.digicert.com/blog/understanding-the-new-code-signing-certificate-validity-change — CA/B Forum CSC-31: 460-day maximum from 2026-03-01 — accessed 2026-11-12
44. https://github.com/electron-userland/electron-builder/blob/master/website/docs/features/auto-update.md (via `gh api`) — auto-update targets incl. Linux AppImage, DEB, Pacman, RPM; electron-builder 26.18.1 (2026-10-26) — accessed 2026-11-12
45. https://v2.tauri.app/plugin/updater/ , https://v2.tauri.app/distribute/ — Tauri updater plugin (Linux update artifact is the AppImage); AppImage, Debian, RPM, Flathub, Snap distribution guides — accessed 2026-11-12
