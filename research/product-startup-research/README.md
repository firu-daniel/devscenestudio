# Product-startup research: DevScene Studio framework choice

> Date: 2026-11-12 · Covers GitHub Issue #1 item 1 ("Product startup") and item 16 ("Licensing check") · Decision document: [`10-recommendation.md`](10-recommendation.md) (Status: reviewed)

## Purpose

DevScene Studio is a small desktop app for macOS, Linux and Windows (Windows through WSL2) that manages DevScene harness runs. This folder holds the research behind its first decision: which framework or frameworks to build it with, how to deliver it (desktop shell or a web mode), how to lay out the repository so the DevScene harness can drive its development, how deep its security work must go, and whether it is within Anthropic's terms.

## Method

Each area went through three steps:

1. **Research.** One agent per area worked from the shared brief, [`_brief.md`](_brief.md). Each was told to verify versions, dates, prices and support status live against primary sources on 2026-11-12, to cite every non-obvious claim inline, and to tag each claim **[verified]** (primary source checked), **[secondary]** (blog, benchmark, forum) or **[inferred]** (the agent's own reasoning). Sources older than about 12 months are flagged. Harness facts were read from the local harness repository (`/Users/daniel/Work/devscene`) with path and line references.
2. **Review.** A separate agent per file worked from [`_review_brief.md`](_review_brief.md). It re-verified every load-bearing claim live, checked citations and confidence tags, coverage against the brief, reasoning and scope, and wrote numbered findings (Must fix / Should fix / Nice to have) to `reviews/<same filename>`.
3. **Fix.** A fix agent re-checked each finding before applying it, recorded the outcome (applied, partially applied or rejected, with the reason) in a `## Review resolution` section at the end of each review file, and set the area file's status to `reviewed`.

The synthesis, `10-recommendation.md`, reads all nine reviewed files and the review resolutions, and maps its harness follow-up list onto devscene #170 (the uncovered security items are filed as devscene #344–#356). It resolves the disagreements between files and adds no new primary research, apart from one check of the harness source (the state-label prefix). It went through the same review and fix steps as the area files.

File 09 adds its own grading for legal questions: **[unambiguous]**, **[strong reading]** or **[ask]**. It is not legal advice.

## How to read it

Start with [`10-recommendation.md`](10-recommendation.md). Its TL;DR gives the pick; §1.2 weighs Electron against Tauri, security first, and lists the flip conditions; §3 answers each of the owner's questions in a few lines and points to the detailed file; §4 lists the decisions the owner must make; §8 lists the harness follow-ups with where each is tracked. Open an area file only when you need the evidence behind a point. The reviews are for checking how a claim was verified or corrected.

## Files

| File | One-line summary | Review verdict |
|---|---|---|
| [`01-framework-landscape.md`](01-framework-landscape.md) | Every candidate's language, rendering, Linux status, health, deprecation risk, licence and signing costs. Shortlist: Electron, Tauri 2, Wails 3; MAUI and React Native desktop dropped (no Linux). | PASS WITH FIXES · [review](reviews/01-framework-landscape.md) |
| [`02-performance.md`](02-performance.md) | Bundle size, idle RAM, cold start, rendering, spawn and WSL costs, and Kotlin Multiplatform. Performance does not decide the framework for this I/O-bound app; only bundle size and Linux WebKitGTK are user-visible. | PASS WITH FIXES · [review](reviews/02-performance.md) |
| [`03-native-vs-cross-effort.md`](03-native-vs-cross-effort.md) | Cost model for native ×3 vs cross-platform with agents (2.1–2.2× for v1, ≈ 2.7× per feature), harness gate limits on native code, agent effectiveness by stack, and career value by language. | PASS WITH FIXES · [review](reviews/03-native-vs-cross-effort.md) |
| [`04-os-integration-blockers.md`](04-os-integration-blockers.md) | Native-side blockers per framework: processes, WSL2 as a remote host, file watching, webview quirks, Linux packaging, macOS/Windows signing, auto-update, tray and terminal hand-off. | PASS WITH FIXES · [review](reviews/04-os-integration-blockers.md) |
| [`05-harness-integration.md`](05-harness-integration.md) | The run logic is ~22.5k lines of per-repo bash, so no stack can import it. Recommends a versioned `devscene runs … --json` contract, no sidecar, and a read-only GitHub read-model. | PASS WITH FIXES · [review](reviews/05-harness-integration.md) |
| [`06-repo-topology-harness-fit.md`](06-repo-topology-harness-fit.md) | Monorepo of native apps vs one cross-platform project vs shared core, and how the harness's gates, dispatch, parity and QA handle each. One project wins; native needs 48–82 O-d of harness work. | PASS WITH FIXES · [review](reviews/06-repo-topology-harness-fit.md) |
| [`07-additional-criteria.md`](07-additional-criteria.md) | Agent-drivable UI testing, the four delivery modes (desktop shell, local web, hosted, hybrid), accessibility, code sharing, observability, app licensing, DX, and a weighted scoring table. | PASS WITH FIXES · [review](reviews/07-additional-criteria.md) |
| [`08-security.md`](08-security.md) | Threat models per delivery mode, cross-cutting controls, effort per mode, CI security suites, the v1 minimum bar, and harness-side findings (H1/H1′ High). | PASS WITH FIXES · [review](reviews/08-security.md) |
| [`09-anthropic-terms-licensing.md`](09-anthropic-terms-licensing.md) | Anthropic terms for headless `claude -p`, Studio's spawn-only design, GitHub Actions credentials, naming, redistribution, monetisation, Apache-2.0 compatibility, and a draft email to Anthropic. | PASS WITH FIXES · [review](reviews/09-anthropic-terms-licensing.md) |
| [`10-recommendation.md`](10-recommendation.md) | **The decision document:** the recommendation, the owner's questions answered, resolved disagreements, owner decisions, the validation spike, the v1 security bar, costs, harness follow-ups, Issue #1 updates, and what remains unverified. | PASS WITH FIXES · [review](reviews/10-recommendation.md) |
| [`11-day0-signing.md`](11-day0-signing.md) | Spike Day 0, step by step: notarizing a hello-world Electron app (certificate, credentials, Hardened Runtime, entitlements, pass checks), and why SignPath Windows signing comes after the first release. | Draft, not reviewed |

All reviews: [`reviews/`](reviews/).

## Owner's decisions (2026-11-24)

The owner answered `10-recommendation.md` §4 on 2026-11-24. The details are in §4.0 of that file.

- **D1** Electron · **D2** Apache-2.0, public repo · **D3** SignPath, after the first release (11 §3) · **D4** deferred: no new Apple account for now, an existing organisation account only for private test builds · **D5** answer/resume in v1, most likely, gated on H1/H1′ · **D6** (a) · **D7** desktop shell only · **D8** AppImage + deb with the signature hook · **D9** leaning towards each person's own subscription, with API key or WIF only for remote runs several people start, pending Anthropic's answer · **D10** no tray or notifications · **D11** React.

Still open: running the validation spike (§5), sending the email to Anthropic (09), and the publish flow once the harness is installed.

## TL;DR of the recommendation

- **Framework: Electron** (TS web UI, TS main process), decided now on the evidence with security first, with **Tauri 2** as the close alternative. A 7–8 O-d validation spike checks the pick against measured flip conditions.
- **Why Electron:** security, the owner's main concern, is even: 08 rates Electron equal to Tauri if its 14-day security-release cadence (≈ 1.6 O-d/yr) and a Linux update-signature hook are kept. Tauri's modest structural edge (a mandatory signed updater, a capabilities ACL) is offset on Linux by its dependence on each distro's WebKitGTK patching. Every other evidence criterion favours Electron: Linux rendering, updater coverage, agent corpus and QA fit, maturity with no pending migration, developer experience and effort. Career value is equal (03) and decides nothing.
- **Flip to Tauri** if you cannot commit to Electron's release cadence, if the Linux update-signature hook cannot be made to work, or if download size or idle RAM becomes a product requirement.
- **Delivery: a desktop shell in v1**, with a web-first UI and a browser mode so the harness's Playwright QA agent can drive it. A hosted remote-only app is optional later. A local web app only as an opt-in developer mode. No hosted UI + local connector.
- **Topology: one cross-platform project** (`app/`, `app/main/`, `contract/`), with OS overrides as `process.platform` branches in the main process, so everything builds and tests on a Linux runner.
- **Native per platform is not worth it,** even with agents: 2.1–2.2× the owner's time for v1, ≈ 2.7× per feature, and the harness cannot verify WinUI or remote SwiftUI.
- **Kotlin Multiplatform works** only as Compose on the JVM. It is viable but has the weakest packaging story here (no AppImage, no updater, no Linux accessibility).
- **Integration:** every stack calls a harness-owned `devscene runs … --json` contract, with one long-lived `runs watch` stream inside WSL on Windows. The Issue's "Electron reuses the CLI" and "Tauri needs a Node sidecar" premises are disproved.
- **Security:** a defined v1 bar (sanitiser + Trusted Types, intent-only IPC, one argv builder, OS-native confirmations, a repo-trust gate, signed updates, three CI suites), about 5.5 O-d on Electron, plus ≈ 1.6 O-d/yr of Chromium bumps. Harness findings H1/H1′ block answer/resume until fixed, unless their runtime measurement shows every write refused.
- **Harness work:** Studio v1 needs the read side of `devscene runs … --json` plus `pause`, `drop` and a global-stop verb. The security follow-ups are filed as devscene #344–#356 (#170 covers none of them fully); re-verify each against the code before fixing.
- **Anthropic terms:** within them. Spawn the user's own unmodified `claude`, never touch credentials, never bundle Claude Code, keep Anthropic marks out of names. Three narrow questions go in a drafted email.
- **Cost:** ≈ US$99/yr if open source (Apple only); ≈ US$220–600/yr otherwise (Artifact Signing ≈ 120 if eligible, or an OV certificate ≈ 300–500; up to ≈ 900 with Sentry Team). ≈ 32.5 owner-days for v1 on Electron, including security; ≈ 36 for spike plus v1.

## Agent briefs

[`_brief.md`](_brief.md) is the brief every research agent worked from (the product, candidates, owner questions, rules and output format). [`_review_brief.md`](_review_brief.md) is the brief every review agent worked from. They are kept for traceability; they are not part of the findings.
