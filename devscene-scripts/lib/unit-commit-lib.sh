#!/usr/bin/env bash
# unit-commit-lib.sh — the readiness-entry tick, every unit and artifact commit
# subject, the unit's body record and stage set, and the artifact table.
#
# The rule this library exists to enforce: every unit and artifact commit
# subject is built from the readiness index or this file's artifact table,
# never from a caller's text.
#
# SOURCED, NEVER EXECUTED, by `commit-on-branch.sh` (its `--unit` and
# `--artifact` front end) and by the watcher for the script-driven planning
# driver, ahead of `lib/planning-record-lib.sh`. It sets no shell option, makes
# no git call and reads no configuration: the caller does the git reads and
# passes their output in as a file.
#
# BASH 3.2 AND JQ 1.5 ARE THE FLOORS, as in `lib/harness-run-lib.sh`; this
# library uses no jq. Every temporary file names an explicit `mktemp` template.
#
# RESULTS AND STATUSES. Every function returns its result in `UCL_*` globals,
# never on stdout. 0 success; 1 "not found / not applicable"; 2 bad input, with
# one `unit-commit-lib: <cause>` line on stderr.
#
# THE ARTIFACT TABLE is `ucl_artifact`'s `case`, the single declaration of
# every artifact kind's subject and path set. Each subject spells the branch as
# `$branch`, so the fixed-form-subject probe of `## Commit-message policy`
# reaches it. `lib/planning-record-lib.sh` → `prl_artifact_commit` reads it for
# every planning-driver commit.
#
# THE STAGE-SET LISTING `ucl_stage_set` reads: the NUL-separated output of
# `git diff --name-status -z --no-renames <old_tip>`, one `--others` record,
# then that of `git ls-files -z --others --exclude-standard`. A deleted path
# is staged as itself; the wrapper commits an absent path the tip holds as a
# removal (`commit-on-branch.sh` → STAGING POLICY).
#
# REPRO — every public function, against a throwaway index:
#
#   r=$(mktemp -d "${TMPDIR:-/tmp}/ucl-repro.XXXXXX"); . <scripts_dir>/lib/unit-commit-lib.sh
#   mkdir -p "$r/s/story_plans"; i="$r/s/story_plans/feat_x_story_plan.md"
#   printf '## Phase 2 Readiness — Ordered Fix List\n\n1. [ ] **Task 2** — Add `x` _(layer: cli)_\n\n## Next\n' > "$i"
#   ucl_entry_find "$i" Task 2; echo "$? $UCL_ENTRY_LINENO $UCL_ENTRY_STATE"   -> 0 3 open
#   ucl_tick "$i" 3; ucl_entry_find "$i" Task 2; echo "$UCL_ENTRY_STATE"       -> done
#   ucl_short_title "$UCL_ENTRY_LINE"; echo "$UCL_OUT"                         -> Add x
#   ucl_index_kind s s/story_plans/feat_x_story_plan.md; echo "$UCL_KIND"      -> story
#   ucl_unit_label story 2; ucl_unit_prefix story feat_x '' ''
#   ucl_subject "$UCL_OUT" "$UCL_LABEL" 'Add x'; echo "$UCL_SUBJECT"           -> feat: Task 2 — Add x
#   ucl_detail_file story s feat_x 2 "$i"; echo "$UCL_OUT"                     -> s/task_plans/feat_x/task_2_plan.md
#   printf '## Disposition\n- **Cause:** refused\n' > "$r/d.md"
#   ucl_record_cause "$r/d.md" Disposition d.md; echo "$UCL_OUT"              -> refused
#   ucl_body_record 'Task 2' "$UCL_OUT" '' 1 ''; echo "$UCL_OUT"               -> record disposition of Task 2 — refused
#   printf 'M\0s/story_plans/feat_x_story_plan.md\0--others\0' > "$r/l"; UCL_STAGE_FILE="$r/st"
#   ucl_stage_set "$r/l" s/story_plans/feat_x_story_plan.md '' d.md ''; echo "$UCL_WORK_COUNT"  -> 0
#   ucl_severity "$i" 2; echo "$?"                                             -> 1, no `### 2. ` pointer
#   ucl_artifact ledger-flip s feat_x '' '' P1; echo "$UCL_SUBJECT ${UCL_PATHS[*]}"
#     -> chore: Flow progress P1 for feat_x s/flow_progress/feat_x_progress.md

UCL_READINESS_HEADING='## Phase 2 Readiness — Ordered Fix List'
UCL_SUBJECT_MAX=72

ucl_fail() {
  printf 'unit-commit-lib: %s\n' "$1" >&2
  return 2
}

# ucl_bytes <text> — its length in bytes, into UCL_N.
ucl_bytes() {
  UCL_N=$(printf '%s' "$1" | LC_ALL=C wc -c)
  UCL_N=$((UCL_N + 0))
}

ucl_trim() {
  local t="$1"
  t="${t#"${t%%[! ]*}"}"
  UCL_OUT="${t%"${t##*[! ]}"}"
}

# ucl_id_ok <value> — a non-empty `[A-Za-z0-9.]+`.
ucl_id_ok() {
  case "$1" in
    '' | *[!A-Za-z0-9.]*) return 1 ;;
  esac
  return 0
}

# ucl_entry_find <index_file> <Task|Finding|Test> <K>
ucl_entry_find() {
  local file="${1-}" word="${2-}" k="${3-}" line n=0 inside=no digits rest
  UCL_ENTRY_LINE=""
  UCL_ENTRY_LINENO=""
  UCL_ENTRY_STATE=""
  case "$word" in
    Task | Finding | Test) ;;
    *) ucl_fail "ucl_entry_find takes Task, Finding or Test, not '$word'"; return 2 ;;
  esac
  ucl_id_ok "$k" || { ucl_fail "'$k' is not an entry id"; return 2; }
  [ -f "$file" ] && [ -r "$file" ] || { ucl_fail "cannot read the index '$file'"; return 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    if [ "$inside" = no ]; then
      [ "$line" = "$UCL_READINESS_HEADING" ] && inside=yes
      continue
    fi
    case "$line" in
      '## '*) break ;;
    esac
    digits="${line%%[!0-9]*}"
    [ -n "$digits" ] || continue
    rest="${line#"$digits"}"
    case "$rest" in
      ". [ ] **$word $k** — "*) UCL_ENTRY_STATE=open ;;
      ". [x] **$word $k** — "*) UCL_ENTRY_STATE=done ;;
      *) continue ;;
    esac
    UCL_ENTRY_LINE="$line"
    UCL_ENTRY_LINENO="$n"
    return 0
  done <"$file"
  return 1
}

# ucl_tick <index_file> <lineno> — that line's `[ ]` becomes `[x]`, every other
# byte unchanged; 1 when the line is already `[x]`.
ucl_tick() {
  local file="${1-}" n="${2-}" line digits rest prefix off tmp dir
  case "$n" in
    '' | 0 | *[!0-9]*) ucl_fail "'$n' is not a line number"; return 2 ;;
  esac
  [ -f "$file" ] && [ -r "$file" ] || { ucl_fail "cannot read the index '$file'"; return 2; }
  line=$(sed -n "${n}p" "$file")
  digits="${line%%[!0-9]*}"
  rest="${line#"$digits"}"
  [ -n "$digits" ] || { ucl_fail "line $n of '$file' is not a readiness entry"; return 2; }
  case "$rest" in
    '. [x] **'*) return 1 ;;
    '. [ ] **'*) ;;
    *) ucl_fail "line $n of '$file' is not a readiness entry"; return 2 ;;
  esac
  ucl_bytes "$(head -n $((n - 1)) "$file"; printf '.')"
  off=$((UCL_N - 1))
  prefix="${line%%"[ ]"*}"
  ucl_bytes "$prefix"
  off=$((off + UCL_N))
  dir=$(dirname "$file")
  tmp=$(mktemp "$dir/.ucl-tick.XXXXXX") || { ucl_fail "cannot create a temporary file beside '$file'"; return 2; }
  { head -c $((off + 1)) "$file" && printf 'x' && tail -c +$((off + 3)) "$file"; } >"$tmp" \
    && chmod 644 "$tmp" && mv "$tmp" "$file" \
    || { rm -f "$tmp"; ucl_fail "cannot rewrite the index '$file'"; return 2; }
  return 0
}

# ucl_normalise <text> — drops `` ` ``, `$`, `|`, `<`, `>`; a control character
# becomes a space; runs of spaces collapse; trimmed.
ucl_normalise() {
  local t
  t=$(printf '%s' "${1-}" | LC_ALL=C tr -d '`$|<>' | LC_ALL=C tr '\001-\037\177' ' ' | LC_ALL=C tr -s ' ')
  ucl_trim "$t"
}

# ucl_strip_tag <text> <opener> — every `<opener>…)_` removed.
ucl_strip_tag() {
  local t="$1" open="$2" before after
  while :; do
    case "$t" in
      *"$open"*) ;;
      *) break ;;
    esac
    before="${t%%"$open"*}"
    after="${t#*"$open"}"
    case "$after" in
      *')_'*) after="${after#*")_"}" ;;
      *) after="" ;;
    esac
    t="$before $after"
  done
  UCL_OUT="$t"
}

# ucl_short_title <entry_line>
ucl_short_title() {
  local line="${1-}" t
  case "$line" in
    *'** — '*) t="${line#*"** — "}" ;;
    *) UCL_OUT=""; ucl_fail "'$line' carries no '** — ' title"; return 2 ;;
  esac
  ucl_strip_tag "$t" '_(layer:'
  ucl_strip_tag "$UCL_OUT" '_(points:'
  ucl_normalise "$UCL_OUT"
}

# ucl_severity <index_file> <K> — `must`, `should`, `nice` or empty; 1 when no
# `### <K>. ` pointer heading exists.
ucl_severity() {
  local file="${1-}" k="${2-}" line sev=""
  UCL_OUT=""
  ucl_id_ok "$k" || { ucl_fail "'$k' is not an entry id"; return 2; }
  [ -f "$file" ] && [ -r "$file" ] || { ucl_fail "cannot read the index '$file'"; return 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      '## Must Fix' | '## Must Fix '*) sev=must ;;
      '## Should Fix' | '## Should Fix '*) sev=should ;;
      '## Nice to Have' | '## Nice to Have '*) sev=nice ;;
      '## '*) sev="" ;;
      "### $k. "*) UCL_OUT="$sev"; return 0 ;;
    esac
  done <"$file"
  return 1
}

# ucl_index_kind <state_dir> <plan_rel> — UCL_KIND and UCL_FINDINGS_DIR.
ucl_index_kind() {
  local s="${1-}" plan="${2-}" rest dir name
  UCL_KIND=""
  UCL_FINDINGS_DIR=""
  s="${s%/}"
  [ -n "$s" ] && [ -n "$plan" ] || { ucl_fail "ucl_index_kind needs <state_dir> <plan_rel>"; return 2; }
  case "$plan" in
    "$s"/*/*.md) ;;
    *) return 1 ;;
  esac
  rest="${plan#"$s"/}"
  dir="${rest%%/*}"
  case "$dir" in
    story_plans) UCL_KIND=story ;;
    code_reviews) UCL_KIND=code_review ;;
    business_parity_branch_reviews) UCL_KIND=parity_review ;;
    architecture_branch_reviews) UCL_KIND=arch_review ;;
    skeptic_reviews) UCL_KIND=skeptic_review ;;
    qa_reviews) UCL_KIND=qa_review ;;
    test_fix_plans) UCL_KIND=test_fix ;;
    user_reviews) UCL_KIND=user_review ;;
    ui_test_plans) UCL_KIND=ui_test ;;
    *) return 1 ;;
  esac
  name="${plan##*/}"
  case "$UCL_KIND:$name" in
    qa_review:qa_review_*.md) UCL_FINDINGS_DIR="${plan%/*}/" ;;
    *) UCL_FINDINGS_DIR="${plan%.md}/" ;;
  esac
  return 0
}

# ucl_unit_label <kind> <K> — UCL_LABEL for the subject, UCL_TOKEN for the body
# record; 1 for `ui_test`, whose subject is `ucl_ui_pass_subject`.
ucl_unit_label() {
  local kind="${1-}" k="${2-}"
  UCL_LABEL=""
  UCL_TOKEN=""
  ucl_id_ok "$k" || { ucl_fail "'$k' is not an entry id"; return 2; }
  case "$kind" in
    story) UCL_LABEL="Task $k" ;;
    code_review) UCL_LABEL="Code review finding $k" ;;
    parity_review) UCL_LABEL="Parity review finding $k" ;;
    arch_review) UCL_LABEL="Architecture review finding $k" ;;
    skeptic_review) UCL_LABEL="Skeptic review finding $k" ;;
    qa_review) UCL_LABEL="QA finding $k" ;;
    test_fix) UCL_LABEL="Test fix $k" ;;
    user_review) UCL_LABEL="User review finding $k" ;;
    ui_test) return 1 ;;
    *) ucl_fail "'$kind' is not an index kind"; return 2 ;;
  esac
  if [ "$kind" = story ]; then UCL_TOKEN="Task $k"; else UCL_TOKEN="Finding $k"; fi
  return 0
}

# ucl_branch_prefix <branch>
ucl_branch_prefix() {
  case "${1-}" in
    feat_*) UCL_OUT=feat ;;
    fix_*) UCL_OUT=fix ;;
    refactor_*) UCL_OUT=refactor ;;
    *) UCL_OUT=chore ;;
  esac
  return 0
}

# ucl_unit_prefix <kind> <branch> <severity> <prefix_arg>
ucl_unit_prefix() {
  local kind="${1-}" branch="${2-}" sev="${3-}" arg="${4-}"
  UCL_OUT=""
  case "$kind" in
    story | code_review | parity_review | arch_review | skeptic_review | qa_review | test_fix | ui_test | user_review) ;;
    *) ucl_fail "'$kind' is not an index kind"; return 2 ;;
  esac
  if [ "$kind" = user_review ] && [ "$sev" = should ]; then
    case "$arg" in
      refactor | chore) UCL_OUT="$arg"; return 0 ;;
      '') ucl_fail "a Should Fix user-review finding needs --prefix refactor or chore"; return 2 ;;
      *) ucl_fail "'$arg' is not a --prefix token: refactor or chore"; return 2 ;;
    esac
  fi
  [ -z "$arg" ] || { ucl_fail "--prefix is accepted only for a Should Fix user-review finding"; return 2; }
  case "$kind" in
    story) ucl_branch_prefix "$branch" ;;
    user_review)
      case "$sev" in
        must) UCL_OUT=fix ;;
        nice) UCL_OUT=chore ;;
        *) ucl_fail "the user-review finding sits under no severity section"; return 2 ;;
      esac
      ;;
    *) UCL_OUT=fix ;;
  esac
  return 0
}

# ucl_subject <prefix> <label> <title> — UCL_SUBJECT, at most 72 bytes; the
# title is cut at the last space that fits, or dropped with its ` — `.
ucl_subject() {
  local base="${1-}: ${2-}" title="${3-}" best="" cand rest w
  [ -n "${1-}" ] && [ -n "${2-}" ] || { UCL_SUBJECT=""; ucl_fail "ucl_subject needs <prefix> <label>"; return 2; }
  ucl_normalise "$title"
  rest="$UCL_OUT"
  while [ -n "$rest" ]; do
    w="${rest%% *}"
    rest="${rest#"$w"}"
    rest="${rest# }"
    if [ -n "$best" ]; then cand="$best $w"; else cand="$w"; fi
    ucl_bytes "$base — $cand"
    [ "$UCL_N" -le "$UCL_SUBJECT_MAX" ] || break
    best="$cand"
  done
  if [ -n "$best" ]; then UCL_SUBJECT="$base — $best"; else UCL_SUBJECT="$base"; fi
  return 0
}

# ucl_record_cause <detail_abs> <Disposition|Already passing> [<detail_rel>]
ucl_record_cause() {
  local file="${1-}" section="${2-}" rel="${3-}" line inside=no
  UCL_OUT=""
  case "$section" in
    Disposition | 'Already passing') ;;
    *) ucl_fail "ucl_record_cause takes Disposition or Already passing, not '$section'"; return 2 ;;
  esac
  [ -f "$file" ] && [ -r "$file" ] || { ucl_fail "cannot read the detail file '$file'"; return 2; }
  [ -n "$rel" ] || rel="$file"
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$inside" = no ]; then
      case "$line" in
        "## $section" | "## $section "*) inside=yes ;;
      esac
      continue
    fi
    case "$line" in
      '## '*) break ;;
      *'**Cause:** '*)
        ucl_normalise "${line#*"**Cause:** "}"
        [ -n "$UCL_OUT" ] && return 0
        break
        ;;
    esac
  done <"$file"
  [ "$inside" = yes ] || return 1
  ucl_normalise "cause not recorded — see $rel"
  return 0
}

# ucl_detail_file <kind> <state_dir> <branch> <K> <index_file> — UCL_OUT. A
# review kind reads UCL_FINDINGS_DIR, set by `ucl_index_kind`; the pointer may
# name the file by its full path or relative to the index's own directory.
ucl_detail_file() {
  local kind="${1-}" s="${2-}" branch="${3-}" k="${4-}" file="${5-}" line inside=no base p rest tok
  UCL_OUT=""
  s="${s%/}"
  ucl_id_ok "$k" || { ucl_fail "'$k' is not an entry id"; return 2; }
  if [ "$kind" = story ]; then
    [ -n "$s" ] && [ -n "$branch" ] || { ucl_fail "ucl_detail_file needs <state_dir> <branch> for a story"; return 2; }
    UCL_OUT="$s/task_plans/$branch/task_${k}_plan.md"
    return 0
  fi
  [ -n "${UCL_FINDINGS_DIR-}" ] || { ucl_fail "UCL_FINDINGS_DIR is not set; call ucl_index_kind first"; return 2; }
  [ -f "$file" ] && [ -r "$file" ] || { ucl_fail "cannot read the index '$file'"; return 2; }
  base="${UCL_FINDINGS_DIR%/}"
  base="${base##*/}/"
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$inside" = no ]; then
      case "$line" in
        "### $k. "*) inside=yes ;;
      esac
      continue
    fi
    case "$line" in
      '## '* | '### '*) break ;;
    esac
    for p in "$UCL_FINDINGS_DIR" "$base"; do
      case "$line" in
        *"$p"*) ;;
        *) continue ;;
      esac
      rest="${line#*"$p"}"
      tok="${rest%%[!A-Za-z0-9._/-]*}"
      case "$tok" in
        '' | *..* | /*) ;;
        *.md) UCL_OUT="$UCL_FINDINGS_DIR$tok"; return 0 ;;
      esac
    done
  done <"$file"
  UCL_OUT="${UCL_FINDINGS_DIR}finding_$k.md"
  return 0
}

# ucl_body_record <token> <disposition_cause> <already_passing_cause> <work_count> <index_only_set>
# — UCL_OUT, one lower-case record line; 1 when none applies.
ucl_body_record() {
  local token="${1-}" disp="${2-}" ap="${3-}" work="${4-}" set="${5-}"
  UCL_OUT=""
  [ -n "$token" ] || { ucl_fail "ucl_body_record needs <token>"; return 2; }
  case "$work" in
    '' | *[!0-9]*) ucl_fail "'$work' is not a work count"; return 2 ;;
  esac
  if [ -n "$disp" ]; then
    ucl_normalise "record disposition of $token — $disp"
  elif [ -n "$ap" ]; then
    ucl_normalise "mark $token already passing — $ap"
  elif [ "$work" -eq 0 ] && [ -n "$set" ]; then
    ucl_normalise "mark $token done — $set"
  else
    return 1
  fi
  return 0
}

# ucl_under <path> <dir> — 0 when <path> is <dir> or lies under it.
ucl_under() {
  local d="${2%/}"
  [ -n "$d" ] || return 1
  case "$1" in
    "$d" | "$d"/*) return 0 ;;
  esac
  return 1
}

# ucl_stage_set <listing> <plan_rel> <findings_rel> <detail_rel> <findings_dir_rel>
# — the NUL-separated stage set into the file UCL_STAGE_FILE names;
# UCL_WORK_COUNT and UCL_INDEX_ONLY_SET.
ucl_stage_set() {
  local listing="${1-}" plan="${2-}" findings="${3-}" detail="${4-}" fdir="${5-}"
  local rec status="" section=diff p have e set=""
  local -a paths
  UCL_WORK_COUNT=0
  UCL_INDEX_ONLY_SET=""
  [ -n "${UCL_STAGE_FILE-}" ] || { ucl_fail "UCL_STAGE_FILE is not set"; return 2; }
  [ -n "$plan" ] || { ucl_fail "ucl_stage_set needs <plan_rel>"; return 2; }
  [ -f "$listing" ] && [ -r "$listing" ] || { ucl_fail "cannot read the listing '$listing'"; return 2; }
  paths=("$plan")
  [ -z "$findings" ] || paths=("${paths[@]}" "$findings")
  while IFS= read -r -d '' rec || [ -n "$rec" ]; do
    if [ "$section" = diff ]; then
      if [ "$rec" = --others ]; then section=others; continue; fi
      if [ -z "$status" ]; then status="$rec"; continue; fi
      p="$rec"
    else
      status=""
      p="$rec"
    fi
    [ -n "$p" ] || { status=""; continue; }
    if [ -n "$findings" ] && ucl_under "$p" "$findings"; then status=""; continue; fi
    status=""
    have=no
    for e in "${paths[@]}"; do
      [ "$e" = "$p" ] && { have=yes; break; }
    done
    [ "$have" = yes ] || paths=("${paths[@]}" "$p")
  done <"$listing"
  [ "$section" = others ] || { ucl_fail "the listing '$listing' carries no --others record"; return 2; }
  : >"$UCL_STAGE_FILE" || { ucl_fail "cannot write '$UCL_STAGE_FILE'"; return 2; }
  for p in "${paths[@]}"; do
    printf '%s\0' "$p" >>"$UCL_STAGE_FILE" || { ucl_fail "cannot write '$UCL_STAGE_FILE'"; return 2; }
    if [ "$p" = "$plan" ] || [ "$p" = "$detail" ] \
      || { [ -n "$fdir" ] && ucl_under "$p" "$fdir"; } \
      || { [ -n "$findings" ] && ucl_under "$p" "$findings"; }; then
      if [ -n "$set" ]; then set="$set, $p"; else set="$p"; fi
    else
      UCL_WORK_COUNT=$((UCL_WORK_COUNT + 1))
    fi
  done
  UCL_INDEX_ONLY_SET="$set"
  return 0
}

# ucl_artifact <kind> <state_dir> <branch> <round> <iteration> <entry> —
# UCL_SUBJECT and the array UCL_PATHS. The single declaration of every
# artifact kind's subject and path set.
ucl_artifact() {
  local kind="${1-}" s="${2-}" branch="${3-}" round="${4-}" iteration="${5-}" entry="${6-}" sfx=""
  UCL_SUBJECT=""
  UCL_PATHS=()
  s="${s%/}"
  [ -n "$s" ] && [ -n "$branch" ] || { ucl_fail "ucl_artifact needs <state_dir> <branch>"; return 2; }
  case "$kind" in
    plan-round | plan-round-partial | fix-plan | fix-plan-round | fix-plan-round-partial)
      case "$round" in
        '' | *[!0-9]*) ucl_fail "the $kind artifact needs a numeric round, not '$round'"; return 2 ;;
      esac
      [ "$round" = 1 ] || sfx="_$round"
      ;;
  esac
  case "$kind" in
    fix-plan-round | fix-plan-round-partial)
      case "$iteration" in
        '' | *[!0-9]*) ucl_fail "the $kind artifact needs a numeric iteration, not '$iteration'"; return 2 ;;
      esac
      ;;
  esac
  if [ -n "$entry" ] || [ "$kind" = ledger-flip ]; then
    ucl_id_ok "$entry" || { ucl_fail "'$entry' is not an entry id"; return 2; }
  fi
  case "$kind" in
    task-plan)
      UCL_SUBJECT="chore: Add task plan for $branch"
      UCL_PATHS=("$s/story_plans/${branch}_story_plan.md" "$s/task_plans/$branch/" "$s/task_plan_reviews/$branch/"
        "$s/business_parity_reviews/$branch/" "$s/architecture_reviews/$branch/" "$s/plan_revisions/$branch/"
        "$s/ui_test_plan_reviews/$branch/")
      ;;
    plan-round | plan-round-partial)
      if [ "$kind" = plan-round ]; then
        UCL_SUBJECT="chore: Plan round $round for $branch"
      else
        UCL_SUBJECT="chore: Plan round $round partial for $branch"
      fi
      UCL_PATHS=("$s/story_plans/${branch}_story_plan.md" "$s/task_plans/$branch/" "$s/task_plan_reviews/$branch/"
        "$s/business_parity_reviews/$branch/" "$s/architecture_reviews/$branch/" "$s/plan_revisions/$branch/")
      ;;
    ui-test-plan)
      UCL_SUBJECT="chore: Add UI-test plan for $branch"
      UCL_PATHS=("$s/ui_test_plans/${branch}_ui_test_plan.md" "$s/ui_test_plans/$branch/")
      ;;
    ledger)
      UCL_SUBJECT="chore: Add flow-progress ledger for $branch"
      UCL_PATHS=("$s/flow_progress/${branch}_progress.md")
      ;;
    ledger-flip)
      UCL_SUBJECT="chore: Flow progress $entry for $branch"
      UCL_PATHS=("$s/flow_progress/${branch}_progress.md")
      ;;
    statistics)
      UCL_SUBJECT="chore: Add branch statistics for $branch"
      UCL_PATHS=("$s/branch_statistics/$branch/statistics.md")
      ;;
    statistics-update)
      UCL_SUBJECT="chore: Update branch statistics for $branch"
      UCL_PATHS=("$s/branch_statistics/$branch/statistics.md")
      ;;
    observations)
      UCL_SUBJECT="chore: Log improvement observations for $branch"
      UCL_PATHS=("$s/improvement_observations/$branch.md")
      ;;
    dispatch-additions)
      UCL_SUBJECT="chore: Log dispatch additions for $branch"
      UCL_PATHS=("$s/dispatch_additions/$branch.md")
      ;;
    clarification-digest)
      UCL_SUBJECT="chore: Record clarification digest for $branch"
      UCL_PATHS=("$s/clarification_digests/$branch.md")
      ;;
    lessons)
      UCL_SUBJECT="chore: Record lessons for $branch"
      UCL_PATHS=("$s/lessons.md")
      ;;
    fix-plan)
      UCL_SUBJECT="chore: Add user-review fix plan for $branch"
      UCL_PATHS=("$s/user_reviews/${branch}_fix_plan$sfx.md" "$s/user_reviews/${branch}_review$sfx.md"
        "$s/user_reviews/${branch}_fix_plan$sfx/" "$s/business_parity_user_review_reviews/$branch/"
        "$s/architecture_user_review_reviews/$branch/" "$s/plan_revisions/$branch/")
      ;;
    fix-plan-round | fix-plan-round-partial)
      if [ "$kind" = fix-plan-round ]; then
        UCL_SUBJECT="chore: Fix plan $round round $iteration for $branch"
      else
        UCL_SUBJECT="chore: Fix plan $round round $iteration partial for $branch"
      fi
      UCL_PATHS=("$s/user_reviews/${branch}_fix_plan$sfx.md" "$s/user_reviews/${branch}_fix_plan$sfx/"
        "$s/business_parity_user_review_reviews/$branch/user_review_$round/"
        "$s/architecture_user_review_reviews/$branch/user_review_$round/" "$s/plan_revisions/$branch/")
      ;;
    rescreened-input)
      UCL_SUBJECT="chore: Commit re-screened input edit for $branch"
      ;;
    *) ucl_fail "'$kind' is not an artifact kind"; return 2 ;;
  esac
  return 0
}

# ucl_review_kind_subject <branch> — the `review_plan_file` unit's subject.
ucl_review_kind_subject() {
  local branch="${1-}"
  [ -n "$branch" ] || { UCL_SUBJECT=""; ucl_fail "ucl_review_kind_subject needs <branch>"; return 2; }
  UCL_SUBJECT="chore: add code review for $branch"
  return 0
}

# ucl_ui_pass_subject <K> <branch> — the `ui_test_pass` unit's subject.
ucl_ui_pass_subject() {
  local k="${1-}" branch="${2-}"
  UCL_SUBJECT=""
  ucl_id_ok "$k" || { ucl_fail "'$k' is not a UI test id"; return 2; }
  [ -n "$branch" ] || { ucl_fail "ucl_ui_pass_subject needs <branch>"; return 2; }
  UCL_SUBJECT="chore: Mark UI test $k passing for $branch"
  return 0
}
