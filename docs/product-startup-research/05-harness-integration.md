# 05 — Integrating with the DevScene harness: code reuse vs CLI contract, and its effect on the framework choice

> Status: reviewed · Date: 2026-11-12 · Area owner: research agent

## TL;DR

- **The premise "Electron can reuse the `devscene` CLI code directly" (Issue #1, item 1) mostly does not hold.** The TypeScript CLI (`cli/src`, 34,347 lines) covers `init`, `doctor`, `config`, `daemon` and `docs`. The logic the app needs for runs lives elsewhere. Reading `registry.json`, pause/resume markers, the inbox drop, park answers, deterministic branch derivation (`hr_derive_branch`), and GitHub dispatch/status/sync are all in **about 22,500 lines of bash** rendered into each adopting repo: `harness-run-lib.sh` 7,522, `remote-run.sh` 8,264, `autonomous-watcher.sh` 6,671. The rest is about 445 lines of plugin prompt prose that Claude interprets. **None of the run read/act logic can be imported from TypeScript.** [verified, local source]
- **The CLI is not published as a library.** `package.json` has a `bin` and no `main` or `exports`. Its internals are clean, though. Nothing calls `process.exit()`, all output goes through an injectable `Reporter`, and `doctor` already computes `runChecks(ctx) → CheckResult[]`. A deep import of `dist/doctor/checks.js` would work technically. It would also pull in about 20k lines of `detect/` and `generators/`, run synchronous `spawnSync` probes, and depend on a module layout with no compatibility promise. [verified]
- **The run logic is installed per repo, so its version is per repo.** The scripts are rendered into `<scriptsDir>` by whichever `devscene init` version last ran in that repo. `registry.json` has **no schema version field**. The only version stamp in a repo is the `DEVSCENE_CLI_VERSION` pin in the GitHub workflows, and only remote-enabled repos have it. [verified]
- **On Windows, the harness only runs inside WSL2.** The run scripts are bash + jq and the daemon backends are launchd/systemd only (`daemon/backend.ts`). `docs/cli.md` §6 additionally makes native Windows unsupported for sandboxing, and the product brief fixes Windows to WSL2. Any code that probes the host or runs scripts (doctor, daemon status, inbox-drop guard, `remote-run.sh`) has to execute in the WSL distro. An in-process library inside a Windows Electron main process would probe the wrong OS. Also, `\\wsl$` (9P) does not deliver file-change notifications to Windows watchers, so a Windows-side app cannot reliably watch run files. [verified for harness; secondary for 9P, see [6]]
- **Recommendation: shape (b), a versioned `devscene runs … --json` contract that every app build calls through one process transport.** The transport is a direct spawn on macOS/Linux and `wsl.exe` on Windows. Add a small app-side, read-only GitHub read-model through `gh` for users with no local setup. That is shape (d), limited to GitHub-side state that the harness already treats as a contract: the `harness run <branch>` run titles, the `devscene: <state>` labels, and `status.json` in the `harness-state` artifact, which is bundle schema `1`.
- **Do not bundle a CLI sidecar (c).** It is useless on Windows, because the Linux CLI inside WSL is what has to run. It is redundant on macOS/Linux, because every harness user already has Node ≥ 20.11 for `npx devscene init`. It would add 57–93 MB per platform, plus signing work, to ship a CLI whose version would then disagree with the repo's rendered scripts.
- **Effect on the framework ranking:** once the integration point is a JSON-over-process contract, Electron's "direct reuse" advantage drops from "reuse the harness" to "the same language as the harness, and TS types for the contract". Any stack can generate those types from a JSON Schema. **Tauri no longer needs a Node sidecar.** Flutter, Wails and the others are on equal footing for integration. The framework decision should rest on the other areas (UI, distribution, career value, WSL process driving).
- **What the harness must add (Issue item 7):** `devscene runs list|show|watch|pause|resume|answer|drop|derive-branch --json`, `devscene doctor --json`, `devscene capabilities --json`, a `schema` field in `registry.json`, and a repo-scripts version stamp. Rough size: the read side (`capabilities`, `runs list/show`, `doctor --json`, `repos --json`) is ~1–1.5k lines; the act side plus `runs watch` is several thousand lines including tests and should be sized in the harness repo. Ship it in phases (read-only first, see §5). [inferred]

## Scope

This file covers how the app gets run state and acts on runs, the four integration shapes, version skew, and how all of that moves the framework ranking. It defers to other areas for:

- the general framework comparison;
- WSL process and file mechanics in depth (see the WSL area);
- signing and notarization cost (see the distribution area);
- the full GitHub read-model design (Issue item 5).

## Findings

### 1. What the harness CLI is, and where the run logic actually lives

| Concern the app needs | Where it lives today | Language | Importable from TS? | Lines (approx.) |
|---|---|---|---|---|
| Entry and dispatch | `cli/src/cli.ts`, `commands/registry.ts` | TS | n/a. It sets `process.exitCode` and never calls `process.exit()` | 332 |
| `doctor` (checks → structured results) | `doctor/checks.ts` (`runChecks`, `CheckResult`), `commands/doctor.ts`, `doctor/branchProtection.ts`, `doctor/sandboxPrerequisites.ts`, `doctor/keepAwake.ts` | TS | Deep import only. Imports `detect/*`, `generators/*` and `retrieval/*`, and uses synchronous `spawnSync` | ~7,900 own + ~20k transitive |
| Machine repo registry `repos.json` (installed daemons, used for the repo dropdown) | `machine/registry.ts`, `machine/paths.ts` | TS | Deep import, fairly pure | ~540 |
| Daemon install/status (launchd/systemd) | `daemon/backend.ts`, `daemon/units.ts`, `commands/daemon.ts` | TS | Deep import, spawns `launchctl`/`systemctl` | ~1,670 |
| Config read/validate (`harness.config.json`) | `config/io.ts`, `model.ts`, `check.ts` | TS | Deep import | ~1,990 |
| GitHub names: workflow files, labels, `RUN_STATES`, artifact name, `@dev-scene` verbs | `remote/githubActions.ts` | TS | Constants, trivially reusable | ~340 |
| **Run registry `registry.json`**: reads, writes and locking (`hr_registry_*`) | `templates/scripts/lib/harness-run-lib.sh` | bash + jq | **No** | part of 7,522 |
| **Statuses and fields** (`running`, `paused`, `parked`, `park_loop`, `failed`, `completed`; `pause_reason`, `paused_by`, `engine`, `worktree`, `started_at`, `resumed_at`, `park_loop_cycles`, …) | written by `autonomous-watcher.sh` and `remote-run.sh` | bash | **No** | 6,671 + 8,264 |
| **Pause/resume markers** (`PAUSE`, `RESUME`, `PAUSE_ACK`, `PAUSE_PROGRESS.md`, `PARK_LOOP_CLEAR`, global `AUTONOMOUS_STOP`) | protocol in `plugin/instructions/autonomous_pause_and_ledger.md`, watcher half in `autonomous-watcher.sh` (`docs/watcher.md` §4) | prose + bash | **No** | — |
| **Inbox drop and collision guard** (`<branch>_task_prompt.md`, guard = registry + live run copy + queued inbox file, restating `hr_run_copy_live_var`) | `plugin/commands/branch-prompt.md` (Claude follows it), plus the shell helper | prose + bash | **No** | 40 + helper |
| **Deterministic branch name** from a title (ASCII-only slug under `LC_ALL=C`, so non-ASCII such as `é` becomes a separator; 60-char cap, `_2`…`_99` suffix, `issue_<n>` fallback) | `hr_derive_branch` in `harness-run-lib.sh` (`docs/github-issue-trigger.md` §2) | bash | **No** | small |
| **Remote verbs**: `dispatch`, `pause`, `stop`, `status`, `sync`, `list`, `start`, `review`, … with a documented exit map | `templates/scripts/remote-run.sh` | bash | **No**. It is already a CLI, but its output is for humans, not JSON | 8,264 |
| Answer a park, pause, resume, status digest | `plugin/commands/branch-{answer,pause,resume,status}.md` | prose for Claude | **No** | ~360 |

Sources: `/Users/daniel/Work/devscene/cli/package.json`, `cli/src/**`, `cli/templates/scripts/**`, `plugin/commands/*.md`, `docs/watcher.md` §4 and §7, `docs/github-issue-trigger.md` §2, `docs/github-run-control.md` §5. Line counts come from `wc -l` on 2026-11-12. [verified]

**Library-readiness verdict.** The TS code is well structured for a future library: commands receive a `CommandContext` and never read `process.argv` or `cwd`, and the `Reporter` sinks are injectable. But the TS CLI is the **setup and diagnostics** half of the harness. The **run** half is bash that the app could only call as a process anyway. Even a Node-based shell would end up running `bash <scriptsDir>/remote-run.sh status <branch>` and parsing human text, or writing marker files by reimplementing the prose protocols. [verified + inferred]

**Does it depend on the harness being installed in the repo?** Yes, for everything about runs:

- the scripts are in the repo's `scriptsDir`;
- the registry and inbox are under the main checkout's `<stateDir>/autonomous_logs/` and `autonomous_inbox/`;
- markers live in each run copy's `<stateDir>`;
- `stateDir` and `scriptsDir` come from the repo's `harness.config.json`.

Only `repos.json` (machine-wide, under `$XDG_STATE_HOME/devscene/`) and the GitHub-side state are readable without a repo checkout. [verified]

### 2. The four integration shapes

| | (a) Embed the CLI as a library | (b) Shell out to `devscene … --json` | (c) Bundle a compiled CLI sidecar | (d) Reimplement the read-model in the app |
|---|---|---|---|---|
| Possible in | Electron, Electrobun (Bun), Tauri + Node sidecar | any framework | any framework | any framework |
| Covers run read/act logic? | **No.** That logic is bash in the repo, so (a) degrades to (b) for runs | Yes, once item 7 is built | Yes, if the sidecar is the CLI with item 7 | Yes, by copying it |
| Covers doctor/daemon/config? | Yes, via unsupported deep imports | Yes (`doctor --json` is ~40 lines to add, since `runChecks` exists) | Yes | Only by copying 8k+ lines (bad) |
| Windows (harness in WSL2) | **Broken in-process.** The Windows Node process would probe Windows, not the distro. It would still have to call `wsl.exe` | `wsl.exe -d <distro> --cd <repo> -- devscene runs … --json` | **Useless.** A Windows `.exe` sidecar cannot be the harness; the Linux CLI inside WSL is what has to run | Reads `\\wsl$\…` over 9P (slow, no change notifications) and still needs `wsl.exe` for git/scripts |
| Version skew | App pins one CLI version at build time; the repo's rendered scripts may be older or newer | Explicit: the contract carries `contract`, `cli` and `repoScripts` versions; the app negotiates | Same as (a), plus it disagrees with the user's `npx devscene` | Worst: silent drift against bash it does not run |
| Drift risk vs the plugin | Low for TS parts, n/a for bash | **Lowest.** The harness owns both the contract and its implementation | Low | **High.** It mirrors ~22k lines of bash semantics (the registry, `park_loop` rules, the `unfinished` pause, stale-sync rules) |
| Extra bundle size | 0 in Electron (Node is built in) | 0 | Node SEA ~93 MB, Bun ~57 MB, Deno ~72 MB per target ([4]) | 0 |
| Effort for the app | Medium, plus a fragile coupling | Small transport layer | Medium: a build matrix plus signing every nested binary | Large, and ongoing |

#### (b) details: transport and version skew

- **Transport.**
  - **GUI apps do not inherit the shell `PATH`.** An app launched from Finder, the Dock or a desktop launcher gets a minimal `PATH` (on macOS, launchd gives `/usr/bin:/bin:/usr/sbin:/sbin`), so `devscene`, `node`, `gh` and `git` from Homebrew, nvm, volta or fnm are often not found ([9]). Inside WSL, `bash -lc` does not fix this either: the nvm installer appends its init to `~/.bashrc` ([10]), and Ubuntu's default `~/.bashrc` returns early for non-interactive shells, so a login-only shell skips the nvm lines. [secondary]
  - macOS/Linux: resolve the CLI once by asking the user's login, interactive shell (`$SHELL -ilc 'command -v devscene; command -v node'`, the technique used by `fix-path`/`shell-env`). Cache the absolute paths, let the user override them in settings, and spawn by absolute path.
  - Windows: resolve the same way inside the distro (`wsl.exe -d <distro> -- bash -ilc 'command -v devscene; command -v node'`). Then call `wsl.exe -d <distro> --cd <linux-repo-path> --exec <abs-path-to-node> <abs-path-to-devscene> runs … --json`, so steady-state calls do not depend on shell init files. [inferred]
  - The app's own doctor-style diagnostics report which paths were found.
  - `npx -y devscene@<min> …` as a fallback hits the network and runs a CLI version different from the user's install. Make it opt-in, never silent.
  - Treat stdout as UTF-8 JSON and stderr as diagnostics. The CLI's exit-code contract (0 / 1 refusal / 2 internal, `docs/cli.md` §1) already exists and carries over. [verified]
- **Avoid polling through `wsl.exe` and avoid watching `\\wsl$`.** Windows change notifications do not work over WSL's 9P share ([6]; [7] only shows that the share is 9P). Each `wsl.exe` spawn also costs a VM round trip (cost unmeasured; measure it in the WSL area). A long-lived `devscene runs watch --json` that streams NDJSON events from *inside* the distro, using inotify on native ext4, solves both problems on every OS. It has its own failure modes (orphaned Linux-side processes, WSL VM idle shutdown, reconnects), so `watch` must emit a full `snapshot` event first and after any resync, send heartbeats, and exit when stdin closes; see Risks. [secondary + inferred]
- **Where the version skew comes from.** There are three parties:
  1. the app;
  2. the `devscene` CLI found on `PATH` or via `npx`, which is global per machine or per WSL distro;
  3. the scripts rendered into each repo by the last `init`.

  The contract must report all three and gate features on capabilities, not on semver comparisons:
  - `devscene capabilities --json` returns `{contract: "1.2", cli: "0.7.0", verbs: [...], repo: {scripts: "0.6.12", registrySchema: 1}}`;
  - the app requires a `contract` major it knows, and hides actions whose verb or capability is absent;
  - it shows "Upgrade harness in this repo: `npx devscene@latest init`" when `repo.scripts` is below the minimum.

  This mirrors the harness's own rule for `repos.json`: an unknown `schema` makes a reader decline the file rather than half-understand it (`machine/registry.ts`). [verified pattern; inferred application]

#### (c) details: bundling a runtime or compiled CLI

| Tool | Status (verified 2026-11-12) | Cross-targets | Typical size | Signing |
|---|---|---|---|---|
| Node SEA (`node --build-sea`, Node ≥ 25.5) | Stability **1.1, Active development**. Docs are for v26.13.1. ESM entry is supported (`mainFormat: "module"`, not together with snapshots) ([1]) | Cross-builds are possible only with `useCodeCache`/`useSnapshot` off ([1]) | ~93 MB (Node 25.6, Feb 2026, [4]) | macOS signing is a listed step not marked optional (ad-hoc `codesign --sign -` at minimum; notarization for distribution); Windows `signtool` is explicitly optional ([1]) |
| `bun build --compile` | Stable feature. Targets `bun-{linux,darwin,windows}-{x64,arm64}` plus `linux-*-musl` ([2]) | Yes, from any host. When cross-compiling for Windows only `hideConsole` works; icon, title, publisher, version, description and copyright do not ([2]) | ~57 MB (Bun 1.3.8, [4]). Bun's docs admit "still way too big" ([2]) | `codesign` on macOS with a five-key entitlements plist (`allow-jit`, `allow-unsigned-executable-memory`, …); codesign support needs Bun ≥ 1.2.4 ([2]) |
| `deno compile` | Stable. Uses the stripped `denort` runtime ([3]) | "all targets regardless of the host platform": x64/arm64 for Windows, macOS and Linux-gnu; Windows ARM64 only from Deno 2.9.3 ([3]) | ~72 MB (Deno 2.6.8, hello-world, [4]). It embeds `node_modules` by default; `--bundle` (experimental) and `--exclude-unused-npm` shrink it ([3]) | Ad-hoc signed on macOS by default. Use your own identity plus notarization ([3]) |
| Electron's own Node (`ELECTRON_RUN_AS_NODE`) | Ships with Electron | n/a | 0 extra | Covered by the app's signature |

Why (c) is not worth it here:

1. On Windows, the sidecar would have to be a **Linux** binary copied into or invoked inside WSL, with `wsl.exe` running a file from `/mnt/c/...`. At that point it is just the CLI in WSL with extra steps, and its version still differs from the repo's scripts.
2. On macOS/Linux, the harness's own install path (`npx devscene init`, Node ≥ 20.11) guarantees Node is already present.
3. Every nested executable needs its own signing and notarization pass (see the distribution area). Tauri's sidecar mechanism also needs per-target-triple binaries ([5]).

[verified facts; inferred conclusion]

#### (d) details: an app-side read-model

This shape is unavoidable in part. Users "whose repo someone else set up" have no local harness (Issue #1, *Data source*), so the app must read GitHub directly:

- `gh run list` filtered on titles `harness run <branch>`;
- the six `devscene: <state>` labels (`RUN_STATES` in `remote/githubActions.ts`);
- the progress comment;
- the `harness-state` artifact's `status.json` (bundle schema `1`, `docs/remote-execution.md` §4);
- pull-request merge state.

These are **GitHub-facing contracts the harness already versions and documents**, so mirroring them is acceptable. Keep the mirror to reads. Do **not** reimplement local-registry semantics or any write: no marker files, no inbox drops, no dispatch inputs. `remote-run.sh` is described as "the one place a `gh workflow run` of the run workflow is composed", and a second producer of its input contract would break that rule. [verified]

### 3. How this changes the framework ranking

| Claimed Electron advantage | After this analysis |
|---|---|
| "Reuse the `devscene` CLI code directly" | The run read/act logic is ~22.5k lines of bash plus ~0.4k of prompt prose, and **0 lines of it can be imported from TS**. The importable TS that is actually useful is doctor (~7.9k own), the `repos.json` registry (~0.5k), daemon (~1.7k), config (~2k) and GitHub constants (~0.3k). Each sits behind a natural CLI boundary (`doctor`, `daemon list`, `config`) that becomes `--json` with small changes. On Windows, all of it must run in WSL anyway. |
| "No sidecar needed" | No framework needs a sidecar under (b). The Tauri "needs a Node sidecar" row in Issue #1 goes away. |
| Same language as the harness (TS) | Still true and still useful: one author, one language, and contract types can be shared as an npm package. The schema-first path is symmetric: the harness publishes JSON Schema, a TS app generates types with `json-schema-to-typescript`, and Rust (`typify`), Dart, Go, Kotlin and Swift codegen get the same guarantee. Moderate advantage only. |
| Can run the CLI with no Node on the user's machine | Irrelevant. Harness users have Node. Windows needs Node inside WSL regardless. |

**Net effect:** integration moves from a decisive argument for Electron to a roughly neutral criterion. What remains is a mild TS affinity and the shared transport requirement (spawn, stream, WSL bridging), which every serious candidate handles. Re-weight the framework decision on the other areas' criteria. [inferred]

### 4. Recommended architecture

```
 App UI ──► RunSource interface (one per repo)
              ├─ LocalHarnessSource   → Transport.spawn("devscene", ["runs", …, "--json"])
              │                          Transport = Direct (macOS/Linux) | Wsl(distro) (Windows)
              │                          long-lived `devscene runs watch --json` → NDJSON events
              └─ GitHubSource (read-only) → gh api / gh run list / artifact status.json
            merge rule: local record wins when present; GitHub fills the gaps (Issue #1, item 5)
 Actions (pause/resume/answer/drop/start-review) → only through the LocalHarnessSource verbs,
            which, for remote runs, call remote-run.sh inside the harness, never from the app
```

Without any local setup, a user can still act on remote runs. The GitHub-side command surface (`@dev-scene pause|resume|answer|stop|clear`, `docs/github-run-control.md` §1) is itself a harness-owned contract, so the app can post those comments through `gh`. That keeps the "app never composes dispatch inputs" rule. [verified surface; inferred design]

### 5. Minimal `devscene runs` JSON contract (sketch)

Every response is a single JSON object on stdout, or NDJSON for `watch`. The `repo` block (`scripts`, `registrySchema`) appears only in `capabilities` and `runs` responses, because `doctor` and `repos` may run with no repo. When the cwd is not an adopted repo, `repo` is `null` and repo-scoped verbs fail with `error.code: "not_adopted"`:

```json
{ "contract": "1.0", "cli": "0.7.0", "repo": { "root": "/home/u/proj", "scripts": "0.6.12", "registrySchema": 1, "executionTarget": "github-actions" },
  "ok": true, "data": { … }, "warnings": [ { "code": "remote_stale", "message": "…" } ] }
```

On error: `"ok": false, "error": {"code": "not_adopted|refused|usage|internal", "message": "…"}`. The exit code follows `docs/cli.md` §1.

| Command | Purpose | `data` |
|---|---|---|
| `devscene capabilities --json` | Negotiation. Works without a repo | `{verbs: [...], features: ["watch","remote","answer-form",…]}` |
| `devscene runs list --json [--remote]` | Board columns | `runs: RunSummary[]`, plus GitHub-only runs from `remote-run.sh list` when `--remote` is set |
| `devscene runs show <branch> --json` | Detail screen | `RunDetail` = summary + `questions[]` + `logTail[]` (bounded) + `analytics` (from `run_analytics/`, `branch_statistics/`) |
| `devscene runs watch --json` | Live updates (NDJSON) | `{type: "snapshot"\|"run_updated"\|"run_removed"\|"log"\|"heartbeat", branch?, run?, runs?}`. `snapshot` comes first and after any resync; the process exits when stdin closes |
| `devscene runs pause <branch> --json` | Writes `PAUSE`, or dispatches for a remote run | `{action: "pause", delivered: "marker"\|"dispatch", runUrl?}` |
| `devscene runs resume <branch> [--clear-park-loop] --json` | Writes `RESUME`, or dispatches | same shape |
| `devscene runs answer <branch> --answers-file <json> --json` | Writes `answer_<n>.md`, or dispatches answers | `{answered: [n…]}` |
| `devscene runs drop --branch <b> --prompt-file <f> --json` | Inbox drop with the collision guard | `{inboxFile, branch}`, or `error.code: "collision"` with `where: ["registry","run_copy","inbox"]` |
| `devscene runs derive-branch --title <t> --json` | Wraps `hr_derive_branch` (item 12) | `{branch, taken: [...], suffix}` |
| `devscene runs review <branch> --review-file <f> --json` | User-review round | `{round, delivered}` |
| `devscene doctor --json` | Item 9 | `{counts, checks: CheckResult[]}`, which already exists as `runChecks` |
| `devscene daemon status --json` | Item 15 | `{installed, running, backend, label}` |
| `devscene repos --json` | Item 8 | entries from `repos.json` |

`RunSummary` fields:

- `branch`, `status` (`queued|running|paused|parked|park_loop|failed|completed|stopped|done`), `source` (`inbox|registry|github`). `queued` comes from inbox files the watcher has not launched yet: they have no registry entry, and the registry has no queued status;
- `engine` (`task|user_review|docs`), `execution` (`local|github-actions`);
- `startedAt`, `updatedAt`, `resumedAt`, `pauseReason`, `pausedBy`;
- `openQuestions` (count), `worktree`;
- `pr` (`{number, url, merged}`), `remoteRunUrl`, `remoteSyncedAt`, `stale` (bool).

**Status → board column (normative, owned by the harness, not the app):**

| Board column | Statuses |
|---|---|
| To Do | `queued` |
| In Progress | `running`, `paused`, `parked`, `park_loop` |
| Done | `completed`, `done`, `failed`, `stopped` |

The enum merges local registry states (`completed`, `park_loop`) with GitHub label states (`done`, `stopped`, from `RUN_STATES`); the contract documents that mapping so the app never has to know harness semantics. [verified states; inferred mapping]

Timestamps are ISO-8601 with an offset. Today the registry writes local time without a zone (`date '+%Y-%m-%dT%H:%M:%S'`), and the contract should normalise that. [verified current format; inferred fix]

**Versioning rules:**

- `contract` is semver. Adding fields or verbs bumps the minor; removing or renaming fields bumps the major.
- The app ignores unknown fields and refuses an unknown major.
- The harness publishes a JSON Schema in `schemas/` (that folder already holds `harness.config.schema.json` and `flow-graph.schema.json`), which the app vendors.

**Phased cut.** Thirteen verbs is too much to wait for. Ship in phases, which `capabilities` negotiation already supports (the app hides verbs that are absent):

- **v1, read-only:** `capabilities`, `runs list`, `runs show`, `runs watch`, `doctor --json`.
- **v1.1:** `pause`, `resume`, `answer`.
- **v1.2:** `drop`, `derive-branch`, `review`.

Phasing also lowers the risk that the app ships parsing human output as an interim.

**What the harness repo would need to add:**

1. A `runs` command module, plus `--json` on `doctor` and `daemon`. The output goes through a JSON path in the `Reporter`: `result()` already exists as the non-quiet stdout channel.
2. JSON emitters for the bash side. Either `remote-run.sh status|list --json` and a small `runs-query.sh` over `hr_registry_*` that the TS verb execs from the repo's `scriptsDir`, or a TS port of the registry *reads only*, with the bash kept as the single writer. **The bash-exec route keeps one implementation and binds the semantics to the repo's own script version.**
3. A `"schema": 1` field in `registry.json`, plus a stamp of the rendering CLI version in the repo (for example in the scripts' header or the state dir), so that `repo.scripts` can be reported.
4. Act verbs that wrap what the plugin commands' prose currently tells Claude to do (pause, resume, answer, drop with guard). The plugin commands should then call the same verbs, so the CLI and the slash commands cannot drift apart. That is the drift Issue item 7 is about.
5. `capabilities` and a contract test suite that the app CI can also run against fixtures.

Estimate: read side ~1–1.5k lines. The act side plus `watch` is several thousand lines including tests: `branch-pause.md` (103 lines) and `branch-resume.md` (114 lines) are prose protocols that branch between a local marker and a GitHub dispatch, so they must be ported, not wrapped; the harness's conventions (long header comments, byte-for-byte shell/TS mirrors, a test suite per contract) add to each feature; and `runs watch` (inotify across the main checkout and every run copy's `stateDir`) is a component in its own right. Size it in the harness repo. [inferred]

## Answers to the owner's questions

- **Q1 (credible cross-platform options), Q2 (is cross-platform worth it), Q5 (native-side blockers):** For the integration layer, every candidate needs the same three primitives: spawn a process with streamed stdout, run commands through `wsl.exe` on Windows, and parse JSON. None needs Node in-process. So integration gives no reason to prefer cross-platform over native or vice versa. A native-per-platform build would write the transport three times (~200–400 lines each, including the shell-`PATH` resolution step from §2), not the harness logic. [inferred]
- **Q5 (blockers):** The real blocker is Windows/WSL, and it is framework-independent: `\\wsl$` cannot be watched, and the harness only runs in WSL2. It is solved by `runs watch` streaming from inside WSL. Any framework that can keep a child process's stdout open (all of them) is fine. [secondary + inferred]
- **Q6 (costs):** Shape (c) would add per-binary signing and notarization work and 57–93 MB per platform. Shape (b) adds nothing. [verified sizes from secondary benchmark]
- **Q7 (momentum):** Node SEA is still "Active development" (1.1) in Node 26. Do not build on it for a core path. [verified]

## Risks and open questions

- **The contract depends on harness work (item 7) that has not been scheduled.** Until then the app would have to parse `remote-run.sh` human output and the registry JSON directly. That is acceptable only as a throw-away spike.
- **Which script version answers?** If `devscene runs` (global CLI) reads a registry written by older repo scripts, field semantics may differ. Mitigations: the registry `schema` field, or having the TS verb exec the repo's own query script.
- **A long-lived `runs watch` through `wsl.exe` can fail silently.** Linux-side processes can outlive a killed `wsl.exe`; the WSL VM can shut down after idle, which ends the stream; and the app must reconnect and resync with a full snapshot. The contract answers with a `snapshot` event, heartbeats and exit-on-stdin-close (§5); the WSL area should test all three.
- **The 9P notification gap is not confirmed on a current WSL release.** The WSL area should run a 10-line `FileSystemWatcher` probe on `\\wsl.localhost\…` to confirm it.
- **`wsl.exe` cost and quirks are unmeasured:** spawn latency, distro selection, login-shell `PATH`, and how CRLF/UTF-16 behave on `wsl.exe`'s own error messages. Measure them in the WSL area.
- **Remote-only users act through GitHub comments or `gh workflow run`.** Confirm with the harness owner that the app posting `@dev-scene` comments is a supported route, as opposed to the app composing dispatch inputs (which it should not do).
- **The status digest's "points needing your attention" section is prose Claude distils from review files.** It has no deterministic equivalent yet. Either the harness emits it as structured data, or the app shows raw links. This is open.
- The size figures in [4] come from a single third-party benchmark (Feb 2026, hello-world). Real sizes for the CLI will differ.

## Sources

1. https://nodejs.org/api/single-executable-applications.html — SEA stability 1.1, `--build-sea` since v25.5.0, ESM support, cross-build caveats, signing — accessed 2026-11-12
2. https://bun.com/docs/compiler/executables.md — Bun `--compile` targets, cross-compile limits, macOS signing/entitlements, size note — accessed 2026-11-12
3. https://docs.deno.com/runtime/reference/cli/compile/ — Deno compile targets, cross-compiling from any host, denort, signing, npm embedding — accessed 2026-11-12
4. https://notes.billmill.org/dev_blog/2026/02/updated_SEA_benchmarks.html — sizes: Node SEA 25.6.0 93 MB, Bun 1.3.8 57 MB, Deno 2.6.8 72 MB (2026-02-05) [secondary] — accessed 2026-11-12
5. https://v2.tauri.app/develop/sidecar/ — Tauri `externalBin`, target-triple suffix requirement — accessed 2026-11-12
6. https://github.com/microsoft/WSL/issues/4581 — Windows file-change notifications do not work over WSL 9P (`\\wsl$`) [secondary; issue closed by an inactivity bot on 2024-02-01 without a fix; behaviour still reported in 2024–25 user forums, e.g. https://resource.dopus.com/t/wsl2-file-system-changes-are-not-updated-automatically-have-to-press-f5-manually/53329; no Microsoft doc states support] — accessed 2026-11-12
7. https://learn.microsoft.com/en-us/windows/wsl/troubleshooting — WSL file access goes through a 9P server (establishes the 9P server only, not the notification gap) — accessed 2026-11-12
8. Local harness source (read 2026-11-12):
   - `/Users/daniel/Work/devscene/cli/package.json`
   - `cli/src/cli.ts`
   - `cli/src/commands/registry.ts`
   - `cli/src/core/report.ts`
   - `cli/src/doctor/checks.ts`
   - `cli/src/machine/registry.ts`
   - `cli/src/remote/githubActions.ts`
   - `cli/templates/scripts/{remote-run.sh, autonomous-watcher.sh, lib/harness-run-lib.sh}`
   - `plugin/commands/branch-{status,pause,prompt}.md`
   - `docs/cli.md` §1, §6, §7
   - `docs/watcher.md` §4, §5, §7
   - `docs/github-run-control.md` §5
   - `docs/remote-execution.md` §1, §4
   - `docs/github-issue-trigger.md` §2
   - `cli/src/daemon/backend.ts`
9. https://github.com/sindresorhus/fix-path — GUI apps on macOS and Linux do not inherit the dotfile `$PATH` [secondary] — accessed 2026-11-12
10. https://github.com/nvm-sh/nvm#install--update-script — nvm installer appends its init to `~/.bashrc` and similar profiles — accessed 2026-11-12
