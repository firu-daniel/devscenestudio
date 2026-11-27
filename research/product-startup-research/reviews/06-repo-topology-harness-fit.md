# Review — 06-repo-topology-harness-fit.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The harness analysis is accurate. I checked every `path:line` citation against `/Users/daniel/Work/devscene` at `a1d0e992` (2026-11-12 08:12), and each one points at text that says what 06 claims. The line ranges are exact or off by one at most. The GitHub Actions prices, the dollar allowances and the postponed self-hosted fee all re-verify live, and so do the Nx, Turborepo, Bazel, moon, quicktype and UniFFI versions.

The recommendation of (B) follows from the evidence and agrees with 03 and 05. Four things still need fixing:

- **The headline effort total is wrong.** "6–10 owner-weeks" is lower than the sum of the file's own H-rows (about 8–13.5 weeks), and its unit doesn't match 03's owner-day model.
- **The typify release date is wrong.**
- **The Tauri "Rust-only desktop plugins" claim is tagged [verified] beyond what its source says.**
- **One option is missing.** The file never evaluates 03's "native Mac + Linux build on Windows via WSLg" variant, which removes the WinUI argument that carries most of the case against (A).

The "OS-switching wrapper reports PASS" trap is real. The harness can also show it more clearly than the file does (S3).

### Spot-check results

| Claim | Result |
|---|---|
| `layers[]` = `{name,path,conventions}`, `additionalProperties:false` (`schema:161-182`, `:163`) | Confirmed. The items run from 161 to 182, and `additionalProperties` is at 163 |
| One `commands.typecheck`/`commands.test` (`schema:184-215`) | Confirmed. The block runs from 184 to **216** (trivial) |
| `<test_file_cmd>` comes from the layer's conventions document (`unit_loop_core.md:21`) | Confirmed |
| A unit runs the whole-tree typecheck (`layer-implementer.md:21`) | Confirmed. It is also `unit_loop_core.md` test-run rule point 2 (line 143) |
| Implementer kept inside `layers[].path` (`layer-implementer.md:48`) | Confirmed |
| Evidence downgrade (`:154`); verification wording (`:179`) | Confirmed. The mechanism is described imprecisely (S2) |
| One layer per task, split with `Depends on:` (`task-plan-writer.md:104`); 20 pts / 5 bullets (`:112`); no shared file (`:126`) | Confirmed |
| Sequential unit loop: "first `[ ]` entry" (`unit_loop_core.md:70`), exactly one layer (`:56`) | Confirmed |
| Cross-layer findings dispatched sequentially, bottom-up (`plan_orchestration_instructions.md:42,48`) | Confirmed |
| Parallelism only across runs (`…_autonomous.md:108`) | Confirmed: "Per-run statistics / Done summary across parallel runs" |
| Run gates: one `run-test-suite.sh` per round (`…_core.md:538`) | Confirmed |
| ROADMAP #11 "Parallel dispatch in waves" (line 74), #8 "Contract-first task plans" (76), #44 "Mobile QA drivers" (130), all Open; no desktop driver; Cloud/CI (125) | Confirmed. The index rows are at 20, 23 and 56. `grep -i desktop ROADMAP.md` finds nothing |
| `phases.parity`: one `referenceName`/`referenceImplPath`, deferred `toolchainCommands` (`schema:292-316`) | Confirmed |
| business-parity-reviewer scope (`:3`) | Confirmed. The description lists exactly those business-logic checks |
| `qa.driver` enum with mobile stubs (`schema:244-248`); stub "silent success" text (`qa-tester-mobile-mcp.md:20`) | Confirmed |
| Remote runs Linux only (`remote-execution.md:791,795`) | Confirmed. Self-hosted runners are Linux too (`:824`, "any Linux machine you own") |
| `monorepo` is layerless (`presets.ts:533, 769-774`); Xcode `-destination` placeholder (`:1240-1253`) | Confirmed |
| No meson/GTK detection in `cli/src` | Confirmed (the grep finds nothing) |
| `devscene config set layers` (`analyze.md:48`); wrappers hold the raw line (`scripts.ts:17-22`) | Confirmed |
| Sandbox `allowWrite` = state dir only (`settings.autonomous.json:119`); network allowlist empty (`:21`, `:125`) | Confirmed. It misses the `sandbox.allowedDomains` config key (N4) |
| Actions rates: Linux $0.006, arm64 $0.005, Windows $0.010, macOS $0.062 / $0.077 / $0.102; rounding up to whole minutes; no multipliers | Confirmed live (https://docs.github.com/en/billing/reference/actions-runner-pricing) |
| Allowances: Free $12, Pro $18, Team $18, Enterprise Cloud $300; standard runners free in public repos | Confirmed live (https://docs.github.com/en/billing/concepts/product-billing/github-actions) |
| Up to 39% cut on 2026-01-01; self-hosted $0.002/min fee postponed with no date (2025-12-15 update) | Confirmed live (https://github.com/resources/insights/2026-pricing-changes-for-github-actions) |
| Arithmetic: $0.77 per 3-OS PR, about 15 PRs on $12; about $0.05 Linux-only, 200+ PRs | Confirmed: 0.62 + 0.10 + 0.048 = $0.768, and $12 / $0.048 = 250 |
| Nx 24.0.6 (2026-11-10); `@nx/dotnet` and `@nx/gradle` 24.0.6; `@nx/swift` 404 | Confirmed (npm). 24.1.0-beta.0 is also out |
| Turborepo 2.11.11 (2026-11-11); Bazel 9.3.2 (2026-11-05); moon v2.6.5 (2026-10-29) | Confirmed (`gh api …/releases`). Bazel 10.0.0rc3 is out, which is not a problem |
| quicktype v26.0.0 (2026-07-20), 13.9k★, Swift/Kotlin/Rust/C#/TS from JSON Schema | Confirmed (13,913★, README) |
| typify 0.8.0 on 2026-10-14 | **Wrong** (M2) |
| UniFFI 0.32.2 (2026-09-23) | Confirmed (crates.io) |
| json-schema-to-typescript last push 2026-09-07 | Confirmed |

## Must fix

**M1. The effort total doesn't match its own components, and it uses an undefined unit.**
- **Location:** §2.6, "Total for (A) to be well supported: about 6–10 owner-weeks (H1–H3, H5, H7, H8, excluding H4)". The same figure appears in the TL;DR, §3 and the answer to Q2.
- **Problem:** The rows the total names add up to more than the total:
  - H1 is 1–2 weeks, H2 0.5–1, H3 2–3, H5 1 and H7 3–6. H8 is "S", call it about 0.25–0.5.
  - That gives about **7.75–13.5 weeks**, not 6–10.
  - "Owner-week" is never defined. 03 costs work in owner-days (O-d) of review time, with agent wall-clock time treated as free (03 §1, line 39). 03's whole cross-platform v1 is about 27 O-d. So this file's numbers can't be compared with 03's.
- **The rows are also likely underestimates:**
  - H1 touches about 24 harness files that read the gate commands. These include the `plugin/hooks/allow-safe-compounds.sh` and `harness-config-lib.sh` hooks, the `run-test-suite.sh`/`typecheck.sh` templates, `doctor/checks.ts`, `config/check.ts`, `model.ts`, the permission-profile generator and 6 instruction/agent files (`grep -rl 'typecheck_cmd\|commands.typecheck\|test_cmd' plugin cli/src cli/templates schemas`).
  - H3 needs a sandboxed run to trigger a `workflow_dispatch` and wait for its result. Two things stand in the way:
    - The run's network allowlist is empty, and `settings.autonomous.json:21` warns that a broad GitHub domain "is an exfiltration path".
    - G.1 forbids `Monitor`/`sleep` while waiting on a gate (`unit_loop_core.md` test-run rule point 6).
  - So H3 is a security-design item, not just plumbing.
- **Fix:**
  - Replace the total with "about **8–14 weeks** of harness work (sum of H1–H3, H5, H7, H8), probably more for H3, which needs a sandbox-safe way to dispatch and await a cross-OS job".
  - State the unit in 03's terms. For example: "≈ 40–70 O-d, i.e. 1.5–2.5× 03's entire cross-platform v1 (≈ 27 O-d)".
  - Update the TL;DR, §3 and the answer to Q2 to match. The conclusion gets stronger.

**M2. The typify date is wrong.**
- **Location:** §1.4 table and source [5]: "0.8.0 on crates.io, 2026-10-14 (0.10.0 alphas tagged on GitHub)".
- **Evidence:** The crates.io API (https://crates.io/api/v1/crates/typify) shows:
  - 0.8.0 was published on **2026-09-09**.
  - 2026-10-14 is the date of **0.10.0-alpha.3**, the crate's last update.
  - The alphas (alpha.1 on 09-28, alpha.2 on 10-05, alpha.3 on 10-14) are **published on crates.io**, not only tagged on GitHub.
  - `max_stable_version` = 0.8.0.
- **Fix:** "0.8.0 stable on crates.io (2026-09-09); 0.10.0-alpha.1–3 also published on crates.io (latest 2026-10-14)."

## Should fix

**S1. The Tauri claim is overstated and tagged too strongly.**
- **Location:** §1.7, "Desktop plugin code is **Rust**. Swift and Kotlin are for mobile only [7] [verified]".
- **Evidence:** https://v2.tauri.app/develop/plugins/ never says that desktop plugins are Rust-only.
  - Its intro says plugins can "handle commands with Rust, Kotlin or Swift code".
  - Kotlin and Swift appear only under "Mobile Plugin Development".
  - The layout labels `desktop.rs` as the "Desktop implementation".
- **Problem:** "Swift/Kotlin are mobile-only" holds for Tauri's *first-class plugin bridge*. But macOS desktop code can still call Swift through Rust FFI crates such as `swift-rs`. Those crates compile Swift in a build script, which is exactly the case that breaks the `cargo check --target` cross-check this section relies on.
- **Fix:** "Tauri's plugin bridge runs desktop code in Rust (`desktop.rs`). Its Swift/Kotlin bridge is iOS/Android only [7] [verified layout; exclusivity inferred]. Swift on macOS is still reachable via FFI crates (e.g. `swift-rs`), which compile Swift in a build script and therefore are not checkable from Linux. Keep overrides in pure Rust (`objc2`, `windows`)."

**S2. The per-unit typecheck mechanism in (A) is described imprecisely, and the real consequence is missing.**
- **Location:** §2.2, "here the failure is *inside* the unit's change and simply can't be produced".
- **Problem:** Read literally, the harness rule grades this case the other way:
  - A whole-tree typecheck on a Mac that dies with `dotnet: command not found` "names no file the unit created or edited and no symbol it defined". That is the definition of an **evidence downgrade** (`unit_loop_core.md:143-144`). So the unit continues, marked as unverified.
  - The failure then surfaces in Phase G. The test-fix-plan writer classifies a missing tool as **"Not fixable on this branch"** (`test-fix-plan-writer.md:78`). That returns `fixable: 0` and **`<escalate>`** (`plan_orchestration_instructions_core.md:615, 740`).
- **Consequence:** Without the switching wrapper, every (A) run on a single OS **parks at Run gates** and never reaches "ready for review" unattended. That is a stronger and more precise statement of the problem.
- **Fix:** Replace the sentence with: "Per the test-run rule, a missing-toolchain error names no unit file, so it is graded an evidence downgrade and the unit proceeds unverified. Phase G then fails, `test-fix-plan-writer` files it under 'Not fixable on this branch' (`:78`), and the run escalates (`…_core.md:615`). Every (A) run on one OS therefore parks at Run gates unless the wrapper hides the skipped toolchains — which is the trap in §2.1."

**S3. The trap is real, but it has the wrong supporting citation.**
- **Location:** §2.1, "silent success the harness explicitly refuses elsewhere (`qa-tester-mobile-mcp.md:20`)".
- **Evidence:** The closer rules are these:
  - `layer-implementer.md:178`: "never report a pass for a gate that was not run".
  - Phase G: the orchestrator "never read[s] their output: you read the one line the wrapper prints" (`plan_orchestration_instructions_core.md:538`). The result is `pass <log>`/`fail <log>` (`:592`).
- **Why it matters:** A wrapper that prints "skipped windows" and exits 0 is reported as `pass`. No agent or summary ever sees the skip, so a warning line can't mitigate it either.
- **Fix:** Add both citations, and add: "Because only the wrapper's exit status reaches the orchestrator, no in-log warning can surface the skip; the only honest wrapper behaviours are exit-non-zero (→ S2's park) or a new harness 'deferred' state (H2)."

**S4. The WSLg variant from 03 is missing.**
- **Location:** §2.4, §3 and the Recommendation.
- **Problem:** The case against (A) rests mostly on "WinUI 3 is unverifiable in every run mode". 03 (line 119) puts forward a variant that removes WinUI altogether: native macOS plus the Linux build shipped inside WSL2 via WSLg. In that variant:
  - The Linux app is verifiable in every run mode, remote included.
  - Only the Swift layer needs a local Mac run.
  - H3's Windows half and one of the three H7 drivers drop out.
- The recommendation mentions the "native Mac plus one cross-platform build" split, but not this variant, and gives neither a harness-fit row.
- **Fix:** Add rows to the §2.4 and §3 tables for "A′: SwiftUI + GTK/Linux build reused on Windows via WSLg" and "A″: SwiftUI + Tauri/Electron". State which H-items each needs (A′: H1, H2, and a macOS-only part of H3/H7). (B) still wins, but the comparison should be on record.

**S5. The CI-cost wording contradicts itself.**
- **Location:** The TL;DR says "CI cost **is the same in (A), (B) and (C)** … Only the *per-PR verification* load differs". §3 and the answer to Q6 say "(A) and (C) pay it on every PR".
- **Problem:** In a private repo the per-PR load *is* most of the CI cost: about 15 PRs versus 200+ on the Free allowance, by the file's own table.
- **Fix:** "Release-build cost is the same in all three shapes; per-PR cost is ~15× higher in (A)/(C) for private repos (≈ $0.77 vs ≈ $0.05), and zero for all shapes in public repos."

**S6. "(B) whole tree typechecks and tests on a Linux runner" needs a qualifier for Tauri.**
- **Location:** TL;DR bullet 3 and §2.4 row "(B) … ✅" in every column.
- **Problem:** On Linux, Tauri needs system packages that the hosted `ubuntu-latest` image does not ship: `libwebkit2gtk-4.1-dev` and its relatives.
  - The remote job sets up only Node (`remote-execution.md:28`).
  - Self-hosted runners must carry "whatever toolchain your own `commands.*` lines need" (`:842`).
  - Those packages can only arrive through `commands.depInstall`, which runs unsandboxed (`:978`), for example `sudo apt-get install …`.
  - Electron, Compose and Avalonia need nothing extra.
- **Fix:** Add a footnote: "Tauri: `depInstall` must apt-install the WebKitGTK dev packages on hosted runners; Rust's `~/.cargo` writes under the strict sandbox are untested (see Risks)." The footnote also slightly favours Electron within (B), so cross-reference 03.

**S7. The sandbox caveat misses the config key that bears on it.**
- **Location:** §2.4, "The network allowlist starts empty (`:21`) … package resolution has to happen in `depInstall`".
- **Evidence:** `settings.autonomous.json:21` says what a sandboxed command may reach is `sandbox.allowedDomains` in `harness.config.json`, each entry with a reason (`cli/src/config/check.ts:163, 597`). SwiftPM fetches from GitHub hosts, and the same line warns that a broad `github.com` entry is an exfiltration path.
- **Fix:** Add: "An `allowedDomains` entry is possible but the SwiftPM hosts are GitHub, which the template flags as an exfiltration path, so `depInstall` resolution is the safer route." Keep the [inferred — needs a measured check] tag.

## Nice to have

- **N1.** In §1.2 / [1], the macOS 12-core ($0.077) and M2 Pro 5-core ($0.102) runners are **larger runners**. They are not free in public repos and are billed outside the standard-runner terms. Say so, or drop them, because the per-PR maths uses only standard runners.
- **N2.** In §1.1, "Bazel … covers everything through rules_swift/rules_apple/rules_dotnet/rules_rust" overreaches. rules_dotnet has no documented WinUI 3 / Windows App SDK (XAML) build support, and meson/GTK would go through rules_foreign_cc. Change it to "covers Swift, Rust and plain .NET; WinUI/XAML and meson would need custom or foreign rules [inferred]".
- **N3.** In §2.1, the schema range is `184-216`, not `-215`. ROADMAP citations could add the index rows (#8 at line 20, #11 at 23, #44 at 56) beside the table rows (76, 74, 130).
- **N4.** The 06 harness-constraint facts (Linux-only remote runs, one preset per repo, layerless `monorepo`, QA stubs) repeat 03 §2 rows 73–78 almost word for word. Replace them with a one-line "see 03 §2" and keep only what 06 adds: line-level citations, the per-unit and Phase G mechanics, and the H-list.
- **N5.** In Risks, "Check whether today's Rust preset already handles `~/.cargo`": I checked. `cli/src` and `cli/templates` have no `CARGO_HOME`/`CARGO_TARGET_DIR` handling and no sandbox carve-out for `~/.cargo`. Record this as "not handled; untested".
- **N6.** H6 (waves, ROADMAP #11/#8) is "already designed" but not shipped and has no date. (A)'s "ideal fit once these land" should say that (A) pays the sequential cost until then.

## Consistency with 03 and 05

- **03:** It agrees on the facts (Linux-only remote runs, a single gate per repo, no GTK preset, QA stubs, no desktop driver on the ROADMAP) and on the conclusion ("don't go fully native"). The two disagree on the unit (M1) and on coverage of 03's WSLg option (S4). The browser-mode QA requirement is cross-referenced correctly (03 line 191).
- **05:** The contract/JSON Schema plan matches 05 §5 (the harness publishes JSON Schema in `schemas/`, line 199; codegen per language, line 128). The point about watching inside WSL, not over `\\wsl$`, matches 05 line 80. I found no contradictions.

## Does the recommendation follow?

Yes. (B) is the only shape whose whole tree the harness can verify in every run mode today, with no harness changes. The evidence for that is sound and verified. The fixes above (corrected effort sum, the S2 park behaviour) make the case for (B) stronger. Only S4 adds an alternative that should be costed. It doesn't overturn (B), because even (A′) needs H1, H2 and macOS gate hosting.

## Review resolution

Resolved 2026-11-12 by the fix agent. Each factual correction was re-checked live or against the harness at `a1d0e992` before it was applied.

- **M1: applied, with higher figures.** The unit is now O-d (03 §1; 1 owner-week = 5 O-d), and §2.6 has a sum table. The draft's own rows summed to 39–68 O-d (7.75–13.5 weeks). After my check of the harness I raised three rows:
  - H1 is 8–12 O-d. The review's grep returns 24 files, including the 7.5k-line `harness-run-lib.sh`, two hooks and 9 instruction/agent files.
  - H2 is 4–6 O-d. The wrapper's verdict line is `pass`/`fail` only (`…_core.md:590-592`), so a third state touches the wrapper, G.1, the Done summary and the PR body.
  - H3 is 15–25 O-d. It is a security-design item. The workable seam is the `<gate_launcher>` binding. Its existing excluded launcher, `launch-sandboxed-gates.sh`, is 504 hardened lines, and `Monitor`/`sleep` are forbidden (`unit_loop_core.md:153`).
  - The total is **48–82 O-d, about 1.8–3.0× 03's v1 (≈ 27 O-d)**. That is higher than the review's suggested 40–70 because of the raised rows. The TL;DR, §3 and Q2 are updated to match.
- **M2: applied.** I verified it on the crates.io API: 0.8.0 on 2026-09-09; 0.10.0-alpha.1–3 published on 09-28, 10-05 and 10-14; `max_stable_version` 0.8.0.
- **S1: applied.** I verified it live. The page says "Rust, Kotlin or Swift code", Kotlin/Swift appear only under mobile, and `desktop.rs` is labelled "Desktop implementation". The tag is now [verified layout; exclusivity inferred], with the `swift-rs` caveat added.
- **S2: applied.** Verified: `unit_loop_core.md:143-144`, `test-fix-plan-writer.md:78`, `…_core.md:615, 740`. Note: under a `Park answer:` clause, `fixable: 0` leads to a re-run rather than an escalation (`:616`). That does not change the conclusion, because an unattended run still parks first.
- **S3: applied.** Verified: `layer-implementer.md:178`, `…_core.md:538`, `:590-592`. The file still keeps `qa-tester-mobile-mcp.md:20`, as a secondary citation.
- **S4: applied.** A′ (SwiftUI + Linux build via WSLg) and A″ (SwiftUI + Tauri/Electron) now have rows in the §2.4 and §3 tables, a short evaluation in §2.4, and costings in §2.6: A′ is ≈ 38–63 O-d and A″ ≈ 33–53 O-d. (B) still wins.
- **S5: applied.** The TL;DR, the §3 row and Q6 now say that release cost is the same in every shape, and per-PR cost is about 15× higher in (A)/(C) for private repos.
- **S6: applied.** Added a footnote to §2.4 and qualifiers to the TL;DR and §3. Verified: `remote-execution.md:28`, `:842`, `:978`.
- **S7: applied.** Verified: `settings.autonomous.json:21` (the `sandbox.allowedDomains` key and the exfiltration warning) and `check.ts:163, 597`.
- **N1: applied.** Verified live: both runners are listed as larger runners, and the page says they are "not free for public repositories".
- **N2: applied.** Verified live: the rules_dotnet README documents no WinUI 3, Windows App SDK or XAML support. Added as source [12].
- **N3: applied.** The schema ranges now read `184-216`, and the ROADMAP index rows (20, 23, 56) are added to the H6/H7 rows.
- **N4: partially applied.** I added a one-line "see 03 §2" pointer at the start of §2.1. I did not delete the repeated rows: they carry the line-level citations that 06 adds, and removing them would change the file's structure.
- **N5: applied.** Verified with a grep: there is no `CARGO_HOME`, `CARGO_TARGET_DIR` or `.cargo` handling in `cli/src` or `cli/templates`. Recorded as "not handled; untested".
- **N6: applied.** §2.2 now says H6 is not shipped or dated, so (A) pays the sequential cost until then. H6 is also marked as excluded from the sum.
