#!/usr/bin/env bash
# planning-record-lib.sh — every durable write the script-driven planning
# driver makes: the round, partial and convergence commits, the `## Planning`
# ledger flips, the clarification park, the pause files and the planning
# phase's improvement-observation entries.
#
# The rule this library exists to enforce: each write is the one the autonomous
# planning fork makes, under the same fixed subject and over the same explicit
# path set, in the same order
# (`plugin/instructions/task_plan_writing_instructions_autonomous.md` →
# Overrides 3 to 6; `plugin/instructions/autonomous_pause_and_ledger.md` →
# `### 1.6`). The fork issues `commit-on-branch.sh --artifact <kind> --push` as
# one call; this library keeps the plain form — the main checkout's
# `commit-on-branch.sh --repo <worktree> <path>… -- "<subject>"`, then its own
# `push-branch.sh <worktree>`, each its own process. Every commit's subject and
# path set are read from `lib/unit-commit-lib.sh` → `ucl_artifact`'s table,
# never spelled here.
#
# IT DECIDES NOTHING. Which `round:` or `ledger:` line fires a commit, when a
# park, pause or hand-off happens, and what a park's body holds are
# `lib/planning-driver-lib.sh`'s.
#
# SOURCED, NEVER EXECUTED. It sets no shell option. The caller sources
# `lib/harness-run-lib.sh` and `lib/unit-commit-lib.sh` first: `prl_init`
# resolves `stateDir` from the worktree and `scriptsDir` from the main checkout
# through the former, `prl_park` takes its index from `hr_max_question_index`,
# and every commit takes its subject and path set from `ucl_artifact`.
#
# BASH 3.2 AND JQ 1.5 ARE THE FLOORS, as in `lib/harness-run-lib.sh`. Every
# temporary file names an explicit `mktemp` template; a rewritten tracked file
# goes through a temporary file beside it and `mv`.
#
# GLOBALS. `prl_init` sets `PRL_BRANCH`, `PRL_WORKTREE`, `PRL_MAIN_REPO`,
# `PRL_LOG`, `PRL_STATE_DIR` and `PRL_SCRIPTS_DIR`. `prl_observe` holds its
# blocks in the file `PRL_OBS_FILE` names until `prl_observe_flush`.
#
# STATUSES. 0 done; 2 a fault, with one `planning-driver: <cause>` line on
# stderr. Every narration line goes to `PRL_LOG`, prefixed `[plan-drive]`.
# `prl_observe_flush` is best-effort and always returns 0.
#
# THE OBSERVATIONS FILE. A flush appends an opening label, its blocks and the
# closing label `PRL_CLOSING_LABEL`; the task run's Phase D entries, appended
# with no label of their own, land under that closing label. Every home
# directory, main-checkout and worktree prefix in the file is rewritten before
# the commit: a worktree path to its repo-relative form, a main-checkout path
# to its repo-relative form followed by ` (main checkout)`, the home directory
# to `~` (`plugin/instructions/improvement_observations_instructions.md` →
# `## The entry format`). Residual: an exit 1 that leaves the path staged is
# logged, not re-staged.
#
# REPRO — every public function, against a throwaway fixture:
#
#   r=$(mktemp -d "${TMPDIR:-/tmp}/prl-repro.XXXXXX"); git init -q --bare "$r/o.git"
#   git init -q -b trunk "$r/m"; git -C "$r/m" remote add origin "$r/o.git"
#   printf '{"version":1,"defaultBranch":"trunk","stateDir":"devscene/","scriptsDir":"s","layers":[],"commands":{}}' > "$r/m/devscene.config.json"
#   mkdir -p "$r/m/s"; cp -R <scripts_dir>/commit-on-branch.sh <scripts_dir>/push-branch.sh <scripts_dir>/lib "$r/m/s/"
#   git -C "$r/m" add -A; git -C "$r/m" commit -qm seed; git -C "$r/m" worktree add -q -b feat_x "$r/w"
#   for l in harness-run-lib unit-commit-lib planning-record-lib; do . "$r/w/s/lib/$l.sh"; done
#
#   init      prl_init feat_x "$r/w" "$r/m" "$r/run.log"; echo "$? $PRL_STATE_DIR"  -> 0 devscene
#   round     mkdir -p "$r/w/devscene/task_plans/feat_x"; echo a > "$r/w/devscene/task_plans/feat_x/task_1_plan.md"
#             prl_round_commit 1     -> 0; again -> 0, the wrapper's exit 3
#   flip      prl_ledger_flip P1     -> 2 with no ledger; 0 once one carries `- [ ] P1.`
#   park      printf 'Which?\n' > "$r/b"; prl_park task-plan-writer 'Questions' "$r/b"
#               -> index 1 under devscene/clarifications/feat_x/
#   pause     prl_pause planning 'dispatch plan_review'   -> PAUSE_PROGRESS.md, PAUSE_ACK
#   observe   prl_observe convention 'p' "$r/w/x" 'c'; prl_observe_flush
#               -> devscene/improvement_observations/feat_x.md, evidence `x`

PRL_CATEGORIES='tooling-gap silent-failure flow-efficiency optimization agent-contract shared-state convention'
PRL_CLOSING_LABEL='# Task run (Phase D)'

prl_log() {
  [ -n "${PRL_LOG-}" ] || return 0
  printf '[plan-drive] %s\n' "$1" >>"$PRL_LOG" 2>/dev/null
  return 0
}

prl_fail() {
  printf 'planning-driver: %s\n' "$1" >&2
  prl_log "$1"
  return 2
}

# prl_log_file <file> — each line of <file> into the log.
prl_log_file() {
  local line
  [ -f "$1" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    prl_log "$line"
  done <"$1"
}

# prl_init <branch> <worktree> <main_repo> <log_path>
prl_init() {
  local branch="${1-}" worktree="${2-}" main_repo="${3-}" log_path="${4-}" w
  PRL_LOG=""
  [ -n "$branch" ] || { prl_fail "prl_init needs <branch> <worktree> <main_repo> <log_path>"; return 2; }
  [ -n "$log_path" ] && [ -d "$(dirname "$log_path")" ] \
    || { prl_fail "the log path '$log_path' has no directory"; return 2; }
  [ -n "$worktree" ] && [ -d "$worktree" ] || { prl_fail "the worktree '$worktree' does not exist"; return 2; }
  [ -n "$main_repo" ] && [ -d "$main_repo" ] || { prl_fail "the main checkout '$main_repo' does not exist"; return 2; }
  command -v hr_state_dir >/dev/null 2>&1 || { prl_fail "lib/harness-run-lib.sh is not sourced"; return 2; }
  command -v ucl_artifact >/dev/null 2>&1 || { prl_fail "lib/unit-commit-lib.sh is not sourced"; return 2; }
  PRL_BRANCH="$branch"
  PRL_WORKTREE="${worktree%/}"
  PRL_MAIN_REPO="${main_repo%/}"
  PRL_LOG="$log_path"
  PRL_STATE_DIR=$(hr_state_dir "$PRL_WORKTREE") || { prl_fail "stateDir does not resolve in '$PRL_WORKTREE/devscene.config.json'"; return 2; }
  PRL_SCRIPTS_DIR=$(hr_scripts_dir "$PRL_MAIN_REPO") || { prl_fail "scriptsDir does not resolve in '$PRL_MAIN_REPO/devscene.config.json'"; return 2; }
  for w in commit-on-branch.sh push-branch.sh; do
    [ -f "$PRL_MAIN_REPO/$PRL_SCRIPTS_DIR/$w" ] || { prl_fail "'$PRL_MAIN_REPO/$PRL_SCRIPTS_DIR/$w' does not exist"; return 2; }
  done
  return 0
}

# prl_commit <subject> <path>… — PRL_COMMIT_LANDED is `yes` once a commit
# stands, whatever is returned.
prl_commit() {
  local subject="${1-}" wrapper push out err rc line cause="" landed=no rc2
  PRL_COMMIT_LANDED=no
  shift
  [ -n "$subject" ] && [ $# -gt 0 ] || { prl_fail "prl_commit needs <subject> <path>…"; return 2; }
  wrapper="$PRL_MAIN_REPO/$PRL_SCRIPTS_DIR/commit-on-branch.sh"
  push="$PRL_MAIN_REPO/$PRL_SCRIPTS_DIR/push-branch.sh"
  out=$(mktemp "${TMPDIR:-/tmp}/planning-record-out.XXXXXX") || { prl_fail "cannot create a temporary file"; return 2; }
  err=$(mktemp "${TMPDIR:-/tmp}/planning-record-err.XXXXXX") || { rm -f "$out"; prl_fail "cannot create a temporary file"; return 2; }

  prl_log "commit: $subject"
  bash "$wrapper" --repo "$PRL_WORKTREE" "$@" -- "$subject" >"$out" 2>"$err"
  rc=$?
  prl_log_file "$out"
  prl_log_file "$err"
  while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] && cause="$line"
    case "$line" in
      'commit-on-branch.sh: committed '*) landed=yes ;;
    esac
  done <"$err"
  [ -n "$cause" ] || cause="commit-on-branch.sh exited $rc with no message"

  if [ "$rc" -eq 0 ]; then
    PRL_COMMIT_LANDED=yes
  elif [ "$rc" -eq 1 ] && [ "$landed" = yes ]; then
    PRL_COMMIT_LANDED=yes
    prl_log "the commit landed with exit 1; re-syncing the index with the identical call"
    bash "$wrapper" --repo "$PRL_WORKTREE" "$@" -- "$subject" >"$out" 2>"$err"
    rc2=$?
    prl_log_file "$out"
    prl_log_file "$err"
    rm -f "$out" "$err"
    [ "$rc2" -eq 3 ] || { prl_fail "index re-sync after a landed commit exited $rc2"; return 2; }
    rc=3
  fi
  rm -f "$out" "$err"

  out=$(mktemp "${TMPDIR:-/tmp}/planning-record-push.XXXXXX") || { prl_fail "cannot create a temporary file"; return 2; }
  bash "$push" "$PRL_WORKTREE" >"$out" 2>&1
  prl_log_file "$out"
  rm -f "$out"

  case "$rc" in
    0 | 3) return 0 ;;
  esac
  prl_fail "$cause"
}

# prl_artifact_commit <kind> [<round>] [<entry>] — `prl_commit` of
# `ucl_artifact`'s subject and path set for <kind>.
prl_artifact_commit() {
  local kind="${1-}" err cause=""
  PRL_COMMIT_LANDED=no
  err=$(mktemp "${TMPDIR:-/tmp}/planning-record-ucl.XXXXXX") || { prl_fail "cannot create a temporary file"; return 2; }
  if ! ucl_artifact "$kind" "$PRL_STATE_DIR" "$PRL_BRANCH" "${2-}" '' "${3-}" 2>"$err"; then
    IFS= read -r cause <"$err"
    rm -f "$err"
    prl_fail "the artifact table refused '$kind': ${cause#unit-commit-lib: }"
    return 2
  fi
  rm -f "$err"
  prl_commit "$UCL_SUBJECT" "${UCL_PATHS[@]}"
}

prl_round_number() {
  case "${1-}" in
    '' | *[!0-9]*) prl_fail "'${1-}' is not a round number"; return 2 ;;
  esac
  return 0
}

# prl_round_commit <n>
prl_round_commit() {
  prl_round_number "${1-}" || return 2
  prl_artifact_commit plan-round "$1"
}

# prl_partial_commit <n>
prl_partial_commit() {
  prl_round_number "${1-}" || return 2
  prl_artifact_commit plan-round-partial "$1"
}

# prl_convergence_commits <yes|no> — <yes> when a UI-test plan was written.
prl_convergence_commits() {
  case "${1-}" in
    yes) prl_artifact_commit ui-test-plan || return 2 ;;
    no) ;;
    *) prl_fail "prl_convergence_commits takes yes or no, not '${1-}'"; return 2 ;;
  esac
  prl_artifact_commit task-plan
}

# prl_ledger_flip <P1|P2|P3> — `[ ]` becomes `[x]`; `[x]` and `[-]` stay.
prl_ledger_flip() {
  local id="${1-}" rel file line state="" tmp
  case "$id" in
    P1 | P2 | P3) ;;
    *) prl_fail "prl_ledger_flip takes P1, P2 or P3, not '$id'"; return 2 ;;
  esac
  rel="$PRL_STATE_DIR/flow_progress/${PRL_BRANCH}_progress.md"
  file="$PRL_WORKTREE/$rel"
  [ -f "$file" ] || { prl_fail "the ledger '$rel' does not exist"; return 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "- [ ] $id."*) state=open; break ;;
      "- [x] $id."* | "- [-] $id."*) state=resolved; break ;;
    esac
  done <"$file"
  [ -n "$state" ] || { prl_fail "the ledger '$rel' carries no $id line"; return 2; }
  if [ "$state" = open ]; then
    tmp=$(mktemp "${file%/*}/.progress.XXXXXX") || { prl_fail "cannot create a temporary file beside '$rel'"; return 2; }
    awk -v open="- [ ] $id." -v done="- [x] $id." '
      !flipped && substr($0, 1, length(open)) == open { $0 = done substr($0, length(open) + 1); flipped = 1 }
      { print }' "$file" >"$tmp" && chmod 644 "$tmp" && mv "$tmp" "$file" \
      || { rm -f "$tmp"; prl_fail "cannot rewrite the ledger '$rel'"; return 2; }
    prl_log "ledger: $id flipped"
  else
    prl_log "ledger: $id already resolved"
  fi
  prl_artifact_commit ledger-flip '' "$id"
}

# prl_park <raised_by> <q_title> <body_file>
prl_park() {
  local raised_by="${1-}" q_title="${2-}" body="${3-}" rel dir n max file tmp has_q=no line
  [ -n "$raised_by" ] && [ -n "$q_title" ] && [ -f "$body" ] \
    || { prl_fail "prl_park needs <raised_by> <q_title> <body_file>"; return 2; }
  rel="$PRL_STATE_DIR/clarifications/$PRL_BRANCH"
  dir="$PRL_WORKTREE/$rel"
  mkdir -p "$dir" || { prl_fail "cannot create '$rel'"; return 2; }
  max=$(hr_max_question_index "$dir") || { prl_fail "cannot read the question index of '$rel'"; return 2; }
  n=$((max + 1))
  file="$dir/question_$n.md"
  [ ! -e "$file" ] || { prl_fail "'$rel/${file##*/}' already exists"; return 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      '## Q'[0-9]*) has_q=yes; break ;;
    esac
  done <"$body"
  tmp=$(mktemp "$dir/.question.XXXXXX") || { prl_fail "cannot create a temporary file in '$rel'"; return 2; }
  {
    printf '# %s\n\nRaised by: %s (script-driven planning)\n\n' "$q_title" "$raised_by"
    [ "$has_q" = yes ] || printf '## Q1 — %s\n\n' "$q_title"
    cat "$body"
  } >"$tmp" && chmod 644 "$tmp" || { rm -f "$tmp"; prl_fail "cannot write '$rel/${file##*/}'"; return 2; }
  [ ! -e "$file" ] && mv "$tmp" "$file" || { rm -f "$tmp"; prl_fail "cannot place '$rel/${file##*/}'"; return 2; }
  prl_log "PARKED: $PRL_BRANCH — 1 question(s) at $rel/"
  return 0
}

# prl_pause <phase> <next_step>
prl_pause() {
  local phase="${1-}" next="${2-}" ts
  [ -n "$phase" ] && [ -n "$next" ] || { prl_fail "prl_pause needs <phase> <next_step>"; return 2; }
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  mkdir -p "$PRL_WORKTREE/$PRL_STATE_DIR" || { prl_fail "cannot create '$PRL_STATE_DIR'"; return 2; }
  printf '\n## %s — %s paused (script-driven planning)\n- phase: %s\n- next step: %s\n' \
    "$ts" "$PRL_BRANCH" "$phase" "$next" >>"$PRL_WORKTREE/$PRL_STATE_DIR/PAUSE_PROGRESS.md" \
    || { prl_fail "cannot append to '$PRL_STATE_DIR/PAUSE_PROGRESS.md'"; return 2; }
  printf '%s\n' "$ts" >"$PRL_WORKTREE/$PRL_STATE_DIR/PAUSE_ACK" \
    || { prl_fail "cannot write '$PRL_STATE_DIR/PAUSE_ACK'"; return 2; }
  prl_log "PAUSED: $PRL_BRANCH — $phase"
  return 0
}

prl_one_line() {
  local text="$1" nl="
"
  text=${text//$'\r'/ }
  PRL_OUT=${text//$nl/ }
}

# prl_observe <category> <problem> <evidence> <cost>
prl_observe() {
  local category="${1-}" problem evidence cost c ok=no
  for c in $PRL_CATEGORIES; do
    [ "$c" = "$category" ] && ok=yes
  done
  [ "$ok" = yes ] || { prl_fail "'$category' is not an observation category"; return 2; }
  prl_one_line "${2-}"; problem=$PRL_OUT
  prl_one_line "${3-}"; evidence=$PRL_OUT
  prl_one_line "${4-}"; cost=$PRL_OUT
  [ -n "$problem" ] || { prl_fail "an observation needs a problem statement"; return 2; }
  if [ -z "${PRL_OBS_FILE-}" ] || [ ! -f "$PRL_OBS_FILE" ]; then
    PRL_OBS_FILE=$(mktemp "${TMPDIR:-/tmp}/planning-record-obs.XXXXXX") \
      || { PRL_OBS_FILE=""; prl_fail "cannot create a temporary file"; return 2; }
  fi
  printf '## %s\n- **category:** %s\n- **evidence:** %s\n- **cost this run:** %s\n\n' \
    "$problem" "$category" "$evidence" "$cost" >>"$PRL_OBS_FILE" \
    || { prl_fail "cannot append to '$PRL_OBS_FILE'"; return 2; }
  return 0
}

# Rewrite every machine prefix of stdin. Needles come from the environment, so
# awk processes no escape in them; a longer needle is rewritten first, and a
# match counts only where the path ends or continues with `/`.
PRL_REWRITE_AWK='
  function delim(c) { return c == "" || index(" \t`\047\"),;]>", c) > 0 }
  function rewrite(line, needle, kind,   out, p, rest, c, i, tok) {
    out = ""
    while ((p = index(line, needle)) > 0) {
      out = out substr(line, 1, p - 1)
      rest = substr(line, p + length(needle))
      c = substr(rest, 1, 1)
      if (c != "/" && !delim(c)) { out = out needle; line = rest; continue }
      if (kind == "home") { out = out "~"; line = rest; continue }
      if (c == "/") rest = substr(rest, 2)
      for (i = 1; i <= length(rest); i++) if (delim(substr(rest, i, 1))) break
      tok = substr(rest, 1, i - 1)
      if (tok == "") tok = "."
      out = out tok
      if (kind == "main") out = out " (main checkout)"
      line = substr(rest, i)
    }
    return out line
  }
  BEGIN {
    n = 0
    if (ENVIRON["PRL_N_WT"] != "") { n++; needles[n] = ENVIRON["PRL_N_WT"]; kinds[n] = "worktree" }
    if (ENVIRON["PRL_N_MAIN"] != "") { n++; needles[n] = ENVIRON["PRL_N_MAIN"]; kinds[n] = "main" }
    if (ENVIRON["PRL_N_HOME"] != "") { n++; needles[n] = ENVIRON["PRL_N_HOME"]; kinds[n] = "home" }
    for (i = 1; i <= n; i++) for (j = i + 1; j <= n; j++)
      if (length(needles[j]) > length(needles[i])) { t = needles[i]; needles[i] = needles[j]; needles[j] = t; t = kinds[i]; kinds[i] = kinds[j]; kinds[j] = t }
  }
  { for (i = 1; i <= n; i++) $0 = rewrite($0, needles[i], kinds[i]); print }'

# prl_needle <source> <path> — the needle, or empty when it cannot be one.
prl_needle() {
  local source="$1" path="${2%/}" rest
  PRL_OUT=""
  case "$path" in
    '' | *"'"*) prl_log "observations: the $source needle is empty or quoted; dropped"; return 0 ;;
  esac
  rest=${path#/}
  case "$rest" in
    '' | */*) ;;
    *) prl_log "observations: the $source needle '$path' is one path segment; dropped"; return 0 ;;
  esac
  [ -n "$rest" ] || { prl_log "observations: the $source needle is '/'; dropped"; return 0; }
  PRL_OUT="$path"
}

prl_obs_reset() {
  [ -z "${PRL_OBS_FILE-}" ] || rm -f "$PRL_OBS_FILE"
  PRL_OBS_FILE=""
}

# prl_observe_flush — best-effort: a failure is one log line, and 0.
prl_observe_flush() {
  local rel file dir tmp tmp2 backup="" ts wt main home rc
  local -a needles
  if [ -z "${PRL_OBS_FILE-}" ] || [ ! -s "$PRL_OBS_FILE" ]; then
    prl_obs_reset
    return 0
  fi
  rel="$PRL_STATE_DIR/improvement_observations/$PRL_BRANCH.md"
  file="$PRL_WORKTREE/$rel"
  dir=${file%/*}
  if ! mkdir -p "$dir" || ! tmp=$(mktemp "$dir/.observations.XXXXXX"); then
    prl_log "observations: cannot write in '$PRL_STATE_DIR/improvement_observations'; not flushed"
    prl_obs_reset
    return 0
  fi
  if [ -f "$file" ]; then
    backup=$(mktemp "${TMPDIR:-/tmp}/planning-record-backup.XXXXXX") && cp "$file" "$backup" \
      || { rm -f "$tmp" "$backup"; prl_log "observations: cannot back up '$rel'; not flushed"; prl_obs_reset; return 0; }
  fi
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  prl_needle worktree "$PRL_WORKTREE"; wt=$PRL_OUT
  prl_needle "main checkout" "$PRL_MAIN_REPO"; main=$PRL_OUT
  [ "$main" != "$wt" ] || main=""
  prl_needle home "${HOME-}"; home=$PRL_OUT
  {
    if [ -n "$backup" ]; then
      # Everything up to the last non-blank line, less that line when it is a
      # bare closing label, and less trailing blank lines.
      awk -v label="$PRL_CLOSING_LABEL" '
        { l[NR] = $0 }
        END {
          last = NR
          while (last > 0 && l[last] !~ /[^ \t\r]/) last--
          if (last > 0 && l[last] == label) last--
          while (last > 0 && l[last] !~ /[^ \t\r]/) last--
          for (i = 1; i <= last; i++) print l[i]
          if (last > 0) print ""
        }' "$backup"
    fi
    printf '# Script-driven planning — %s\n\n' "$ts"
    cat "$PRL_OBS_FILE"
    printf '%s\n' "$PRL_CLOSING_LABEL"
  } >"$tmp" || { rm -f "$tmp" "$backup"; prl_log "observations: cannot assemble '$rel'; not flushed"; prl_obs_reset; return 0; }
  prl_obs_reset
  tmp2=$(mktemp "$dir/.observations.XXXXXX") \
    && PRL_N_WT="$wt" PRL_N_MAIN="$main" PRL_N_HOME="$home" awk "$PRL_REWRITE_AWK" "$tmp" >"$tmp2" \
    && chmod 644 "$tmp2" && mv "$tmp2" "$file" \
    || { rm -f "$tmp" "$tmp2" "$backup"; prl_log "observations: cannot write '$rel'; not flushed"; return 0; }
  rm -f "$tmp"

  needles=()
  [ -z "$wt" ] || needles=("${needles[@]}" -e "$wt")
  [ -z "$main" ] || needles=("${needles[@]}" -e "$main")
  [ -z "$home" ] || needles=("${needles[@]}" -e "$home")
  if [ ${#needles[@]} -gt 0 ]; then
    grep -qF "${needles[@]}" "$file"
    rc=$?
  else
    rc=2
  fi
  case "$rc" in
    1) ;;
    0)
      prl_log "observations: '$rel' still carries a machine path after the rewrite; not committed"
      [ -z "$backup" ] || cp "$backup" "$file"
      rm -f "$backup"
      return 0
      ;;
    *) prl_log "observations: the machine-path check could not run; committing" ;;
  esac
  if ! prl_artifact_commit observations 2>/dev/null; then
    prl_log "observations: the commit of '$rel' failed"
    if [ "$PRL_COMMIT_LANDED" = no ] && [ -n "$backup" ]; then cp "$backup" "$file"; fi
  fi
  rm -f "$backup"
  return 0
}
