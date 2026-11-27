#!/usr/bin/env bash
# review-sweep.sh — apply the rows of `.claude/review-sweep.md`, as the default
# branch commits it, to the lines the current branch adds, and print one
# `<path>:<line>: <escape class>` per added line a row's regex matches inside
# that row's `Covers` minus its `Exempts`. `<line>` is the branch file's line
# number. The state directory is never swept. A hit is a lead for the reviewer
# to verify in context, never a finding.
#
# EXIT MAP.
#   0  no hit; nothing printed.
#   1  at least one hit, one line each on stdout, rows in document order.
#   2  a configuration error; exactly one line on stderr naming the cause, and
#      nothing on stdout. Bad usage; this script's own `devscene.config.json`
#      unreadable; `--repo` not a work tree; `<default_branch>` not resolvable
#      — or `origin/<default_branch>` when `--repo` carries no local
#      `<default_branch>`, as a run copy does; the document not committed on
#      `<default_branch>`; the document still an
#      untouched skeleton (`<!-- devscene:unfilled -->` and
#      `**What belongs here**` both present); no `## Sweep rows` heading, a
#      header row other than the exact one, or no data row; a malformed row
#      (not five cells, a `Regex` cell that is not one code span, an empty
#      `Escape class` or `Covers`, a list entry that is not a code span); an
#      invalid regex, named by its escape class; a diff git refuses.
#
# WHO RUNS IT. `branch-reviewer`'s Pass 0, as
# `bash <MAIN_REPO>/<scriptsDir>/review-sweep.sh --repo <repo_root>`: the main
# checkout's copy, aimed at the run's checkout. `defaultBranch` and `stateDir`
# come from the configuration beside THIS script, never from `--repo`'s, and
# the rows come from `git show <default_branch>:.claude/review-sweep.md` — or
# `origin/<default_branch>` when `--repo` carries no local `<default_branch>`,
# as a run copy does — in `--repo`, never its working tree: a branch cannot
# weaken its own sweep.
#
# REUSED FROM `lib/harness-run-lib.sh`: `hr_script_root`, `hr_config_load`,
# `hr_default_branch`, `hr_state_dir`, `hr_repo_root`. The row parser is this
# script's own; `cli/templates/claude/review-sweep.md` states the format it
# reads, and a change to either is a change to both.
#
# NO `set -e`. Every refusal must leave exactly one stderr line and exit 2, and
# grep's exit 1 ("no match") is an ordinary answer; each step tests its own
# status instead.
#
# WRITES NO FILE. Lines are fed to `grep` through pipes and process
# substitution, never a here-string, which bash 3.2 backs with a temporary file.
#
# REPRO — reproduce each exit by hand, against a throwaway fixture:
#
#   w=$(mktemp -d); d="$w/demo"; git init -q -b main "$d"
#   mkdir -p "$d/scripts/lib"   # copy this script + lib/harness-run-lib.sh there
#   printf '{"defaultBranch":"main","stateDir":"devscene"}\n' > "$d/devscene.config.json"
#   git -C "$d" -c user.name=r -c user.email=r@x commit -q --allow-empty -m base
#
#   not committed  bash "$d/scripts/review-sweep.sh"; echo $?
#                  -> one line on stderr ("... not committed on main"), 2
#   no hit         mkdir -p "$d/.claude"
#                  printf '## Sweep rows\n\n| Escape class | Regex | Covers | Exempts | A hit is a candidate for |\n|---|---|---|---|---|\n| Raw console | `console\\.log` | `.` | — | the logger |\n' > "$d/.claude/review-sweep.md"
#                  git -C "$d" add .claude && git -C "$d" -c user.name=r -c user.email=r@x commit -qm rows
#                  git -C "$d" checkout -qb feat
#                  bash "$d/scripts/review-sweep.sh" --repo "$d"; echo $?
#                  -> nothing printed, 0
#   hit            printf 'x\nconsole.log(1)\n' > "$d/a.js"
#                  git -C "$d" add a.js && git -C "$d" -c user.name=r -c user.email=r@x commit -qm a
#                  bash "$d/scripts/review-sweep.sh" --repo "$d"; echo $?
#                  -> "a.js:2: Raw console" on stdout, 1
#   bad usage      bash "$d/scripts/review-sweep.sh" --bogus; echo $?
#                  -> one usage line on stderr, 2

set -u

RS_SWEEP_PATH=".claude/review-sweep.md"
RS_HEADING="## Sweep rows"
RS_HEADER_ROW="| Escape class | Regex | Covers | Exempts | A hit is a candidate for |"
RS_NONE="—"
# Stands in for an escaped `\|` while a row is split on the unescaped ones.
RS_SEP=$'\001'
RS_TAB=$'\t'

rs_fail() {
  printf 'review-sweep.sh: %s\n' "$1" >&2
  exit 2
}

rs_usage() {
  printf 'usage: review-sweep.sh [--repo <checkout>]\n' >&2
  exit 2
}

{ . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/harness-run-lib.sh"; } 2>/dev/null \
  || rs_fail "cannot load lib/harness-run-lib.sh beside this script"

repo=""
repo_given=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] && [ -n "$2" ] && [ "$repo_given" -eq 0 ] || rs_usage
      repo=$2
      repo_given=1
      shift 2
      ;;
    *) rs_usage ;;
  esac
done

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || rs_fail "cannot resolve this script's directory"
root=$(hr_script_root "$script_dir") || rs_fail "cannot place this script's repository root"

hr_config_load "$root"
case $? in
  0) ;;
  1) rs_fail "no devscene.config.json at $root" ;;
  *) rs_fail "devscene.config.json at $root could not be read (unreadable, not valid JSON, no defaultBranch, or jq missing)" ;;
esac
default_branch=$(hr_default_branch "$root") || rs_fail "devscene.config.json at $root has no readable defaultBranch"
[ -n "$default_branch" ] || rs_fail "devscene.config.json at $root has an empty defaultBranch"
state_dir=$(hr_state_dir "$root") || rs_fail "devscene.config.json at $root has no readable stateDir"
while [ -n "$state_dir" ] && [ "${state_dir%/}" != "$state_dir" ]; do state_dir=${state_dir%/}; done
[ -n "$state_dir" ] || rs_fail "devscene.config.json at $root has an empty stateDir"

[ "$repo_given" -eq 1 ] || repo=$root
top=$(hr_repo_root "$repo") || rs_fail "--repo $repo is not a git work tree"

if git -C "$top" rev-parse --verify --quiet "refs/heads/$default_branch^{commit}" >/dev/null 2>&1; then
  base_ref=$default_branch
elif git -C "$top" rev-parse --verify --quiet "refs/remotes/origin/$default_branch^{commit}" >/dev/null 2>&1; then
  base_ref=origin/$default_branch
else
  rs_fail "default branch $default_branch does not resolve in $top, as a local branch or as origin/$default_branch"
fi

doc=$(git -C "$top" show "$base_ref:$RS_SWEEP_PATH" 2>/dev/null) \
  || rs_fail "$RS_SWEEP_PATH is not committed on $base_ref"

case "$doc" in
  *"<!-- devscene:unfilled -->"*)
    case "$doc" in
      *"**What belongs here**"*) rs_fail "$RS_SWEEP_PATH on $base_ref is still an untouched skeleton" ;;
    esac
    ;;
esac

# Trim leading and trailing whitespace from $1 into RS_TRIMMED.
rs_trim_var() {
  local s="${1-}"
  s=${s#"${s%%[![:space:]]*}"}
  s=${s%"${s##*[![:space:]]}"}
  RS_TRIMMED=$s
}

# Set RS_SPAN to the inside of $1 when $1 is exactly one non-empty backtick code
# span; return 1 otherwise.
rs_code_span_var() {
  local cell="${1-}" inner
  RS_SPAN=""
  case "$cell" in
    \`*\`) ;;
    *) return 1 ;;
  esac
  inner=${cell#\`}
  inner=${inner%\`}
  case "$inner" in
    '' | *\`*) return 1 ;;
  esac
  RS_SPAN=$inner
}

# Set RS_LIST to the code-span entries of the `, `-separated cell $1, one per
# line; return 1 when any entry is not a code span.
rs_span_list_var() {
  local rest="${1-}" item out=""
  RS_LIST=""
  while :; do
    item=${rest%%, *}
    rs_code_span_var "$item" || return 1
    out="$out$RS_SPAN
"
    [ "$item" != "$rest" ] || break
    rest=${rest#*, }
  done
  RS_LIST=$out
}

# Parallel arrays, one entry per row in document order.
row_class=()
row_regex=()
row_covers=()
row_exempts=()
rows=0

state=seek
lineno=0
while IFS= read -r line || [ -n "$line" ]; do
  lineno=$((lineno + 1))
  case "$state" in
    seek)
      [ "$line" = "$RS_HEADING" ] && state=header
      ;;
    header)
      [ -z "$line" ] && continue
      [ "$line" = "$RS_HEADER_ROW" ] \
        || rs_fail "the table under '$RS_HEADING' does not open with the exact header row (document line $lineno)"
      state=separator
      ;;
    separator)
      case "$line" in
        \|*) ;;
        *) rs_fail "the table under '$RS_HEADING' has no separator row (document line $lineno)" ;;
      esac
      case "$line" in
        *[!\|:[:space:]-]*) rs_fail "the table under '$RS_HEADING' has no separator row (document line $lineno)" ;;
      esac
      state=rows
      ;;
    rows)
      case "$line" in
        \|*) ;;
        *) break ;;
      esac
      rs_trim_var "$line"
      rest=${RS_TRIMMED#|}
      case "$rest" in
        *\\\|) ;;
        *\|) rest=${rest%|} ;;
      esac
      rest=${rest//\\|/$RS_SEP}
      cells=()
      while :; do
        cell=${rest%%|*}
        cells[${#cells[@]}]=$cell
        [ "$cell" != "$rest" ] || break
        rest=${rest#*|}
      done
      [ "${#cells[@]}" -eq 5 ] \
        || rs_fail "malformed row at document line $lineno: ${#cells[@]} cells, not 5"

      rs_trim_var "${cells[0]//$RS_SEP/\\|}"
      class=$RS_TRIMMED
      [ -n "$class" ] || rs_fail "malformed row at document line $lineno: empty Escape class"

      rs_trim_var "${cells[1]}"
      rs_code_span_var "$RS_TRIMMED" \
        || rs_fail "malformed row '$class': the Regex cell is not exactly one code span"
      regex=${RS_SPAN//$RS_SEP/|}

      rs_trim_var "${cells[2]//$RS_SEP/\\|}"
      [ -n "$RS_TRIMMED" ] || rs_fail "malformed row '$class': empty Covers"
      rs_span_list_var "$RS_TRIMMED" \
        || rs_fail "malformed row '$class': a Covers entry is not a code span"
      covers=$RS_LIST

      rs_trim_var "${cells[3]//$RS_SEP/\\|}"
      if [ "$RS_TRIMMED" = "$RS_NONE" ]; then
        exempts=""
      else
        [ -n "$RS_TRIMMED" ] || rs_fail "malformed row '$class': empty Exempts (write $RS_NONE for none)"
        rs_span_list_var "$RS_TRIMMED" \
          || rs_fail "malformed row '$class': an Exempts entry is not a code span"
        exempts=$RS_LIST
      fi

      row_class[$rows]=$class
      row_regex[$rows]=$regex
      row_covers[$rows]=$covers
      row_exempts[$rows]=$exempts
      rows=$((rows + 1))
      ;;
  esac
done < <(printf '%s\n' "$doc")

case "$state" in
  seek) rs_fail "$RS_SWEEP_PATH on $base_ref has no '$RS_HEADING' heading" ;;
  header) rs_fail "the '$RS_HEADING' heading has no table under it" ;;
  separator) rs_fail "the table under '$RS_HEADING' has no separator row" ;;
esac
[ "$rows" -gt 0 ] || rs_fail "the table under '$RS_HEADING' has no data row"

i=0
while [ "$i" -lt "$rows" ]; do
  grep -E -e "${row_regex[$i]}" </dev/null >/dev/null 2>&1
  [ "$?" -ne 2 ] || rs_fail "invalid regex in row '${row_class[$i]}'"
  i=$((i + 1))
done

hits=""
i=0
while [ "$i" -lt "$rows" ]; do
  spec=()
  while IFS= read -r p; do
    [ -n "$p" ] && spec[${#spec[@]}]=$p
  done < <(printf '%s' "${row_covers[$i]}")
  spec[${#spec[@]}]=":(top,exclude)$state_dir"
  while IFS= read -r p; do
    [ -n "$p" ] && spec[${#spec[@]}]=":(top,exclude)$p"
  done < <(printf '%s' "${row_exempts[$i]}")

  diff=$(git -C "$top" -c core.quotePath=false diff --no-color --no-ext-diff --unified=0 \
    --src-prefix=a/ --dst-prefix=b/ "$base_ref...HEAD" -- "${spec[@]}" 2>/dev/null) \
    || rs_fail "git diff $base_ref...HEAD failed in $top for row '${row_class[$i]}'"

  # The added lines' text and, at the same index, their `<path>:<line>`.
  texts=()
  locs=()
  path=""
  old_left=0
  new_left=0
  new_line=0
  while IFS= read -r d; do
    if [ "$old_left" -gt 0 ] || [ "$new_left" -gt 0 ]; then
      case "$d" in
        +*)
          if [ -n "$path" ]; then
            texts[${#texts[@]}]=${d#+}
            locs[${#locs[@]}]="$path:$new_line"
          fi
          new_line=$((new_line + 1))
          new_left=$((new_left - 1))
          ;;
        -*) old_left=$((old_left - 1)) ;;
      esac
      continue
    fi
    case "$d" in
      "+++ /dev/null") path="" ;;
      "+++ "*)
        p=${d#"+++ "}
        # git ends a `+++` name holding a space with a tab.
        p=${p%"$RS_TAB"}
        case "$p" in
          \"*\") p=${p#\"}; p=${p%\"} ;;
        esac
        path=${p#b/}
        ;;
      "@@ -"*)
        h=${d#"@@ -"}
        old=${h%% *}
        h=${h#* +}
        new=${h%% *}
        case "$old" in *,*) old_left=${old#*,} ;; *) old_left=1 ;; esac
        case "$new" in *,*) new_line=${new%%,*}; new_left=${new#*,} ;; *) new_line=$new; new_left=1 ;; esac
        case "$old_left$new_left$new_line" in
          *[!0-9]* | '') rs_fail "unreadable hunk header in git diff output: $d" ;;
        esac
        ;;
    esac
  done < <(printf '%s\n' "$diff")

  if [ "${#texts[@]}" -gt 0 ]; then
    matched=$(printf '%s\n' "${texts[@]}" | grep -n -a -E -e "${row_regex[$i]}")
    [ "$?" -ne 2 ] || rs_fail "grep failed applying row '${row_class[$i]}'"
    if [ -n "$matched" ]; then
      while IFS= read -r m; do
        n=${m%%:*}
        hits="$hits${locs[$((n - 1))]}: ${row_class[$i]}
"
      done < <(printf '%s\n' "$matched")
    fi
  fi
  i=$((i + 1))
done

[ -n "$hits" ] || exit 0
printf '%s' "$hits"
exit 1
