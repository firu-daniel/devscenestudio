#!/usr/bin/env bash
# planning-node-lib.sh — one planning node session, for the script-driven
# planning driver: the node's prompt, read out of the pinned plugin's planning
# core; the return schema its agent's return object must satisfy, read out of
# the pinned plugin's `schemas/<agent>.return.json`; the per-node launch flags;
# the background launch; and the validated read of the session's stream once it
# has exited.
#
# The rule this library exists to enforce: a node's result is a declared
# outcome, `error` or `undelivered`, never a guess. `pnl_reap` decides it from
# the stream alone, in one fixed order: the outcome is read only from the
# return block that ends the `result` text, validated against the agent's own
# `schemas/<agent>.return.json`, and an outcome the node's graph entry does not
# declare is `error`, whatever else the session printed. Every `error` carries
# its class, decided here and nowhere else: `infra` for no `init` event, a
# session that ended not `success` or with `is_error`, a result whose return
# block is missing, not one JSON object or fails the schema, and a `FAIL` — or
# a round gate's `PASS` — that carries no non-blank `findings_file` —
# infrastructure because the driver's bounded re-dispatch of the same prompt is
# the remedy for a malformed reply, as the plugin's return contract
# (`agent_return_contract.md` → `## A return that fails the check`) bounds it at
# three attempts; `agent` for every other `error`. A session is refused for its
# tools only when its `init` tools carry one the agent does not declare; a
# declared tool the session lacks is reported on `withheld=` and never refused,
# because a missing tool cannot widen what the session does.
#
# IT LAUNCHES NOTHING ON ITS OWN AND DECIDES NO ROUTING. Which node runs next,
# when a set is launched, STOP, PAUSE, the dispatch cap, recording with
# `flow-walker.sh next`, retries and the stall kill are
# `lib/planning-driver-lib.sh`'s. Every durable write is
# `lib/planning-record-lib.sh`'s, except the two run-log-side writes `pnl_reap`
# makes — the node's stream appended to the run's `.stream.jsonl` and the
# node-session manifest under `${log_path%.log}.planning/`. The shared flag vector — the binary, the
# per-run settings, the permission mode, the model, the effort, the added
# directories, the environment scrub and the main-checkout anchor's export — is
# the watcher function the caller names in `PD_SESSION_EXEC`; this library
# appends only the per-node flags `pnl_agent_flags` prints.
#
# SOURCED, NEVER EXECUTED. It sets no shell option. The caller sources
# `lib/harness-run-lib.sh` first: `pnl_init` resolves `stateDir` and
# `scriptsDir` through it.
#
# BASH 3.2 AND JQ 1.5 ARE THE FLOORS, as in `lib/harness-run-lib.sh`: no
# associative array, no array-reading builtin, no `local -n`; no regex in jq,
# every jq `if` has an `else`.
#
# TEMPORARY FILES. Every one — a node's return schema, a filtered MCP config,
# a `result` text, a return object, a verdict — lives in the one directory
# `pnl_init` makes, which
# holds files only. `pnl_cleanup` removes its files and then the directory,
# never recursively; the driver calls it on every return path.
#
# THE CORE IS WIRE TEXT. `PNL_CORE_SETUP_HEADING` and `PNL_CORE_BLOCKS` below
# are the headings of `<plugin_dir>/instructions/task_plan_writing_instructions_core.md`
# this library keys on, declared once so a suite can hold them against the core.
# Each `PNL_CORE_BLOCKS` row is `<## section>|<### heading>|<keys>`: the
# heading's fenced blocks, in order, become the keys' prompts.
#
# GLOBALS. `pnl_init` sets `PNL_PLUGIN_DIR`, `PNL_WORKTREE`, `PNL_STATE_DIR`,
# `PNL_SCRIPTS_DIR`, `PNL_GRAPH`, `PNL_TMP`, `PNL_PLUGIN_NAME`,
# `PNL_MAX_DISPATCHES`, one `PNL_BLOCK_<key>` per key, and writes
# `<PNL_TMP>/schema-<node>.json` per `kind: "dispatch"` node. `pnl_launch` sets
# `PNL_HANDLE`, and must run in the shell that will `wait` on the session —
# never inside `$(…)`. It reads `PD_SESSION_EXEC`, `PD_FORMATTER` and the
# optional `PD_PLUGIN_DIR_ADDED`.
#
# STATUSES. 0 done; 2 a fault, with one `planning-driver: <cause>` line on
# stderr.
#
# REPRO — every public function, against a throwaway fixture:
#
#   w=$(mktemp -d "${TMPDIR:-/tmp}/pnl-repro.XXXXXX"); mkdir -p "$w/s/lib" "$w/s/flows"
#   printf '{"defaultBranch":"main","stateDir":"devscene/","scriptsDir":"s"}' > "$w/devscene.config.json"
#   cp <scripts_dir>/lib/harness-run-lib.sh <scripts_dir>/lib/planning-node-lib.sh "$w/s/lib/"
#   cp <scripts_dir>/flows/task_plan_writing.graph.json "$w/s/flows/"
#   . "$w/s/lib/harness-run-lib.sh"; . "$w/s/lib/planning-node-lib.sh"
#
#   init      pnl_init <plugin_root> "$w"; echo "$? $PNL_PLUGIN_NAME $PNL_MAX_DISPATCHES"
#               -> 0 devscene 40
#             pnl_init "$w" "$w"     -> 2, `planning-driver: … plugin.json …`
#   prompt    pnl_prompt plan_writer revision feat_x 1 '' a.md b.md
#               -> `Revise the task plan per findings at a.md, b.md.` …
#   schema    jq -c '[.oneOf[].properties.outcome.const]' "$PNL_TMP/schema-plan_review.json"
#               -> ["PASS","FAIL","blocker"]
#   flags     pnl_agent_flags plan_review task-plan-reviewer
#               -> --agent / devscene:task-plan-reviewer / --plugin-dir / <plugin_root> /
#                  --add-dir / <plugin_root> / --strict-mcp-config / --mcp-config /
#                  <PNL_TMP>/mcp-plan_review.json
#   launch    s() { printf '%s\n' '{"type":"system","subtype":"init","tools":[]}'; }
#             PD_SESSION_EXEC=s PD_FORMATTER=cat
#             pnl_launch 1 plan_review task-plan-reviewer "$(pnl_prompt plan_review '' feat_x 0 '')" "$w/run.log"
#             h=$PNL_HANDLE; wait "${h%%	*}"
#   reap      pnl_reap "$h"   -> kind=undelivered … withheld=<the reviewer's
#                                non-mcp__ tools:> / reason=no result event
#   cleanup   pnl_cleanup; echo "$PNL_TMP"   -> empty, the directory gone

PNL_CORE_SETUP_HEADING='## Setup (once per session)'
PNL_CORE_BLOCKS='## Loop|### 1. Spawn `task-plan-writer`|plan_writer_initial plan_writer_revision
## Loop|### 2. Business-parity review (plan-review mode)|business_parity_review
## Loop|### 3. Architecture review (plan-review mode)|architecture_review
## Loop|### 4. Spawn `task-plan-reviewer`|plan_review
## UI-test-plan write loop|### 1. Spawn `ui-tests-plan-writer`|ui_writer_initial ui_writer_revision
## UI-test-plan write loop|### 2. Spawn `ui-tests-plan-reviewer`|ui_review'

pnl_fail() {
  printf 'planning-driver: %s\n' "$1" >&2
  return 2
}

# Remove the library's temporary directory: its files, then the directory.
pnl_cleanup() {
  if [ -n "${PNL_TMP-}" ] && [ -d "$PNL_TMP" ]; then
    rm -f "$PNL_TMP"/*
    rmdir "$PNL_TMP" 2>/dev/null
  fi
  PNL_TMP=""
  return 0
}

# pnl_core_scan <core> <section> <heading> <n>
#
# With <n> 0, print `<section found> <heading found> <fence lines>`. With <n>
# above 0, print the text between the fences of the heading's <n>th block. A
# heading is scoped to its `##` section and ends at the next `##` or `###`; a
# fence line opens with three backticks, and nothing inside a fence is read as
# a heading.
pnl_core_scan() {
  awk -v sec="$2" -v head="$3" -v want="$4" '
    BEGIN { insec = 0; inhead = 0; infence = 0; fences = 0; block = 0; fsec = 0; fhead = 0 }
    {
      line = $0
      sub(/\r$/, "", line)
      if (substr(line, 1, 3) == "```") {
        if (infence) { infence = 0 } else { infence = 1; if (inhead) block++ }
        if (inhead) fences++
        next
      }
      if (infence) {
        if (inhead && want > 0 && block == want) print line
        next
      }
      if (substr(line, 1, 3) == "## ") {
        insec = (line == sec); if (insec) fsec = 1
        inhead = 0
        next
      }
      if (substr(line, 1, 4) == "### ") {
        inhead = (insec && line == head); if (inhead) fhead = 1
        next
      }
    }
    END { if (want == 0) printf "%d %d %d\n", fsec, fhead, fences }
  ' "$1"
}

# pnl_init <plugin_dir> <worktree>
pnl_init() {
  local plugin_dir="${1-}" worktree="${2-}" core manifest name scan row section heading keys key
  local fsec fhead fences want n line max="" in_setup=0 text count
  pnl_cleanup
  [ -n "$plugin_dir" ] && [ -d "$plugin_dir" ] || { pnl_fail "the plugin directory '$plugin_dir' does not exist"; return 2; }
  [ -n "$worktree" ] && [ -d "$worktree" ] || { pnl_fail "the worktree '$worktree' does not exist"; return 2; }
  command -v jq >/dev/null 2>&1 || { pnl_fail "jq is not on PATH"; return 2; }
  command -v hr_state_dir >/dev/null 2>&1 || { pnl_fail "lib/harness-run-lib.sh is not sourced"; return 2; }

  PNL_PLUGIN_DIR="${plugin_dir%/}"
  PNL_WORKTREE="${worktree%/}"
  PNL_STATE_DIR=$(hr_state_dir "$PNL_WORKTREE") || { pnl_fail "stateDir does not resolve in '$PNL_WORKTREE/devscene.config.json'"; return 2; }
  PNL_SCRIPTS_DIR=$(hr_scripts_dir "$PNL_WORKTREE") || { pnl_fail "scriptsDir does not resolve in '$PNL_WORKTREE/devscene.config.json'"; return 2; }
  PNL_GRAPH="$PNL_WORKTREE/$PNL_SCRIPTS_DIR/flows/task_plan_writing.graph.json"
  jq -e '.nodes | type == "object"' "$PNL_GRAPH" >/dev/null 2>&1 \
    || { pnl_fail "the planning graph '$PNL_GRAPH' is missing or carries no nodes"; return 2; }

  manifest="$PNL_PLUGIN_DIR/.claude-plugin/plugin.json"
  name=$(jq -r '.name | strings' "$manifest" 2>/dev/null) || name=""
  [ -n "$name" ] || { pnl_fail "'$manifest' carries no non-empty name"; return 2; }
  PNL_PLUGIN_NAME="$name"

  core="$PNL_PLUGIN_DIR/instructions/task_plan_writing_instructions_core.md"
  [ -f "$core" ] && [ -r "$core" ] || { pnl_fail "the planning core '$core' cannot be read"; return 2; }

  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case "$line" in
      '## '*)
        if [ "$line" = "$PNL_CORE_SETUP_HEADING" ]; then in_setup=1; else in_setup=0; fi
        continue
        ;;
    esac
    [ "$in_setup" -eq 1 ] || continue
    case "$line" in
      *'MAX_TOTAL_DISPATCHES = '[0-9]*)
        n=${line#*MAX_TOTAL_DISPATCHES = }
        max=${n%%[!0-9]*}
        break
        ;;
    esac
  done <"$core"
  [ -n "$max" ] || { pnl_fail "no 'MAX_TOTAL_DISPATCHES = <n>' line under '$PNL_CORE_SETUP_HEADING' in '$core'"; return 2; }
  PNL_MAX_DISPATCHES=$((10#$max))

  while IFS= read -r row; do
    [ -n "$row" ] || continue
    section=${row%%|*}
    heading=${row#*|}
    keys=${heading#*|}
    heading=${heading%%|*}
    scan=$(pnl_core_scan "$core" "$section" "$heading" 0)
    fsec=${scan%% *}
    fhead=${scan#* }
    fences=${fhead#* }
    fhead=${fhead%% *}
    [ "$fsec" = 1 ] || { pnl_fail "the heading '$section' is not in '$core'"; return 2; }
    [ "$fhead" = 1 ] || { pnl_fail "the heading '$heading' is not under '$section' in '$core'"; return 2; }
    count=0
    for key in $keys; do count=$((count + 1)); done
    [ "$fences" -eq $((count * 2)) ] \
      || { pnl_fail "the heading '$heading' carries $fences fence lines in '$core', where $count fenced block(s) are expected"; return 2; }
    want=0
    for key in $keys; do
      want=$((want + 1))
      text=$(pnl_core_scan "$core" "$section" "$heading" "$want")
      printf -v "PNL_BLOCK_$key" '%s' "$text"
    done
  done <<EOF
$PNL_CORE_BLOCKS
EOF

  PNL_TMP=$(mktemp -d "${TMPDIR:-/tmp}/planning-node.XXXXXX") || { PNL_TMP=""; pnl_fail "cannot create a temporary directory"; return 2; }
  pnl_load_schemas || { pnl_cleanup; return 2; }
  return 0
}

# pnl_load_schemas — for every `kind: "dispatch"` node of the planning graph,
# its agent's `<PNL_PLUGIN_DIR>/schemas/<agent>.return.json` as compact JSON in
# `<PNL_TMP>/schema-<node>.json`. A missing or unreadable file, a file that is
# not one JSON object, or one with no top-level `oneOf` array is a fault naming
# the file, so no session is launched against an agent with no schema.
pnl_load_schemas() {
  local pairs node agent f obj
  pairs=$(jq -r '.nodes | to_entries[] | select(.value.kind == "dispatch") | .key + " " + (.value.agent | if type == "string" then . else "" end)' "$PNL_GRAPH" 2>/dev/null) \
    || { pnl_fail "the planning graph '$PNL_GRAPH' could not be read for its dispatch nodes"; return 2; }
  while IFS=' ' read -r node agent; do
    [ -n "$node" ] || continue
    [ -n "$agent" ] || { pnl_fail "the planning graph '$PNL_GRAPH' names no agent for dispatch node '$node'"; return 2; }
    f="$PNL_PLUGIN_DIR/schemas/$agent.return.json"
    [ -f "$f" ] && [ -r "$f" ] || { pnl_fail "the return schema file '$f' cannot be read"; return 2; }
    obj=$(jq -c -s 'if length == 1 and (.[0] | type) == "object" then .[0] else error("not one object") end' "$f" 2>/dev/null) \
      || { pnl_fail "the return schema file '$f' is not one JSON object"; return 2; }
    printf '%s\n' "$obj" | jq -e '(.oneOf | type) == "array"' >/dev/null 2>&1 \
      || { pnl_fail "the return schema file '$f' carries no top-level oneOf array"; return 2; }
    printf '%s\n' "$obj" >"$PNL_TMP/schema-$node.json" || { pnl_fail "cannot write '$PNL_TMP/schema-$node.json'"; return 2; }
  done <<EOF
$pairs
EOF
  return 0
}

# pnl_sub_var <text> <token> <value> — every <token> in <text> replaced by
# <value>, into PNL_OUT. Replaced text is not scanned again, and `&` in <value>
# stays literal under any bash.
pnl_sub_var() {
  local rest="$1" token="$2" value="$3" out=""
  while :; do
    case "$rest" in
      *"$token"*) ;;
      *) break ;;
    esac
    out="$out${rest%%"$token"*}$value"
    rest=${rest#*"$token"}
  done
  PNL_OUT="$out$rest"
}

# pnl_prompt <node> <variant> <branch> <iteration> <review_mode> [findings_file…]
#
# The node's dispatch block with the values `## The walker` → `action:
# dispatch` fills, and nothing else. <variant> (`initial` or `revision`) picks a
# writer's block and is ignored for a gate. The findings tokens are filled only
# when at least one findings file is given.
pnl_prompt() {
  local node="${1-}" variant="${2-}" branch="${3-}" iteration="${4-}" review_mode="${5-}" key var text joined="" first="" f
  case "$node" in
    plan_writer | ui_writer)
      case "$variant" in
        initial | revision) key="${node}_$variant" ;;
        *) pnl_fail "no '$variant' prompt for $node"; return 2 ;;
      esac
      ;;
    business_parity_review | architecture_review | plan_review | ui_review) key="$node" ;;
    *) pnl_fail "no dispatch block for node '$node'"; return 2 ;;
  esac
  var="PNL_BLOCK_$key"
  text="${!var-}"
  [ -n "$text" ] || { pnl_fail "the $key block is not loaded; call pnl_init first"; return 2; }
  shift 5 2>/dev/null || shift $#
  for f in "$@"; do
    if [ -z "$first" ]; then
      first="$f"
      joined="$f"
    else
      joined="$joined, $f"
    fi
  done
  pnl_sub_var "$text" '<prompt_path>' "$PNL_STATE_DIR/task_prompts/${branch}_task_prompt.md"; text=$PNL_OUT
  pnl_sub_var "$text" '<state_dir>' "$PNL_STATE_DIR"; text=$PNL_OUT
  pnl_sub_var "$text" '<branch>' "$branch"; text=$PNL_OUT
  pnl_sub_var "$text" '<iteration>' "$iteration"; text=$PNL_OUT
  pnl_sub_var "$text" '<review_mode>' "$review_mode"; text=$PNL_OUT
  if [ $# -gt 0 ]; then
    pnl_sub_var "$text" '<findings_files>' "$joined"; text=$PNL_OUT
    pnl_sub_var "$text" '<findings_file>' "$first"; text=$PNL_OUT
  fi
  printf '%s\n' "$text"
}

# pnl_agent_tools_var <agent> — the `tools:` line of the agent's frontmatter,
# one tool per line, into PNL_TOOLS; 1 when the file or the line is missing.
pnl_agent_tools_var() {
  local agent="${1-}" f line rest item out="" first=1 nl="
"
  PNL_TOOLS=""
  f="${PNL_PLUGIN_DIR-}/agents/$agent.md"
  [ -n "$agent" ] && [ -f "$f" ] && [ -r "$f" ] || return 1
  rest=""
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    if [ "$first" -eq 1 ]; then
      [ "$line" = "---" ] || return 1
      first=0
      continue
    fi
    [ "$line" != "---" ] || return 1
    case "$line" in
      tools:*) rest=${line#tools:}; break ;;
    esac
  done <"$f"
  while [ -n "$rest" ]; do
    item=${rest%%,*}
    if [ "$item" = "$rest" ]; then rest=""; else rest=${rest#*,}; fi
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [ -n "$item" ] && out="$out$item$nl"
  done
  [ -n "$out" ] || return 1
  PNL_TOOLS="$out"
}

# pnl_agent_flags <node> <agent> — the per-node flags, one argv word per line:
# `--agent <plugin>:<agent>`, `--plugin-dir` and `--add-dir` the plugin
# directory — the `--add-dir` left out when `PD_PLUGIN_DIR_ADDED` is `1`, the
# caller's shared vector already carrying it — then the MCP flags. An agent whose
# `tools:` line names no `mcp__` tool gets `--disallowedTools mcp__*`; one that
# names some gets `--strict-mcp-config --mcp-config <file>`, the worktree's
# `.mcp.json` cut to the servers those entries name (an empty server set when
# there is no such file).
pnl_agent_flags() {
  local node="${1-}" agent="${2-}" t server servers="" nl="
" file
  pnl_agent_tools_var "$agent" || { pnl_fail "'${PNL_PLUGIN_DIR-}/agents/$agent.md' carries no tools: line"; return 2; }
  printf '%s\n' --agent "$PNL_PLUGIN_NAME:$agent" --plugin-dir "$PNL_PLUGIN_DIR"
  [ "${PD_PLUGIN_DIR_ADDED-}" = "1" ] || printf '%s\n' --add-dir "$PNL_PLUGIN_DIR"
  while IFS= read -r t; do
    case "$t" in
      mcp__?*__*)
        server=${t#mcp__}
        server=${server%%__*}
        case "$nl$servers" in
          *"$nl$server$nl"*) ;;
          *) servers="$servers$server$nl" ;;
        esac
        ;;
    esac
  done <<EOF
$PNL_TOOLS
EOF
  if [ -z "$servers" ]; then
    printf '%s\n' --disallowedTools 'mcp__*'
    return 0
  fi
  [ -n "${PNL_TMP-}" ] && [ -d "$PNL_TMP" ] || { pnl_fail "no temporary directory; call pnl_init first"; return 2; }
  file="$PNL_TMP/mcp-$node.json"
  if [ -f "$PNL_WORKTREE/.mcp.json" ]; then
    jq -c --arg keep "$servers" '
      ($keep | split("\n") | map(select(length > 0))) as $k
      | { mcpServers: ((.mcpServers // {}) | with_entries(select(.key as $s | any($k[]; . == $s)))) }' \
      "$PNL_WORKTREE/.mcp.json" >"$file" 2>/dev/null \
      || { pnl_fail "'$PNL_WORKTREE/.mcp.json' could not be read as an MCP configuration"; return 2; }
  else
    printf '%s\n' '{"mcpServers":{}}' >"$file" || { pnl_fail "cannot write '$file'"; return 2; }
  fi
  printf '%s\n' --strict-mcp-config --mcp-config "$file"
}

# pnl_launch <seq> <node> <agent> <prompt> <log_path>
#
# Start the session in the background: `"$PD_SESSION_EXEC" <prompt> <flags>`,
# its stdout teed to `${log_path%.log}.planning/<seq>-<node>.stream.jsonl` and
# formatted by `"$PD_FORMATTER"` into <log_path>, its stderr appended there.
# Sets PNL_HANDLE to `<pid>\t<seq>\t<node>\t<agent>\t<stream>\t<log_path>\t<start epoch>`.
pnl_launch() {
  local seq="${1-}" node="${2-}" agent="${3-}" prompt="${4-}" log_path="${5-}" dir stream flags_text flag start pid
  local -a flags=()
  PNL_HANDLE=""
  [ -n "$seq" ] && [ -n "$node" ] && [ -n "$agent" ] && [ -n "$log_path" ] \
    || { pnl_fail "pnl_launch needs <seq> <node> <agent> <prompt> <log_path>"; return 2; }
  [ -n "${PD_SESSION_EXEC-}" ] || { pnl_fail "PD_SESSION_EXEC is not set"; return 2; }
  [ -n "${PD_FORMATTER-}" ] || { pnl_fail "PD_FORMATTER is not set"; return 2; }
  flags_text=$(pnl_agent_flags "$node" "$agent") || return 2
  while IFS= read -r flag; do
    flags[${#flags[@]}]="$flag"
  done <<EOF
$flags_text
EOF
  dir="${log_path%.log}.planning"
  mkdir -p "$dir" || { pnl_fail "cannot create '$dir'"; return 2; }
  stream="$dir/$seq-$node.stream.jsonl"
  : >"$stream" || { pnl_fail "cannot write '$stream'"; return 2; }
  start=$(date +%s)
  (
    "$PD_SESSION_EXEC" "$prompt" "${flags[@]}" </dev/null 2>>"$log_path" |
      tee "$stream" |
      "$PD_FORMATTER" >>"$log_path"
  ) &
  pid=$!
  PNL_HANDLE="$pid	$seq	$node	$agent	$stream	$log_path	$start"
  return 0
}

# The decision over one session's stream, in `pnl_reap`'s order. Input: the raw
# stream; `$g` the planning graph; `$sch` the node's return schema, loaded from
# its agent's `schemas/<agent>.return.json`; `$node`; `$tools` the agent's
# `tools:` list. `vfail` and `schemafail` hold a value to the closed dialect
# that file is written in, an array's object items included, and yield the first
# failure, or "" when there is none.
PNL_REAP_JQ='
  def blank: if type == "string" then ([explode[] | select(. != 32 and . != 9 and . != 10 and . != 13)] | length) == 0 else true end;
  def oneline: tostring | split("\r") | join(" ") | split("\n") | join(" ");
  def firstof: if length > 0 then .[0] else "" end;
  def vfail(p): p as $p | . as $v
    | if ($p | type) != "object" then ""
      elif ($p | has("const")) and $v != $p.const then "is not " + ($p.const | tojson)
      elif $p.type == "string" and ($v | type) != "string" then "is not a string"
      elif $p.type == "integer" and (($v | type) != "number" or $v != ($v | floor)) then "is not an integer"
      elif $p.type == "boolean" and ($v | type) != "boolean" then "is not a boolean"
      elif $p.type == "array" and ($v | type) != "array" then "is not an array"
      elif $p.type == "object" and ($v | type) != "object" then "is not an object"
      elif $p.type == "object"
      then ($p.properties // {}) as $props
        | [($p.required // [])[] | select(. as $k | $v | has($k) | not)] as $miss
        | [$v | keys_unsorted[] | select(. as $k | $props | has($k) | not)] as $unknown
        | if ($miss | length) > 0 then "missing required key " + $miss[0]
          elif ($unknown | length) > 0 then "unknown key " + $unknown[0]
          else [$v | keys_unsorted[] as $k | $v[$k] | vfail($props[$k]) | select(. != "") | $k + " " + .] | firstof
          end
      elif ($p | has("enum")) and (any($p.enum[]; . == $v) | not) then "is not one of " + ($p.enum | tojson)
      elif ($p | has("minLength")) and ($v | type) == "string" and ($v | length) < $p.minLength
      then "is shorter than " + ($p.minLength | tostring)
      elif ($p | has("minimum")) and ($v | type) == "number" and $v < $p.minimum
      then "is below " + ($p.minimum | tostring)
      elif ($p | has("minItems")) and ($v | type) == "array" and ($v | length) < $p.minItems
      then "has fewer than " + ($p.minItems | tostring) + " items"
      elif ($p | has("items")) and ($v | type) == "array"
      then [range(0; $v | length) as $i | $v[$i] | vfail($p.items) | select(. != "") | "item " + ($i | tostring) + " " + .] | firstof
      else "" end;
  def schemafail(s): s as $s | . as $d
    | if ($d | has("outcome") | not) then "missing required key outcome"
      else
        ([($s.oneOf // [])[] | select(type == "object")
          | select((.properties.outcome // {}) | (type == "object") and has("const") and .const == $d.outcome)] | first) as $var
        | if ($var | type) != "object" then "outcome " + ($d.outcome | tojson) + " matches no variant"
          else
            ($var.properties // {}) as $props
            | [($var.required // [])[] | select(. as $k | $d | has($k) | not)] as $miss
            | [$d | keys_unsorted[] | select(. as $k | $props | has($k) | not)] as $unknown
            | if ($miss | length) > 0 then "missing required key " + $miss[0]
              elif ($unknown | length) > 0 then "unknown key " + $unknown[0]
              else [$d | keys_unsorted[] as $k | $d[$k] | vfail($props[$k]) | select(. != "") | $k + " " + .] | firstof
              end
          end
      end;
  (($g[0].nodes[$node].outcomes // {}) | keys_unsorted) as $declared
  | [$g[0].nodes[] | select(.kind == "round") | (.gates // [])[]] as $gates
  | ($tools | split("\n") | map(select(length > 0))) as $agent
  | [split("\n")[] | select(length > 0) | fromjson? | objects] as $ev
  | ([$ev[] | select(.type == "system" and .subtype == "init")] | first) as $init
  | ([$ev[] | select(.type == "result")] | last) as $res
  | { outcome: "", findings: "", ret: "", obj: null, read: false, class: "", withheld: "",
      cost: (if ($res | type) == "object" and ($res.total_cost_usd | type) == "number" then ($res.total_cost_usd | tostring) else "" end),
      denials: (if ($res | type) == "object" and ($res.permission_denials | type) == "array" then ($res.permission_denials | length) else 0 end) } as $m
  | if ($init | type) != "object" then $m + { kind: "error", class: "infra", reason: "the agent did not resolve: no init event" }
    else
      (if ($init.tools | type) == "array" then $init.tools else [] end) as $it
      | [$agent[] | select(startswith("mcp__") | not) | select(. as $t | any($it[]; . == $t) | not)] as $missing
      | [$it[] | select(. as $t | any($agent[]; . == $t) | not)] as $extra
      | ($m + { withheld: ($missing | join(", ")) }) as $m
      | if ($extra | length) > 0
        then $m + { kind: "error", class: "agent", reason: ("the init event grants tools the agent does not declare: [" + ($extra | join(", ")) + "]") }
        elif ($res | type) != "object" then $m + { kind: "undelivered", reason: "no result event" }
        elif $res.is_error == true
          and (($res.result // "") | tostring | (contains("API Error: 500") or contains("API Error: 503") or contains("API Error: 529") or contains("Overloaded")))
        then $m + { kind: "undelivered", reason: ("API error: " + (($res.result // "") | oneline | .[0:200])) }
        elif $res.is_error == true or ($res.subtype // "") != "success"
        then $m + { kind: "error", class: "infra", reason: ("the session ended as " + (($res.subtype // "no subtype") | oneline) + (if $res.is_error == true then " with is_error" else "" end)) }
        else
          (if ($res.result | type) == "string" then $res.result else "" end) as $text
          | (("\n" + $text) | split("\r\n") | join("\n") | split("\n```json\n")) as $open
          | (if ($open | length) < 2 then [] else ("\n" + ($open | last)) | split("\n```") end) as $close
          | if ($close | length) < 2 or (($close[1:] | join("\n```")) | blank | not)
            then $m + { kind: "error", class: "infra", reason: "the result carries no return block" }
            else
              [$close[0] | fromjson?] as $parsed
              | if ($parsed | length) != 1 or ($parsed[0] | type) != "object"
                then $m + { kind: "error", class: "infra", reason: "the return block is not one JSON object" }
                else
                  $parsed[0] as $d
                  | ($d | schemafail($sch[0])) as $sf
                  | if $sf != ""
                    then $m + { kind: "error", class: "infra", reason: ("the return fails its schema: " + $sf) }
                    elif ($d.outcome | type) != "string" or (any($declared[]; . == $d.outcome) | not)
                    then $m + { kind: "error", class: "agent", reason: ("undeclared outcome " + (if ($d.outcome | type) == "string" then $d.outcome else ($d.outcome | tojson) end | oneline)) }
                    else
                      ($m + { read: true, ret: $text, obj: $d,
                          findings: (if ($d.findings_file | type) == "string" then $d.findings_file else "" end) }) as $r
                      | if ($r.findings | blank) and ($d.outcome == "FAIL" or ($d.outcome == "PASS" and any($gates[]; . == $node)))
                        then $m + { kind: "error", class: "infra", reason: ($d.outcome + " carries no findings_file") }
                        else $r + { kind: "returned", outcome: $d.outcome, reason: "" } end
                    end
                end
            end
        end
    end'

# pnl_reap <handle> — after the session's pid has exited. Appends the node's
# stream to the run's `${log_path%.log}.stream.jsonl` once and, when the stream
# carries an `init` event, one `{"session_id", "seq", "node"}` line — that
# event's session_id — to `${log_path%.log}.planning/node-sessions.jsonl`, the
# manifest `run-analytics.sh` classes node sessions by. Then it prints
# `kind=`, `class=`, `outcome=`, `findings=`, `return_file=`, `object_file=`,
# `cost=`, `duration_secs=`, `denials=`, `withheld=` and `reason=`, one per
# line. `class=` is `infra` or `agent` and set only for `kind=error`;
# `outcome=` only for `kind=returned`. `return_file=` (the whole `result` text)
# and `object_file=` (the validated return object, compact JSON) are set only
# once the outcome was read as declared. `withheld=` is the agent's declared
# non-`mcp__` tools the `init` event lacks, in `tools:` order, joined by `, `,
# on every kind; empty when none is lacking or there is no `init` event.
pnl_reap() {
  local handle="${1-}" pid seq node agent stream log_path start now verdict ret_file="" obj_file="" tools="" sid schema
  IFS='	' read -r pid seq node agent stream log_path start <<EOF
$handle
EOF
  [ -n "$pid" ] && [ -n "$node" ] && [ -n "$stream" ] && [ -n "$log_path" ] && [ -n "$start" ] \
    || { pnl_fail "pnl_reap: '$handle' is not a handle pnl_launch set"; return 2; }
  [ -n "${PNL_TMP-}" ] && [ -d "$PNL_TMP" ] || { pnl_fail "no temporary directory; call pnl_init first"; return 2; }
  schema="$PNL_TMP/schema-$node.json"
  [ -f "$schema" ] || { pnl_fail "pnl_reap: no return schema is loaded for node '$node'"; return 2; }
  [ -f "$stream" ] || : >"$stream"
  cat "$stream" >>"${log_path%.log}.stream.jsonl" || { pnl_fail "cannot append to '${log_path%.log}.stream.jsonl'"; return 2; }
  sid=$(jq -n -R -r '[inputs | fromjson? | objects | select(.type == "system" and .subtype == "init") | .session_id | strings] | if length == 0 then "" else .[0] end' <"$stream" 2>/dev/null) \
    || { pnl_fail "pnl_reap: the stream '$stream' could not be read for its session id"; return 2; }
  if [ -n "$sid" ]; then
    jq -n -c --arg s "$sid" --arg q "$seq" --arg n "$node" '{session_id: $s, seq: $q, node: $n}' \
      >>"${log_path%.log}.planning/node-sessions.jsonl" \
      || { pnl_fail "cannot append to '${log_path%.log}.planning/node-sessions.jsonl'"; return 2; }
  fi
  now=$(date +%s)

  if pnl_agent_tools_var "$agent"; then tools="$PNL_TOOLS"; fi
  verdict="$PNL_TMP/$seq-$node.verdict"
  jq -R -s -c --slurpfile g "$PNL_GRAPH" --slurpfile sch "$schema" --arg node "$node" --arg tools "$tools" "$PNL_REAP_JQ" "$stream" >"$verdict" 2>/dev/null \
    || { pnl_fail "pnl_reap: the stream '$stream' could not be judged"; return 2; }
  if [ "$(jq -r '.read' "$verdict")" = "true" ]; then
    ret_file="$PNL_TMP/$seq-$node.return"
    obj_file="$PNL_TMP/$seq-$node.object.json"
    jq -j '.ret' "$verdict" >"$ret_file" && jq -c '.obj' "$verdict" >"$obj_file" \
      || { pnl_fail "pnl_reap: cannot write the return of '$stream'"; return 2; }
  fi
  jq -r --arg ret "$ret_file" --arg obj "$obj_file" --arg dur "$((now - start))" '
    def oneline: tostring | split("\r") | join(" ") | split("\n") | join(" ");
    "kind=" + .kind,
    "class=" + .class,
    "outcome=" + (.outcome | oneline),
    "findings=" + (.findings | oneline),
    "return_file=" + $ret,
    "object_file=" + $obj,
    "cost=" + .cost,
    "duration_secs=" + $dur,
    "denials=" + (.denials | tostring),
    "withheld=" + (.withheld | oneline),
    "reason=" + (.reason | oneline)' "$verdict"
}
