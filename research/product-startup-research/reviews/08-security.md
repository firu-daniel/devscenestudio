# Review — 08-security.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The file is careful and mostly right, and its harness evidence holds up well. I checked every §5 path:line against `/Users/daniel/Work/devscene` at `a1d0e992`. All the cited lines exist and say what the file claims, with drift of a few lines at most. **H1 is confirmed at the configuration level.** It is also understated: the same grants let a run write sibling run copies and the main checkout's whole working tree, including `.claude/CLAUDE.md` and `.claude/agents|commands|skills`. H2–H11 are confirmed as stated. The positive claims about the workflows are confirmed. Two external facts are wrong. DOMPurify had about 25 advisories in 2026, not six, one of them a default-config bypass, so the floor must be 3.4.17. Chrome 147 now gates WebSockets under LNA. The rest are confirmed.

Four gaps carry the verdict:
- the threat model misses the **hostile-repo** class: Issue item 8 auto-detects repos, and item 9 auto-runs `doctor` on them;
- the **start confirmation is rendered in the renderer**, so an XSS can click through it, and the "after" scores E1/T1 = I2 depend on it not being;
- the **branch regex** in §3.2 rejects every branch name the harness generates;
- the **effort table contradicts the TL;DR**.

---

## Part A — App findings (Studio's own threat model)

## Must fix

**M1. §3.2 rule 2: the branch regex rejects every harness branch.** The regex `^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$` has no `_`. The harness derives `chore_devscene_env_variables`, `feat_x` and similar names (see `harness-runs/autonomous_logs/*.log` and the watcher's own examples, `autonomous-watcher.sh:808`). The builder would refuse every real run. A §4.3 fuzz suite built on this regex would pass while the feature is broken.
*Fix:* use `^[A-Za-z0-9][A-Za-z0-9_./-]{0,199}$`, i.e. add `_` to the class. Keep the other checks: no `..`, no `//`, no `@{`, no component starting with `.`, no trailing `/` or `.lock`, and `check-ref-format --branch` printed equals input. Add a real harness branch (`chore_devscene_env_variables`) to the fixtures.

**M2. The confirmation dialog must be rendered by the privileged side. Otherwise the E1/T1/W6/H-1 "after" scores don't hold.** §3.10 and §6.2 item 4 make "a confirmation per start, answer and resume" the control that brings XSS → `startRun` from I3 down to I2. If that dialog is HTML in the same renderer, an XSS payload can call the intent verb and then click "Confirm", or skip the dialog, because the dialog is UI state and not part of the verb.
*Fix:* add a MUST row to §4.1:
- **desktop:** the act verb (`start`, `answer`, `resume`, `drop`) opens an **OS-native modal** from the main process or Rust core (`dialog.showMessageBox` / `tauri-plugin-dialog` / `NSAlert`). The modal shows repo, branch, source author and a hash or excerpt of the exact text, and the verb executes only on that modal's result. The renderer never passes "confirmed: true".
- **local web:** a server-issued one-time nonce bound to the exact payload hash. This does not stop XSS (an XSS can read the nonce), which is why W6 after stays I3. Say so explicitly.

State the dependency in the E1/T1 rows ("after = 1×2 *only with a native confirmation*").

**M3. A missing threat class: hostile or untrusted repos picked up by the repo scan (Issue items 8 and 9).** Issue item 8 auto-detects repos with a `harness.config.json` scan. Item 9 runs `devscene doctor` "on startup and whenever the repo changes". Every cloned OSS repo, extracted tarball or shared-drive folder that carries a `harness.config.json` becomes a repo Studio spawns processes in. Concrete paths I verified:
- **`doctor` spawns with an env overlay taken from the repo's `.mcp.json`.** `cli/src/doctor/checks.ts:6233-6251` (`runPythonSelfCheck`) copies every string in `.mcp.json` → `mcpServers.<docs server>.env` into the child's environment (`env: { ...process.env, ...overlay, … }`). The repo's own `harness.config.json` enables this branch (`pythonRetrievalApplies`). A repo can therefore set `LD_PRELOAD=./x.so` (Linux/WSL), `PYTHONPATH=./evil` or `BASH_ENV`, which is code execution when the Python launcher is installed. That is a **harness** bug (H12 below), but Studio's auto-doctor is what makes it reachable without a click.
- `doctor` also runs `npm view` (`checks.ts:5883`) with cwd in the repo, so the repo's `.npmrc` (registry, proxy, `cafile`) applies.
- **`stateDir` and `scriptsDir` come from the repo's config.** §3.3 confines reads to `<stateDir>/…`, but in a hostile repo `"stateDir": "../../.."` moves the confinement root. The root must be validated (a relative path, no `..`, realpath inside the repo) before it is used as a root.
- `git` in a repo whose `.git/config` the user did not write (an archive with `.git`, a shared folder): `core.fsmonitor` and `core.pager` run commands, and so do `diff.external`, `core.sshCommand` and `filter.*` on checkout.

*Fix:* add an "Untrusted repo" row to §1.3 and a section §3.11:
- detected repos are listed but **not trusted** until the user confirms each one (like VS Code's Workspace Trust);
- no `doctor`, no `devscene`/`git` spawn with cwd in an untrusted repo;
- spawn `devscene … --cwd <repo>` with the process cwd outside the repo (the harness's own rule, `sandbox-record.md` residual 1.1);
- validate `stateDir`/`scriptsDir` from config before use;
- extend rule 7's `-c` list with `core.pager=cat`, `core.fsmonitor=`, `diff.external=` and `--no-pager`.

Add a fuzz/fixture repo test to §4.3.

**M4. A missing threat: runs (or anyone with write access) can plant code in the main checkout that Studio then runs.** Because of H1′ (Part B), a sandboxed run can write the main checkout's working tree outside the protected list: `node_modules/.bin/devscene`, `package.json`, `.npmrc`. If Studio ever runs `npx devscene …` or `npm …` with cwd in the main checkout, `npx` prefers the repo-local `node_modules/.bin/devscene`. 05 §2 also proposes `npx -y devscene@<min>` as a fallback.
*Fix (MUST):* resolve `devscene` once by absolute path from `$HOME` (not from a repo cwd), refuse a resolved path that lies inside any detected repo or a group- or world-writable directory, and never use `npx` with a repo cwd. Note that 05 line 76 uses `wsl.exe … -- bash -ilc …` for resolution, which contradicts §3.2 rule 5 ("always `--exec`"). It is harmless with a constant string, but say so.

**M5. The effort figures contradict each other (§TL;DR, §4.2, §4.4).**
- The point totals don't sit inside their own ranges:
  - Tauri ≈ 5.75 but "4.5–6";
  - local web ≈ 7.25 but "7.5–9.5";
  - hosted ≈ 8.3 but "9–12";
  - hybrid ≈ 14.5 but "15–19".
- "±30% as in 03" would make Electron 3.7–6.8, not 5–6.5.
- Summed from the doc's own table, **Tauri (5.75) costs more than Electron (5.25)**, yet the TL;DR's ranges (Tauri 4.5–6 vs Electron 5–6.5) read as Tauri being cheaper.
- The TL;DR's "native ≈ 2–3" is per app. The table total is ≈ 5.25 for three apps, the same as Electron. Stated per app, it makes native look half the cost.

*Fix:* recompute each range as point ± 30%. Give native as "≈ 5.25 total (≈ 1.75 per app)". Say plainly that Tauri's security work is ≈ 0.5 O-d *more* than Electron's (capabilities + isolation + cargo-deny), offset by a smaller recurring cost.

**M6. Studio's GitHub read model can be spoofed, and the file doesn't say so.** Issue item 5 builds state from `sdlc-harness: <state>` **labels**, the **progress comment**, and `run_analytics/` / `branch_statistics/` **committed on the branch**:
- anyone with triage can set labels;
- anyone can post comments on a public repo;
- anyone who can push a branch controls the committed analytics.

§1.3 notes that the harness trusts `<!-- devscene` markers only from `github-actions[bot]` (`remote-run.sh:688-694`, verified), but it never requires Studio to apply the same rule.
*Fix:* add to §1.3 and §6.2:
- trust the progress comment only when `user.login == github-actions[bot]` and it has the exact marker shape;
- prefer Actions run state (API) over labels for status;
- treat branch-committed JSON as untrusted: schema-validate it, cap its size, and render numbers only.

## Should fix

**S1. Electron custom-protocol path traversal is missing from §2a.** The file says to "load the UI from a custom protocol" but doesn't require the handler to confine paths. Electron's own `protocol.handle` example does it (`path.relative` + reject `..`/absolute → 400), and a hand-rolled handler without it serves any file. *Fix:* add an E-row and a MUST: register `app` as `standard, secure` with no `bypassCSP`, confine to the bundle as in the doc example, and add a test in §4.3 item 4. Evidence: https://www.electronjs.org/docs/latest/api/protocol.

**S2. Deep links are not modelled.** 04 §9 and 07 8.5 discuss a custom URL scheme for "open run in Studio". 08 never mentions it, although a scheme is reachable from any web page. *Fix:* add a row: v1 registers no scheme. If one is added later, it is navigation-only (`open?repo=&branch=`, validated by the §3.2 rules) and never an act verb.

**S3. Remote "global stop" needs a permission the minimal GitHub App set omits.** §3.10 says to put `DEVSCENE_REMOTE_STOP` one click away. That is a **repository variable** (`remote-run.sh:242`), and setting it needs the *Variables* permission (write) and repo-admin-level rights for a user. H-6's minimal set (Issues RW, PRs R, Actions RW, Contents R, Metadata R) can't do it. *Fix:* either add Variables RW (and justify it) or make remote stop "cancel the run's workflow" (Actions RW) plus an "open settings" link.

**S4. The child-env allowlist in §1.4 is too narrow to work, and the file doesn't say what breaks.** `PATH, HOME, LANG, WSL_UTF8` drops:
- `SSH_AUTH_SOCK` (git fetch over SSH);
- `HTTPS_PROXY`/`NO_PROXY`/`NODE_EXTRA_CA_CERTS` (corporate networks);
- `XDG_CONFIG_HOME`/`GH_CONFIG_DIR` (gh config location);
- `WSLENV`.

*Fix:* list these as allowed passthroughs and keep denying `ANTHROPIC_*`, `CLAUDE_*`, `GIT_*`, `NODE_OPTIONS`, `LD_*`/`DYLD_*`, `BASH_ENV` and `ENV` explicitly.

**S5. Windows file reads over `\\wsl$`: the §3.3 algorithm doesn't carry over.** Windows `realpath` doesn't resolve Linux absolute symlinks behind `\\wsl.localhost` (they appear as LX reparse points), and there is no `O_NOFOLLOW` or inode compare over 9P. *Fix:* on Windows, do all run-file reads **inside WSL**, through `devscene runs … --json` (05 §5) or a fixed reader under `wsl.exe --exec`, and use `\\wsl$` only for nothing security-relevant. Mark this as Windows-specific in §3.3 and §6.2 item 3. [inferred; flag it for the WSL measurement in 04]

**S6. The residual-risk ordering hides a weighting choice.** The TL;DR puts hosted < local web, but §4.4 grades both "Medium". Hosted's worst case is "every user's repos", local web's is "one user's machine". The order holds only per user. *Fix:* state the axis ("per-user residual; hosted is worse in aggregate"), or show them as tied.

**S7. The bidi/invisible list in §3.1 is narrower than the harness's.** The harness also flags U+2060 and U+FEFF (`prompt-injection-screen.sh:35-37`). *Fix:* add U+2060 and U+FEFF (not at offset 0), plus U+00AD and U+180E.

**S8. Git hardening in §3.2 rule 7.** It names only `core.fsmonitor` and `core.hooksPath`. *Fix:* also neutralise the pager (`--no-pager` / `GIT_PAGER=cat`), `diff.external`, `core.sshCommand` (only for network verbs Studio runs) and `protocol.ext.allow=never`. Set `GIT_CONFIG_NOSYSTEM` only if it doesn't break users. Note that `safe.directory` doesn't help: the repos are owned by the same user.

**S9. Some MUSTs are overkill for a solo v1. Downgrade them to SHOULD.**
- **Start budget** (N per 10 min, M per day, anomaly banner). Once M2's native confirmation is in place, each start needs a human click, so a rate limit adds little against XSS or automation. Keep "no batch start" and "global stop" as MUST.
- **"1M fuzz cases nightly"** and **"a real Windows + WSL runner"**. GitHub-hosted Windows runners don't support WSL2 nested virtualisation (the file's own risk #2). MUST = 10k property cases on every PR plus a mocked `wsl.exe`. The real round-trip is a release-checklist step on the owner's machine.
- **"Track harness H2 as a v1 release blocker."** H2 matters only for API-key users. Subscription users are bounded by the usage gate. *Fix:* H1 stays a blocker (it makes Studio's answer form decorative), and H2 becomes a blocker only if Studio exposes API-key configuration.
- The **150-string XSS corpus × every component in Playwright** is fine as MUST, but say it can start at around 50 strings and grow.

**S10. "Ship within 14 days" (#24) for DOMPurify and Tauri is fine. For Electron, say what drives it.** The renderer loads no remote content, so a Chromium n-day needs an XSS foothold first. E7's after score of 1×3 is consistent with that. Add one line: Tauri on Windows (WebView2 Evergreen) and macOS (WKWebView) is patched by the OS vendor, while Electron's window is the Electron release lag *plus* Studio's release lag *plus* the user's update lag. That is the real argument for Tauri on the n-day axis.

## Nice to have

- **N1.** Clipboard: "copy log" already excludes revealed secrets. Also strip bidi characters and C0 controls from any "copy command" button (pastejacking).
- **N2.** `gh` extension or alias hijack is a non-issue. Extensions and aliases can't shadow built-in commands. Say so in one line, so the reader knows it was considered, and always pass `--repo`, so `gh` never infers the repo from a hostile `.git/config` remote.
- **N3.** §3.9 says "Other users … can read". That is OS-dependent and worth stating:
  - macOS homes are `drwxr-x---+` with group `staff`, which every local user is in, so other accounts *can* traverse into `~/Work` (observed on this machine);
  - Ubuntu ≥ 21.04 homes are `0750` with a per-user group, so they can't.
- **N4.** §2b T5: the "6 WSA advisories in 2026" comes from 07. Cite the WebKitGTK security advisories page directly.

---

## Part B — Harness findings (§5), verified against `/Users/daniel/Work/devscene` @ `a1d0e992`

| ID | Grade | Evidence checked |
|---|---|---|
| **H1** | **Confirmed (config level), not yet measured.** Understated, see H1′ | See below |
| H2 | **Confirmed** | `autonomous-watcher.sh:3640-3648`: `claude -p … --settings --permission-mode … --add-dir`, with no `--max-budget-usd` or `--max-turns`. The only `--max-budget-usd` is the mention reader's (`remote-run.sh:1745` `MENTION_MAX_BUDGET_USD=1`, `:7618`). Concurrency: `autonomous-watcher.sh:1450-1453`. `timeout-minutes: 7200` at `devscene-run.yml:607`. Nit: `:2324` is the tunables `echo` line, not the usage gate itself |
| H3 | **Confirmed** | `stat`: `*.log` and `*.stream.jsonl` `0644`; `autonomous_inbox/`, `clarifications/` `0755`; `registry.json` `0600`. No `redact`/`add-mask` in the three scripts (grep). `retention-days: 400` at `devscene-run.yml:1075`. `.stream.jsonl` keeps `tool_result` bodies (`autonomous-format-stream.sh:13-20` describes what the `.log` drops) |
| H4 | **Confirmed** | `autonomous-watcher.sh:4751-4754` reads `pid`, checks it with `kill -0` only, and at `:4826-4831` runs `kill -9 "$pid"` + `kill -9 $descendants`. No `lstart`/`comm` check anywhere in the watcher (grep). The reliability framing is right: `registry.json` is write-denied |
| H5 | **Confirmed** | `devscene-run.yml:797` and `devscene-control.yml:342`: `npm install -g @anthropic-ai/claude-code` with no version, and **only `if ! command -v claude`**, so on a self-hosted runner any `claude` on PATH is used. Secrets in the same job (`devscene-run.yml:804-805`, `devscene-control.yml:381-383`). The plugin is cloned by `--branch "devscene--v$pin"` with only a `plugin.json` version-string check (`:347-379`). `npx --yes devscene@$DEVSCENE_CLI_VERSION` at `:768, :857, :1001` |
| H6 | **Confirmed** | The snapshot `printf` at `remote-run.sh:4653` names `$login` (the sender/labeller) and the time. The event fields read at `:4515-4524` have no `.issue.user.login`, `author_association` or `updated_at` (grep finds none in the file). One nuance for §3.4: the snapshot is the **event payload's** body, so the edit window is effectively zero on the harness side. The Studio-side window (re-fetch → label) remains |
| H7 | **Confirmed design**, inferred risk | `conversation.md` = the last `MENTION_COMMENTS_MAX=30` comments by anyone (`remote-run.sh:620-628`, `:1743`); "serve the commenter" is a prompt rule (`mention_reading.md:28-31`) |
| H8 | **Confirmed** | `prompt-injection-screen.sh:62-66`: SAFE = a ledger line in `flow_progress/<branch>_progress.md`, which is in the run copy and session-writable. Add: the screen is *run by the orchestrating session itself* (header "WHO RUNS IT"), which reinforces the "tripwire" framing |
| H9 | **Confirmed** | `settings.autonomous.json:48-51` (`grep`, `find`, `sed`, `awk`); denies at `:69-73` are `-D/-d/-M/-m` prefixes only |
| H10 | **Confirmed** | `harness-run-lib.sh:3525` `date '+%Y-%m-%dT%H:%M:%S'`, with no offset |
| H11 | **Confirmed** | `devscene-trigger.yml:152-153` and `devscene-control.yml:306-307` `echo "SCRIPTS_DIR=${scripts_dir%/}" >> "$GITHUB_ENV"`, unvalidated. The source is the default branch's config, so Info is the right grade |

**H1 in detail: confirmed at the configuration level.** Each link in the chain:
1. The **file tools** run outside the sandbox and are governed by `Edit` rules (template `_README` line 19). The base profile grants `Edit(/{{repoRoot}}/**)` (`cli/templates/claude/settings.autonomous.json:59`), rendered as `Edit(//Users/daniel/Work/devscene/**)`, and `Edit(/{{worktreeGlob}}/**)` (`:60`) → `Edit(//Users/daniel/Work/devscene-*/**)`.
2. The **sandbox** grants `allowWrite: ["{{stateDirAbs}}"]` (`:119`), which renders to `/Users/daniel/Work/devscene/harness-runs`. The watcher also passes `--add-dir "$main_state"` (`autonomous-watcher.sh:3647`), so the main state dir is a working directory of every session.
3. The inbox is `hr_state_path "$MAIN_REPO" autonomous_inbox` = `harness-runs/autonomous_inbox` (`autonomous-watcher.sh:1298`), and the kill switch is `harness-runs/AUTONOMOUS_STOP` (`:1300`). Both lie under (1) and (2).
4. The only state-dir entry in `deny`/`denyWrite` is `registry.json` (rendered `.claude/settings.autonomous.json:176` and `:256`).
5. The per-run render (`run_profile_render`, `autonomous-watcher.sh:2774-2846`) only **adds** `hr_run_protected_rel_paths`: githooks, `.mcp.json`, `.claude/settings.json`, `.claude/settings.local.json`, plus the docs-search launcher and lib (`harness-run-lib.sh:4151-4152`). There is nothing for `autonomous_inbox`, `clarifications/*/answer_*.md`, `RESUME`, `PAUSE` or `PARK_LOOP_CLEAR`.
6. The only Edit/Write hook is `git-trust-file-guard.sh` (`plugin/hooks/hooks.json`), which guards three `.git` trust files.
7. The intake `process_inbox_file` (`autonomous-watcher.sh:5133-`) checks the name pattern, branch validity and protection, the kill switch, the usage hold, the cap and duplicates. **It does not check who wrote the file.** The new run's prompt then goes through the PI screen, run by the new session itself.
8. Answers are `<worktree>/<state_rel>/clarifications/<branch>/answer_<n>.md` (`branch-answer.md:39-41`, watcher `:4303`), and `RESUME` is `<worktree>/<state_rel>/RESUME` (`:4026`, `:4563`). Both are in the run copy, which is the session's cwd.

So (a), (b) and (c) hold as written. (d) also holds: `Bash(find:*)` is allowed (`:49`), and the stop file is in the sandbox write root, so `find <stateDir> -name AUTONOMOUS_STOP -delete` is allowed. What is **not** established is runtime behaviour: whether Claude Code honours the `Edit` allow for a path in `--add-dir` under `dontAsk` exactly as the profile assumes. Risk #1's measurement plan is the right next step. I'd grade it "**confirmed by configuration, High**", not "inferred".

**H1′ (new, High): the grant is wider than the inbox.** The same two `Edit` allows reach:
- **(e) every sibling run copy** (`devscene-*/**`), so a compromised run can write `answer_<n>.md`, `RESUME` or `PARK_LOOP_CLEAR` into *another* parked or paused run's copy. That answers other runs' human checkpoints, not only its own.
- **(f) the main checkout's whole working tree** outside the protected list. That includes `.claude/CLAUDE.md`, which exists in this repo, plus `.claude/context/*.md` (conventions every agent loads), `.claude/agents|commands|skills/` if present, `package.json`, `.npmrc` and `node_modules/`. Those are read or executed **unsandboxed** by the owner's next *interactive* Claude session in the main checkout, by IDE tasks, and by any tool run there (see M4). This is a sandbox escape by persistence: none of it lands on the run's branch, so PR review never sees it.

*Suggested follow-up:* now that every run uses a clone (`copy_kind: clone`, `sandbox-verification.md` CS9), narrow `Edit(/{{repoRoot}}/**)` to the state-dir subtrees a session actually writes (`task_plans/`, `flow_progress/`, `run_analytics/` …). Deny `autonomous_inbox/**`, `AUTONOMOUS_STOP`, `PAUSE*`, `RESUME`, `clarifications/*/answer_*.md` and `PARK_LOOP_CLEAR`. Deny other sibling copies by exact path in the per-run render, which already enumerates live worktrees for `.git` pointers (`run_profile_entries`).

**H12 (new, Medium): `doctor` applies a repo-controlled env overlay to a spawned process.** `cli/src/doctor/checks.ts:6236-6251` merges `.mcp.json` → `mcpServers.<docs>.env` into the Python self-check's env. `LD_PRELOAD`, `PYTHONPATH` or `BASH_ENV` from a repo that the user only *inspects* with `doctor` becomes code execution. *Fix:* allow-list the overlay keys (`DATABASE_URL` and the documented retrieval keys only).

**Positive claims, all confirmed:**
- `permissions: {}` at workflow level: `devscene-trigger.yml:110`, `devscene-control.yml:259`, `devscene-run.yml:477`, `devscene-resume.yml:108`.
- All `uses:` are pinned by 40-hex SHA (grep, 17 occurrences).
- No `pull_request_target` in any workflow, only the comment at `devscene-control.yml:96`.
- `persist-credentials: false` at `devscene-run.yml:741, :1324`.
- The trigger job reads no secret (`devscene-trigger.yml:45-48`).
- Event text goes through `env:` only (`:64-70`).
- The job-surface step is at `devscene-run.yml:764`.
- The actor default is owner-only: `remote-run.sh:4366-4393`. Nuance to add: for an **org-owned** repo with `DEVSCENE_RUN_ACTORS` unset, it admits **nobody** (fail-closed), not the owner.
- `devscene-run.yml`'s own `workflow_dispatch` re-checks `github.triggering_actor` against `DEVSCENE_RUN_ACTORS` (`:509-534`), so a writer can't bypass the label gate by dispatching directly. Worth stating in §5.1.

**Other harness citations, spot-checked and correct:**
- `harness-run-lib.sh:3014-3035` (inbox refusal) and `:3532-3540` (tmp + lock + mv);
- `remote-run.sh:683-694` (fork-PR refusal, bot marker) and `:297-306` (dispatch sender);
- `prompt-injection-screen.sh:7-10` (tripwire).

---

## Part C — Third-party facts

Checked live on 2026-11-12 (`gh api` against source repos, plus the official docs).

### Must fix (wrong or outdated facts)

**M7. DOMPurify: "six 2026 bypass advisories", "≥ 3.4" and "default mode avoids them" are all wrong** (§TL;DR, §3.1, §4.1 #1, Q7).
- **The count.** `gh api repos/cure53/DOMPurify/security-advisories` lists **25** repository advisories published in 2026. The global advisory DB adds CVE-2026-0540 (GHSA-v2wj-7wpq-c8vv) and CVE-2025-15599, both published 2026-03-03.
- **Fixes landed after 3.4.0.** GHSA-r47g-fvhr-h676 was fixed in 3.4.6 and GHSA-rp9w-3fw7-7cwq in 3.4.7. 3.4.16 and 3.4.17 fix several more, including GHSA-cg2g, which the GHSA database rates critical.
- **A default-config bypass exists.** **GHSA-87xg-pxx2-7hvx** (CVE-2026-47423, high, "XSS via selectedcontent re-clone") hits plain `DOMPurify.sanitize(dirty)` on 3.4.4 and was fixed in 3.4.5.
- **Wrong fix version.** CVE-2026-0540 (rawtext, `SAFE_FOR_XML` regex) was fixed in 3.3.2 / 2.5.9, not 3.4.

*Fix:* "DOMPurify **≥ 3.4.17** (latest, 2026-10-12), with the floor raised on every advisory. 2026 brought about 25 advisories. Most need non-default options (IN_PLACE ≈ 10, SAFE_FOR_TEMPLATES + RETURN_DOM, CUSTOM_ELEMENT_HANDLING, hooks, ADD_TAGS predicates), but at least one (GHSA-87xg-pxx2-7hvx) bypassed the default configuration." Change the source [11] to the primary https://github.com/cure53/DOMPurify/security/advisories and the tag to [verified]. In 4.1 #1, change "≥ 3.4" to "latest, auto-tracked". This also makes the case for Trusted Types + CSP stronger, and the file should say so.

**M8. Chrome LNA does now gate WebSockets** (§2d tree, W3, risk #8, source [5]). The 2025-06 blog is outdated. ChromeStatus shows "LNA for WebSockets" (feature 5197681148428288) and WebTransport (5126430912544768) **shipping in Chrome 147**, with split `local-network`/`loopback-network` permissions in 145. WebRTC is still ungated. *Fix:*
- in W3, replace the text with: "Chrome ≥ 147 prompts before a public page opens a WebSocket to loopback. Chrome 142–146, Firefox and Safari don't gate it, so the Origin check on upgrade + token stays MUST";
- update risk #8 the same way.

L stays 3 before controls, because of Firefox/Safari and older Chrome.

### Should fix

**S11. Electron fuses: one recommended fuse is missing** (§2a MUST list). `@electron/fuses` (`src/config.ts`) also has `GrantFileProtocolExtraPrivileges`, which defaults to on. Electron's fuse doc says: "If you aren't serving pages from `file://`, you should disable this fuse." *Fix:* add `GrantFileProtocolExtraPrivileges=false`, since Studio loads from `app://`. Leave `EnableCookieEncryption` and `WasmTrapHandlers` optional. Change the tag from [secondary] to [verified]: https://github.com/electron/fuses.

**S12. electron-updater: the claim is right for the shipping line, but the quote and the version are not.** In released **6.8.12** (the GitHub "latest", npm dist-tag `v26`; npm `latest` is **6.8.11**, 2026-10-20), Linux checks only the manifest sha512 and has no verify hook. That supports the file's conclusion. But the quoted sentence ("The package is checked only against the sha512 in the update manifest") exists only on `master` (7.0.0-alpha.13). Master also adds an opt-in Ed25519 `updateManifestPublicKey`, a `verifyUpdateFile` hook (a stub by default) and `allowUnverifiedLinuxPackages` (default true). *Fix:* cite the 6.8.12 tag for the behaviour, and add: "7.0 (alpha) adds an opt-in manifest signature and verify hook. Adopt it when stable; it replaces the custom hook in §3.6." Also: `allowDowngrade` is documented as cross-channel only, but in code (`isUpdateAvailable`) it gates any older version, and setting `channel`/`allowPrerelease` sets it to `true`. Add "never set `channel` without resetting `allowDowngrade=false`".

**S13. The artifact-visibility claim (risk #3, H3, source [16]) can be made [verified].** The REST "Download an artifact" endpoint needs authentication. Anonymous `GET /repos/cli/cli/actions/artifacts/<id>/zip` returned **401**, while anonymous *listing* (`/actions/artifacts`) returned **200**. *Fix:* "On a public repo, artifact names and metadata are anonymous. Downloading needs any signed-in account (read access). Treat run logs as public." Replace the search-summary source with https://docs.github.com/en/rest/actions/artifacts#download-an-artifact.

**S14. `GITHUB_TOKEN` and workflow files (risk #4, [17]): use a primary source.** The `GITHUB_TOKEN` permission list (docs reusable `github-token-available-permissions`) has no `workflows` key. GitHub Apps have a separate "Workflows" repository permission (https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps#repository-permissions-for-workflows), and `GITHUB_TOKEN` is an installation token of the Actions app. The conclusion holds. Label it [verified, derived], not resting on two forum threads.

**S15. Risk #5 (`offline_access`) is correct, and so is 07. They are not in conflict.** Expiring user tokens are **on by default** ("enabled unless you opt out"). `offline_access` is a real, documented scope that forces expiry for an app that opted out ("The only supported value is `offline_access`"). PKCE: "Must be `S256`". *Fix:* resolve risk #5 as "both true; Studio's app keeps expiry on, so `offline_access` is not needed".

### Confirmed as written

- Trusted Types: MDN "Baseline 2026, newly available since February 2026". Firefox 148 and Safari 26. **WebKitGTK has had it on by default since 2.50.0** (2025-09-17). *Fix:* risk #7 and §3.1 can now say: "on in WebKitGTK ≥ 2.50; Ubuntu 22.04/24.04 ship it only if their webkit2gtk-4.1 security updates are at 2.50 or later. Check `doctor`."
- Tauri updater: a signature is mandatory and "cannot be disabled"; a lost key strands installs; downgrades need `version_comparator`; "TLS is enforced in production mode".
- `--end-of-options`: git 2.24.0 is correct. Add that **gh (pflag) supports only `--`, not `--end-of-options`**, which fits the file's "flag form for gh" rule. Make it explicit, so nobody adds `--end-of-options` to `gh` argv.
- `wsl.exe`: `--exec` means "without using the default Linux shell", and `--` means "pass the remaining command line as-is", which still goes through `$SHELL -c`. Exec mode re-parses with `CommandLineToArgvW` (`microsoft/WSL` `src/windows/common/WslClient.cpp`). The Learn page documents neither flag. Upgrade [13] from secondary to [verified] with the WSL repo's `Resources.resw` and `WslClient.cpp`. Knowing it is `CommandLineToArgvW` makes the round-trip test in §4.3 #2c mockable on any Windows runner, which also answers part of risk #2.
- GitHub App tokens: 8 h and 6 months, `expires_in` 28800.
- Electron 45.3.1 is the latest (supported lines 45, 44, 43). Tauri 2.12.5 (2026-10-21).
- npm trusted publishing: npm ≥ 11.5.1, Node ≥ 22.14.0, and "Require two-factor authentication and disallow tokens".
- Electron and Tauri capability quotes (checked: https://v2.tauri.app/security/capabilities/ on `AppManifest::commands`).

---

## Part D — Calibration and the v1 recommendation

- **The scores are mostly consistent.**
  - E1/T1 "after" = I2 depends on M2.
  - W1–W3 at L3 before controls is defensible for a public-repo user base.
  - E7's 2×3 before controls is high for a renderer with no remote content. 1×3 would match T5's reasoning ("needs E1/T1 first"), which is applied to Tauri but not to Electron.
- **The residual ordering (native ≈ Tauri < Electron < hosted < local web < hybrid) is reasonable,** with S6's caveat that hosted vs local web depends on whether you weigh per-user or aggregate impact. Tauri's edge over Electron rests on three things: OS-patched webviews (S10), the mandatory signed updater, and the narrower IPC. All three are sound.
- **The v1 recommendation (desktop shell, Tauri slightly ahead; local web as dev mode only; no hybrid) follows from the evidence.** It is not undermined by any finding here. Two things should be explicit preconditions in §6.2:
  - M2: native confirmation;
  - M3: no spawns in an untrusted repo.
- **MUSTs that are overkill for v1:** see S9 (rate-limit budget, 1M fuzz, a real WSL runner as a PR gate, H2 as a blocker for subscription users). The others are cheap and right.
- **Harness grades.** H1 + H1′ should be **High and a v1 blocker** for any Studio feature that answers or resumes runs: if a run can answer its own or a sibling's park, the answer form gives no real human checkpoint. H2 stays High for API-key users only. H12 should be Medium, a fix in the next devscene release.

## Finding counts

- **Must fix:** 8. App: M1–M6. Facts: M7, M8.
- **Should fix:** 15 (S1–S15).
- **Nice to have:** 4 (N1–N4).
- **New harness findings:** H1′ (High) and H12 (Medium).
- **H1–H11:** all confirmed. H1 is confirmed at the configuration level and still needs a runtime measurement.

---

## Review resolution

Applied to `08-security.md` on 2026-11-12 (header now `Status: reviewed`). Each finding was checked before it was applied: the harness claims against `/Users/daniel/Work/devscene` at `a1d0e992`, and the external facts live (`gh api`, `npm view`, `curl` against docs, ChromeStatus and the WSL source). App findings went into §1–§4 and §6, harness findings into §5 only.

### Part A — App findings

- **M1 — rejected.** The original class `[A-Za-z0-9._/-]` already contains `_` (between `.` and `/`). Tested with `grep -E`: `chore_devscene_env_variables` and `feat_x` both match the original regex. The parts that are cheap and right were still added to §3.2 rule 2 and §4.3 #2: no `@{`, no component starting with `.`, and real harness branch names as must-accept fixtures. The regex itself is unchanged.
- **M2 — applied.** The confirmation is now rendered by the privileged side: an OS-native modal from the main process or Rust core, never renderer HTML, and the renderer never passes `confirmed: true` (§3.10, Electron and Tauri MUST lists, §4.1 row 8). The local web app gets a payload-bound nonce, stated not to stop XSS (W6). The E1/T1 "after" scores now say "1×2 *only with a native confirmation*". H-1 notes that a browser has no such modal. It is a v1 precondition in §6.2 item 4 and in the TL;DR.
- **M3 — applied.** I verified `checks.ts:6230-6251` (env overlay), `:5883` (`npm view` with cwd in the repo), and that `hr_state_path` joins `stateDir` without a `..` check (`harness-run-lib.sh:3202-3215`). Changes: a new §1.3 row; a new §3.11 (Workspace-Trust-style gate, no spawn before trust, process cwd outside the repo per `sandbox-record.md` §6 residual 1.1, `stateDir`/`scriptsDir` validation); extended git hardening; a hostile-repo fixture (§4.3 #5); §4.1 row 26; and a v1 precondition (§6.2 item 9).
- **M4 — applied.** I verified that `package.json` and `node_modules/` exist in the main checkout and have no write deny, and that 05 line 76 uses `-- bash -ilc`. §3.2 rule 1 now requires absolute-path resolution from `$HOME`, refuses paths inside a repo or in a writable directory, and forbids `npx` with a repo cwd. It names 05's `bash -ilc` as the one allowed constant-string exception. Also §1.3 and §4.1 row 27.
- **M5 — applied, with one extension.** All ranges are now point ± 30%, the same in the TL;DR, §4.2, §4.4, Q1/Q2 and Q6. Native is given as a total for three apps plus a per-app figure. Tauri is stated as ≈ 0.5 O-d more than Electron up front, offset by a smaller recurring cost. *Extension:* the points themselves changed, because the review's own MUSTs add work (a new trust-gate row: M2, M3, M4, M6) and S9 removes some (start budget −0.25). New figures: Electron 5.5 (3.9–7.2), Tauri 6.0 (4.2–7.8), native 5.75 for three apps (4.0–7.5; ≈ 1.9 per app), local web 7.75 (5.4–10.1), hosted 8.5 (6.0–11.1) plus ops, hybrid 15.5 (10.9–20.2). §4.2 explains the changes.
- **M6 — applied.** I verified the bot-marker rule at `remote-run.sh:683-694`. Added a §1.3 row, a new §3.12, §4.1 row 28 and §6.2 item 10.
- **S1 — applied.** Added row E12 and the MUST (`standard, secure`, no `bypassCSP`, confined as in Electron's example, which I verified: `path.relative` + 400). A traversal test is in §4.3 #4.
- **S2 — applied.** Added a §1.3 row, §3.13 (no scheme in v1; any later one navigation-only) and §4.1 row 29.
- **S3 — applied.** I verified that `DEVSCENE_REMOTE_STOP` is read as `vars.DEVSCENE_REMOTE_STOP`. §3.10 and H-6 now say: with `gh` the user's own rights apply; in the hosted app, remote stop = cancel the workflow (Actions RW) plus an "open settings" link. No Variables permission added.
- **S4 — applied.** The §1.4 allowlist now lists the passthroughs (`SSH_AUTH_SOCK`, proxy and CA variables, gh config, `WSLENV`) and the explicit denies.
- **S5 — applied.** §3.3 now has a Windows paragraph: security-relevant reads happen inside WSL. It is also in §6.2 item 3 and Q5. Tagged [inferred], pending 04's WSL measurement.
- **S6 — applied.** The axis (per-user) is stated in the TL;DR. §4.4 has a note under the table and a "worst in aggregate" label on hosted.
- **S7 — applied.** I verified U+2060 and U+FEFF in `prompt-injection-screen.sh:34-38`. Added them, plus U+00AD and U+180E.
- **S8 — applied.** §3.2 rule 7 now uses `--no-pager`, `core.pager=cat`, `diff.external=`, `protocol.ext.allow=never`, and `core.sshCommand` on network verbs, with `GIT_CONFIG_NOSYSTEM` only if harmless and a note that `safe.directory` doesn't help. I tested the flag set on the harness repo; it works.
- **S9 — applied.** Each downgrade carries its reason:
  - start budget and anomaly banner → SHOULD for non-hosted modes (a native modal means no start without the human), still MUST server-side for hosted (§3.10, §4.1 row 9b);
  - 1M nightly fuzz → SHOULD, 10k per PR stays MUST;
  - real Windows + WSL runner → a release-checklist step, with a mocked `wsl.exe` (`CommandLineToArgvW`) as the CI MUST;
  - H2 → a v1 blocker only if Studio exposes API-key configuration, while H1 + H1′ stay blockers;
  - XSS corpus → starts at about 50 strings and grows.
- **S10 — applied.** Added the n-day exposure-window sentence to the Electron MUST list. Tauri's edge in §6.1 now names OS-patched webviews.
- **N1 — applied.** Added a "Copy buttons" row in §3.1.
- **N2 — applied.** §3.2 rule 3 says extensions and aliases can't shadow built-ins, and always pass `--repo`.
- **N3 — applied.** Added a §3.9 row. I observed macOS `drwxr-x---+ staff` on this machine; Ubuntu is tagged [inferred].
- **N4 — applied.** T5 now cites https://webkitgtk.org/security.html directly (WSA-2026-0001…0006, verified), as source 22.

### Part B — Harness findings (§5 only)

- **H1 — applied.** Marked "confirmed by settings analysis, runtime test pending" in the TL;DR, §5.2 and risk #1. I verified each link: `settings.autonomous.json:59-60, :119`; watcher `:1298-1300, :3647, :4026, :4303, :4563, :5133`; `harness-run-lib.sh:4140-4153`; rendered denies `:176, :256`. The test plan is kept and extended (a sibling `RESUME`, a `CLAUDE.md` append, the stop-file delete). The follow-up adopts the review's narrowing of `Edit(/{{repoRoot}}/**)`.
- **H1′ — applied.** It is a new §5.2 row (High) and in the TL;DR. I verified that the rendered deny list protects scripts, githooks, `.mcp.json`, `.claude/settings*.json`, `harness.config.json` and `.git`, but not `.claude/CLAUDE.md`, `.claude/context/`, `package.json` or `node_modules/`, all present in the harness repo. `.npmrc` is absent there, so it is named as possible, not present.
- **H12 — applied.** It is a new §5.2 row (Medium), placed in severity order after H6, and in the TL;DR. Studio's side is §3.11. I verified the code at `checks.ts:6230-6251`.
- **H2 nit (`:2324` is the tunables echo) — applied.** The text now says the tunables are echoed at `:2324`.
- **H8 addition (the screen is run by the session itself) — applied.** The line reference was also corrected to `:62-66`.
- **Positive-claim nuances (org-owned repo fail-closed; `devscene-run.yml` re-checks `triggering_actor`) — applied** to §5.1. I verified both in the code.
- **H3–H7, H9–H11 — no change needed** (confirmed as written).

### Part C — Third-party facts

- **M7 — applied.** I verified it live:
  - 25 repository advisories in 2026;
  - GHSA-87xg-pxx2-7hvx (high, default-config `selectedcontent`, fixed 3.4.5);
  - GHSA-r47g-fvhr-h676 fixed 3.4.6, GHSA-rp9w-3fw7-7cwq fixed 3.4.7;
  - CVE-2026-0540 fixed 3.3.2 / 2.5.9;
  - latest release 3.4.17 (2026-10-12).

  The floor is now ≥ 3.4.17, auto-tracked, everywhere. Source 11 now points to the primary advisories page, tagged [verified]. The case for TT + CSP is stated.
- **M8 — applied.** I verified on ChromeStatus that features 5197681148428288 (WebSockets) and 5126430912544768 (WebTransport) ship in 147. W3, the attack tree, risk #8 and source 5 are updated. *Partially:* I did not apply the review's "split permissions in 145" detail, because I could not confirm it.
- **S11 — applied.** I verified `GrantFileProtocolExtraPrivileges = 7` in `@electron/fuses` and the "If you aren't serving pages from `file://`…" quote. Source 21 is new.
- **S12 — applied.** I verified the dist-tags (`latest` 6.8.11, `v26` 6.8.12, `next` 7.0.0-alpha.13) and the `allowDowngrade` code (`isUpdateAvailable`, and set to true by `channel`). E6, source 9 and Q7 are updated. The "never set `channel` without resetting `allowDowngrade`" rule is in E6.
- **S13 — applied.** I verified anonymous list → 200 and zip download → 401 on `cli/cli`. H3, risk #3 and source 16 are updated.
- **S14 — applied.** I verified that the workflow-syntax `permissions` keys have no `workflows`. Risk #4 and source 17 are now [verified, derived], with the GitHub docs URLs replacing the forum threads.
- **S15 — applied.** I verified the doc text on default-on expiry, the opt-out, `offline_access` and `S256`. Risk #5 is resolved.
- **"Confirmed as written" notes — applied:**
  - `gh` rejects `--end-of-options` (observed: `unknown flag`);
  - WSL `CommandLineToArgvW` verified in `WslClient.cpp`, and source 13 upgraded to [verified].

  *Partially:* WebKitGTK Trusted Types from 2.50.0 is added but tagged [secondary], because the 2.50.0 release note I fetched doesn't mention it.

### Part D — Calibration

- **E7 before-score 2×3 → 1×3 — applied**, with T5's reasoning, as the review suggested.
- **M2/M3 as explicit §6.2 preconditions — applied** (items 4 and 9).
- **v1 recommendation — unchanged.** It is a desktop shell, with Tauri slightly ahead; the local web app only as an opt-in dev mode; hosted remote-only later; no hybrid in v1.
