# 06 — Repository topology and how the DevScene harness would manage it
> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **Three shapes are compared.** (A) is a monorepo of 2–3 native apps (`apps/macos` SwiftUI, `apps/linux` GTK4/Qt, `apps/windows` WinUI 3, plus an optional contract package). (B) is one cross-platform project with small native overrides. (C) is a shared core (Rust/Go/Kotlin) with thin native UIs, in one monorepo. **For this app (B) wins on every axis that the harness can measure today.** (C) has all of (A)'s harness problems and adds a fourth toolchain. [inferred]
- **The config can express (A), but the gates can't verify it.** `harness.config.json` accepts one layer per platform, each with its own `path` and conventions document (`schemas/harness.config.schema.json:161-182`). Each layer can even name its own **single-file** test command, because that command lives in the layer's conventions document (`plugin/instructions/unit_loop_core.md:21`). The Run gates, though, use **one** `commands.typecheck` and **one** `commands.test` for the whole repo (`schemas/harness.config.schema.json:184-215`). Every unit also runs that whole-tree typecheck (`plugin/agents/layer-implementer.md:21`). So in (A), any run on one OS hits toolchains it can't run. [verified, local source]
- **What a harness run can verify in (A).** In a remote run (Linux only, `devscene/docs/remote-execution.md:795`) or a local run on Linux or Windows/WSL2, only `apps/linux` and the core build. In a local run on a Mac, `apps/macos` builds too, and GTK may build through Homebrew. **No run mode, local or remote, can build or test `apps/windows` (WinUI 3).** In (B), with Electron, Tauri, Compose or Avalonia, the whole tree typechecks and tests on a Linux runner (Tauri needs its WebKitGTK dev packages installed through `commands.depInstall`, §2.4). [verified + inferred]
- **Dispatch is one task, one layer, run one after another.** The task-plan writer splits a cross-layer capability into **one task per layer** with `Depends on:` links (`plugin/agents/task-plan-writer.md:104`). The unit loop runs the first unchecked entry and then the next (`unit_loop_core.md:56,70`). So "one feature = N platform tasks" happens on its own, but **sequentially**. Parallel per-layer waves are on the roadmap: ROADMAP #11 "Parallel dispatch in waves" and #8 "Contract-first task plans" (`ROADMAP.md:74,76`), status Open.
- **The parity machinery is the wrong shape for keeping platform apps in step.** `phases.parity` names **one** reference implementation (`schema:292-316`). Its reviewer checks *business logic*: external-call names, payload shapes, constants, predicates (`plugin/agents/business-parity-reviewer.md:3`). It was built for porting from a fixed reference, not for keeping sibling apps in step. You could point `referenceImplPath` at `apps/macos`. It would catch drift in `gh` arguments and JSON field names, but not missing UI features, and the reference is edited in the same branch it is checked against. [verified + inferred]
- **QA.** Only `web-playwright` works, and the mobile drivers are stubs (`schema:244-248`). In (B), a webview UI with a browser mode can be QA'd today (see 03). Native QA in (A) or (C) would need **three new drivers**: macOS Accessibility (AX), Linux AT-SPI and Windows UI Automation. Each must run on its own OS, which the harness can't do for Windows. [verified + inferred]
- **CI cost (verified live).** Standard GitHub-hosted runners are **free in public repos**. Private repos draw on a **dollar allowance**, not minutes: Free $12/mo, Pro/Team $18/mo. Per-minute rates are Linux $0.006, Windows $0.010 (≈1.7×) and macOS $0.062 (≈10×). A 3-OS PR build of about 10 minutes per OS costs about $0.77 in a private repo, so the Free allowance covers about 15 such PRs a month. **Release-build cost is the same in all three shapes**, because every shape has to build signed bundles on all three OSes. **Per-PR cost is about 15× higher in (A)/(C) for private repos** (≈ $0.77 vs ≈ $0.05), and zero for every shape in public repos.
- **To make (A) or (C) work well, the harness would need about 48–82 owner-days (O-d, 03's unit) of work, roughly 1.8–3.0× 03's entire cross-platform v1 (≈ 27 O-d)** [inferred; sum of §2.6 rows]: per-layer gate commands, layer OS affinity with a "deferred / unverifiable" gate state, sandbox-safe remote gate jobs on macOS/Windows runners, a sibling-parity reviewer, and three native QA drivers, plus wave fan-out (already planned). **(B) needs none of this.** It only needs the browser-mode QA requirement from 03. 03's WSLg variant (native Mac + the Linux build reused on Windows) drops the Windows items but still needs ≈ 38–63 O-d (§2.4, §2.6).
- **Recommendation: (B), one cross-platform project. Keep native overrides in the host language behind `process.platform` / `#[cfg]` / runtime OS checks, so they stay verifiable on Linux.** Put the contract types in a `contract/` folder generated from the harness's JSON Schema (05). Use one version number for all three platforms. Revisit (A) only for 03's two-codebase splits (A′/A″, §2.4), and only if the harness first gains per-layer gates and a macOS gate job.

## Scope

This file covers how the repo is laid out (A/B/C), the build, CI and release mechanics of each shape, and how well today's harness can drive each one, with the harness changes each would need. Framework choice, effort ratios and OS blockers are in 01–04. The JSON contract between the app and the harness is in 05.

## Findings

### 1. How hard each shape is

#### 1.1 Build orchestration

| Shape | Toolchains in one repo | Orchestrator options (status verified 2026-11-12) | Practical choice for a small app |
|---|---|---|---|
| **A** native ×3 | Xcode/SwiftPM, meson+GTK4 (or CMake+Qt), MSBuild/.NET + Windows App SDK | **Nx 24.0.6** (2026-11-10) has first-party `@nx/dotnet` and `@nx/gradle` plugins but **no first-party Swift/Xcode or meson plugin** (`@nx/swift` does not exist on npm) [verified]. **Turborepo 2.11.11** (2026-11-11) only runs `package.json` scripts, so every native build becomes an opaque script [verified]. **Bazel 9.3.2** (2026-11-05) covers Swift, Rust and plain .NET (rules_swift/rules_apple/rules_rust/rules_dotnet); WinUI/XAML and meson would need custom or foreign rules (rules_dotnet documents no WinUI 3 / Windows App SDK support [12]; meson via rules_foreign_cc), and it costs far too much setup for three small apps [verified version; fit inferred]. **moon 2.6.5** is similar to Turbo [verified]. | No orchestrator. Each app uses its own native tool, with a root `justfile`/`Makefile` and CI `paths:` filters. Each app must still be **built on its own OS**. [inferred] |
| **B** one cross-platform project | One (npm/pnpm; or Cargo+npm for Tauri; Gradle for Compose) | The framework's own CLI (`electron-builder`/`electron-forge`, `tauri build`, Gradle) | Native. No orchestrator needed. [inferred] |
| **C** core + thin native UIs | A's three, plus Cargo/Go/Gradle for the core, plus FFI glue (UniFFI 0.32.2, 2026-09-23 [verified], cgo, or Kotlin/Native) | As in A. A Cargo workspace covers only the core. | Worst of both: four toolchains plus FFI bindings. [inferred] |

#### 1.2 CI matrix and its cost

GitHub-hosted runner rates, per minute: Linux 2-core x64 **$0.006**, Linux arm64 $0.005, Windows 2-core **$0.010**, macOS 3/4-core **$0.062** [1] [verified]. (The macOS 12-core $0.077 and M2 Pro 5-core $0.102 runners are **larger runners**, which are not free in public repos and are not used in the maths below [1] [verified].) Jobs are rounded up to whole minutes. GitHub no longer publishes OS "multipliers". The allowance is now a **dollar amount**: Free $12, Pro $18, Team $18, Enterprise Cloud $300 a month. **Standard runners in public repos are free and don't use the allowance** [2] [verified]. Hosted prices fell by up to 39% on 2026-01-01. The planned $0.002/min fee for self-hosted runners was **postponed with no new date** [3] [verified].

| Per PR (private repo, illustrative) | A (3 apps) | B | C |
|---|---|---|---|
| Verify on every PR | mac 10 min + win 10 + linux 8 ≈ **$0.77** (paths filters help only when a PR touches one app) | Linux-only typecheck/test ≈ **$0.05**. A 3-OS packaging smoke test can wait for merge or release | As A, plus core tests ≈ $0.80 |
| Release (signed bundles on 3 OSes) | ≈ $0.8–1.5 | ≈ $0.8–1.5 (Electron, Tauri and Flutter still build each bundle on its own OS) | ≈ $1–2 |
| PRs per month that the **Free** $12 allowance covers | ≈ 15 | ≈ 200+ (Linux only) | ≈ 15 |

All figures [inferred] from [1][2]. **The conclusion: CI money only matters for a private repo with frequent PRs.** In a public repo it is zero for all three shapes. The real difference is that in (B) one Linux job is a *sufficient* gate, while in (A) and (C) every PR needs a Mac and a Windows job to say anything at all.

#### 1.3 Dependency and version alignment

- **A/C.** Three or four dependency ecosystems (SPM, meson wraps or distro GTK, NuGet, Cargo), three update bots and three security feeds. Version alignment exists only at the **contract** (the JSON shapes `devscene runs --json` returns; 05) and the app version. [inferred]
- **B.** One lockfile, plus a Cargo lockfile for Tauri. Overrides share it. [inferred]

#### 1.4 Shared contract types across languages

The source of truth should be the **JSON Schema the harness publishes** for `devscene runs … --json` (05). Codegen options:

| Tool | Status (verified 2026-11-12) | Targets relevant here |
|---|---|---|
| quicktype | v26.0.0, 2026-07-20, 13.9k★, active [4] | TypeScript, **Swift**, **C#**, Kotlin, Rust, Go, Dart, C++ and others, from JSON Schema input [4] |
| typify (oxide) | 0.8.0 stable on crates.io (2026-09-09); 0.10.0-alpha.1–3 also published on crates.io (latest 2026-10-14) [5] | Rust (serde) |
| json-schema-to-typescript | repo active (last push 2026-09-07) [6] | TypeScript |

In (A) or (C), codegen produces **three type sets that must be regenerated and committed together**. It still can't keep *behaviour* (polling, state mapping, badge rules) in sync. In (B), one generated TS or Rust module is enough. [inferred]

#### 1.5 Release versioning

- **Use one product version across all platforms** (`v1.4.0` tags all three bundles). This is recommended for every shape. The product site lists one product (Issue #1), and a per-platform version (macOS 1.6 / Windows 1.4) makes "is feature X on Windows yet?" a support question. Separately, record the **contract schema version** the app was built against (05). [inferred]
- **A.** One version means a release waits for the slowest platform, or ships "feature flagged off on Windows". Per-platform versions publicise the drift instead. Neither fixes it. [inferred]

#### 1.6 Keeping features in step (one feature = N tasks)

- **A/C.** Every user-visible feature becomes ≥3 UI tasks plus 0–1 core/contract tasks. Each needs its own review, test and QA. Drift is the default unless something enforces parity (§2.3). Every bug fix needs triage: "does this affect the other two?" [inferred]
- **B.** One feature becomes one UI task plus an occasional override. Drift can only happen inside overrides. [inferred]

#### 1.7 Where native overrides creep into (B) for this app

| Concern | Electron | Tauri 2 | Compose (JVM) | Flutter | Avalonia | Notes |
|---|---|---|---|---|---|---|
| Tray / menu bar | built in (`Tray`) | core tray feature | built in (`Tray`) | plugin with per-OS native code | built in (`TrayIcon`) | macOS template icons and Linux AppIndicator quirks (see 04) |
| Notifications | built in | `notification` plugin (Rust) | tray notification or JNA | plugin | community / per-OS | — |
| File watching | `fs.watch` / chokidar | `notify` crate | `WatchService` | `watch` | `FileSystemWatcher` | **On Windows, watching must run inside WSL, not on `\\wsl$`** (02, 04). That is a transport choice, not a native override. |
| PATH resolution (macOS GUI) | TS (`shell-env`-style login-shell probe) | Rust | Kotlin | Dart | C# | Same logic in every framework (04) |
| WSL bridging | TS branch on `process.platform === 'win32'` | Rust `#[cfg(windows)]` | runtime OS check | Dart `Platform.isWindows` | `OperatingSystem.IsWindows()` | Windows-only code path. It can be unit-tested on Linux with a mocked `wsl.exe` transport. [inferred] |
| Keychain | `safeStorage` | `keyring` crate | JNA / Java KeyStore | plugin | per-OS | **Probably not needed.** The app has no Claude credentials, and `gh` stores its own token. [inferred] |
| Autostart, single instance, deep link | built in or small modules | official plugins | per-OS | plugins | per-OS | — |

**What matters for the harness is which language the override is written in, not that it exists.**
- **Electron, Compose and Avalonia.** The overrides are runtime branches in the host language. They typecheck and unit-test on a Linux runner. [inferred]
- **Tauri.** Tauri's plugin bridge runs desktop code in Rust (`desktop.rs`, "Desktop implementation"). Its Swift/Kotlin bridge is documented only under mobile (iOS/Android) [7] [verified layout; exclusivity inferred]. Swift on macOS is still reachable via FFI crates (e.g. `swift-rs`), which compile Swift in a build script and therefore are not checkable from Linux. Keep overrides in pure Rust (`objc2`, `windows`): `#[cfg(target_os)]` modules can then be `cargo check --target …`-ed from Linux. Crates with C or Swift build scripts break this. [inferred]
- **Flutter platform channels.** These are written in Swift (macOS) and C++ (Linux/Windows runners), which brings back (A)'s problem on a small scale. [secondary]
- **Compose.** `expect`/`actual` splits by *target* (jvm, ios, android), **not by desktop OS**. Desktop is one JVM target, so OS differences are runtime checks. [inferred]

### 2. How the harness would manage each shape

#### 2.1 What `harness.config.json` can express

The headline harness facts (Linux-only remote runs, one preset per repo, layerless `monorepo`, QA stubs) are 03 §2's. This file adds the line-level citations, the per-unit and Phase G mechanics, and the H-list.

| Need | Expressible today? | Evidence |
|---|---|---|
| One layer per platform app, each with its own path scope and conventions document | **Yes.** `layers[]` items are `{name, path, conventions}`, `additionalProperties: false` | `schemas/harness.config.schema.json:161-182`; `docs/config.md:136-138` |
| Implementer kept inside its platform's path | **Yes.** It must stop if work falls outside `layers[].path` | `plugin/agents/layer-implementer.md:48` |
| Per-layer **single-file** test command (`swift test --filter …`, `dotnet test --filter …`) | **Yes, indirectly.** `<test_file_cmd>` is read from the dispatched layer's conventions document | `plugin/instructions/unit_loop_core.md:21` |
| Per-layer **typecheck** / full **test** commands | **No.** One `commands.typecheck` and one `commands.test` for the repo | `schema:184-216`; `docs/config.md:139-140` |
| Per-layer build / dev server / QA driver | **No.** `commands.build` and `devServer` are repo-wide; `qa.driver` is one enum | `schema:184-216, 244-248` |
| Layer → OS affinity ("this layer only builds on darwin") | **No.** No such key. `additionalProperties: false` rejects one | `schema:163` |
| Multi-app detection at `init` | **No.** `init` picks one preset. `monorepo` is deliberately "general"-only. Nested-app detection stays **silent on ≥2 apps** and never creates layers | `cli/src/detect/presets.ts:533, 769-774`; `cli/src/detect/nestedApplication.ts:6-13, 82` |
| GTK/meson preset | **No.** There is no meson/GTK detection anywhere in `cli/src` | `grep -ril 'meson\|gtk' cli/src` → none |
| Xcode tests | **Partly.** `commands.test` is left as a placeholder because `xcodebuild test` needs a machine-specific `-destination` | `presets.ts:1240-1253` |

**Workaround today for (A).** Hand-write the layers with `devscene config set layers '<json>'` (`docs/analyze.md:48`). Then put an OS-switching script in the `typecheck.sh`/`test.sh` wrappers, which hold any raw command line (`cli/src/generators/scripts.ts:17-22`). The script would run `swift build` only on darwin, `dotnet build` only on Windows, and so on. **This is a trap.** The skipped platforms then report **PASS** without having been built. That breaks the harness's own rule "never report a pass for a gate that was not run" (`plugin/agents/layer-implementer.md:178`; the same "silent success" refusal appears in `qa-tester-mobile-mcp.md:20`). Phase G's orchestrator "never read[s] their output: you read the one line the wrapper prints" (`plan_orchestration_instructions_core.md:538`), and that line is `pass` or `fail <log>` (`:590-592`). **Because only the wrapper's exit status reaches the orchestrator, no in-log warning can surface the skip.** The only honest wrapper behaviours are exit-non-zero (→ the park described in §2.2) or a new harness "deferred" state (H2). [verified + inferred]

#### 2.2 Per-platform task split and dispatch

- **Split. Yes, automatically.** Each readiness entry carries **exactly one** layer tag. A capability that spans layers is split into one task per layer, ordered bottom-up with `Depends on:` (`plugin/agents/task-plan-writer.md:104`). Tasks are capped at 20 points or 5 work bullets each (`:112`). No two tasks may edit the same file (`:126`). A feature such as "add Parked badge" in (A) becomes `contract` → `macos` → `linux` → `windows` (→ `general`). [verified]
- **Dispatch. Sequential only.** The unit loop picks "the **first `[ ]` entry**" (`unit_loop_core.md:70`) and runs one implementer, then the optional reviewer, then the committer, then moves on. Cross-layer finding fixes are also "dispatch sequentially in bottom-up order" (`plugin/instructions/plan_orchestration_instructions.md:42,48`). The only parallelism available is **across runs**: separate run copies and branches (`plan_orchestration_instructions_autonomous.md:108`). [verified]
- **Planned.** ROADMAP #11 "Parallel dispatch in waves" would dispatch "one implementer per layer" per wave. #8 "Contract-first task plans" defines the waves as baseline, then contracts, then implementations (`ROADMAP.md:74,76`). Both are Open. In (A), the three platform tasks of a feature depend only on the contract task, which makes (A) an ideal fit *once these land*. Neither is shipped or dated, so until then (A) pays the sequential cost. [verified]
- **Per-unit typecheck in (A).** Each unit runs the whole-tree `<typecheck_cmd>` (`layer-implementer.md:21,179`). On a Mac, a `windows`-layer unit can't typecheck its own code. Per the test-run rule, a missing-toolchain error (`dotnet: command not found`) names no unit file and no symbol the unit defined, so it is graded an **evidence downgrade** and the unit proceeds unverified (`unit_loop_core.md:143-144`; `layer-implementer.md:154`). Phase G then fails, `test-fix-plan-writer` files a missing tool under "Not fixable on this branch" (`test-fix-plan-writer.md:78`), it returns `fixable: 0`, and the run escalates (`plan_orchestration_instructions_core.md:615, 740`). **Every (A) run on one OS therefore parks at Run gates and never reaches "ready for review" unattended**, unless the wrapper hides the skipped toolchains, which is the trap in §2.1. [verified + inferred]

#### 2.3 Can the parity reviewer keep platforms in step?

- **What it is.** `phases.parity` takes one `referenceName`, one `referenceImplPath` (absolute or repo-relative) and optional `toolchainCommands`, which are reported as *deferred* when unavailable (`schema:292-316`). `business-parity-reviewer` runs at three points: the plan, the implemented diff and the user-review fix plan. It checks external-call names and payloads, serialized field names, thresholds, predicates and side-effect order (`business-parity-reviewer.md:3`). [verified]
- **Using `apps/macos` as the reference.** It would help with exactly the drift that hurts this app: `gh` arguments, JSON field names from `devscene runs --json`, status-to-badge mapping thresholds and polling intervals. [inferred]
- **Where it falls short:**
  1. It is built for porting toward a **fixed** reference, but in (A) the reference changes **in the same branch**.
  2. It checks business logic, **not feature presence or UI behaviour**, so "Linux has no answer form yet" is out of its scope.
  3. There is one reference, and no notion of "each sibling must match the layer the plan changed first".
  4. In a Linux remote run, the Swift reference can still be *read*, which is fine, but its `toolchainCommands` would be deferred.

  [inferred]
- **Verdict.** It is useful as a stopgap. A real fit needs a **sibling-parity mode**: the reference is a designated layer (or a feature spec in `contract/`), checked against each sibling layer's diff in the same branch.

#### 2.4 Run gates per run mode: what can actually be verified

Run gates run `run-test-suite.sh` once per round, executing the whole-tree typecheck and the full suite (`plugin/instructions/plan_orchestration_instructions_core.md:538`). Remote runs use `ubuntu-latest` by default, and "macOS and Windows GitHub-hosted runners" are **not supported** (`docs/remote-execution.md:791,795`). On Windows the harness runs only inside WSL2 (05).

| Layer \ run mode | Local, macOS host | Local, Linux host | Local, Windows (harness in WSL2) | Remote (GitHub Linux runner) |
|---|---|---|---|---|
| SwiftUI `apps/macos` | ✅ (sandbox caveat below) | ❌ (no SwiftUI/AppKit on Linux) | ❌ | ❌ |
| GTK4 `apps/linux` | ⚠️ via Homebrew GTK, not the target environment | ✅ | ✅ (inside the distro) | ✅ |
| WinUI 3 `apps/windows` | ❌ | ❌ | ❌ (`dotnet.exe` through WSL interop is theoretical, unsandboxed and over 9P) | ❌ |
| Core (Rust/Go/Kotlin) or TS contract | ✅ | ✅ | ✅ | ✅ |
| **(B)** Electron, Tauri, Compose or Avalonia (whole tree) | ✅ | ✅ | ✅ | ✅¹ |
| **A′** SwiftUI + Linux build reused on Windows via WSLg: whole tree | ⚠️ Swift ✅, GTK via Homebrew | ⚠️ Linux ✅, Swift ❌ | ⚠️ Linux ✅ (same distro the app runs in), Swift ❌ | ⚠️ Linux ✅, Swift ❌ |
| **A″** SwiftUI + Tauri/Electron for Linux and Windows: whole tree | ✅ | ⚠️ cross ✅, Swift ❌ | ⚠️ cross ✅, Swift ❌ | ⚠️ cross ✅, Swift ❌ |

[verified for the harness constraints; toolchain availability inferred]

¹ Tauri: the hosted `ubuntu-latest` job sets up only Node (`remote-execution.md:28`), and self-hosted runners must carry "whatever toolchain your own `commands.*` lines need" (`:842`). So `commands.depInstall`, which runs unsandboxed (`:978`), must apt-install the WebKitGTK dev packages (`libwebkit2gtk-4.1-dev` and relatives). Rust's `~/.cargo` writes under the strict sandbox are untested (Risks). Electron, Compose and Avalonia need nothing extra, which slightly favours Electron within (B) (see 03).

**03's WSLg variant (A′), evaluated briefly.** 03 §4 proposes shipping the Linux build inside WSL2 on Windows via WSLg (≈ 1.3–1.5× the cross-platform v1). For the harness this removes WinUI, the one layer no run mode can verify: the Linux app is verifiable in every run mode, remote included, and only the Swift layer needs a local Mac run. It still needs H1 and H2 (two toolchains under one gate, and Swift is unverifiable in Linux runs), the macOS half of H3, H5 (two siblings still drift), and two of the three H7 drivers (macOS AX and Linux AT-SPI; the Linux one can run inside WSLg). Cost ≈ 38–63 O-d of harness work (§2.6). If the Linux build is a webview app, the variant becomes A″ and the Linux QA driver drops too (≈ 33–53 O-d). Its product drawbacks are 03's: no signed Windows bundle, install inside a distro and a vGPU-driver dependency, which conflict with the Issue's distribution plan (03 §4, 04). **(B) still wins: it needs none of the H-items, and A′'s Mac-side gap is exactly (A)'s Swift gap.** [inferred]

**Sandbox caveat for Xcode in local macOS runs.** The unattended profile's sandbox `allowWrite` holds only the state directory (`cli/templates/claude/settings.autonomous.json:119`, plus the run copy and temp). The network allowlist starts empty (`:21`). `xcodebuild` writes to `~/Library/Developer/Xcode/DerivedData` by default, and SwiftPM fetches packages over the network. So the wrapper needs `-derivedDataPath` inside the run copy. What a sandboxed command may reach is `sandbox.allowedDomains` in `harness.config.json`, each entry with a reason (`settings.autonomous.json:21`; `cli/src/config/check.ts:163, 597`). An `allowedDomains` entry is possible, but the SwiftPM hosts are GitHub, which the template flags as an exfiltration path, so resolution in `depInstall`, which runs outside the session, is the safer route. [inferred — needs a measured check]

#### 2.5 QA for a native desktop app

Today `qa.driver` ∈ {`web-playwright` (implemented), `mobile-maestro`, `mobile-mcp` (stubs that return a blocker)} (`schema:244-248`; `qa-tester-mobile-mcp.md:12-20`). ROADMAP #44 "Mobile QA drivers" is Open, and **no desktop driver is planned** (`ROADMAP.md:130`).

A desktop-native driver needs the following [inferred]:

1. **Launch instead of serving.** A `commands.launchApp` (or a per-layer equivalent) that builds and starts the app binary and returns a PID. Today's QA phase assumes `devServer` and a `base_url`.
2. **An inspection and automation backend per OS:**
   - macOS: the Accessibility API (AXUIElement) through an MCP server, or computer use.
   - Linux: AT-SPI (dogtail- or pyatspi-style).
   - Windows: UI Automation (FlaUI-style).
3. **A locator convention.** Accessibility identifiers (`accessibilityIdentifier`, `AutomationId`, GTK accessible names) take the place of the `data-testid` the ui-tests-plan-reviewer checks today.
4. **A host on the matching OS.** For Windows this means a Windows machine the harness can't run on (§2.4).
5. **A new agent variant per driver**, following the mobile stub pattern, with a tool closure that grants only that driver's MCP tools.

Size: roughly the current `qa-tester.md` plus scripts, **×3**. **In (B) with a webview, the browser-mode route from 03 avoids all of this.**

#### 2.6 What the harness would need for (A) or (C)

| # | Change | Why | Rough size [inferred] | Already on ROADMAP? |
|---|---|---|---|---|
| H1 | **Per-layer gate commands**: `layers[].commands.{typecheck,test}`; per-unit typecheck scoped to the dispatched layer; Run gates run each layer's gates in their own log section | Removes the single repo-wide gate | M: 24 harness files read the gate commands today (`grep -rl 'typecheck_cmd\|commands.typecheck\|test_cmd' plugin cli/src cli/templates schemas`): schema, `config/model.ts`/`check.ts`, `init`/`config` commands, `detect/presets.ts`, two generators, the `typecheck.sh`/`run-test-suite.sh` templates and the 7.5k-line `harness-run-lib.sh`, two hooks (`allow-safe-compounds.sh`, `harness-config-lib.sh`), `doctor/checks.ts` and 9 instruction/agent files, plus tests. **8–12 O-d** (was 1–2 weeks) | No |
| H2 | **Layer OS affinity + a "deferred" gate state** (`layers[].hosts: ["darwin"]`), modelled on `parity.toolchainCommands`' deferred reporting | A Linux run reports `apps/macos` as *not verified here* instead of PASS or FAIL. The PR or branch summary says so | S–M: the wrapper's verdict line is `pass`/`fail` only (`…_core.md:590-592`), so a third state touches the wrapper, G.1's parsing, the Done summary and the PR body. **4–6 O-d** (was 0.5–1 week) | No |
| H3 | **Remote gate jobs on OS-targeted runners**: the Linux run job dispatches a `workflow_dispatch` "gates-only" job on `macos-latest` / `windows-latest` for the affected layers and reads the verdict back | The only way WinUI is ever verified inside a run. Much cheaper than porting the whole run (`remote-run.sh` is Linux-shaped) to macOS or Windows | L, and a **security-design item, not just plumbing**: the sandboxed session's network allowlist is empty and the template warns a broad GitHub domain "is an exfiltration path" (`settings.autonomous.json:21`), and `Monitor`/`sleep` are forbidden while waiting on a gate (`unit_loop_core.md:153`). The workable seam is the `<gate_launcher>` binding, whose existing launcher (`launch-sandboxed-gates.sh`, 504 lines) is an excluded, hardened main-checkout script; a cross-OS dispatcher would follow that pattern and run branch code on hosted Macs/Windows. **15–25 O-d** (was 2–3 weeks; roughly 60% is the shared plumbing a macOS-only half still needs). Costs about $0.62 per 10 macOS minutes in private repos | No. ROADMAP "Cloud / CI execution" covers Linux execution only (`ROADMAP.md:125`) |
| H4 | **A macOS remote runner for whole runs** | Would let a remote run implement *and* verify Swift | L: bootstrap, Seatbelt sandbox on a hosted Mac, 10× minute rate. H3 makes it mostly unnecessary | No |
| H5 | **Sibling-parity reviewer** (§2.3) | Feature drift is the main recurring cost of (A) | M: one new agent definition plus three insertion points. **4–6 O-d** | No. The existing parity is single-reference |
| H6 | **Layer fan-out (parallel waves)** | N platform tasks run in parallel | Already designed, not shipped or dated; excluded from the sum | **Yes, #11 and #8 (Open)** (`ROADMAP.md:74,76`; index rows 20, 23) |
| H7 | **Native desktop QA drivers ×3** (§2.5) | QA phase for native UIs | L: roughly today's `qa-tester.md` (226 lines) plus scripts ×3, and Windows needs H3-like hosting. **15–30 O-d** (5–10 per driver) | No (#44 is mobile only; `ROADMAP.md:130`, index row 56) |
| H8 | **Multi-app `init`** (layer per `apps/*`, meson/GTK preset, Xcode `-destination` prompt) | Smoother adoption | S: hand-editing works today. **2–3 O-d** | No |

**Unit.** Owner-days (O-d) as in 03 §1: owner review, steering and verification time, with agent wall-clock time treated as free. One owner-week = 5 O-d.

**Total for (A) to be well supported** (H1 + H2 + H3 + H5 + H7 + H8; H4 and the planned H6 excluded):

| | H1 | H2 | H3 | H5 | H7 | H8 | **Sum** |
|---|---|---|---|---|---|---|---|
| Low | 8 | 4 | 15 | 4 | 15 | 2 | **48 O-d** |
| High | 12 | 6 | 25 | 6 | 30 | 3 | **82 O-d** |

That is **≈ 48–82 O-d (≈ 10–16 owner-weeks), about 1.8–3.0× 03's entire cross-platform v1 (≈ 27 O-d)**. The draft's rows as first written summed to 39–68 O-d (7.75–13.5 weeks), not the 6–10 weeks it stated. H1 and H2 are raised after counting the files they touch, and H3 because it needs a sandbox-safe way to dispatch and await a cross-OS job. The Windows layer stays verifiable only through CI jobs, never by the session that wrote the code. **(B) needs none of H1–H8.** (C) needs the same as (A). Its core layer is verifiable, but the UIs aren't. [inferred]

**For 03's two-codebase variants** (§2.4): A′ (SwiftUI + Linux build via WSLg) needs H1 8–12, H2 4–6, the macOS half of H3 ≈ 10–16, H5 4–6, two H7 drivers 10–20 and H8 2–3: **≈ 38–63 O-d**. A″ (SwiftUI + Tauri/Electron) needs the same with one H7 driver (5–10): **≈ 33–53 O-d**. [inferred]

### 3. Comparison

| Shape | Build complexity | CI cost (private repo; public = $0) | Harness fit today | Harness changes needed | Feature-sync risk | Agent dispatch model |
|---|---|---|---|---|---|---|
| **A** monorepo, 3 native apps | High: 3 native toolchains, each built only on its own OS | High per PR (~$0.77, needs mac+win on every PR) | **Poor.** Layers expressible; gates single and repo-wide; WinUI unverifiable in every run mode; Swift only in local Mac runs; no QA | H1, H2, H3, H5, H7, H8 (≈ 48–82 O-d); H6 planned | **High.** Every feature ×3, drift by default | 1 feature → ≥3 sequential layer tasks; parallel only after ROADMAP #11 |
| **B** one cross-platform project + overrides | Low: one toolchain (+Cargo for Tauri) | Low per PR (Linux-only gate ~$0.05, ≈ 15× less than A); 3-OS cost only at release | **Good.** Whole tree builds and tests on Linux (Tauri: WebKitGTK via `depInstall`, §2.4); webview QA works with a browser mode (03); Flutter platform-channel code is the exception | None required. Optional H2 for Flutter/Swift-channel code | **Low.** Drift only inside small overrides | 1 feature → 1–2 tasks (ui, maybe a Rust/main-process layer) |
| **C** shared core + thin native UIs | Highest: 4 toolchains + FFI | As A, + core | **Poor.** Core layer verifiable everywhere; UIs as in A | As A | Medium-high. Logic shared, UI ×3 | 1 feature → core task + ≥3 UI tasks, sequential |
| **A′** SwiftUI + Linux build reused on Windows via WSLg (03 §4) | Medium: 2 native toolchains | Mac + Linux per PR (≈ $0.67) | **Fair-poor.** Linux app verifiable in every run mode; Swift only in local Mac runs; no QA | H1, H2, macOS half of H3, H5, 2 of 3 H7 drivers, H8 (≈ 38–63 O-d) | Medium-high. Every feature ×2 | 1 feature → ≥2 sequential layer tasks |
| **A″** SwiftUI + Tauri/Electron for Linux/Windows | Medium: 2 toolchains | As A′ | **Fair-poor.** Cross build verifiable everywhere; Swift as in A′ | As A′ with 1 H7 driver (≈ 33–53 O-d) | Medium-high. Every feature ×2 | As A′ |

**Recommendation.** Choose **(B)**. Make the overrides runtime or `cfg` branches in the host language, not separate native modules. With Tauri, keep them in Rust. With Electron, keep them in TS. Avoid Flutter if native platform-channel code would be needed. Lay out the repo as `app/` (UI), `app/src-tauri` or `app/main` (platform layer), and `contract/` (types generated from the harness's JSON Schema), each as a harness layer with its own conventions document, plus the `general` catch-all. Use one version for all platforms. Run Linux typecheck and tests on every PR, and the 3-OS build, sign and smoke test on release tags.

## Answers to the owner's questions

- **Q2 (cross-platform vs N native).** Topology adds a cost that 03's effort model only touches on: **in (A), the harness can't close the loop on two of three apps.** Any agent-written Windows code reaches a human or CI unverified. Fixing that means about 48–82 O-d of harness work first, 1.8–3.0× 03's whole cross-platform v1 (≈ 27 O-d); even 03's WSLg variant (A′) needs ≈ 38–63 O-d. This strengthens 03's "don't go fully native". [inferred]
- **Q5 (native blockers in a cross-platform choice).** The overrides this app needs (tray, notifications, PATH probe, WSL transport, file watching inside WSL) are all available in the host language for Electron, Tauri, Compose and Avalonia. None forces a separate native project. Flutter is the exception. Keychain is probably unnecessary. [inferred]
- **Q6 (costs).** CI is free for public repos. For private ones, macOS minutes are the cost driver at about 10× Linux, so (A) and (C) pay it on every PR (≈ 15× (B)'s per-PR cost), while (B) pays it mainly at release. Release-build cost is the same for every shape [1][2].

## Risks and open questions

- **Sandbox vs native toolchains (untested).** Xcode DerivedData, the NuGet/SPM caches and network fetches under the strict profile (§2.4) need a measured check before (A) is ever tried. Tauri's `cargo` cache (`~/.cargo`) has the same question in (B). Checked: `cli/src` and `cli/templates` have no `CARGO_HOME`/`CARGO_TARGET_DIR` handling and no sandbox carve-out for `~/.cargo`, so it is **not handled; untested**.
- **The `cargo check --target` cross-check for Tauri overrides is unmeasured.** Crates with C build scripts would break it.
- **If the harness ships per-layer gates (H1) and remote gate jobs (H3) for other reasons** (for example mobile adopters), (A) becomes cheaper. Re-evaluate then.
- **ROADMAP #11 and #8 timing** decides whether "one feature = N tasks" runs in parallel or serially.
- **Parity on the Mac reference** (§2.3) is speculative. No adopter has used `phases.parity` with an in-repo, same-branch reference.

## Sources

1. https://docs.github.com/en/billing/reference/actions-runner-pricing — per-minute runner rates (Linux $0.006, Windows $0.010, macOS $0.062 standard; $0.077/$0.102 larger runners, "not free for public repositories"), rounding up to whole minutes — accessed 2026-11-12 [verified]
2. https://docs.github.com/en/billing/concepts/product-billing/github-actions — dollar allowances (Free $12, Pro/Team $18, Enterprise $300); standard runners free in public repos — accessed 2026-11-12 [verified]
3. https://github.com/resources/insights/2026-pricing-changes-for-github-actions — hosted price cut of up to 39% on 2026-01-01; self-hosted $0.002/min fee postponed (update of 2025-12-15), no new date — accessed 2026-11-12 [verified]
4. https://github.com/glideapps/quicktype — v26.0.0 (2026-07-20), target-language list including Swift, C#, Kotlin, Rust, TS — accessed 2026-11-12 [verified]
5. https://crates.io/crates/typify (API: https://crates.io/api/v1/crates/typify) and https://github.com/oxidecomputer/typify — 0.8.0 stable (2026-09-09), 0.10.0-alpha.1–3 published on crates.io (latest 2026-10-14) — accessed 2026-11-12 [verified]
6. https://github.com/bcherny/json-schema-to-typescript — active, last push 2026-09-07 — accessed 2026-11-12 [verified]
7. https://v2.tauri.app/develop/plugins/ — plugins handle commands "with Rust, Kotlin or Swift code"; Kotlin/Swift appear only under Mobile Plugin Development; `desktop.rs` labelled "Desktop implementation" — accessed 2026-11-12 [verified]
8. https://github.com/nrwl/nx (24.0.6, 2026-11-10); npm `@nx/dotnet` and `@nx/gradle` 24.0.6; `@nx/swift` not found — tool status — accessed 2026-11-12 [verified]
9. https://github.com/vercel/turborepo (v2.11.11, 2026-11-11), https://github.com/bazelbuild/bazel (9.3.2, 2026-11-05), https://github.com/moonrepo/moon (v2.6.5, 2026-10-29) — tool status — accessed 2026-11-12 [verified]
10. https://crates.io/crates/uniffi — 0.32.2 (2026-09-23), FFI option for shape C — accessed 2026-11-12 [verified]
11. Harness, local at `/Users/daniel/Work/devscene`: `schemas/harness.config.schema.json`, `docs/config.md`, `docs/analyze.md`, `docs/remote-execution.md`, `ROADMAP.md`, `cli/src/detect/{presets,signals,nestedApplication}.ts`, `cli/src/generators/scripts.ts`, `cli/templates/claude/settings.autonomous.json`, `cli/templates/scripts/launch-sandboxed-gates.sh`, `cli/src/config/check.ts`, `plugin/agents/{task-plan-writer,layer-implementer,business-parity-reviewer,qa-tester-mobile-mcp,test-fix-plan-writer}.md`, `plugin/instructions/{unit_loop_core,plan_orchestration_instructions,plan_orchestration_instructions_core,plan_orchestration_instructions_autonomous}.md` — line references inline — read 2026-11-12 at commit `a1d0e992` [verified]
12. https://github.com/bazel-contrib/rules_dotnet — README describes an alternative to MSBuild; no WinUI 3 / Windows App SDK / XAML support documented — accessed 2026-11-12 [verified]
