# Review — 01-framework-landscape.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

Most of the load-bearing facts hold up when checked live against primary sources. That covers Electron v45.3.1 and its policy (3 majors, 8 weeks), the Tauri v3 alpha dates and its CEF runtime and GTK gating, Wails v3.0.0 on 2026-10-26, Flutter 3.50 on 2026-11-11, Compose Multiplatform 1.12.2, Avalonia 12.1.6, MAUI 11.0.0 without Linux, Qt 6.12 LTS, Apple's US$99, Azure Artifact Signing at US$9.99 with its country rules, the Avalonia Plus and Pro prices, and the licence lines for PyQt6 and PySide6. The Flutter/Canonical claim is substantively correct, but it is cited to a blog when Google's own post exists. Two things must change before the file is used for a decision:
- The ranking rests partly on "Electron reuses the `devscene` TypeScript code directly". The sibling file 05 shows this is false.
- The Slint licence summary says attribution is optional. Slint's current licence makes disclosure a condition of free proprietary use.

There are also several citation and precision fixes: the 459-day figure, iced "staleness", two dead links, and confidence tags that understate verified facts.

## Must fix

**M1. The ranking relies on a premise that 05 refutes ("reuses the `devscene` TypeScript code").**
- *Location:* TL;DR bullet 2 ("It also reuses the `devscene` TypeScript CLI directly"). Ranked shortlist #1 Electron ("reuses the `devscene` TypeScript code directly"). Ranked shortlist #2 Tauri ("Caveats: a Node sidecar to reuse the CLI").
- *Problem:* The TL;DR of `05-harness-integration.md` (same folder) found three things.
  - None of the run read/act logic can be imported from TypeScript. Registry reads, pause/resume markers, inbox drop, park answers, branch derivation and GitHub dispatch live in about 22.5k lines of bash rendered per repo (`harness-run-lib.sh`, `remote-run.sh`, `autonomous-watcher.sh`).
  - The CLI is published with a `bin` only. It has no `main` or `exports`.
  - On Windows the harness runs only inside WSL2. An in-process library in a Windows Electron main process "would probe the wrong OS", so the app must call the CLI via `wsl.exe`.

  05 concludes that Electron's advantage shrinks to "the same language, and TS types for the contract", and that **Tauri needs no Node sidecar**. File 01 ranks Electron first partly on direct reuse and penalizes Tauri for a sidecar. Both points are wrong under 05's evidence, so the Electron-over-Tauri ordering is under-justified as written.
- *Evidence:* `05-harness-integration.md` TL;DR, bullets 1, 2, 4 and 7.
- *Fix:*
  - Replace the TL;DR clause with: "It shares the harness's language (TypeScript), so the types for a future `devscene runs … --json` contract are native. It cannot import the run logic, which lives in per-repo bash scripts, and on Windows it must call the CLI through `wsl.exe` like any other stack (see 05)."
  - Ranked #1: replace "reuses the `devscene` TypeScript code directly" with "the same language as the harness CLI (TS contract types); the most mature ecosystem (electron-builder/updater)".
  - Ranked #2 Tauri: delete "a Node sidecar to reuse the CLI".
  - Re-justify the Electron vs Tauri order on maturity, Linux webview quality, bundle size and the v3 migration alone, or state that the two are close.

**M2. Slint's licence: "Attribution is optional" is wrong.**
- *Location:* TL;DR ("Slint is free for proprietary desktop apps under its Royalty-free licence"), §4a Slint row ("Attribution is optional, and embedded use is excluded [verified, 25, 33]"), and Q6.
- *Problem:* The current `LICENSE.md` says: "The Royalty-free License is free, as long as you disclose that you use Slint (for example with the `AboutSlint` widget or the Slint badge); without that disclosure, use the Commercial license." Disclosure is a condition, not an option. The licence is now `LicenseRef-Slint-Royalty-free-2.0`. It also covers proprietary *mobile and web* apps as well as desktop. Embedded use is excluded.
- *Evidence:* https://github.com/slint-ui/slint/blob/master/LICENSE.md (checked through `gh api`, 2026-11-12).
- *Fix:* Change the §4a text to: "**Free for proprietary desktop apps** under the Royalty-free License 2.0, **on condition that the app discloses that it uses Slint** (`AboutSlint` widget or badge). Without disclosure, a Commercial licence is needed. Embedded use always needs the Commercial licence [verified, 25]." Mirror this in the TL;DR and Q6 ("free if you show Slint attribution").

## Should fix

**S1. Flutter/Canonical: cite the primary source and separate quotation from interpretation.**
- *Location:* TL;DR bullet 4, §2 Flutter row ("[secondary, 12]"), §3, Q7, ranking #5.
- *Problem:* The claim is supported, but it is cited only to OMG! Ubuntu. Google's own post is "What's new in Flutter 3.44" (flutter.dev blog, 2026-05-20, published during I/O 2026). It says:
  - "We are excited to announce an expanded partnership with Canonical, who will now serve as the lead maintainer and Strategic Steward for Flutter Desktop."
  - "Canonical will lead the Flutter Desktop roadmap and oversee the maintenance of our Linux, Windows, and macOS embedders."
  - "Moving forward, we are actively expanding our governance with more partners."

  So this is more than Canonical "simply contributing". Google formally transferred lead maintenance and roadmap ownership of desktop to Canonical, for all three OSes. Two parts are not in the source, though:
  - Google frames it as an "expanded partnership", not as "handing over".
  - The reading "reduced Google investment" is the author's inference, as is OMG! Ubuntu's "handing stewardship of platforms it's less invested in".
- *Evidence:* https://flutter.dev/blog/whats-new-in-flutter-3-44 ; https://www.omgubuntu.co.uk/2026/05/flutter-desktop-canonical-maintained
- *Fix:*
  - Add the flutter.dev post as a source, and tag the fact "[verified]".
  - Rephrase the TL;DR as: "At I/O 2026 (Flutter 3.44 post, 2026-05-20), Google named Canonical 'lead maintainer and Strategic Steward for Flutter Desktop'. Canonical leads the desktop roadmap and maintains the Linux, Windows and macOS embedders [verified]. Reading this as reduced first-party Google investment in desktop is an inference [inferred]."
  - Keep OMG! Ubuntu only as a secondary source.

**S2. The 459-day figure is Certum's cutoff, not the industry rule.**
- *Location:* §4b Commercial OV row ("From 2026-02-27 a certificate is valid for at most 459 days [secondary, 38]").
- *Problem:* Certum's own code-signing page says exactly this, so the quote is accurate for Certum. The underlying CA/Browser Forum rule is different: Ballot CSC-31 (Code Signing BR v3.10.0) sets a **460-day** maximum for certificates issued on or after **2026-03-01**. CAs set their own earlier and shorter cutoffs (Certum 459 days from 02-27, SSL.com 458 days, DigiCert 459 days). The file presents Certum's figure as the general rule.
- *Evidence:* https://shop.certum.eu/code-signing.html (verbatim: "Starting from February 27, 2026, a single Code Signing certificate may be valid for a maximum of 459 days.") ; https://www.digicert.com/blog/understanding-the-new-code-signing-certificate-validity-change (CSC-31, 460 days, 2026-03-01).
- *Fix:* "CA/B Forum Code Signing BRs cap publicly trusted code-signing certificates at 460 days from 2026-03-01 (CSC-31). Certum applies 459 days from 2026-02-27 [verified, 38]. Plan for yearly renewal."

**S3. Certum Open Source in the cloud is listed as out of stock.**
- *Location:* §4b and Q6 ("Certum Open Source in the cloud, from €49").
- *Problem:* The product page shows "from €49.00", but also "Product is out of stock" today. The cheapest Certum open-source option is €25, but it needs an existing cryptoCertum card and reader; the €69 "set" includes the hardware. The "from about €49/yr" route may not be purchasable right now.
- *Evidence:* https://shop.certum.eu/open-source-code-signing-on-simplysign.html ; https://shop.certum.eu/code-signing.html
- *Fix:* Add "(listed as out of stock on 2026-11-12; the card-based Open Source variant is €25 with existing hardware, or €69 with a card set)".

**S4. Confidence tags understate primary-verified facts.**
- *Location:* §4b Azure price "[secondary, 35]"; §2 Wails "GHSA-2p5f-2gx8-mh8m … [secondary, 9]".
- *Problem and evidence:*
  - The Azure product page states "Basic: $9.99/month for up to 5,000 signatures; $0.005 per additional signature; Premium: $99.99/month for up to 100,000". The Azure Retail Prices API also returns Basic Account 9.99/month, Premium 99.99/month and Overage 0.005. This is primary (https://azure.microsoft.com/en-us/products/artifact-signing ; https://prices.azure.com/api/retail/prices). Note that the pricing-details page renders "$-" placeholders, so cite the product page or the API, not the pricing page.
  - The Wails advisory note appears verbatim in the primary GitHub release (https://github.com/wailsapp/wails/releases/tag/v3.0.0: "GHSA-2p5f-2gx8-mh8m is only partly fixed"). It also states a concrete Linux limit: same-origin child frames are not blocked.
- *Fix:*
  - Tag both "[verified]".
  - Add the Premium price ($99.99/month).
  - Replace the newreleases.io mirror (source 9) with the GitHub release.
  - Add the Linux limitation in one clause: "don't embed untrusted same-origin content".

**S5. iced is under-maintained in releases, not stale in development.**
- *Location:* §3 iced, Q7 "Stale: iced (no release in about 11 months)", Dropped list.
- *Problem:* The last release is 0.14.0 (2025-12-07), which is correct. But master has commits on 2026-11-01 and 2026-11-11. "Stale" suggests abandonment.
- *Evidence:* `gh api repos/iced-rs/iced/releases` and `gh api 'repos/iced-rs/iced/commits?per_page=3'` (2026-11-12).
- *Fix:* "No release in about 11 months (0.14.0, 2025-12-07), though master is active (commits in November 2026). The risk is unpredictable release timing, not abandonment."

**S6. Back the gpui claim with primary data.**
- *Location:* §1 and §2 gpui, "crates.io `gpui` is about 11 months behind Zed [secondary, 26]".
- *Problem:* The claim cites a personal blog and an unrelated crate (`gpui-box`). The primary data is easy to get: crates.io `gpui` 0.2.2 was published 2025-10-22, and Zed's in-tree `crates/gpui/Cargo.toml` is still `version = "0.2.2"`, `publish = true`. Zed ships weekly (v1.28.1, 2026-11-11). So it is fair to say the published crate is about 13 months old while Zed's in-tree gpui has moved on under an unchanged version number.
- *Evidence:* https://crates.io/api/v1/crates/gpui/versions ; https://github.com/zed-industries/zed/blob/main/crates/gpui/Cargo.toml
- *Fix:* "crates.io `gpui` 0.2.2 (2025-10-22) is the only published release. Zed vendors gpui in-tree and changes it weekly without bumping the version [verified]."

**S7. Qt details.**
- *Location:* §2 Qt row "[secondary, 20]" and "an LTS every 4th minor"; §4a Qt Small Business; Sources 21.
- *Problem:*
  - Qt 6.12 LTS (2026-09-30) is confirmed. The Qt 6 releases doc lists Qt 6.12.0 with standard support to 2031-09-30, and Qt's blog post is "Qt 6.12 LTS Released!". It can be tagged [verified].
  - The LTS designation applies to commercial users. The doc lists "Qt 6.8.8 (LTS, commercial only)", so LGPL users do not get the LTS patch stream. That matters for an LGPL-based choice.
  - LTS lines have been 6.2, 6.5, 6.8 and 6.12, so "every 4th minor" is inaccurate.
  - The cited URL https://www.qt.io/qt-for-small-business returns 404 today. The €546/US$618 price, ≤ €1M revenue cap and max-3-licences terms come only from search snippets of Qt pages and from aggregators. The max-3 and 12-month-term rules were confirmed on https://www.qt.io/pricing.
- *Evidence:* https://doc.qt.io/qt-6/qt-releases.html ; https://www.phoronix.com/news/Qt-6.12-LTS-Released ; https://www.qt.io/pricing
- *Fix:*
  - Tag 6.12 [verified].
  - Write "LTS patch releases are commercial-only; open-source users get the regular patch releases".
  - Change the cadence text to "an LTS roughly every 3–4 minors".
  - Update source 21's URL, and keep the price tagged [secondary].

**S8. Qt LGPL obligations need a primary citation and a hedge.**
- *Location:* §4a Qt row. The list of obligations is uncited.
- *Problem:* The listed obligations (relinking, replaceable libraries, LGPL text plus source or offer, notice, no ban on reverse engineering for debugging) are a correct reading of LGPLv3. But the row cites nothing. Qt's official page states the core duty ("Provide a re-linking mechanism for Qt libraries") and names GPL-only modules (Qt Charts, Qt Data Visualization, Qt Virtual Keyboard). The file's example of "Qt Quick 3D" as GPL/commercial-only was not confirmed.
- *Evidence:* https://www.qt.io/development/open-source-lgpl-obligations ; https://www.qt.io/faq/3.7.-what-are-my-obligations-when-using-qt-under-the-lgpl ; https://www.qt.io/download-open-source
- *Fix:*
  - Cite these pages.
  - Use Qt's own list of GPL-only modules: Charts, Data Visualization, Virtual Keyboard.
  - Add "Qt gives no legal advice; LGPLv3 also requires 'Installation Information' for consumer devices (not relevant to a desktop download)", or drop the uncited extras.

**S9. PyQt6 and PySide6 are correct, but cite primary sources.**
- *Location:* §4a PyQt6 and PySide6 rows.
- *Evidence:*
  - PyPI metadata: PySide6 6.12.0 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; PyQt6 6.12.0 `GPL-3.0-only`.
  - Riverbank: the "free versions are licensed under the GNU GPL v3"; the commercial licence grants "the right for a single developer". No price is published.
  - Links: https://pypi.org/project/PySide6/ ; https://pypi.org/project/PyQt6/ ; https://www.riverbankcomputing.com/commercial/pyqt
- *Fix:* Replace the pythonguis.com citation with these, and tag both rows [verified].

**S10. Dead or weak links in Sources.**
- Source 17's https://avaloniaui.net/xpf/pricing/internal returns 404, so the XPF "from €9,500" price is unconfirmed. Re-cite it or mark it [unverified].
- Source 21: see S7.
- Source 36's FAQ date and source 37's "updated 2026-10-08" are fine. The quickstart's eligibility wording matches the file verbatim.

**S11. SignPath conditions overstated.**
- *Location:* §4b SignPath ("builds must come from a public repository's CI").
- *Problem:* The terms require "an OSI-approved Open Source license without commercial dual-licensing for all components", MFA for all team members, and binaries "built from source code in a verifiable way". They do not explicitly say "public repository". The page is also marked as a draft.
- *Evidence:* https://signpath.org/terms
- *Fix:* "Builds must be verifiable automated CI builds from the project's source repository (terms page is marked draft)."

## Nice to have

**N1. Compose 1.12.0 date.** The GitHub release v1.12.0 is dated 2026-08-25, not 08-26 (`gh api repos/JetBrains/compose-multiplatform/releases`). 1.13.0-beta02 (2026-11-04) is also out; mentioning it shows the cadence. The 1.12.2 date (2026-10-15) is correct.

**N2. Flutter on macOS: Intel phase-out.** The supported-platforms page (updated 2026-11-11) says macOS 27 requires Apple Silicon and Tahoe (26) is the last Intel release. Ubuntu support is LTS-only (20.04–24.04). These are worth one clause each in §1. https://docs.flutter.dev/reference/supported-platforms

**N3. Tauri v3 nuance.** In alpha.0, `tauri-runtime-wry` enables `gtk3` and `tauri-runtime-cef` enables `gtk4`. The default wry runtime on Linux is therefore still GTK3/WebKitGTK. Only choosing CEF moves to GTK4 and Chromium. This strengthens the file's point that CEF is the Linux escape hatch, at a bundle-size cost. Alpha dates are confirmed: alpha.0 on 2026-09-13 and alpha.6 on 2026-11-06. https://github.com/tauri-apps/tauri/releases/tag/tauri-v3.0.0-alpha.0

**N4. Wails.** Note that the GTK3 path (`-tags gtk3`) was announced as available only "until v3.1", and v3.1.0 shipped on 2026-11-01. On older distros without WebKitGTK 6.0 that matters. Also, v2.17.1 shipped the same day as v3.1.0, which supports "v2 isn't going away".

**N5. Electron support window wording.** The 3-majors and 8-week policy is verbatim on the timelines page. Today the supported majors are v43, v44 and v45, and all three received patches on 2026-11-12 (v43.8.9, v44.11.2, v45.3.1). That concretely confirms the policy and can be stated.

**N6. Scope pointer.** "see 03/04 if assigned" is vague. Name the actual files once they exist. WSL process driving matters for every framework and is covered in 05.

### Verified as stated (no change needed)

- Electron v45.3.1 (2026-11-12). v45.0.0 (2026-10-21) shipped Chromium 156.0.8078.48 and Node 24.22.0.
- Tauri v2.12.5 (2026-10-21). v3 alpha.0 to alpha.6 have the CEF runtime, selection through `.runtime(...)`, GTK feature gating and MSRV 1.95.
- Wails v3.0.0 (2026-10-26), v3.1.0 (2026-11-01). Go 1.26, GTK4/WebKitGTK 6.0 default.
- Flutter 3.50.0 stable (2026-11-11), Dart 3.14.0.
- Compose Multiplatform 1.12.2 (2026-10-15). Desktop (JVM) is Stable on kotlinlang (page dated 2025-09-10, as the file already flags).
- Avalonia 12.1.6 (2026-11-09); Plus €299/yr, Pro €899/yr, Enterprise from €21,000/yr.
- MAUI 11.0.0 (2026-11-10) and 11.0.10 (2026-11-11), with no Microsoft Linux target.
- Apple Developer Program US$99/yr; D-U-N-S and website required for organizations.
- Azure Artifact Signing: Public Trust for organizations in the US, Canada, EU, UK, Australia, New Zealand, Japan, South Korea, Singapore, Switzerland, Norway and Israel. "Individual developers must be located in the United States or Canada". Identity validation takes 1–20 business days.

## Review resolution

Each correction was re-checked live on 2026-11-12, using `gh api`, crates.io, PyPI, the Azure Retail Prices API and the vendor pages, before it was applied.

- **M1: applied.** Removed the "reuses the `devscene` TypeScript code directly" claim (TL;DR and ranking) and the Tauri "Node sidecar" caveat. The TL;DR now uses the reviewer's wording. The ranked shortlist starts with a note that harness integration is equal across stacks (see 05). The order is re-justified on maturity and support policy, Linux rendering (bundled Chromium versus WebKitGTK), the updater and packaging ecosystem, and line stability, using newly verified electron-builder and Tauri updater/bundler docs (sources 44, 45). The order is unchanged: Electron, Tauri 2, Wails 3. Electron and Tauri are stated to be close, and same-language TS types count only as a minor tie-breaker.
- **M2: applied.** The Slint text in §4a, the TL;DR, Q6 and the Dropped list now says free proprietary use depends on disclosure, under Royalty-free License 2.0 (which also covers mobile and web); embedded use needs the Commercial licence. Verified against `LICENSE.md`.
- **S1: applied.** Added the flutter.dev 3.44 post as source 40 (quotes confirmed) and tagged the fact [verified]. "Reduced Google investment" is now marked [inferred], and OMG! Ubuntu is kept as a secondary source only.
- **S2: applied.** The text now gives the 460-day CSC-31 limit from 2026-03-01 (DigiCert, source 43) and Certum's 459 days from 2026-02-27. The Certum quote was confirmed verbatim.
- **S3: applied.** Confirmed "Product is out of stock" for the €49 cloud product and the €25/€69 card variants. Noted in §4b, the TL;DR and Q6.
- **S4: applied.** Azure is tagged [verified] and the Premium price (US$99.99/month) added; the Retail Prices API returned 9.99, 99.99 and 0.005. Source 9 is replaced by the GitHub release. Wails is tagged [verified], and the Linux same-origin child-frame limit is added.
- **S5: applied.** iced is reworded in §2, §3, Q7 and the Dropped list. Confirmed 0.14.0 (2025-12-07) and master commits on 2026-11-11 and 2026-11-12.
- **S6: partially applied.** Used crates.io and Zed `Cargo.toml` as primary sources (0.2.2, 2025-10-22, in-tree 0.2.2, `publish = true`; Zed v1.28.1 2026-11-11). The text says "latest published release", not "only published release", because crates.io also lists 0.1.0, 0.2.0 and 0.2.1.
- **S7: partially applied.** Applied: 6.12 tagged [verified], with support to 2031-09-30; LTS patches are commercial-only; the cadence is now "roughly every 3–4 minors". Disagreement: https://www.qt.io/qt-for-small-business does not return 404. It redirects to https://www.qt.io/development/qt-for-small-business, which shows "546 EUR ($618) per year", the ≤ €1M revenue and/or funding limit, the 3-licence maximum and the 12-month term. So source 21 now uses the canonical URL, and the price is tagged [verified] rather than kept as [secondary].
- **S8: partially applied.** Cited Qt's LGPL-obligations page (source 41) and added the no-legal-advice and Installation Information hedge. The uncited extras are tagged [inferred]. Disagreement on the module list: the doc.qt.io module pages mark Qt Quick 3D as "Commercial or GPLv3", which confirms the original example. The text therefore lists Charts, Graphs, Quick 3D and Virtual Keyboard (source 42). Data Visualization is not listed, because no live GPL statement for it was found.
- **S9: applied.** PyPI metadata (PySide6 and PyQt6 6.12.0) and Riverbank's "single developer" wording were confirmed. The pythonguis.com citation was replaced, and both rows are tagged [verified].
- **S10: applied.** The XPF pricing URL was confirmed as 404. The €9,500 figure is marked [unverified] in §4a and the source list. Source 21 is handled under S7.
- **S11: applied.** Confirmed the OSI licence without dual licensing, MFA for all team members, verifiable builds and the draft marking; no "public repository" wording was found. Reworded and tagged [verified].
- **N1: applied.** Compose 1.12.0 is dated 2026-08-25, and 1.13.0-beta02 (2026-11-04) is added.
- **N2: applied.** Added the Intel Mac phase-out (Tahoe last, macOS 27 Apple Silicon only) and Ubuntu LTS-only to the §1 Flutter row.
- **N3: applied.** Added the wry=GTK3 versus CEF=GTK4 detail to the TL;DR and §3 Tauri. Confirmed in the alpha.0 notes.
- **N4: applied.** Added the GTK3 "until v3.1" cutoff and the v2.17.1/v3.1.0 same-day releases (both 2026-11-01) to §2 Wails and ranking #3.
- **N5: applied.** Added that v43.8.9, v44.11.2 and v45.3.1 were all patched on 2026-11-12, to §2 Electron and ranking #1.
- **N6: applied.** The Scope section now names 02, 03, 04 and 05 (05 for harness integration and WSL process driving).
