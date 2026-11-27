# Architecture research: DevScene Studio application architecture

> Date: 2026-11-25 · Covers the application architecture for the validation spike (Issue #4) and the project skeleton (Issue #1 items 2 and 3) · Decision document: [`07-recommendation.md`](07-recommendation.md) (Status: reviewed)

## Purpose

The framework research ([`../product-startup-research/`](../product-startup-research/)) picked Electron and React. The spike is about to write real code that will very likely become the product's skeleton, and the harness will turn its folders into its layer map. This folder decides the application architecture before spike Day 1: the layers and what goes where, how live data flows from child processes and files to React, the performance and security consequences of each choice, the test and build tooling, and what carries over from the owner's expause_web app. It aims for a small, basic architecture, not a framework of our own.

## Method

Each area went through three steps:

1. **Research.** One agent per area worked from the shared brief, [`_brief.md`](_brief.md). Each was told to verify versions, APIs and library status live against primary sources on 2026-11-25, to cite every non-obvious claim inline, and to tag each claim **[verified]** (primary source checked), **[secondary]** (blog, benchmark, forum) or **[inferred]** (the agent's own reasoning). Sources older than about 12 months are flagged. Several claims were checked with scratch tests (TypeScript project references, ESLint rules, `devscene init` and `doctor` on a scratch tree, Electron 45.5.0 micro-benchmarks).
2. **Review.** A separate agent per file worked from [`_review_brief.md`](_review_brief.md). It re-verified every load-bearing claim live, checked citations, coverage, reasoning, proportion (over-engineering counts as a finding) and consistency with the security bar, and wrote numbered findings (Must fix / Should fix / Nice to have) to `reviews/<same filename>`.
3. **Fix.** A fix agent re-checked each finding before applying it, recorded the outcome (applied, partially applied or rejected, with the reason) in a `## Review resolution` section at the end of each review file, and set the area file's status to `reviewed`.

The synthesis, `07-recommendation.md`, reads all six reviewed files and the review resolutions, settles the disagreements between them from their final text, and adds no new primary research. It goes through the same review and fix steps.

**Measurement caveat.** 04's local performance numbers were taken while the machine was under heavy load. Only ratios between variants measured in the same run support its conclusions; the spike re-measures every absolute target on an idle machine.

## How to read it

Start with [`07-recommendation.md`](07-recommendation.md). Its TL;DR gives the architecture; §1 answers the owner's six questions; §3 is the reference architecture (folder tree, dependency rules, the `layers[]` JSON, the pattern table and the data flow); §2 lists each disagreement between files and how it was resolved; §4 is the revised Day 1 and Day 2 plan for Issue #4, with effort; §5 lists the edits made to Issues #4 and #1; §6 lists harness asks; §7 lists deferred mechanisms with their triggers; §8 lists risks and what remains unverified. Open an area file only when you need the evidence behind a point. The reviews are for checking how a claim was verified or corrected.

## Files

| File | One-line summary | Review verdict |
|---|---|---|
| [`01-electron-process-model.md`](01-electron-process-model.md) | What Electron provides vs. what we build; main, renderer, preload and utility processes; IPC primitives and structured-clone rules; hand-written typed IPC (no library); the `getStudio()` browser-mode seam; lifecycle (single instance, `app://`, quit cleanup). | PASS WITH FIXES · [review](reviews/01-electron-process-model.md) |
| [`02-layered-architecture.md`](02-layered-architecture.md) | One folder per process plus `src/shared`; ports and adapters in main; the five-row harness layer map (set by hand, `init` won't detect it); project references plus core ESLint rules for enforcement; patterns kept and skipped; expause_web compared. | PASS WITH FIXES · [review](reviews/02-layered-architecture.md) |
| [`03-reactive-data-flow.md`](03-reactive-data-flow.md) | Live data from child processes and `gh` to React: plain Node streams in main (no RxJS), a read-model in main, `snapshot` + `upsert`/`remove` pushes, Zustand for live state, TanStack Query for on-demand reads, ring buffers for logs, ETag polling. | PASS WITH FIXES · [review](reviews/03-reactive-data-flow.md) |
| [`04-performance.md`](04-performance.md) | Measured on Electron 45.5.0 (under load; ratios only): batch logs, virtualise only the log tail, memoise cards by id, no `utilityProcess`, never block main, a main-owned hidden-window policy, bundling and library sizes. | PASS WITH FIXES · [review](reviews/04-performance.md) |
| [`05-security-architecture.md`](05-security-architecture.md) | Where each v1 security-bar item lives: nine choke points with lint or type guards and tests; IPC validated in main with TypeBox; DOMPurify ≥ 3.5.0 under Trusted Types; hardening, fuses, browser-mode risks, CI suites per layer. | PASS WITH FIXES · [review](reviews/05-security-architecture.md) |
| [`06-testing-and-tooling.md`](06-testing-and-tooling.md) | Vite + esbuild build, tsconfig layout, Vitest (node + jsdom), co-located tests plus one `tests/` root, the IPC contract suite, Playwright for browser and Electron, fixtures, lint and format, harness gate commands. | PASS WITH FIXES · [review](reviews/06-testing-and-tooling.md) |
| [`07-recommendation.md`](07-recommendation.md) | **The decision document:** the architecture, the owner's questions answered, resolved disagreements, the reference architecture, the revised Day 1/Day 2 plan and effort, the Issue edits (applied), harness asks, deferred mechanisms and open risks. PASS WITH FIXES · [review](reviews/07-recommendation.md) |

All reviews: [`reviews/`](reviews/).

## TL;DR of the recommendation

- **Layout:** `src/shared/{domain,contract}`, `src/main`, `src/preload`, `src/renderer`, plus one `tests/` root for cross-layer suites. Issue #1's `app/` + `app/main/` + `contract/` layout is replaced.
- **Harness layers:** `shared`, `main`, `renderer`, `tests`, and the catch-all `general` (which also takes the one-file preload), set with one `devscene config set layers` command.
- **Enforcement:** TS project references make cross-process imports a compile error; ESLint core rules enforce the rules inside each process and the security choke points.
- **Build:** Vite for the renderer, an esbuild script for main and preload, landing in the same change as the tsconfig split. electron-vite is the fallback.
- **Data flow:** sources and the read-model live in main; main pushes a snapshot, then per-entity updates, into a Zustand mirror; logs go through ring buffers; TanStack Query handles on-demand reads and commands.
- **Patterns:** ports and adapters, hand-wired composition roots, Strategy for `Direct | Wsl`, one argv builder, a fixture/IPC adapter behind `StudioApi`, the preload facade, intents as data, `Result` over IPC, branded types. No DI container, use-case classes, event bus or IPC library.
- **Security and gates:** DOMPurify ≥ 3.5.0; the XSS gate becomes 0 Trusted Types violations and 0 executions; IPC is validated in main.
- **Cost:** spike Days 1–2 grow from 3 to ≈ 5–5.5 owner-days, and the spike from ≈ 6–7 (Day 4 moved to Issue #1 item 4) to ≈ 8–9.5; about 1.5 owner-days of that is v1 work done earlier, so spike plus v1 grows by ≈ 0.5–1.

## Agent briefs

[`_brief.md`](_brief.md) is the brief every research agent worked from (the product, the owner's questions, rules and output format). [`_review_brief.md`](_review_brief.md) is the brief every review agent worked from. They are kept for traceability; they are not part of the findings.
