# Research brief: Studio application architecture

Shared brief for every research agent. Read all of it before starting your area.

## Why this research exists

DevScene Studio (this repo, `firu-daniel/devscenestudio`) has picked Electron (D1) and React (D11). The framework research is in [`../product-startup-research/`](../product-startup-research/). Start with `10-recommendation.md` (TL;DR, §5 spike, §6 security bar). Read `08-security.md` §6.2 only if your area touches security. The validation spike checklist is GitHub Issue #4 (`gh issue view 4`). The product is described in Issue #1 (`gh issue view 1`).

The spike is about to build real code: a board, a detail screen, a log tail, browser mode, Playwright tests (Day 1), then the main process, `gh` calls, a native modal and the preload (Day 2). The owner expects Electron to stay, so this code will very likely become the product's skeleton (Issue #1 item 2). The harness will then be installed on it (item 3). `devscene init` detects **layers** from the code: each layer is a directory with its own conventions document, and the harness gives each layer its own implementer and reviewer agent (harness docs: `/Users/daniel/Work/devscene/docs/config.md`, keys `layers[].name/path/conventions`; one catch-all row with `path: "."` is required). So the directory layout decided now becomes the harness's layer map.

This research decides **the application architecture before Day 1 starts**: the layers, what goes where, how data flows, and the rules that keep it clean. It must stay proportionate. This is a small app, and the architecture should be basic: layers and placement rules, not a framework of our own.

## The product, in short

- A board with three columns: To Do (GitHub Issues), In Progress (unmerged runs with a status badge), Done (merged runs). A run detail screen: status, timings, analytics, actions (pause, resume, answer questions), and a log tail. A repo dropdown, doctor status icons.
- It mostly drives processes and files: it spawns `git`, `gh` and the `devscene` CLI, reads JSON, tails logs, watches folders, and calls the GitHub API. It runs no Claude session and handles no Claude credentials.
- **Live state is central.** The owner wants the UI to reflect live changes: an Issue's state (open, in progress, done), a run's phase (planning, implementation unit, review, gates; not final), log lines as they arrive. Sources: child-process stdout (a future `devscene runs watch --json` NDJSON stream: a `snapshot`, then `run_updated` events, heartbeats), file watching, and polling `gh`/the GitHub API.
- Windows talks to a harness inside WSL2 through `wsl.exe --exec`; the transport is `Direct | Wsl`.
- **Browser mode is a v1 requirement:** the renderer must run in a plain browser against fixture-backed IPC, so Playwright (and the harness's QA agent) can drive it.
- Security bar (10 §6): sanitised markdown with Trusted Types, a strict CSP, intent-only IPC (the preload exposes verbs, never `ipcRenderer`), one argv builder, OS-native confirmations, a repo-trust gate, `contextIsolation`, `sandbox`, fuses.
- Current code: `src/main/main.ts`, `src/preload/preload.ts`, `src/renderer/*` (a hello world, built with `tsc` only). Issue #1 item 2 suggested `app/` (renderer), `app/main/` (main process and preload), `contract/` (types generated from the harness's JSON Schema). That layout is a suggestion this research may change.

## The owner's questions

1. How do Electron's parts fit together (main, renderer, preload, utility processes, IPC), and what does Electron itself provide versus what we build? Is it "like React for the web"?
2. Should the spike start on a clean layered architecture, and what is the smallest one that is still clean?
3. How do clean architecture, SOLID and design patterns apply concretely to this app, across Electron's process boundary? Name the pattern, where it lives, and the file that would hold it. Skip patterns that add ceremony without a payoff here.
4. Reactive programming: how do live updates flow from a child process or a watched file to a React component? Streams, observables, or what the platform offers? What does Electron provide, and what do we add?
5. Performance and security consequences of each architectural choice.
6. Can the owner's existing React web app, `/Users/daniel/Work/expause/expause_web` (TypeScript, React 18, layered `data/` `domain/` `presentation/`, use cases, an event bus, TanStack Query, Redux Toolkit, Dexie), serve as a model? Its docs are in `docs/architecture/` (`ARCHITECTURE.md`, `STATE_MANAGEMENT.md`) and `docs/REACT_STATE_BEST_PRACTICES.md`. Say what carries over, what doesn't, and why. Read only what your area needs.

## Rules

- **Today is 2026-11-25.** The repo pins Electron 45.5.0, electron-builder 26.18.1 and TypeScript 6.0.3. Verify versions, APIs, library status (last release, maintenance) and recommendations live against primary sources: the Electron docs, release notes, library repos. Your training data may be stale. Flag any source older than about 12 months.
- Cite every non-obvious claim inline with a URL, or a path and line for local code. Tag each claim **[verified]** (primary source checked), **[secondary]** (blog, benchmark, forum) or **[inferred]** (your reasoning).
- Stay in your area. Other agents cover the others; a one-line cross-reference such as "see 03" is fine.
- Be concrete and decision-oriented. Prefer tables, folder trees and short code sketches (a few lines each) over prose. Don't pad. Every recommendation must say what it costs and what it buys **for this app**; generic best-practice lists are not useful.
- Proportion: when a pattern or library is not worth it at this size, say so.
- Don't read large docs folders in other repos beyond what is named here.

## Areas

| File | Area |
|---|---|
| `01-electron-process-model.md` | Electron's processes and IPC primitives, and what Electron provides vs. what we build |
| `02-layered-architecture.md` | The layers, folder tree, dependency rules and their enforcement, SOLID and patterns, the harness layer map, the expause_web comparison |
| `03-reactive-data-flow.md` | Live data from sources to React: streams, observables, stores, IPC push, lifecycle |
| `04-performance.md` | Performance consequences of the architecture |
| `05-security-architecture.md` | Where each item of the v1 security bar lives in the layers |
| `06-testing-and-tooling.md` | Tests per layer, browser mode, Playwright, build and lint tooling, harness gate fit |
| `07-recommendation.md` | Synthesis (written after 01–06 are reviewed) |

## Output format (one Markdown file, at the path your dispatch gives)

```
# NN — <Area title>
> Status: draft · Date: 2026-11-25 · Area owner: research agent

## TL;DR            (5–10 bullets: the answers that matter for the decision)
## Scope            (what this file covers, and what it leaves to other files)
## Findings         (a section per sub-topic; tables, trees and short sketches)
## Recommendation for the spike   (what Day 1 and Day 2 should build in this area, concretely)
## Answers to the owner's questions   (only the ones your area touches)
## Risks and open questions
## Sources          (numbered list: URL or path — what it supports — accessed 2026-11-25)
```

The file is your deliverable. Return a summary of your conclusions in 15 lines or fewer.
