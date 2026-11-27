#!/usr/bin/env bash
# commit-on-branch.sh — the deterministic commit wrapper every dispatched
# agent's unattended commit point calls (the run watcher's own artifact commit
# does not go through it: it calls `lib/harness-run-lib.sh` → `hr_commit_placed`
# directly): commit exactly the paths it was given, on the branch the target
# checkout has out, refuse a branch the main checkout's configuration protects,
# and take the message as ordinary positional arguments.
#
# WHY A WRAPPER EXISTS AT ALL. In an unattended run a command the profile does
# not allow is refused, and `git commit -m "$(…)"` is refused twice over: a
# command carrying a shell expansion (`$VAR` / `${…}` / `$(…)`) cannot be
# matched statically, so it reaches the commit branch-guard
# (`plugin/hooks/git-commit-branch-guard.sh`), which is fail-closed and answers
# `ask` for anything it could not read — and a `$(…)` in the message defeats a
# literal allow entry as well. An invocation of a SCRIPT PATH has neither
# problem: the generated permission profile allow-lists
# `bash <scripts_dir>/commit-on-branch.sh` in literal forms, and the commit
# guard's parser never matches it. A run in a run copy — a clone — calls the
# MAIN checkout's copy, `bash
# <main>/<scripts_dir>/commit-on-branch.sh --repo <run copy> …` (WHY THE MAIN
# CHECKOUT'S COPY RUNS OUTSIDE THE SANDBOX below); a session a person runs in a
# linked worktree they made by hand with `git worktree add` calls the main
# checkout's copy the same way, with `--repo <worktree>`. From a run copy the
# script-allowlist guard does not vouch for that copy, so the profile's literal
# `allow` entry is its only grant, and MESSAGE ARGUMENTS below states what that
# costs the caller. Either way the caller's command line
# carries NO heredoc and NO `$(…)`: the subject and every body paragraph are
# ordinary positional arguments.
#
# WHY THE MAIN CHECKOUT'S COPY RUNS OUTSIDE THE SANDBOX. A run's branch is the
# main checkout's `refs/heads/<branch>`, and a sandboxed git cannot move it: the
# permission profile write-denies the main checkout's whole `.git`, so a
# sandboxed commit in a clone lands on the clone's own ref alone
# (docs/sandbox-verification.md -> CL4; the whole-`.git` deny itself is row
# CS2, pass). A hand-made linked worktree is closed one step earlier: a sandboxed git
# cannot write a linked worktree's record, `<main>/.git/worktrees/<name>/`:
# `git add` and `git commit` there fail with `Operation not permitted` on
# `index.lock` (docs/sandbox-verification.md -> G1, G2 and F1, measured on
# Claude Code 2.1.299, macOS, headless). So the permission profile names the
# main checkout's copy in `sandbox.excludedCommands`, beside `push-branch.sh`
# and `refresh-branch.sh`, and an excluded command runs with full access. Every paragraph from THE
# TARGET IS NOT TRUSTED to NO FILTER DRIVER RUNS is what that access costs. A
# run copy's own `commit-on-branch.sh` sits in a sandbox-writable tree and is
# never excluded: in a clone it cannot move the main checkout's branch, and in
# a hand-made linked worktree it still fails on the record.
#
# SAFETY-CRITICAL CONSEQUENCE. Not reaching the commit branch-guard also means
# not reaching its protected-branch refusal, so this script MUST make that
# decision itself — and it makes it from the MAIN checkout's
# `devscene.config.json` at run time (THE TARGET'S `devscene.config.json` IS NOT
# TRUSTED EITHER below), through `lib/harness-run-lib.sh`, never from a list of
# branch names written into this file. A remembered list enforces the wrong set
# the moment `protectedBranches` changes, and enforces nothing at all in a
# repository whose integration branch is named something else. The library
# answers three states — protected, not protected, unresolvable — and all three
# are closed here.
#
# THE TARGET IS NOT TRUSTED. The profile's excluded rule ends in `:*`, which
# takes any argument. So before its first git call this script refuses (exit 1,
# a "refusing to commit:" line) unless the target is the main checkout this
# file sits in — placed from this file's own location by
# `lib/harness-run-lib.sh` → `hr_wrapper_main_of`, never from the argument — or
# a worktree that main repository lists (`hr_wrapper_target_check_var`). The
# reasoning and the residual are `push-branch.sh` → the paragraph of the same
# name.
#
# GIT NEVER RE-READS THE TARGET'S RECORDS. The checks read the target's `.git`
# pointer, its record's `commondir` and `gitdir`, and its `config.worktree`
# once (the reasoning: `push-branch.sh` → the paragraph of the same name). After
# them the branch is read once from the main checkout (`hr_wrapper_branch_var`)
# and named as `refs/heads/<branch>` from then on; every call that needs no
# working tree runs as `git -C <main checkout>`; and the calls that read the
# working tree (`ls-files`, `check-attr`, and the commit's index sync) run with
# `GIT_DIR=<main>/.git`, `GIT_INDEX_FILE=<record>/index` and
# `GIT_WORK_TREE=<target>`. So git reads nothing of the record but its `index`:
# not the `.git` pointer, not the record's `commondir`, `HEAD` or
# `config.worktree`. A `HEAD` flipped to another branch after the read is not
# followed: only `refs/heads/<branch>` moves.
#
# THE TARGET'S `devscene.config.json` IS NOT TRUSTED EITHER. A worktree's own
# copy is a tracked file in a sandbox-writable tree, so a sandboxed command
# could commit one whose `protectedBranches` drops the branch it is on. The
# protected set is read from the MAIN checkout's `devscene.config.json`, a file
# the permission profile write-protects, whichever checkout is the target; a
# main checkout whose configuration cannot be read is a refusal (exit 1), never
# a fall-back to the target's (`push-branch.sh` → the paragraph of the same
# name).
#
# THE PER-WORKING-COPY CONFIG IS NOT TRUSTED. Before its first git call this
# script refuses (exit 1) unless the target's `config.worktree` is absent,
# empty, or holds only the `core.hooksPath` `setup-worktree.sh` writes
# (`hr_worktree_config_check_var`); a refusal names each offending key and never
# its value. Every later git call pins `core.hooksPath` to the MAIN repository's
# hooks directory (`hr_pinned_hooks_path`) — exported as `GIT_CONFIG_COUNT` for
# the library's calls and spelled `-c core.hooksPath` on every call here — and
# carries `-c submodule.recurse=false` (the reasoning: `push-branch.sh` → the
# paragraph of the same name).
#
# A CLONE IS A TARGET TOO. The target may also be a run copy made as a clone,
# accepted only on the library's clone conditions (`lib/harness-run-lib.sh` →
# `hr_clone_target_check_var`). Those conditions accept only an empty, regular
# `config.worktree` with `extensions.worktreeConfig` off, which git never
# reads, and hold `.git/config` to an allow-list, so
# `hr_worktree_config_check_var` is skipped on that arm alone. The commit goes
# sync-in, operate, swap: after the protected-branch decision the main
# checkout takes the clone's `refs/heads/<branch>` (`hr_copy_sync_in_var`,
# which also heals a clone strictly behind it; a refusal reported as
# `refusing to commit:`, exit 1); the commit is then built in the main
# checkout exactly as for a worktree; and `hr_commit_paths_var` moves the
# clone's `refs/heads/<branch>` first and the main checkout's second
# (`hr_copy_ref_swap_var`). A commit landing in the clone after sync-in loses
# the clone's compare-and-swap with nothing moved on either side: the exit 1
# of a branch moved under this script. A main checkout's ref that cannot follow
# the clone's, with the clone's rollback failing too, is a second exit 1 after
# which the clone's `refs/heads/<branch>` has moved, reported on stderr as
# `committed <short_sha> on <branch>, but … — the commit stands`; the main
# checkout's ref follows on the next wrapper call's sync-in. Every refusal in
# this header holds on that arm too. `create-worktree.sh` creates such a
# clone.
#
# THE INHERITED GIT ENVIRONMENT IS DROPPED. As its first statement after
# sourcing the library, before any git call, this script drops through
# `lib/harness-run-lib.sh` → `hr_git_env_drop` the same `GIT_*` names
# `push-branch.sh` does, every `GIT_TRACE*` included, and keeps
# `GIT_SSH_COMMAND`; `PATH` and `BASH_ENV` are trusted as they arrive (the list
# and the reasoning: `push-branch.sh` → the paragraph of the same name). It sets
# `GIT_DIR`, `GIT_INDEX_FILE` and `GIT_WORK_TREE` itself afterwards, for the
# working-tree calls only.
#
# THE COMMIT IS BUILT FROM PLUMBING, AND NO COMMIT HOOK RUNS. A hook runs
# project content, which would run here with full access. The commit is
# `lib/harness-run-lib.sh` → `hr_commit_paths_var`'s, the same owner
# `hr_commit_placed` uses; this script owns only its paths and its messages. Its
# runners pin `core.hooksPath=/dev/null`, so no hook of any kind runs during the
# commit: not `pre-commit`, `prepare-commit-msg`, `commit-msg`, `post-commit`
# nor `reference-transaction`. This script's own git calls before it
# (`rev-parse`, `ls-tree`, `ls-files`, `check-attr`) carry the pinned `<main>`
# hooks directory, and none of them starts a hook. The message lands exactly as
# given, one paragraph per argument, because `commit-tree` does no clean-up.
# The identity is the main repository's configuration (`user.*`); the commit
# is unsigned, because `commit-tree` never reads `commit.gpgSign` and is passed
# no `-S`. The ref update is logged in `logs/refs/heads/<branch>` (reflog
# subject `commit-on-branch.sh: <subject>`), and no `logs/HEAD` entry is
# written for a linked worktree.
#
# NO FILTER DRIVER RUNS. Every blob is hashed under `hr_commit_paths_var`'s
# filter policy, so content is stored exactly as the working tree holds it:
# neither a clean filter nor an eol (`text` / `eol`) conversion is applied.
# Before hashing, this script refuses (exit 1) a path whose attributes select a
# `filter` (`check-attr`, read as data only), naming the path and never the
# driver: an LFS-tracked path is never committed raw without anyone noticing.
# Safety does not rest on that check — `--no-filters` holds even if the
# attributes are rewritten after it.
#
# LOUD-FAILURE CONTRACT (the KEY difference from push-branch.sh). push-branch.sh
# makes every failure non-fatal because a stale remote is tolerable. A commit
# caller cannot tolerate that ambiguity: if a commit did NOT land, the caller
# must NOT proceed as if it did. Exit-code map a caller can switch on, for the
# plain form (a front-end form's is THE RETURN below):
#
#   0  committed. Stdout is exactly
#      `commit-on-branch.sh: committed <short_sha> on <branch>`
#   1  a usage error / a non-git directory / a detached HEAD / a configuration
#      that cannot be resolved / a refused target or `config.worktree` / a
#      refused hooks pin / a branch starting with `-` / a branch with no commit
#      yet / a path whose attributes select a filter driver / a path reached
#      through a symbolic link, or that is neither a regular file nor a
#      symbolic link (a submodule, a special file) / a git failure / the branch
#      moving under this script / a commit that landed but whose working
#      copy's index could not take the committed paths, or, on a clone, that
#      landed on the clone's ref while the main checkout's could not follow (A
#      CLONE IS A TARGET TOO above) — the only exit 1 after which a
#      `refs/heads/<branch>` has moved, reported on stderr as
#      `committed <short_sha> on <branch>, but …`. Only the branch moving under
#      this script leaves the given paths staged, the same residue a failed
#      `git commit` left
#   2  protected-branch refusal, with nothing staged
#   3  nothing to commit: the given paths match the branch's tip. The paths are
#      still synced into the working copy's index, so a second call re-stages a
#      file reverted after a failed one
#
# Every refusal is one stderr line beginning `commit-on-branch.sh: refusing to
# commit: ` that names its reason, except four lines kept byte-identical:
# `detached HEAD — refusing to commit`, `'<dir>' is not a git repository —
# refusing to commit`, `branch '<branch>' is protected — refusing to commit`
# (followed by its `protected set` line) and `cannot resolve
# '<main>/devscene.config.json' — refusing to commit` (followed by its
# parenthesised causes). A usage error keeps its own line and its usage hint.
# The exit-1 `committed <short_sha> on <branch>, but …` line is not a refusal
# and does not begin with that prefix.
#
# WHAT IT NEVER DOES. The plain form never pushes (that is push-branch.sh,
# called as a SEPARATE statement — an `if …; then push; fi` block is a compound
# the guards do not cover, which an unattended run refuses) and never flips a
# plan checkbox; only a front-end form does either (THE TICK, THE PUSH). It
# never commits anything it was not given or, in a front-end form, did not
# derive (THE STAGE SET) — nothing the working copy had staged before is swept
# in. It never runs a commit hook, never runs a filter driver, and never
# retries a failed commit.
#
# STAGING POLICY. Only the explicit paths passed before
# `--` are committed, and the commit is exactly the branch's tip plus those
# paths as the working tree holds them. A path absent from the working tree
# that the tip holds, as a file or a directory, is committed as the removal of
# every blob the tip holds at or under it. A path absent from both is
# skip-with-warning rather than a hard error, and that tolerance is what lets
# callers pass their paths UNCONDITIONALLY: an optional-but-absent one (an empty
# per-finding folder, say) must not fail the commit, and a caller-side
# `if [ -d … ]; then` existence check would reintroduce the refusal described
# under WHY A WRAPPER EXISTS AT ALL — a shell conditional cannot be matched
# statically, so it reaches the fail-closed guards and an unattended run
# refuses it. Callers were deliberately stripped of those checks; do not
# restore one. The existence check is made against `<repo_top>/<path>`, never a
# cwd-relative path. A directory (not a symbolic link) stands for every path
# the tip holds under it plus every tracked or untracked, not ignored, path the
# working copy holds there — except a gitlink (a submodule), which is carried
# from the tip unchanged, and an untracked embedded repository, which is left
# out; anything else stands for itself.
#
# MESSAGE ARGUMENTS, AND THE BYTES ONE MAY NOT CARRY. The subject and every body
# line arrive as ordinary shell arguments, so none of them may carry `$(…)`, a
# backtick, `|`, `>`, `<`, or a braced expansion other than a bare `${IDENT}`.
# Two independent reasons, either one fatal on its own. THE SHELL: inside the
# caller's double quotes `$(…)` and a backtick are substituted before this
# script is reached, and any `$` spelling is expanded — so a `$`, a backtick or
# a placeholder meant as TEXT is not text by the time it lands. THE GUARD: the
# script-allowlist guard (`autonomous-script-allowlist-guard.sh`, shipped with the
# plugin)
# scans the WHOLE command string for `$(…)`, a backtick, `|`, `<`, a braced form
# other than a bare `${IDENT}`, and a `>` that is neither a descriptor
# duplication (`2>&1`, `>&2`, `2>&-`) nor a redirection to the literal
# `/dev/null`, and silences the invocation on a match, which, unattended, is the
# refusal described under WHY A WRAPPER EXISTS AT ALL.
# That scanned set is the set above minus the two `>` shapes a MESSAGE cannot
# be, which is why the rule here stays whole-byte for `>`. The guard reads the
# raw string, so quoting and escaping rescue nothing: `|`, `<` and a prose `>`
# are inert to the shell inside quotes and still silence the command, and an
# escaped backtick matches exactly as a bare one does. The ONE admitted
# expansion is a bare `${IDENT}`, bought back by the guard's narrowed `${` arm —
# but only for a call the guard vouches for. THE MAIN CHECKOUT'S COPY, called
# from a run copy, is granted only by the profile's literal `allow` entry, which
# a command carrying any shell expansion does not match: that caller spells its
# main checkout, its `--repo` and every message token literally, and its command
# carries no `$` at all. THIS SCRIPT ENFORCES NONE OF THIS: it validates no
# message, rewrites no message, and passes each one to the commit exactly as
# given. The constraint binds the CALLER, and the caller's own contract states
# what to do with a title that cannot satisfy it.
#
# THE UNIT AND ARTIFACT FORMS. Five front-end forms (the Usage block) let a
# commit point name WHAT it commits — a readiness unit or an artifact kind —
# instead of spelling a subject and a path set: `--unit task`,
# `--unit review_item`, `--unit review_plan_file`, `--unit ui_test_pass` and
# `--artifact <kind>`. Flags come in any order; a front-end call carries no
# `--`, no positional path and no free text, so every value is a repo-relative
# path, a closed token or a number and every call is a literal with no `$`.
# They are this wrapper rather than a new script so they add no excluded
# command and no profile entry: the literal `allow` entry and the
# `sandbox.excludedCommands` entry for the main checkout's copy already take
# any argument. Every check above runs first and unchanged — the target, the
# `config.worktree`, the configuration, the hooks pin, the branch, the
# protected set, the clone sync-in and the tip — so a protected branch exits 2
# with nothing ticked. The flags decide only what is staged inside a target
# those checks admitted; which target, which branch, the protected set and
# `stateDir` are read from the MAIN checkout (`hr_state_dir <main>`), never
# from an argument or the target's configuration. A usage error — a front-end
# flag beside `--`, `--unit` with `--artifact`, a flag its form does not take,
# a missing or non-numeric `--id` — is exit 1 with its own line and the usage
# hint. The subject and the paths come from `lib/unit-commit-lib.sh`, sourced
# beside `lib/harness-run-lib.sh`; an unreadable one is an exit 1 for every
# form.
#
# THE PLAN PATH IS NOT TRUSTED. The index is read and rewritten with full
# access, so before the first read this script refuses (exit 1, a `refusing to
# commit:` line naming the flag and never a file's content): a `--plan` that
# is absolute, has a `..` segment, does not sit under `<stateDir>/`, is reached
# through a symbolic link at any component under the target, or is not a
# regular file; a `--findings`, `--extra` or `--path` that is absolute or has
# a `..` segment; a `--findings` or `--extra` outside `<stateDir>/`; an index
# the library cannot classify; and an index whose kind the unit does not take
# (`task` takes a story index, `ui_test_pass` a UI-test index, `review_item`
# and `review_plan_file` every review index). A detail file reached through a
# symbolic link is refused the same way before its cause is read. Residual: a
# component swapped for a link between the check and the tick is followed.
#
# THE TICK. `task`, `review_item` and `ui_test_pass` find the entry by `--id`
# inside the readiness section alone (`Task K` in a story index, `Test K` in a
# UI-test index, `Finding K` otherwise) and turn that one entry's `[ ]` into
# `[x]`, every other byte unchanged, through a temporary file beside the index
# and `mv` (`ucl_tick`). No entry is `error: --id K matched no readiness
# entry in <plan>`, exit 1. The tick is the last step before the commit: every
# refusal above it leaves the index untouched, and a commit refused after it
# restores the index from a copy taken first. An entry already `[x]` is not
# edited; on `ui_test_pass` it is `noop: UI test K already marked`, exit 0,
# no commit and no push.
#
# THE STAGE SET. For `task` and `review_item` it is read through the commit's
# own `GIT_DIR` / `GIT_INDEX_FILE` / `GIT_WORK_TREE` triple against
# `refs/heads/<branch>`'s tip — `diff --name-status -z --no-renames <tip>`
# and `ls-files -z --others --exclude-standard` — never `git status`, which
# compares against the main checkout's `HEAD`. The library turns that listing
# into the plan, `--findings` and every changed path, a deletion staged as the
# deleted path (STAGING POLICY), the `--findings` folder staged whole and
# its contents excluded from the work files (`ucl_stage_set`). An already-`[x]`
# entry with nothing changed is `error: nothing to commit`, exit 3.
# `review_plan_file` stages the plan, its findings folder and `--extra`;
# `ui_test_pass` the plan; `--artifact` its table's paths, or for
# `rescreened-input` the `--path` values, at least one. The resulting list goes
# through the same staging loop and commit as the plain form's paths, so
# every path refusal, the filter-driver refusal and the no-hook commit hold.
#
# THE SUBJECT AND ITS RECORD. Built by the library from the index and its
# artifact table, never from the command line: `<prefix>: <label> — <title>`
# at most 72 bytes for a unit (`ucl_unit_prefix`, `ucl_unit_label`,
# `ucl_short_title`, `ucl_subject`), the fixed forms for `review_plan_file`,
# `ui_test_pass` and every artifact kind. `--prefix` is taken only by
# `review_item`, and the library refuses it on any entry but a user-review
# Should Fix. At most one body line, in this precedence: `record disposition
# of <token> — <cause>`, `mark <token> already passing — <cause>`, `mark
# <token> done — <set>` when no work file was staged (`ucl_body_record`). The
# cause is read from the `**Cause:** ` line of the detail file `ucl_detail_file`
# names, only when that file is in the stage set, and never from an argument.
#
# THE RETURN. A front-end form prints, on stdout in place of the plain form's
# `committed` line, `commit_sha:` (the full id), `subject:`,
# `files_committed:` (the paths the commit changes against the old tip),
# `plan_flipped:` (the ticked entry line, `already-[x]: <entry> — not flipped
# by this call`, or `none`) and `pushed:` (`yes`, `no` or `failed`); then
# `staged: index-only — <set> was the whole diff; no work file was staged` when
# a `task` / `review_item` staged no work file, and `index_sync: failed —
# <exit>, <last stderr line>` when a re-sync failed. Exits: 0 committed, or a
# landed exit 1 already re-synced, or a `noop:`; 1 a refusal or a failure; 2
# the protected branch; 3 `error: nothing to commit`. Every non-zero outcome
# prints one `error: <the refusal line without its script prefix>` on stdout,
# and the plain form's stderr lines are kept. A landed exit 1 — the commit
# stands, the index could not take it — runs ONE identical plain-form call of
# this script as a child to re-sync the index and exits 0; anything but that
# call's exit 3 adds the `index_sync:` line.
#
# THE PUSH. `--push` runs `bash <this directory>/push-branch.sh <target>` as a
# child after exit 0 or exit 3, never after a refusal, so a commit point is
# one call and a resumed run's earlier unpushed commit still reaches the
# remote; its output goes to stderr. `pushed: failed` when the child exits
# non-zero or prints a failure line of push-branch.sh's EVERY FAILURE PATH IS
# NON-FATAL (exit 0): one carrying `refusing to push`, ending `— nothing to
# push`, `push failed for <branch>: …` or `… attempts (see output above)`, or
# `no longer has`; else `yes`. Without `--push`, `no`.
#
# Usage: commit-on-branch.sh [--repo <repo-dir>] <path>... -- <subject> [<body-line>...]
#        bash <main checkout>/<scripts_dir>/commit-on-branch.sh --repo <run copy> <path>... -- <subject>
#        commit-on-branch.sh --repo <root> --unit task --plan <index> --id <K> [--findings <dir>] [--push]
#        commit-on-branch.sh --repo <root> --unit review_item --plan <index> --id <K> [--findings <dir>] [--prefix refactor|chore] [--push]
#        commit-on-branch.sh --repo <root> --unit review_plan_file --plan <index> [--extra <dir>] [--push]
#        commit-on-branch.sh --repo <root> --unit ui_test_pass --plan <index> --id <K> [--push]
#        commit-on-branch.sh --repo <root> --artifact <kind> [--round <n>] [--iteration <k>] [--entry <id>] [--path <p>]... [--push]
#   --repo <repo-dir>  the main checkout, a run copy (a clone), or a linked
#                      worktree made by hand, to operate in (default: $PWD)
#   <path>...          explicit paths to commit (before `--`); missing paths warn+skip
#   --                 separates the path list from the message lines
#   <subject>          first token after `--` — the commit subject; see
#                      MESSAGE ARGUMENTS for the bytes it may not carry
#   <body-line>...     each remaining token — one additional body paragraph,
#                      under that same constraint
#   The second form, the main checkout's copy aimed at a run copy or a
#   hand-made linked worktree, is the one the permission profile runs
#   unsandboxed.
#
# REPRO — reproduce any decision by hand, against a throwaway fixture:
#
#   d=$(mktemp -d); git -C "$d" init -q -b feat_x
#   printf '%s' '{"version":1,"defaultBranch":"trunk","protectedBranches":["trunk","release/*"],"stateDir":"devscene/","layers":[],"commands":{}}' > "$d/devscene.config.json"
#   mkdir -p "$d/scripts"; cp -R <this script> <its lib/> "$d/scripts/"
#   git -C "$d" add -A && git -C "$d" commit -qm seed
#   printf 'x\n' > "$d/f.txt"
#   # `commit-on-branch.sh` below is `bash "$d/scripts/commit-on-branch.sh"`: a
#   # copy outside the checkout it is aimed at refuses (THE TARGET IS NOT TRUSTED).
#
#   ordinary branch   commit-on-branch.sh --repo "$d" f.txt -- "feat: x" "body"
#                     -> exit 0, prints the new short SHA
#                     re-run with nothing changed                     -> exit 3
#   protected branch  git -C "$d" checkout -q -b trunk; same call     -> exit 2,
#                     and `git -C "$d" status --porcelain` is unchanged
#   not in the set    git -C "$d" checkout -q -b main; printf 'y\n' >> "$d/f.txt";
#                     same call -> exit 0 (the set is configured, not remembered)
#   unresolvable      printf 'x' > "$d/devscene.config.json"; same call -> exit 1,
#                     no commit; then `git -C "$d" checkout -q -- devscene.config.json`
#   deleted path      rm "$d/f.txt"; passing `f.txt` -> exit 0, and
#                     `git -C "$d" ls-files f.txt` prints nothing
#   absent path       passing a path neither the tip nor the working tree
#                     holds -> a "skipping" line, exit 3
#   no commit hook    mkdir -p "$d/githooks"; git -C "$d" config core.hooksPath githooks
#                     printf '%s\n' '#!/bin/sh' "touch $d.hook" > "$d/githooks/pre-commit"
#                     chmod +x "$d/githooks/pre-commit"; printf 'z\n' > "$d/h.txt"
#                     commit-on-branch.sh --repo "$d" h.txt -- "feat: h" -> exit 0,
#                     and no "$d.hook"
#   a filtered path   printf 'h.txt filter=marker\n' > "$d/.gitattributes"
#                     git -C "$d" config filter.marker.clean "touch $d.filter; cat"
#                     printf 'w\n' >> "$d/h.txt"; the call above -> exit 1, a
#                     "refusing to commit: 'h.txt' selects a filter driver" line,
#                     and no "$d.filter"; then `rm "$d/.gitattributes"`
#
#   The main checkout's copy committing in a linked worktree:
#   w=$(mktemp -d)/wt; git -C "$d" worktree add -q -b feat_w "$w"
#   printf 'g\n' > "$w/g.txt"
#
#   a worktree        commit-on-branch.sh --repo "$w" g.txt -- "feat: g" "body"
#                     -> exit 0; `git -C "$w" status --porcelain` is empty, and
#                     `git -C "$w" log -1 --pretty=%B` shows "feat: g", a blank
#                     line, then "body"
#   a scratch repo    s=$(mktemp -d); git -C "$s" init -q -b feat_s
#                     git -C "$s" commit -qm s --allow-empty; printf 's\n' > "$s/s.txt"
#                     commit-on-branch.sh --repo "$s" s.txt -- "feat: s"
#                     -> exit 1, a "refusing to commit:" line,
#                     `git -C "$s" rev-parse HEAD` unchanged
#   a planted monitor git -C "$w" config extensions.worktreeConfig true
#                     git -C "$w" config --worktree core.fsmonitor "touch $s.marker"
#                     printf 'g2\n' >> "$w/g.txt"; the "a worktree" call
#                     -> exit 1, a "refusing to commit:" line naming
#                     core.fsmonitor and not its value, and no "$s.marker"
#
#   The front-end forms, in the worktree (stateDir `devscene/`):
#   mkdir -p "$w/devscene/story_plans" "$w/devscene/code_reviews" "$w/devscene/ui_test_plans"
#   printf '## Phase 2 Readiness — Ordered Fix List\n\n1. [ ] **Task 1** — Add x _(layer: cli)_\n' > "$w/devscene/story_plans/feat_w_story_plan.md"
#   printf 'x\n' > "$w/x.txt"
#
#   task              commit-on-branch.sh --repo "$w" --unit task --plan devscene/story_plans/feat_w_story_plan.md --id 1
#                     -> exit 0, `subject: feat: Task 1 — Add x`, the entry ticked
#                     same call again                                 -> exit 3,
#                     `error: nothing to commit`
#   review_item       printf '## Phase 2 Readiness — Ordered Fix List\n\n1. [ ] **Finding 1** — Fix y\n' > "$w/devscene/code_reviews/feat_w_review.md"
#                     … --unit review_item --plan devscene/code_reviews/feat_w_review.md --id 1
#                     -> `subject: fix: Code review finding 1 — Fix y`
#   review_plan_file  … --unit review_plan_file --plan devscene/code_reviews/feat_w_review.md
#                     -> `subject: chore: add code review for feat_w`
#   ui_test_pass      printf '## Phase 2 Readiness — Ordered Fix List\n\n1. [ ] **Test 1** — Log in\n' > "$w/devscene/ui_test_plans/feat_w_ui_test_plan.md"
#                     … --unit ui_test_pass --plan devscene/ui_test_plans/feat_w_ui_test_plan.md --id 1
#                     -> `subject: chore: Mark UI test 1 passing for feat_w`;
#                     again -> `noop: UI test 1 already marked`, exit 0
#   artifact          … --artifact ledger-flip --entry P1
#                     -> `subject: chore: Flow progress P1 for feat_w`
#   usage errors      … --unit task --plan <index> --id 1 -- "x"; --unit task
#                     --artifact ledger; --unit task --plan <index> --extra d;
#                     --unit task --plan <index> --id one   -> exit 1 each
#   untrusted plan    --plan /etc/hosts; --plan devscene/../x.md; --plan x.md;
#                     --plan through a symbolic link; --plan a directory;
#                     --findings /tmp; --findings x/; --extra ../d; --path /etc;
#                     --plan devscene/other/x.md (unclassified); --unit task
#                     --plan devscene/code_reviews/feat_w_review.md (kind)
#                     -> exit 1 each, a "refusing to commit:" line, the index
#                     and `refs/heads/feat_w` unchanged

set -uo pipefail

# The library is reached by a path computed from this script's own location, so
# a copy that was moved with its `lib/` still finds it, and no session root or
# runtime-substituted token is assumed.
hr_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/harness-run-lib.sh"
if [ ! -r "$hr_lib" ]; then
  echo "commit-on-branch.sh: cannot read '$hr_lib' — refusing to commit" >&2
  exit 1
fi
# shellcheck source=lib/harness-run-lib.sh
. "$hr_lib"
ucl_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/unit-commit-lib.sh"
if [ ! -r "$ucl_lib" ]; then
  echo "commit-on-branch.sh: cannot read '$ucl_lib' — refusing to commit" >&2
  exit 1
fi
# shellcheck source=lib/unit-commit-lib.sh
. "$ucl_lib"
# THE INHERITED GIT ENVIRONMENT IS DROPPED (header). GIT_SSH_COMMAND is kept.
hr_git_env_drop

repo_dir="$PWD"

# THE RETURN (header): in a front-end form every refusal also prints one
# `error:` line on stdout, and a refusal after the tick restores the index.
fe=0
tick_backup=""
fe_untick() {
  local file dir tmp
  [ -n "$tick_backup" ] || return 0
  tick_backup=""
  file="$top/$plan_rel"
  dir="${file%/*}"
  tmp=$(mktemp "$dir/.ucl-untick.XXXXXX") \
    && cp -p "$work/plan.orig" "$tmp" && mv "$tmp" "$file" \
    || { rm -f "${tmp-}"; echo "commit-on-branch.sh: could not restore '$plan_rel' after the refusal below; its entry stays ticked" >&2; }
}
# fail <exit> <line> [<continuation-line>...]
fail() {
  local code="$1" line="$2"
  shift 2
  fe_untick
  printf '%s\n' "$line" >&2
  [ "$#" -eq 0 ] || printf '%s\n' "$@" >&2
  [ "$fe" -eq 0 ] || printf 'error: %s\n' "${line#commit-on-branch.sh: }"
  exit "$code"
}
FE_USAGE="  usage: commit-on-branch.sh [--repo <dir>] <path>... -- <subject> [<body-line>...]
         commit-on-branch.sh [--repo <dir>] --unit task|review_item|review_plan_file|ui_test_pass --plan <index> [--id <K>] [--findings <dir>] [--extra <dir>] [--prefix refactor|chore] [--push]
         commit-on-branch.sh [--repo <dir>] --artifact <kind> [--round <n>] [--iteration <k>] [--entry <id>] [--path <p>]... [--push]"
fe_usage() {
  fail 1 "commit-on-branch.sh: $1" "$FE_USAGE"
}

# --- Parse args: optional --repo, then <path>... up to `--`, then message
# lines; or the front-end flags, in any order (THE UNIT AND ARTIFACT FORMS).
paths=()
msgs=()
saw_sep=0
fe_seen=" "
opt_unit="" opt_artifact="" opt_plan="" opt_id="" opt_findings="" opt_extra=""
opt_prefix="" opt_round="" opt_iteration="" opt_entry="" opt_push=0
opt_paths=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      if [ "$#" -lt 2 ]; then
        fail 1 "commit-on-branch.sh: --repo requires a directory argument"
      fi
      repo_dir="$2"
      shift 2
      ;;
    --push)
      fe=1
      case "$fe_seen" in *" --push "*) fe_usage "--push is given twice" ;; esac
      fe_seen="$fe_seen--push "
      opt_push=1
      shift
      ;;
    --unit | --artifact | --plan | --id | --findings | --extra | --prefix | --round | --iteration | --entry | --path)
      fe=1
      [ "$#" -ge 2 ] || fe_usage "$1 requires a value"
      if [ "$1" != --path ]; then
        case "$fe_seen" in *" $1 "*) fe_usage "$1 is given twice" ;; esac
      fi
      fe_seen="$fe_seen$1 "
      case "$1" in
        --unit) opt_unit="$2" ;;
        --artifact) opt_artifact="$2" ;;
        --plan) opt_plan="$2" ;;
        --id) opt_id="$2" ;;
        --findings) opt_findings="$2" ;;
        --extra) opt_extra="$2" ;;
        --prefix) opt_prefix="$2" ;;
        --round) opt_round="$2" ;;
        --iteration) opt_iteration="$2" ;;
        --entry) opt_entry="$2" ;;
        --path) opt_paths+=("$2") ;;
      esac
      shift 2
      ;;
    --)
      saw_sep=1
      shift
      break
      ;;
    *)
      paths+=("$1")
      shift
      ;;
  esac
done

if [ "$fe" -eq 1 ]; then
  # THE UNIT AND ARTIFACT FORMS (header): usage, settled before any check.
  [ "$saw_sep" -eq 0 ] || fe_usage "a front-end flag cannot be combined with '--' and a message"
  [ "${#paths[@]}" -eq 0 ] || fe_usage "a front-end call takes no positional path ('${paths[0]}'); --artifact rescreened-input takes --path"
  if [ -n "$opt_unit" ] && [ -n "$opt_artifact" ]; then
    fe_usage "--unit and --artifact cannot be combined"
  fi
  case "$fe_seen" in
    *" --unit "* | *" --artifact "*) ;;
    *) fe_usage "a front-end flag needs --unit or --artifact" ;;
  esac
  case "$opt_unit" in
    task) fe_takes=" --unit --plan --id --findings --push " ;;
    review_item) fe_takes=" --unit --plan --id --findings --prefix --push " ;;
    review_plan_file) fe_takes=" --unit --plan --extra --push " ;;
    ui_test_pass) fe_takes=" --unit --plan --id --push " ;;
    '')
      [ -n "$opt_artifact" ] || fe_usage "--artifact needs a kind"
      fe_takes=" --artifact --round --iteration --entry --push "
      [ "$opt_artifact" != rescreened-input ] || fe_takes="$fe_takes--path "
      ;;
    *) fe_usage "--unit takes task, review_item, review_plan_file or ui_test_pass, not '$opt_unit'" ;;
  esac
  for fe_flag in $fe_seen; do
    case "$fe_takes" in
      *" $fe_flag "*) ;;
      *)
        if [ -n "$opt_unit" ]; then
          fe_usage "$fe_flag is not taken by --unit $opt_unit"
        else
          fe_usage "$fe_flag is not taken by --artifact $opt_artifact"
        fi
        ;;
    esac
  done
  if [ -n "$opt_unit" ]; then
    [ -n "$opt_plan" ] || fe_usage "--unit $opt_unit needs --plan <index>"
  fi
  case "$opt_unit" in
    task | review_item | ui_test_pass)
      case "$opt_id" in
        '') fe_usage "--unit $opt_unit needs --id <K>" ;;
        *[!0-9]*) fe_usage "--id '$opt_id' is not a number" ;;
      esac
      ;;
  esac
  case "$fe_seen" in
    *" --prefix "*)
      case "$opt_prefix" in
        refactor | chore) ;;
        *) fe_usage "--prefix takes refactor or chore, not '$opt_prefix'" ;;
      esac
      ;;
  esac
  if [ "$opt_artifact" = rescreened-input ] && [ "${#opt_paths[@]}" -eq 0 ]; then
    fe_usage "--artifact rescreened-input needs at least one --path"
  fi
else
  if [ "$saw_sep" -ne 1 ]; then
    echo "commit-on-branch.sh: missing '--' separator before the commit message" >&2
    echo "  usage: commit-on-branch.sh [--repo <dir>] <path>... -- <subject> [<body-line>...]" >&2
    exit 1
  fi

  # Everything after `--` is the message: the first token is the subject, the
  # rest are additional body paragraphs.
  while [ "$#" -gt 0 ]; do
    msgs+=("$1")
    shift
  done

  # An empty subject is refused here because `commit-tree`, unlike `git
  # commit`, would record it.
  if [ "${#msgs[@]}" -eq 0 ] || [ -z "${msgs[0]}" ]; then
    echo "commit-on-branch.sh: no commit subject after '--'" >&2
    exit 1
  fi
fi

# THE TARGET IS NOT TRUSTED and THE PER-WORKING-COPY CONFIG IS NOT TRUSTED
# (header): settled before the first git call, each function called directly so
# its variables survive. A non-git directory keeps its loud non-zero error.
top_nogit="$(hr_checkout_top_nogit "$repo_dir")" || top_nogit=""
if [ -z "$top_nogit" ]; then
  fail 1 "commit-on-branch.sh: '$repo_dir' is not a git repository — refusing to commit"
fi
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! main_top="$(hr_wrapper_main_of "$script_dir")"; then
  fail 1 "commit-on-branch.sh: refusing to commit: cannot place this script in a main checkout (its .git is a symbolic link, or a directory holding a commondir)"
fi
# Fail closed: a configuration that cannot be read is a branch that cannot be
# judged. Loaded unsubstituted, so the clone arm's registry lookup, the pin and
# the protected-branch decision below read the warmed cache. It runs ahead of
# the target check, so a clone target gets this refusal rather than the clone
# arm's registry sentence, and ahead of the pin, so it is not the pin's either.
# It reads only `<main_top>/devscene.config.json` and makes no git call.
if ! hr_config_load "$main_top"; then
  fail 1 "commit-on-branch.sh: cannot resolve '$main_top/devscene.config.json' — refusing to commit" \
    "  (no configuration there, invalid JSON, more than one document, no defaultBranch, or jq missing/older than 1.5)"
fi
if ! hr_wrapper_target_check_var "$main_top" "$top_nogit"; then
  fail 1 "commit-on-branch.sh: refusing to commit: $HR_TARGET_REFUSAL"
fi
wt_gitdir="$HR_TARGET_GITDIR"
# A CLONE IS A TARGET TOO (header): the clone arm judged its configuration.
if [ "$HR_TARGET_KIND" != clone ] && ! hr_worktree_config_check_var "$top_nogit"; then
  fail 1 "commit-on-branch.sh: refusing to commit: $HR_WT_CONFIG_REFUSAL"
fi
if ! hr_pinned_hooks_path "$main_top"; then
  if [ -n "$HR_PINNED_HOOKS_REFUSAL" ]; then
    fail 1 "commit-on-branch.sh: refusing to commit: $HR_PINNED_HOOKS_REFUSAL"
  else
    fail 1 "commit-on-branch.sh: refusing to commit: could not resolve the hooks directory to pin for '$top_nogit'"
  fi
fi
pinned="$HR_PINNED_HOOKS_PATH"
# Pins the library helpers' git calls below; every call spelled here also
# carries `-c`, which an older git than 2.31 still honours.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$pinned"

# GIT NEVER RE-READS THE TARGET'S RECORDS (header).
top="$top_nogit"
main_git() {
  git -C "$main_top" -c core.hooksPath="$pinned" -c submodule.recurse=false "$@"
}
wt_git() {
  GIT_DIR="$main_top/.git" GIT_INDEX_FILE="$wt_gitdir/index" GIT_WORK_TREE="$top" \
    git -C "$top" -c core.hooksPath="$pinned" -c submodule.recurse=false "$@"
}

# Read once, from the main checkout, and named as `refs/heads/<branch>` from
# here on.
if ! hr_wrapper_branch_var "$main_top" "$wt_gitdir"; then
  fail 1 "commit-on-branch.sh: detached HEAD — refusing to commit"
fi
branch="$HR_WRAPPER_BRANCH"
case "$branch" in
  -*)
    fail 1 "commit-on-branch.sh: refusing to commit: branch '$branch' starts with '-', which git would read as an option"
    ;;
esac

# THE TARGET'S `devscene.config.json` IS NOT TRUSTED EITHER (header): the
# protected-branch decision is the main checkout's. Called unsubstituted so the
# library's per-process cache is warmed here and the `$(hr_protected_patterns …)`
# in the refusal message below re-reads nothing.
hr_branch_is_protected "$main_top" "$branch"
protected=$?
case "$protected" in
  0)
    # Name the resolved set as well as the branch: the adopter configured it, so
    # a refusal that only names the branch cannot be acted on.
    patterns="$(hr_protected_patterns "$main_top")" || patterns=""
    protected_set=""
    while IFS= read -r pattern; do
      [ -n "$pattern" ] || continue
      if [ -z "$protected_set" ]; then
        protected_set="$pattern"
      else
        protected_set="$protected_set $pattern"
      fi
    done <<EOF
$patterns
EOF
    fail 2 "commit-on-branch.sh: branch '$branch' is protected — refusing to commit" \
      "  protected set (from devscene.config.json): $protected_set"
    ;;
  2)
    # Fail closed: a configuration that cannot be read is a branch that cannot
    # be judged.
    fail 1 "commit-on-branch.sh: cannot resolve '$main_top/devscene.config.json' — refusing to commit" \
      "  (no configuration there, invalid JSON, more than one document, no defaultBranch, or jq missing/older than 1.5)"
    ;;
esac

# A CLONE IS A TARGET TOO (header): sync in before the branch's tip is read; a
# no-op on the main checkout and a worktree.
if ! hr_copy_sync_in_var "$main_top" "$HR_TARGET_GITDIR" "$branch"; then
  fail 1 "commit-on-branch.sh: refusing to commit: $HR_SYNC_REFUSAL"
fi

# The tip the commit is built on, read once: the ref moves only if it still
# points here.
old_tip="$(main_git rev-parse --verify --quiet "refs/heads/$branch^{commit}")" || old_tip=""
if [ -z "$old_tip" ]; then
  fail 1 "commit-on-branch.sh: refusing to commit: '$branch' has no commit yet in '$main_top'"
fi

# The path lists are NUL-separated files, because a path may hold any byte but
# NUL; the directory goes with this process.
if ! work="$(mktemp -d "${TMPDIR:-/tmp}/commit-on-branch.XXXXXX")"; then
  fail 1 "commit-on-branch.sh: refusing to commit: cannot create a temporary directory"
fi
trap 'rm -rf "$work"' EXIT
: >"$work/paths"

plan_rel=""
plan_flipped=none
staged_line=""
if [ "$fe" -eq 1 ]; then
  # THE TARGET'S `devscene.config.json` IS NOT TRUSTED EITHER (header):
  # `stateDir` is the main checkout's.
  state_dir="$(hr_state_dir "$main_top")" || state_dir=""
  [ -n "$state_dir" ] || fail 1 "commit-on-branch.sh: refusing to commit: cannot read stateDir from '$main_top/devscene.config.json'"

  # ucl <function> <arg>... — a library call whose cause, on a non-zero
  # status, becomes UCL_ERR; run in this shell so its UCL_* globals survive.
  ucl() {
    local rc=0
    "$@" 2>"$work/ucl.err" || rc=$?
    UCL_ERR=""
    if [ -s "$work/ucl.err" ]; then
      cat "$work/ucl.err" >&2
      UCL_ERR="$(tail -n 1 "$work/ucl.err")"
      UCL_ERR="${UCL_ERR#unit-commit-lib: }"
    fi
    return "$rc"
  }
  # THE PLAN PATH IS NOT TRUSTED (header). fe_rel <flag> <value> — FE_REL, the
  # value with no empty or `.` segment; an absolute value or a `..` segment
  # is refused.
  fe_rel() {
    local rest seg
    FE_REL=""
    case "$2" in
      /*) fail 1 "commit-on-branch.sh: refusing to commit: $1 '$2' is not a path relative to '$top'" ;;
    esac
    rest="$2"
    while [ -n "$rest" ]; do
      seg="${rest%%/*}"
      if [ "$seg" = "$rest" ]; then rest=""; else rest="${rest#*/}"; fi
      case "$seg" in
        '' | .) ;;
        ..) fail 1 "commit-on-branch.sh: refusing to commit: $1 '$2' has a '..' segment" ;;
        *) FE_REL="${FE_REL:+$FE_REL/}$seg" ;;
      esac
    done
    [ -n "$FE_REL" ] || fail 1 "commit-on-branch.sh: refusing to commit: $1 '$2' names no path"
  }
  fe_under_state() {
    case "$2" in
      "$state_dir"/?*) ;;
      *) fail 1 "commit-on-branch.sh: refusing to commit: $1 '$2' is not under '$state_dir/'" ;;
    esac
  }
  # fe_no_link <flag> <rel> — no component of <rel> under the target is a
  # symbolic link.
  fe_no_link() {
    local acc="" rest="$2" seg
    while [ -n "$rest" ]; do
      seg="${rest%%/*}"
      if [ "$seg" = "$rest" ]; then rest=""; else rest="${rest#*/}"; fi
      acc="${acc:+$acc/}$seg"
      if [ -L "$top/$acc" ]; then
        fail 1 "commit-on-branch.sh: refusing to commit: $1 '$2' is reached through the symbolic link '$acc'"
      fi
    done
  }

  if [ -n "$opt_unit" ]; then
    fe_rel --plan "$opt_plan"
    plan_rel="$FE_REL"
    fe_under_state --plan "$plan_rel"
    fe_no_link --plan "$plan_rel"
    [ -f "$top/$plan_rel" ] || fail 1 "commit-on-branch.sh: refusing to commit: --plan '$plan_rel' is not a regular file"
    plan_abs="$top/$plan_rel"
    findings_rel=""
    if [ -n "$opt_findings" ]; then
      fe_rel --findings "$opt_findings"
      findings_rel="$FE_REL"
      fe_under_state --findings "$findings_rel"
    fi
    extra_rel=""
    if [ -n "$opt_extra" ]; then
      fe_rel --extra "$opt_extra"
      extra_rel="$FE_REL"
      fe_under_state --extra "$extra_rel"
    fi
    kind_rc=0
    ucl ucl_index_kind "$state_dir" "$plan_rel" || kind_rc=$?
    [ "$kind_rc" -ne 1 ] || fail 1 "commit-on-branch.sh: refusing to commit: --plan '$plan_rel' is not a readiness index this wrapper can classify"
    [ "$kind_rc" -eq 0 ] || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
    kind="$UCL_KIND"
    fdir_rel="$UCL_FINDINGS_DIR"
    case "$opt_unit:$kind" in
      task:story | ui_test_pass:ui_test) ;;
      review_item:story | review_item:ui_test | review_plan_file:story | review_plan_file:ui_test | task:* | ui_test_pass:*)
        fail 1 "commit-on-branch.sh: refusing to commit: --plan '$plan_rel' is a $kind index, which --unit $opt_unit does not take"
        ;;
    esac
  fi

  case "$opt_unit" in
    task | review_item | ui_test_pass)
      case "$kind" in
        story) word=Task ;;
        ui_test) word=Test ;;
        *) word=Finding ;;
      esac
      find_rc=0
      ucl ucl_entry_find "$plan_abs" "$word" "$opt_id" || find_rc=$?
      [ "$find_rc" -ne 1 ] || fail 1 "commit-on-branch.sh: --id $opt_id matched no readiness entry in $plan_rel"
      [ "$find_rc" -eq 0 ] || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      entry_line="$UCL_ENTRY_LINE"
      entry_lineno="$UCL_ENTRY_LINENO"
      entry_state="$UCL_ENTRY_STATE"
      ;;
  esac

  case "$opt_unit" in
    ui_test_pass)
      if [ "$entry_state" = done ]; then
        echo "noop: UI test $opt_id already marked"
        exit 0
      fi
      ucl ucl_ui_pass_subject "$opt_id" "$branch" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      msgs=("$UCL_SUBJECT")
      paths=("$plan_rel")
      ;;
    task | review_item)
      # THE SUBJECT AND ITS RECORD (header): settled before the tick, so every
      # refusal leaves the index as it was.
      ucl ucl_unit_label "$kind" "$opt_id" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      label="$UCL_LABEL"
      token="$UCL_TOKEN"
      sev=""
      if [ "$kind" = user_review ] && ucl ucl_severity "$plan_abs" "$opt_id"; then
        sev="$UCL_OUT"
      fi
      ucl ucl_unit_prefix "$kind" "$branch" "$sev" "$opt_prefix" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      prefix="$UCL_OUT"
      ucl ucl_short_title "$entry_line" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      title="$UCL_OUT"
      ucl ucl_subject "$prefix" "$label" "$title" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      subject="$UCL_SUBJECT"
      [ "$kind" != story ] || fdir_rel=""
      ucl ucl_detail_file "$kind" "$state_dir" "$branch" "$opt_id" "$plan_abs" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      detail_rel="$UCL_OUT"

      # THE STAGE SET (header): read through the commit's own triple, against
      # the tip the commit is built on.
      if ! wt_git diff --name-status -z --no-renames "$old_tip" >"$work/diff"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list the changes in '$top' against '$branch' (see output above)"
      fi
      if ! wt_git ls-files -z --others --exclude-standard >"$work/others"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list the untracked paths in '$top' (see output above)"
      fi
      if [ "$entry_state" = done ] && [ ! -s "$work/diff" ] && [ ! -s "$work/others" ]; then
        echo "commit-on-branch.sh: nothing to commit" >&2
        fe_nothing=1
      else
        fe_nothing=0
        { cat "$work/diff" && printf -- '--others\0' && cat "$work/others"; } >"$work/listing.fe"
        UCL_STAGE_FILE="$work/stage"
        ucl ucl_stage_set "$work/listing.fe" "$plan_rel" "$findings_rel" "$detail_rel" "$fdir_rel" \
          || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
        work_count="$UCL_WORK_COUNT"
        index_only_set="$UCL_INDEX_ONLY_SET"
        paths=()
        detail_staged=no
        while IFS= read -r -d '' e; do
          paths+=("$e")
          ucl_under "$detail_rel" "$e" && detail_staged=yes
        done <"$work/stage"
        disp="" ap=""
        if [ "$detail_staged" = yes ] && [ -e "$top/$detail_rel" ]; then
          fe_no_link "the detail file" "$detail_rel"
          if [ -f "$top/$detail_rel" ]; then
            if ucl ucl_record_cause "$top/$detail_rel" Disposition "$detail_rel"; then
              disp="$UCL_OUT"
            elif ucl ucl_record_cause "$top/$detail_rel" 'Already passing' "$detail_rel"; then
              ap="$UCL_OUT"
            fi
          fi
        fi
        msgs=("$subject")
        if ucl ucl_body_record "$token" "$disp" "$ap" "$work_count" "$index_only_set"; then
          msgs+=("$UCL_OUT")
        fi
        if [ "$work_count" -eq 0 ]; then
          staged_line="staged: index-only — $index_only_set was the whole diff; no work file was staged"
        fi
      fi
      if [ "$entry_state" = done ]; then
        plan_flipped="already-[x]: $entry_line — not flipped by this call"
      fi
      ;;
    review_plan_file)
      ucl ucl_review_kind_subject "$branch" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      msgs=("$UCL_SUBJECT")
      paths=("$plan_rel" "$fdir_rel")
      [ -z "$extra_rel" ] || paths+=("$extra_rel")
      ;;
    '')
      ucl ucl_artifact "$opt_artifact" "$state_dir" "$branch" "$opt_round" "$opt_iteration" "$opt_entry" \
        || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
      msgs=("$UCL_SUBJECT")
      paths=()
      if [ "$opt_artifact" = rescreened-input ]; then
        for p in "${opt_paths[@]}"; do
          fe_rel --path "$p"
          paths+=("$FE_REL")
        done
      else
        paths=("${UCL_PATHS[@]}")
      fi
      ;;
  esac
fi

# THE PUSH (header). fe_push sets `pushed`.
fe_push() {
  local out rc=0 l
  pushed=no
  [ "$opt_push" -eq 1 ] || return 0
  out="$(bash "$script_dir/push-branch.sh" "$top" 2>&1)" || rc=$?
  [ -z "$out" ] || printf '%s\n' "$out" >&2
  pushed=yes
  [ "$rc" -eq 0 ] || pushed=failed
  while IFS= read -r l; do
    case "$l" in
      'push-branch.sh: '*'refusing to push'* | 'push-branch.sh: '*' — nothing to push' \
        | 'push-branch.sh: push failed for '*': '* | 'push-branch.sh: push failed for '*' attempts (see output above)' \
        | 'push-branch.sh: '*' no longer has '*)
        pushed=failed
        ;;
    esac
  done <<<"$out"
}
# fe_nothing_exit — the front end's exit 3: one `error:` line, then the push,
# so a resumed run's earlier unpushed commit still reaches the remote.
fe_nothing_exit() {
  tick_backup=""
  echo "error: nothing to commit"
  fe_push
  exit 3
}
# fe_return <new_commit> — THE RETURN (header).
fe_return() {
  local n
  n="$(main_git diff --name-only -z --no-renames "$old_tip" "$1" | LC_ALL=C tr -cd '\000' | LC_ALL=C wc -c)"
  fe_push
  echo "commit_sha: $1"
  echo "subject: ${msgs[0]}"
  echo "files_committed: $((n + 0))"
  echo "plan_flipped: $plan_flipped"
  echo "pushed: $pushed"
  [ -z "$staged_line" ] || echo "$staged_line"
}

if [ "$fe" -eq 1 ]; then
  [ "${fe_nothing-0}" -eq 0 ] || fe_nothing_exit
  # THE TICK (header): after every refusal above, restored by `fail` if the
  # commit below is refused.
  case "$opt_unit" in
    task | review_item | ui_test_pass)
      if [ "$entry_state" = open ]; then
        cp -p "$plan_abs" "$work/plan.orig" \
          || fail 1 "commit-on-branch.sh: refusing to commit: cannot keep a copy of '$plan_rel' before the tick"
        tick_backup=1
        ucl ucl_tick "$plan_abs" "$entry_lineno" || fail 1 "commit-on-branch.sh: refusing to commit: $UCL_ERR"
        plan_flipped="${entry_line/\[ \]/[x]}"
      fi
      ;;
  esac
fi

# STAGING POLICY (header). The count guard is required: on bash 3.2 (the
# floor) `"${paths[@]}"` on an EMPTY array under `set -u` raises `unbound
# variable` instead of expanding to nothing, which would abort a legal
# zero-path call before it could reach the nothing-to-commit exit 3.
if [ "${#paths[@]}" -gt 0 ]; then
  for p in "${paths[@]}"; do
    case "$p" in
      /*)
        fail 1 "commit-on-branch.sh: refusing to commit: '$p' is not a path relative to '$top'"
        ;;
    esac
    # The repo-relative form the commit's records need: no empty or `.`
    # segment. A `..` segment is refused.
    rel=""
    rest="$p"
    while [ -n "$rest" ]; do
      seg="${rest%%/*}"
      if [ "$seg" = "$rest" ]; then rest=""; else rest="${rest#*/}"; fi
      case "$seg" in
        '' | .) ;;
        ..)
          fail 1 "commit-on-branch.sh: refusing to commit: '$p' has a '..' segment"
          ;;
        *) rel="${rel:+$rel/}$seg" ;;
      esac
    done
    if [ ! -e "$top/$p" ]; then
      : >"$work/listing"
      if [ -n "$rel" ] && ! main_git ls-tree -r -z "$old_tip" -- "$rel" >"$work/listing"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list '$p' at '$branch' (see output above)"
      fi
      if [ ! -s "$work/listing" ]; then
        echo "commit-on-branch.sh: path '$p' does not exist under '$top' — skipping" >&2
        continue
      fi
      while IFS= read -r -d '' entry; do
        case "$entry" in 160000\ *) continue ;; esac
        printf '%s\0' "${entry#*	}" >>"$work/paths"
      done <"$work/listing"
      continue
    fi
    if [ -d "$top/$p" ] && [ ! -L "$top/$p" ]; then
      [ -n "$rel" ] || rel=.
      # A gitlink (a submodule) under a passed directory is carried from the tip
      # unchanged: this wrapper never commits one, and an unchanged one must not
      # refuse the rest of the directory. An untracked embedded repository,
      # which `ls-files --others` lists as `<path>/`, is left out the same way.
      if ! main_git ls-tree -r -z "$old_tip" -- "$rel" >"$work/listing"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list '$p' at '$branch' (see output above)"
      fi
      while IFS= read -r -d '' entry; do
        case "$entry" in 160000\ *) continue ;; esac
        printf '%s\0' "${entry#*	}" >>"$work/paths"
      done <"$work/listing"
      if ! wt_git ls-files -z --stage -- "$rel" >"$work/listing"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list '$p' in '$top' (see output above)"
      fi
      while IFS= read -r -d '' entry; do
        case "$entry" in 160000\ *) continue ;; esac
        printf '%s\0' "${entry#*	}" >>"$work/paths"
      done <"$work/listing"
      if ! wt_git ls-files -z --others --exclude-standard -- "$rel" >"$work/listing"; then
        fail 1 "commit-on-branch.sh: refusing to commit: git could not list '$p' in '$top' (see output above)"
      fi
      while IFS= read -r -d '' entry; do
        case "$entry" in */) continue ;; esac
        printf '%s\0' "$entry" >>"$work/paths"
      done <"$work/listing"
    else
      printf '%s\0' "$rel" >>"$work/paths"
    fi
  done
fi
if ! LC_ALL=C sort -z -u "$work/paths" >"$work/sorted"; then
  fail 1 "commit-on-branch.sh: refusing to commit: could not sort the path list"
fi
commit_paths=()
while IFS= read -r -d '' rel; do
  commit_paths+=("$rel")
done <"$work/sorted"

# NO FILTER DRIVER RUNS (header): attributes are read as data, and a path that
# selects a filter is refused rather than committed raw.
if [ "${#commit_paths[@]}" -gt 0 ]; then
  if ! wt_git check-attr -z --stdin filter <"$work/sorted" >"$work/attrs"; then
    fail 1 "commit-on-branch.sh: refusing to commit: git could not read the attributes of the given paths (see output above)"
  fi
  while IFS= read -r -d '' a_path && IFS= read -r -d '' _ && IFS= read -r -d '' a_value; do
    case "$a_value" in
      unspecified | unset) ;;
      *)
        fail 1 "commit-on-branch.sh: refusing to commit: '$a_path' selects a filter driver, which this wrapper never runs"
        ;;
    esac
  done <"$work/attrs"
fi

# THE COMMIT IS BUILT FROM PLUMBING, AND NO COMMIT HOOK RUNS (header).
status=0
hr_commit_paths_var "$main_top" "$top" "$wt_gitdir" "$branch" "$old_tip" auto always \
  "commit-on-branch.sh: ${msgs[0]}" ${commit_paths[@]+"${commit_paths[@]}"} -- "${msgs[@]}" || status=$?
case "$status" in
  0)
    if [ "$fe" -eq 1 ]; then
      tick_backup=""
      fe_return "$HR_COMMIT_NEW"
      exit 0
    fi
    sha="$(main_git rev-parse --short "$HR_COMMIT_NEW")" || sha="$HR_COMMIT_NEW"
    echo "commit-on-branch.sh: committed $sha on $branch"
    exit 0
    ;;
  3)
    echo "commit-on-branch.sh: nothing to commit" >&2
    [ "$fe" -eq 0 ] || fe_nothing_exit
    exit 3
    ;;
  4)
    fail 1 "commit-on-branch.sh: refusing to commit: '$branch' moved under this wrapper, or its ref could not be locked — no commit made, and the given paths are left staged"
    ;;
  *)
    if [ -n "$HR_COMMIT_NEW" ]; then
      tick_backup=""
      sha="$(main_git rev-parse --short "$HR_COMMIT_NEW")" || sha="$HR_COMMIT_NEW"
      if [ "${HR_COMMIT_SYNC_FAILED-}" = 1 ]; then
        echo "commit-on-branch.sh: committed $sha on $branch, but $HR_COMMIT_REFUSAL — the commit stands in the clone, and the main checkout's ref follows it on the next wrapper call" >&2
      else
        echo "commit-on-branch.sh: committed $sha on $branch, but the index of '$top' could not take the committed paths — the commit stands; the same call again re-syncs the index and exits 3" >&2
      fi
      if [ "$fe" -eq 1 ]; then
        # THE RETURN (header): a landed exit 1 is re-synced by one identical
        # plain-form call, and the commit stands.
        sync_rc=0
        bash "$script_dir/commit-on-branch.sh" --repo "$repo_dir" ${commit_paths[@]+"${commit_paths[@]}"} -- "${msgs[@]}" \
          >&2 2>"$work/sync.err" || sync_rc=$?
        sync_line=""
        if [ "$sync_rc" -ne 3 ]; then
          [ ! -s "$work/sync.err" ] || cat "$work/sync.err" >&2
          sync_line="index_sync: failed — exit $sync_rc, $(tail -n 1 "$work/sync.err" 2>/dev/null)"
        fi
        fe_return "$HR_COMMIT_NEW"
        [ -z "$sync_line" ] || echo "$sync_line"
        exit 0
      fi
      exit 1
    fi
    fail 1 "commit-on-branch.sh: refusing to commit: $HR_COMMIT_REFUSAL"
    ;;
esac
