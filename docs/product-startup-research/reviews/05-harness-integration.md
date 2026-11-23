# Review — 05-harness-integration.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The harness claims hold up well. I checked every one against `/Users/daniel/Work/devscene` at `a1d0e992` (2026-11-12): line counts, `package.json`, `process.exit`, `Reporter`, `runChecks`, `hr_derive_branch`, the registry format and the `DEVSCENE_CLI_VERSION` pin. The third-party tooling facts also check out live: the Node SEA, Bun and Deno docs and the size benchmark. The central conclusion stands. The run logic is bash in the repo, so "Electron reuses the CLI" is mostly void, and a versioned `--json` process contract is the right integration point.

The file still needs fixes in three places:

- **The transport.** It ignores how GUI apps get their `PATH`. The `bash -lc` claim for nvm is wrong on default Ubuntu.
- **The contract sketch.** It has no "queued" state, so it cannot fill the To Do column.
- **The framing.** The WSL-only claim cites the wrong source, the 9P source is labelled more vaguely than it should be, and the size estimate is overconfident.

### Spot-check results (all against local source, 2026-11-12)

| Claim | Result |
|---|---|
| `cli/src` 34,347 lines | Confirmed (`*.ts`, no test files in `src`) |
| `harness-run-lib.sh` 7,522 / `remote-run.sh` 8,264 / `autonomous-watcher.sh` 6,671 (22,457 total) | Confirmed |
| `package.json`: `bin` only, no `main`/`exports` | Confirmed (`"bin": {"devscene": "./dist/cli.js"}`, version 0.6.12) |
| No `process.exit()` | Confirmed. Only comments mention it (`cli.ts:14`, `core/errors.ts:6`). `docs/cli.md` §1 states it too |
| Injectable `Reporter` | Confirmed (`core/report.ts`: `ReporterOptions.out/err` sinks, `class Reporter`) |
| `runChecks()` returns `CheckResult[]` | Confirmed (`doctor/checks.ts:6611`). The doctor files total 7,925 lines, matching "~7,900 own" |
| `hr_derive_branch`, 60-char cap, `_2`…`_99`, `issue_<n>` fallback | Confirmed (`harness-run-lib.sh:3740–3765, 3940`; `remote-run.sh:278, 4634`) |
| No schema version in `registry.json` | Confirmed. `hr_registry_init` writes `{"runs":{}}`, while sibling files (`repos.json`, the usage gate, run analytics) do carry `schema` |
| `DEVSCENE_CLI_VERSION` pin only in workflows | Confirmed. It is in `devscene-run.yml`/`devscene-control.yml`, generated only when remote execution or the forge trigger applies (`generators/githubWorkflows.ts`). The scripts carry no version stamp |
| Registry timestamps are zone-less local time | Confirmed (`date '+%Y-%m-%dT%H:%M:%S'`, e.g. `autonomous-watcher.sh:3729`) |
| Six `RUN_STATES` labels | Confirmed (`remote/githubActions.ts:139`) |
| Exit codes 0/1/2 | Confirmed (`docs/cli.md` §1) |
| ~445 lines of prompt prose | Consistent: `branch-{answer,pause,resume,status,prompt,user-review}.md` total 445 |

## Must fix

**M1. §2 "(b) details: transport", "macOS/Linux: spawn `devscene` from `PATH`" and "Windows: … `bash -lc` … nvm-style Node installs only appear on a login `PATH`".**

- **Problem:** The transport design misses the best-known failure mode of this exact architecture.
  - A GUI app launched from Finder, the Dock or a desktop launcher does not inherit the user's shell `PATH`. On macOS, launchd gives it `/usr/bin:/bin:/usr/sbin:/sbin`. So `devscene`, `node`, `gh` and `git` from Homebrew, nvm, volta or fnm are often not found.
  - On WSL, the nvm installer appends its init to `~/.bashrc`. Ubuntu's default `~/.bashrc` returns early for non-interactive shells. A login shell (`-l`) sources `~/.profile`, which sources `~/.bashrc`, but that guard then skips the nvm lines. So `bash -lc` does **not** reliably expose nvm's Node. The `[inferred]` claim is wrong as stated.
- **Evidence:**
  - https://github.com/sindresorhus/fix-path ("GUI apps on macOS and Linux do not inherit the `$PATH` defined in your dotfiles")
  - https://github.com/nvm-sh/nvm#install--update-script (the profile lines go to `~/.bashrc` and similar files)
- **Fix:** Replace the transport bullets with:
  > macOS/Linux: resolve the CLI once by asking the user's login, interactive shell (`$SHELL -ilc 'command -v devscene; command -v node'`, the technique used by `fix-path`/`shell-env`). Cache the absolute paths, let the user override them in settings, and spawn by absolute path. Windows: resolve the same way inside the distro (`wsl.exe -d <distro> -- bash -ilc 'command -v devscene'`). Then call `wsl.exe -d <distro> --cd <path> --exec <abs-path-to-node> <abs-path-to-devscene> runs … --json`, so steady-state calls do not depend on shell init files. Doctor-style diagnostics in the app should report which path was found.

  The "cost of the transport" line (~200–400 lines per native platform, in "Answers") should mention this resolution step. Also note that `npx -y devscene@<min>` as a fallback hits the network and runs a CLI version different from the user's install. It should be opt-in, not silent.

**M2. §5 `RunSummary.status` and the board mapping.**

- **Problem:** The contract cannot fill the board's **To Do** column. A prompt dropped into `autonomous_inbox/` that the watcher has not yet launched has no registry entry. The registry has no `queued` status (grep of `autonomous-watcher.sh` and `docs/watcher.md`). The file's own collision guard treats "queued inbox file" as a distinct place.
- **Second problem:** The status enum merges local registry states (`completed`, `park_loop`) with GitHub label states (`done`, `stopped`) and gives no mapping. The app would then have to know harness semantics, which is the drift §2 warns about.
- **Evidence:** `harness-run-lib.sh` `hr_registry_init` / registry functions; `remote/githubActions.ts:139` (`RUN_STATES`); Issue #1 board columns.
- **Fix:**
  - Add `queued` (from inbox files; also user-review and answer files waiting for pickup if relevant) to `RunSummary.status`, with `source: "inbox"|"registry"|"github"`.
  - Add a normative table in the contract: status → board column (To Do: `queued`; In Progress: `running|paused|parked|park_loop`; Done: `completed|done|failed|stopped`). The harness owns this table, not the app.

## Should fix

**S1. TL;DR bullet 4, "Native Windows is unsupported (`docs/cli.md` §6)".**

- **Problem:** `docs/cli.md` §6 (line 395) says native Windows is unsupported **for sandboxing**, and it offers `sandbox.optOut` as the escape hatch. It does not say the harness as a whole cannot run on native Windows.
- **Why the conclusion still holds:** The harness needs bash, jq, and launchd/systemd daemon backends (`daemon/backend.ts`), and the product brief fixes "Windows via WSL2 only".
- **Fix:** Cite those reasons instead: "The run scripts are bash + jq and the daemon backends are launchd/systemd only (`daemon/backend.ts`). §6 additionally makes native Windows unsupported for sandboxing. The product brief fixes Windows to WSL2." Keep the tag `[verified]`.

**S2. Source [6] and the 9P claim.**

- **Problem:** The tag "2019–2021 reports, possibly stale" undersells and misdescribes the source. Issue #4581 was **closed on 2024-02-01 by an inactivity bot, with no fix**. Nothing newer from Microsoft contradicts it, and 2024–2025 user reports still show `\\wsl.localhost` changes not refreshing.
- **Evidence:**
  - https://github.com/microsoft/WSL/issues/4581
  - https://resource.dopus.com/t/wsl2-file-system-changes-are-not-updated-automatically-have-to-press-f5-manually/53329
- **Fix:** Re-tag as "[secondary] issue closed as stale 2024-02-01 without a fix; behaviour still reported in 2024–25 user forums; no Microsoft doc states support". Add the second URL. Source [7] (WSL troubleshooting) only establishes the 9P server, not the notification gap. Say so, or drop it from the claim. Also add a test: the WSL area should confirm this with a 10-line `FileSystemWatcher` probe on a current WSL release.

**S3. TL;DR bullet 7 and §5, "1.2–2k lines … most of it thin wrappers".**

- **Problem:** This estimate is likely low and is stated with false precision.
  - The act verbs are not thin. `branch-pause.md` (103 lines) and `branch-resume.md` (114 lines) are prose protocols that branch between a local marker and a GitHub dispatch. Turning them into deterministic code means porting that logic, not wrapping a function.
  - The harness's own conventions add a lot per feature: long header comments, byte-for-byte shell/TS mirrors (`remote/githubActions.ts` header), and a test suite per contract.
  - `runs watch` (an inotify loop across the main checkout plus every run copy's `stateDir`) is a component in its own right.
- **Fix:** Split the estimate into "read side (`capabilities`, `runs list/show`, `doctor --json`, `repos --json`): ~1–1.5k" and "act side + `watch`: several thousand lines including tests; size it in the harness repo". Keep the `[inferred]` tag.

**S4. §5, contract scope for a first version.**

- **Problem:** Thirteen verbs before the app can show a board is a lot to make the app wait for (Risk 1 already says item 7 is unscheduled).
- **Fix:** Add a phased cut.
  - **v1, read-only:** `capabilities`, `runs list`, `runs show`, `runs watch`, `doctor --json`.
  - **v1.1:** `pause`/`resume`/`answer`.
  - **v1.2:** `drop`/`derive-branch`/`review`.

  The capability negotiation already supports this, so say so explicitly. Phasing also lowers the risk that the app ships parsing human output as an interim.

**S5. §2 "Avoid polling … A long-lived `devscene runs watch --json` … solves both problems".**

- **Problem:** A long-lived child through `wsl.exe` has its own failure modes, and the file does not list them:
  - Linux-side processes can outlive a killed `wsl.exe`.
  - The WSL VM can shut down after idle, which ends the stream.
  - The app has to handle reconnects and resync with a full `runs list` after a reconnect.
- **Fix:** Add these to "Risks and open questions" and to the contract. Make `watch` emit a full `snapshot` event first and after any resync, plus a heartbeat, so the app can detect a dead stream. Make the CLI exit when stdin closes, so the Linux side dies with the app.

**S6. Table §1, row "Deterministic branch name … ASCII fold".**

- **Problem:** The code does not transliterate. Under `LC_ALL=C`, a non-ASCII letter such as `é` becomes a separator (`harness-run-lib.sh:3744`).
- **Fix:** Use "ASCII-only slug (non-ASCII → separator)". This matters because an app that previews names has to match exactly, which is another argument for `derive-branch --json`.

## Nice to have

**N1. Table §2(c), `deno compile` row.** Two current details are missing: Windows ARM64 is supported only from Deno 2.9.3, and `--bundle` / `--exclude-unused-npm` shrink the binary well below the hello-world/`node_modules`-embedded figure (https://docs.deno.com/runtime/reference/cli/compile/). This does not change the conclusion.

**N2. Bun row.** Say that only `hideConsole` works when cross-compiling (icon, title, publisher, version, description and copyright do not). Also note that the documented macOS entitlements list has five keys, not just `allow-jit`, and needs Bun ≥ 1.2.4 (https://bun.com/docs/compiler/executables.md).

**N3. Node SEA row.** "macOS needs `codesign`" could say that the docs call signing *required* on macOS (ad-hoc `codesign --sign -` at minimum) (https://nodejs.org/api/single-executable-applications.html). The rest of the row is confirmed: v26.13.1 docs, Stability 1.1, `--build-sea` since v25.5.0, `mainFormat: "module"` not combined with `useSnapshot`, and the cross-build caveat.

**N4. §5 envelope.** Consider putting `repo.scripts` / `registrySchema` only in `capabilities` and `runs` responses, not in every response. `doctor` and `repos` may run with no repo. Also define what `repo` is when the cwd is not an adopted repo (`null` plus `error.code: "not_adopted"`).

**N5. §3 "Same language" row.** Name a concrete schema-first path (for example, the harness publishes JSON Schema and the app generates TS with `json-schema-to-typescript`). That makes the "TS types are a mild advantage" claim symmetric with the Rust/`typify` mention.

**N6. Scope.** §2(d) and §4's GitHub read-model is appropriately brief and defers to Issue item 5. No duplication of 01–04 was noticed.

## Review resolution

- **M1** — applied. §2(b) transport now resolves `devscene`/`node` once through a login, interactive shell (`$SHELL -ilc`, and `bash -ilc` inside WSL), caches absolute paths with a user override, spawns by absolute path, and makes the `npx` fallback opt-in. The wrong `bash -lc` claim is replaced with the `~/.bashrc` non-interactive guard explanation. "Answers" Q1/Q2 mentions the resolution step. Sources [9] (fix-path) and [10] (nvm) added.
- **M2** — applied. `queued` and `source: inbox|registry|github` added to `RunSummary`; a normative status → board column table added to §5. Verified: the registry has no queued status (no hit in `autonomous-watcher.sh`/`docs/watcher.md`), and `RUN_STATES` at `remote/githubActions.ts:139` is `running, parked, paused, done, failed, stopped`.
- **S1** — applied. Verified `docs/cli.md` §6 is about sandboxing, and `daemon/backend.ts` has only `launchd | systemd | none`. TL;DR bullet re-cited as proposed.
- **S2** — applied. Verified via `gh`: #4581 closed 2024-02-01 by `microsoft-github-policy-service[bot]` for inactivity. Source [6] re-tagged and the dopus forum URL added; [7] scoped to "9P server only"; a `FileSystemWatcher` probe added to Risks for the WSL area.
- **S3** — applied. The estimate is split in the TL;DR and §5: read side ~1–1.5k lines; act side plus `watch` is several thousand lines, to be sized in the harness repo. Verified `branch-pause.md` 103 and `branch-resume.md` 114 lines.
- **S4** — applied. A phased cut (v1 read-only, v1.1 pause/resume/answer, v1.2 drop/derive-branch/review) added to §5, tied to `capabilities` negotiation.
- **S5** — applied. The `watch` failure modes are added to Risks, and the contract now requires a `snapshot` event first and after resync, heartbeats, and exit when stdin closes (§2(b) and the §5 table).
- **S6** — applied. Verified the comment at `harness-run-lib.sh:3744` ("ASCII-only under `LC_ALL=C`, so `é` is a separator"). The §1 row is reworded.
- **N1** — applied. Verified live on the Deno compile docs: Windows ARM64 from 2.9.3, plus `--bundle` (experimental) and `--exclude-unused-npm`.
- **N2** — applied. Verified live on the Bun docs: only `hideConsole` works when cross-compiling, the entitlements plist has five keys, and codesign needs Bun ≥ 1.2.4.
- **N3** — partially applied. The Node docs list macOS `codesign --sign -` as a step that is not marked optional, while Windows is explicitly optional. The docs do not use the word "required", so the row says "not marked optional (ad-hoc at minimum)" instead of "required".
- **N4** — applied. The §5 envelope note limits `repo` to `capabilities`/`runs` responses and defines `repo: null` plus `not_adopted`.
- **N5** — applied. The §3 row names `json-schema-to-typescript` as the schema-first TS path.
- **N6** — no action needed (observation only).
