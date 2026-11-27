# Research brief — Issue #1, item 1 "Product startup" (framework choice)

Shared brief for every research agent. Read it whole before starting your area.

## The product

DevScene Studio (repo `firu-daniel/devscenestudio`, this repo) is a small desktop app for macOS, Linux and Windows that manages runs of the DevScene harness. The source of truth is GitHub Issue #1 (`gh issue view 1 --repo firu-daniel/devscenestudio`). Read it. The points that matter for the framework choice:

- **Small app.** It has a Jira-like board with three columns (To Do, In Progress, Done), cards, a session detail screen (status, analytics, a form to answer questions, a log tail), a repo dropdown, doctor status icons and a donations link. It has no editor, no canvas and no heavy rendering.
- **It mostly drives processes and files.** It spawns `git`, `gh`, `claude` (headless only) and the `devscene` CLI. It reads JSON files (`registry.json`, `status.json`, run analytics), tails log files, and watches folders. It calls the GitHub API, through `gh` or directly.
- **Windows through WSL2 only.** The Windows app talks to a harness installed inside WSL2. It runs processes through `wsl.exe` and reads files through `\\wsl$\…` / `\\wsl.localhost\…` paths. macOS and Linux run natively.
- **No Claude sessions and no Claude credentials inside the app.**
- **Distribution.** No app stores. Downloadable bundles from a product web site, with code signing and notarization (Apple, Windows), Linux packaging (AppImage and/or deb) and auto-update.
- **The harness** lives at `/Users/daniel/Work/devscene`. Its CLI is Node ≥ 20.11 and TypeScript, in `cli/`, published to npm as `devscene` (`npx devscene init`, `devscene doctor`, `devscene daemon install`, …). A JSON read/act verb (`devscene runs … --json`) is being considered (Issue item 7).
- **Future siblings.** The same author plans more products (ragscene, langscene, tracescene, scenewise). A choice that carries over to those has extra value.

## Candidates

The Issue names Electron, Tauri and Flutter desktop. Also consider at least: Wails (Go), Kotlin / Compose Multiplatform (desktop), .NET (Avalonia, MAUI and its Linux gap), Qt (C++ / PySide6 / PyQt), Python native-ish options (Toga/BeeWare, Flet, pywebview), Rust native GUI (Slint, iced, egui, gpui), Go native (Fyne, Gio), React Native for Windows/macOS, Neutralino.js, Electrobun and any other credible newcomer. Also consider **fully native per platform**: Swift/SwiftUI/AppKit on macOS, GTK4/libadwaita or Qt on Linux, WinUI 3 / WPF on Windows. Drop candidates that obviously don't fit, and say in one line why.

## The owner's questions (answer them explicitly in your area)

1. Are there cross-platform solutions for writing macOS, Linux and Windows apps? Which are credible in late 2026?
2. Is cross-platform worth it compared with native implementations? The app is small, and AI agents write code much faster than humans. Test the claim that "one cross-platform project versus N native projects means N times the time". With agents writing the code, what does N native codebases really cost? Consider writing, reviewing, testing, CI, signing, bug parity, feature drift and maintenance.
3. Career value. The owner would benefit from using a framework or language that builds their career, for example Python, Go or Rust (also Kotlin and TypeScript).
4. Performance: cross-platform and multi-platform frameworks compared with native. The owner specifically asks whether **Kotlin Multiplatform** works.
5. If a cross-platform framework is chosen, could native-side blockers come up?
6. Are there financial costs for any framework (licences, commercial tiers, paid tooling, signing certificates)?
7. Is any framework deprecated, or losing support or momentum?

## Rules

- **Today is 2026-11-12.** Use web search and fetch primary sources: official docs, release notes, GitHub repos (stars, release cadence, last release date, open-issue trends), licence pages and pricing pages. Your training data may be stale, so verify version numbers, dates, prices and support status live. Flag any source older than about 12 months.
- Cite every non-obvious claim inline with a URL. Mark each claim's confidence: **[verified]** (you checked a primary source), **[secondary]** (blog, benchmark or forum), **[inferred]** (your reasoning).
- Stay in your assigned area. Other agents cover the other areas. A one-line cross-reference is fine, for example "see 04".
- Be concrete and decision-oriented. Prefer tables. Don't pad.
- Read only what you need from the harness repo. Don't read `docs/rag-extraction-research` or other large docs folders.

## Output format (one Markdown file, path given in your dispatch)

```
# NN — <Area title>
> Status: draft · Date: 2026-11-12 · Area owner: research agent

## TL;DR            (5–10 bullets, the answers that matter for the decision)
## Scope            (what this file covers / defers to other files)
## Findings         (sections per sub-topic; tables where useful)
## Answers to the owner's questions   (only the ones your area touches)
## Risks and open questions
## Sources          (numbered list: URL — what it supports — accessed 2026-11-12)
```

The file is your deliverable. Return a ≤ 15-line summary of your conclusions to the dispatcher.
