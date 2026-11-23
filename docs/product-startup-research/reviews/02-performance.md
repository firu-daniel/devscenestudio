# Review — 02-performance.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The file is careful, decision-oriented and mostly accurate. I re-checked the version table against GitHub releases, the JetBrains PR #5644 start-up tables, the Kotlin/Native tier page, the Compose packaging docs, the Kotlin roadmap, the Elanis CI tables, Better Stack, the two WebKit bugs, the Tauri Linux-graphics page and the Codex `wsl.exe` issue. Most numbers match their sources exactly. I also re-ran the local measurements on this machine and reproduced them within a few ms.

There are four problems. The 9P "5–10× slower" claim rests on an AI-generated forum table that is about the wrong direction of access. The Electrobun row uses vendor numbers that the cited pages no longer carry, and its version status is wrong. Deno Desktop is missing even though the file's own source [2] benchmarks it. The plan to fix WebKitGTK with "Tauri 3 + CEF" does not say that Tauri 3 is an alpha with no stable date.

The conclusion that "performance does not decide" is well supported. Flutter gets slightly harsher treatment than the other stacks: the file sets aside CI data for Flutter that it accepts for Tauri and Wails.

## Must fix

**M1. The 9P slowdown has no real source, and the source it has measures the wrong direction.**
- **Location:** TL;DR WSL2 bullet ("Under 9P, each file read is 5–10× slower"), §7 ("Reading many small files over 9P is ≈5–10× slower than native [17]"), and Sources #17.
- **Problem:** Source [17] is a Julia Discourse post (2025-11-02). The poster relays an AI-generated table ("I'm assuming my info (from AI) is still valid") with no method and no data. The row in that table is also about Linux tools reading `/mnt/c` (Windows files read from Linux). DevScene Studio's case is the opposite: Windows reading Linux files over `\\wsl$`. The claim is also tagged as fact in the TL;DR.
- **Evidence:**
  - https://discourse.julialang.org/t/wsl-1-vs-wsl-2/133599 (AI table, an assertion, not a measurement).
  - The primary source is https://learn.microsoft.com/en-us/windows/wsl/filesystems (updated 2026-06-02). It recommends against working across file systems "for the fastest performance" but gives no multiplier.
  - The long-running WSL thread https://github.com/microsoft/WSL/issues/4197 is still open (2019, 525 comments).
- **Fix:** Drop the number, or mark it unmeasured. Suggested text: "Cross-OS file access over 9P is markedly slower than native access. Microsoft recommends against it for performance [MS docs]. No trustworthy multiplier was found for Windows→`\\wsl$` reads, so measure it in the WSL spike. [secondary + inferred]" Replace source #17 with the Microsoft page and WSL #4197.

**M2. The Electrobun status and numbers are stale or unverifiable.**
- **Location:**
  - §1 table: "Electrobun | v2.0.7 beta".
  - §2 row "Electrobun docs [6] … 14 MB bundle, <50 ms start, 15–30 MB RAM".
  - §3 Electrobun row.
  - TL;DR size group "Electrobun on the system webview … ≈3–20 MB".
  - Source #6.
- **Problem 1, version:** The latest *stable* release is **v2.0.6 (2026-11-04)**. v2.0.7 is still in beta (v2.0.7-beta.12, 2026-11-12). The table's column is "Current stable (pre-release)", so the cell should read "2.0.6 (2.0.7-beta.12)".
- **Problem 2, dead source:** The cited URL `blackboard.sh/electrobun/docs/` now redirects (301) to `docs.electrobun.dev`.
- **Problem 3, missing claims:** Neither the docs landing page nor the bundling-CEF page contains the 14 MB, <50 ms, 15–30 MB or "≈100 MB with CEF" figures. The current vendor claim is different: "A hello world ships at about a megabyte" (https://electrobun.dev/electrobun/). The vendor gives no start-up or RAM figures.
- **Problem 4, CEF framing:** The CEF page confirms that the system webview is the default on all three OSes and that CEF is opt-in per platform via `bundleCEF`. It also says the docs *recommend* CEF on Linux for consistent behaviour, which is relevant to the WebKitGTK point in §6.
- **Evidence:**
  - `gh release list --repo blackboardsh/electrobun` (v2.0.6 is marked Latest; 13k stars; pushed 2026-11-12).
  - https://docs.electrobun.dev/electrobun/apis/bundling-cef
  - https://electrobun.dev/electrobun/
- **Fix:**
  - Version cell: "2.0.6 (2.0.7-beta.12); Electrobun 2.0 launched, Bun runtime by default, Cottontail runtime experimental".
  - Bundle cell: "≈1 MB hello-world claimed (vendor, system webview); 418 MB with CEF [2]".
  - RAM and start cells: "no vendor or independent system-webview figure; 208 MB / 773 ms with CEF [2]".
  - Update source #6 to the new URLs.
  - Add one line to §6: Electrobun's own docs recommend CEF on Linux.

**M3. Deno Desktop is missing, even though source [2] benchmarks it.**
- **Location:** §2 (Better Stack row names "Deno Desktop"), §3 table, and the TL;DR size groups.
- **Problem:** The brief asks for "any other credible newcomer". Deno Desktop shipped officially in **Deno 2.9.0 (2026-06-25)**. Per those release notes, it uses the system webview by default and outputs .msi, .deb and .rpm installers. It is a TypeScript runtime, so it is directly relevant to reusing the Node/TS `devscene` CLI code. Better Stack measured it alongside the others: **111 MB bundle, 242 ms start, 98 MB idle RAM** (macOS). The file cites this source but drops the row.
- **Evidence:**
  - https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/ (updated 2026-07-20).
  - `gh release view v2.9.0 --repo denoland/deno` ("feat(desktop): default UI backend to webview", "add Windows .msi installer output format", "add Linux .deb and .rpm").
- **Fix:**
  - Add a §3 row: "Deno Desktop (Deno 2.9+, system webview) | 111 MB (real app, macOS) | 98 MB | 242 ms | no data | [2] [secondary]".
  - Mention it in the TL;DR size discussion. Its bundle is mid-sized because it ships the Deno runtime.
  - Add a cross-reference to 01 and 03 for maturity and CLI reuse.

**M4. Tauri 3 + CEF is presented as a mitigation and a measured size group, but it is an alpha.**
- **Location:**
  - TL;DR ("Engines that bundle Chromium (Electron, Electrobun with CEF, Tauri 3 with CEF) ship ≈250–420 MB unpacked").
  - §6 ("Tauri 3's optional CEF runtime is a future fix … [verified: releases]").
  - Risks ("or plan for Tauri 3 + CEF").
- **Problem:** Tauri 3 is **alpha only**. `tauri v3.0.0-alpha.0` came out on 2026-09-13 and `alpha.6` on 2026-11-06. `tauri-runtime-cef` is at v3.0.0-alpha.7. No stable date or official roadmap was found. Stable Tauri is 2.12.5 (2026-10-21).
- **A trap to note:** GitHub's "Latest" badge currently sits on `tauri v3.0.0-alpha.6`, so a quick `gh release list` read can mislead.
- **No measurement:** No source measures a Tauri + CEF bundle. Putting it in the 250–420 MB group is an inference.
- **Evidence:** `gh release list --repo tauri-apps/tauri` (alpha.0 2026-09-13, alpha.6 2026-11-06, tauri-runtime-cef alpha.7, tauri v2.12.5 2026-10-21). The search found no stable 3.0 or roadmap date.
- **Fix:**
  - TL;DR: "(… Tauri 3 with CEF, [inferred]; Tauri 3 is alpha)".
  - §6: "Tauri 3 (alpha since 2026-09, no stable date) adds an optional CEF runtime. If it ships stable, it is a possible fix, but it brings Electron-sized bundles."
  - Risks: "plan for Tauri 3 + CEF *only if it has reached stable by then*".

## Should fix

**S1. The Tauri free-memory range is cherry-picked, and the "1.5–2×" conclusion does not hold on Windows.**
- **Location:** §3 "How to read the RAM column" ("≈14–90 MB for Tauri … Tauri's real RAM advantage over Electron is about 1.5–2×, not 10×").
- **Problem:** The Elanis free-memory-delta table (release builds) is not consistent with that range:
  - Tauri is **187 MB on Windows**, 76 MB on macOS and 14 MB on Linux.
  - Electron is 110 MB on Windows, 111 MB on macOS and 79 MB on Linux.
  - So on Windows, Tauri is *worse* than Electron by this measure as well, not only by the RSS sums. On Linux the 14 MB figure is unreliable, because that Tauri build takes 30 s to start on the same VM.
- **Evidence:** https://github.com/Elanis/web-to-desktop-framework-comparison (README, "Memory Usage – … difference between system measured free memory", 01-empty-app).
- **Fix:** "Free-memory delta [1]: Electron ≈80–110 MB; Tauri ≈14–190 MB (Windows 187 MB, higher than Electron). On macOS and Linux Tauri uses less, by roughly 1.5×. On Windows, WebView2 removes the advantage. The 10× claims are not supported."

**S2. Flutter: CI data is applied to the other stacks but set aside for Flutter.**
- **Location:** §3 Flutter row ("No trustworthy release-mode desktop number"), §2 Elanis row ("Flutter numbers are mostly Debug builds"), and Risks.
- **Problem:** Elanis does have **release-mode Flutter numbers on Windows**:
  - RSS sum ≈377 MB.
  - Free-memory delta ≈86 MB.
  - Start ≈2,008 ms.
  - Bundle ≈25 MB.

  The file uses the same CI rows for Tauri and Wails, so declining them for Flutter is inconsistent. The explanation that the 2.0 s start is "inflated by the GPU-less CI VM" is plausible, since Skia/Impeller may fall back to software rendering. But it is untested: on the same VMs, Electron, Tauri and Wails release builds start in 0.2–0.7 s.
- **Already correct:** Flutter 3.50.0 is current (released 2026-11-11, per the release manifest at storage.googleapis.com/flutter_infra_release/releases/releases_macos.json).
- **Fix:**
  - Fill the Flutter row with the Windows release figures (377 MB RSS sum, 86 MB free-delta, 2.0 s start, 25 MB). Use the same caveats as for the other stacks.
  - Tag the GPU explanation [inferred].
  - In Risks, add: "if Flutter stays a finalist, include it in the 1-day spike, since it is the one stack whose release start time on CI is slow and unexplained."

**S3. The Nucleus claims go beyond the cited README, and alternatives to Nucleus are missing.**
- **Location:** §8 GraalVM bullet ("and 100–150 MB / ≈0.5 s for real apps [5]"; "Users report AWT/Skiko edge cases, long and RAM-heavy builds") and §3 Nucleus row.
- **Problem 1, unsupported figures:** The current README states only the hello-world figures: "cold-starts in about 0.2 s and around 30 MB of RAM (measured on Windows 11)". It does not contain the "100–150 MB / ≈0.5 s real apps" figures. Nor does the user-report sentence have a citation.
- **Problem 2, Nucleus details:** Nucleus is at 441 stars, last push 2026-11-07, with v3.0.0-dev pre-releases and 2.5.0 in the README. It also lists AppImage, Flatpak and Snap among 18 formats, which supports §8's AppImage remark.
- **Problem 3, missing alternative:** The JetBrains packaging page points to **Conveyor** as an alternative, with cross-building and online updates, and a licence needed for closed-source projects.
- **Evidence:**
  - `gh api repos/NucleusFramework/Nucleus/readme`
  - https://kotlinlang.org/docs/multiplatform/compose-native-distribution.html
- **Fix:** Cite the exact page for the real-app figures, or remove them. Cite a Kotlin Slack or issue link for the edge cases, or tag them [inferred]. In §8 packaging, add: "Alternatives for AppImage, cross-building and update: Nucleus (MIT) or Conveyor (paid for closed source); see 04."

**S4. The WSL sources are weaker than their tags suggest.**
- **Location:** §7 (WSL #4581, Codex #26149) and Sources #15 and #16.
- **Problem 1, #4581:** WSL #4581 dates from **2019-10**. It was **auto-closed for inactivity on 2024-02-01**, not fixed. That is older than the 12-month threshold and should be flagged as such.
- **Problem 2, #26149:** The ≈0.1 s per `wsl.exe` spawn comes from a single Codex issue (2026-06-03) that states no method, no repeat count and no Windows or WSL version. The only version given is Ubuntu 26.04. No independent per-spawn benchmark was found.
- **Assessment:** The architectural conclusion (one long-lived in-WSL process) is still right.
- **Evidence:**
  - `gh issue view 4581 --repo microsoft/WSL` (CLOSED, COMPLETED by the policy bot, last comment from a human 2020-03).
  - https://github.com/openai/codex/issues/26149
- **Fix:**
  - "WSL #4581 (2019; bot-closed in 2024 without a fix)".
  - "≈0.1 s per spawn (single unreproduced report, method not stated) [secondary]". This is already a spike item; keep it.

**S5. The WebKitGTK bugs are real, but they are weak evidence for a log tail.**
- **Location:** §6 ("A log tail is the kind of view that exposes these bugs. This is the **one place where the choice of rendering engine could become user-visible**").
- **Verified:**
  - WebKit #305290: [GTK] slow scrollbar drag after resize. Reported 2026-01-11. NEW, unassigned.
  - WebKit #310814: [GTK] stuttering scroll on a WordPress carousel. Reported 2026-03-26, tested on 2.50.5. NEW.
  - The Tauri NVIDIA/DMABUF page and its env vars exist as described.
- **Problem:** Both bugs are site-specific reports from one reporter (a long article page and a carousel). Neither involves a virtualized monospace list. Linking them to the log tail is reasonable but is an inference.
- **Fix:** Tag the log-tail sentence [inferred]. Change "known scrolling and compositing bugs" to "open, site-specific scrolling bugs in 2026 plus the documented NVIDIA/DMABUF issues". Keep the spike check on Wayland + NVIDIA.

**S6. Some confidence tags cover more than they verified.**
- **Location:**
  - TL;DR cold-start bullet, tagged "[verified: JetBrains PR #5644 numbers]".
  - TL;DR KMP bullet "[verified + secondary]".
- **Problem:** The cold-start bullet also contains the Electron, Tauri and native start figures, which are secondary or inferred. Only the Compose figures are verified.
- **Fix:** Split the tag: "Compose figures [verified: #5644]; Electron/Tauri [secondary: 1, 2]; native [secondary/inferred]".

**S7. Local measurements: plausible and labelled, with two small labelling gaps.**
- **What I re-ran:** I re-ran them on the same machine (Apple M4, macOS 15.7.4 / Darwin 24.6, Node 22.23.2, git 2.50.1, gh 2.100.0, devscene 0.6.12):

  | Measurement | Re-run median | p90 |
  |---|---|---|
  | `/usr/bin/true` | 0.9 ms | 1.1 ms |
  | `git --version` | 7.8 ms | — |
  | `gh --version` | 32.7 ms | — |
  | `node -e 0` | 36.6 ms | — |
  | devscene `--version` | 71.3 ms | 81 ms |
  | `gh api rate_limit` | 0.52–0.60 s | — |
  | `gh issue list` | 0.50 s | — |

  Notes.app is 15 MB on disk and uses 58 MB RSS. GitHub Desktop (Electron 44.9.1) uses **166 MB** RSS over 4 processes now, against 206 MB in the file.
- **Labelling:** These are clearly labelled as local (§2 row, §7 heading, source #22).
- **Gap 1:** The TL;DR calls the CLI figure "≈70 ms *cold* start", but it is a repeated, warm-cache run.
- **Gap 2:** A single RSS snapshot of GitHub Desktop varies with use.
- **Fix:** Use "≈70 ms start (warm file cache)" and "GitHub Desktop idles at ≈170–210 MB RSS across 4 processes (two snapshots)".

## Nice to have

**N1. JEP and DSL naming.** The AOT cache itself is JEP 483 (JDK 24). JDK 25 added JEP 514 (command-line ergonomics) and JEP 515 (method profiling). PR #5644 links JEP 514, so "JDK 25 AOT (JEPs 483/514/515)" is more precise. The DSL value is `AotMode.AotPrebuild`. The PR's other caveats (training run needs a display, archive grows the bundle, 919 ms when relocated on Windows) are reproduced correctly. Source: https://github.com/JetBrains/compose-multiplatform/pull/5644 (merged 2026-07-17; CHANGELOG lists it under 1.13.0-alpha01; 1.13.0-beta02 2026-11-04; stable 1.12.2).

**N2. Internal consistency.**
- **Electron RAM:** The TL;DR gives "Electron ≈130–400 MB", but the table goes up to ≈600 MB (Linux CI sum).
- **Disk ratio:** Q4 says "≈20–50× bigger on disk". The file's own numbers (3–15 MB native against 250–370 MB) give ≈17–120×. "An order of magnitude or more" would be safer.

**N3. jpackage formats.** jpackage's `app-image` type is not the Linux AppImage format. One sentence would prevent confusion. The rest is verified: the Compose docs list only Dmg, Pkg, Exe, Msi, Deb and Rpm; JDK 17+; no cross-compilation; "operates on the JVM platform" (page dated 2026-08-25).

**N4. Polling arithmetic.** `gh issue list` and `gh pr list` use GraphQL, which has its own 5,000-point budget, separate from the REST core limit. The "two repos exceed 5,000/h" example holds only for REST endpoints. Add one clause.

**N5. Items verified with no change needed**, listed for the record:
- Electron 45.3.1 (46.0.0-alpha.10).
- Wails v3.1.0 (2026-11-01; v3.0.0 2026-10-26) and v2.17.1.
- Avalonia 12.1.6, Slint 1.18.1.
- Kotlin/Native tiers: macosArm64 Tier 1, linuxX64 Tier 2, mingwX64 Tier 3, macosX64 deprecated from 2.3.20 and scheduled for removal. Page modified 2026-08-19.
- The Kotlin roadmap (Aug 2026, next update Feb 2027) has no Kotlin/Native desktop UI item; the only desktop-adjacent item is Skiko Graphite.
- Elanis sizes and start times for Electron, Tauri, Wails and Neutralino. The repo was last pushed 2026-11-03.
- Better Stack figures (Tauri 57 MB / 311 ms / 109 MB; Electron 323 MB / 273 ms / 128 MB; Electrobun 418 MB / 773 ms / 208 MB; median of 10 launches, macOS, no versions given).

**On "performance does not decide":** The claim is well supported. The evidence (network-bound first paint ≈0.5–1 s, spawn floor ≈1 ms, the same WSL architecture in every stack) carries it. The caveats are honest: download size, the JVM without AOT, and WebKitGTK. One factor deserves a sentence in §9 under "Relevant, but small": Windows WebView2 removes Tauri and Wails' RAM advantage (S1), and Linux WebKitGTK may push Tauri, Wails or Electrobun toward CEF. Both narrow the gap between system-webview stacks and Electron on the two non-macOS platforms.

## Review resolution

Resolved 2026-11-12. Factual corrections were re-checked live before being applied (`gh release list` for Electrobun/Tauri, `gh release view v2.9.0 --repo denoland/deno`, `gh issue view 4581 --repo microsoft/WSL`, the Nucleus README, the Elanis README tables, Better Stack, the Electrobun site and CEF docs, and the Microsoft WSL filesystems page).

- **M1 — applied.** The 5–10× figure was removed from the TL;DR and §7. It now says 9P cross-OS access is markedly slower, that Microsoft recommends against it, and that there is no trustworthy multiplier, so it needs measuring in the spike. Source #17 now points to the Microsoft page (updated 2026-06-02) and WSL #4197.
- **M2 — partially applied.** Version is now 2.0.6 (2.0.7-beta.12), with the ≈1 MB vendor claim, no system-webview RAM or start figures, new URLs, a CEF opt-in note, and a §6 line saying the docs recommend CEF on Linux. I did not add "Cottontail runtime experimental" to the version cell because I did not verify it and it does not affect performance.
- **M3 — partially applied.** I added a §3 row (111 MB / 98 MB / 242 ms, verified on Better Stack, updated 2026-07-20), a TL;DR size-group mention, a Q1 line, and a cross-reference to 01/03 for maturity and dev effort. I did not add the review's claim that Deno Desktop helps reuse the `devscene` CLI code. Sibling file 05 found that the run logic is per-repo bash, not an importable TS library.
- **M4 — applied.** The TL;DR tags Tauri 3 + CEF as [inferred] and alpha. §1 and §6 say "alpha since 2026-09-13, no stable date" and note the misleading "Latest" badge. Risks now say "only if it has reached stable by then". I verified that alpha.6 and the runtime-cef alpha.7 were released on 2026-11-06 and that stable is 2.12.5.
- **S1 — applied.** Verified in the Elanis release table: Tauri is 187 MB on Windows, 76 MB on macOS and 14 MB on Linux; Electron is 110, 111 and 79 MB. I rewrote the RAM paragraph to match. The Electron RAM range in the TL;DR was adjusted to match (see N2).
- **S2 — applied.** Verified: Flutter on Windows release is 377 MB RSS, 86 MB free-delta and 2,008 ms. I filled in the row, tagged the GPU explanation [inferred], fixed the §2 wording, and added the Flutter spike to Risks.
- **S3 — applied.** Verified that the README has only the hello-world figures. I removed the real-app figures, tagged the edge cases [inferred], and added Nucleus (AppImage among 18 formats) and Conveyor as packaging alternatives in §8.
- **S4 — applied.** Verified that #4581 was created in 2019-10 and bot-closed on 2024-02-01. That age flag and the "single report, method not stated" note for #26149 now appear in §7, the TL;DR, Sources and Risks.
- **S5 — applied.** The bugs are now described as site-specific, and the log-tail link is tagged [inferred].
- **S6 — applied.** I split the tags on the cold-start and KMP TL;DR bullets.
- **S7 — applied.** The CLI figure now reads "≈70 ms start (warm file cache)". GitHub Desktop now reads ≈170–210 MB (two snapshots), and Notes.app 58–61 MB.
- **N1 — applied.** Added JEPs 483/514/515 and `AotMode.AotPrebuild`.
- **N2 — applied.** The TL;DR Electron RAM range is now 130–600 MB, and Q4 says "an order of magnitude or more".
- **N3 — applied.** Added a sentence explaining that jpackage's `app-image` is not AppImage.
- **N4 — applied.** Added a clause saying the limit is REST-only and that GraphQL has a separate 5,000-point budget.
- **N5 — no change needed** (verification record). I added the §9 "relevant but small" sentence suggested in the closing paragraph to the Idle RAM row and the TL;DR bottom line.
