#!/usr/bin/env bash
# flow-walker.sh — the next step of a declared flow, read off its graph instead
# of worked out from prose: given the flow, the branch and the outcome of the
# node that just ran, print the next action in one fixed form. This script is a
# hand-off: the walk is `devscene-flow-walker`'s, the flow host's compatibility
# command (`devscene-flow-host/README.md` → `## The command line`), and HAND-OFF
# below is all this script does itself.
#
# THE WALKER ROUTES; THE ORCHESTRATOR JUDGES. It owns the next node, the shared
# counter and its cap, both skip semantics, the round number, each reviewer's
# `iteration:` and review-mode arguments and the escalation payload, and it
# rejects an outcome the pending node does not declare. Which outcome a return
# carries, and what a binding resolves to, stay the orchestrator's.
#
# THE SAFETY CONTRACT IS DELIBERATELY NOT THE WALKER'S. The STOP check, the
# `.dispatch_counter` increment, the PAUSE check and the halt messages stay
# orchestrator steps, so the heartbeat carries the literal slot
# `(#<total_dispatches>)` for the orchestrator to fill. A binding is printed by
# NAME and never resolved; no dispatch prompt is composed — only the values the
# core's dispatch block lacks (`arg.iteration`, `arg.review_mode`,
# `arg.findings_file`) and the prompt variant.
#
# USAGE — each call one literal command from the repository root:
#
#   bash <scripts_dir>/flow-walker.sh start   --flow <flow> --branch <branch> [--entry <node>] [--skipped <ids|none>]
#   bash <scripts_dir>/flow-walker.sh next    --flow <flow> --branch <branch> --outcome <outcome> [--node <node>] [--findings <path>] [--skipped <ids|none>]
#   bash <scripts_dir>/flow-walker.sh current --flow <flow> --branch <branch>
#   bash <scripts_dir>/flow-walker.sh check-round-file --findings <path>
#
#   `check-round-file` runs the check a round gate's return must pass, for a
#   flow routed by prose. It is read-only, takes no lock, reads no configuration
#   or graph, and refuses `--flow` and `--branch`; a relative <path> resolves
#   against the repository root.
#
#   `current` is read-only and takes no lock: it re-renders the saved pending
#   step in the form it was printed, with the values read from disk when it was
#   printed, and is how a planning (re-)entry finds a saved walk to continue.
#   Its output names the saved `awaiting`: one `action: dispatch` block of a
#   non-gate node is `dispatch`; gate blocks are `set`; `binding: <ask>` is
#   `answer`, any other `binding:` (`<escalate>`, `<terminal_handoff>`) is
#   `done` — a finished walk, re-printed but continued by nothing: `next`
#   refuses it with exit 1.
#
#   <outcome>  a key of the pending node's `outcomes` (of the `--node` gate
#              while a set is pending), or `answered` while an `<ask>` is
#              pending. `FAIL` requires `--findings`; so do `PASS` and `FAIL`
#              at a round gate — a node some `round` node lists in its
#              `gates` — whose reviewer writes a file every round.
#   --node     the node the outcome is for, `[a-z0-9_]` only. Required while a
#              set is pending, naming a gate of the set with no recorded
#              outcome; otherwise optional and, when given, the pending node.
#   --findings the reviewer's findings_file; it may not carry a tab. A round
#              gate's `PASS` or `FAIL` reads it, absolute as given and relative
#              under the repository root (ROUNDS, on a refused file).
#   --skipped  the run mode's skipped ids; read only when no flow-progress
#              ledger exists, and re-read on every arrival at a gated node.
#   The graph is `<this script's dir>/flows/<flow>.graph.json`, formatVersion
#   5; the root is a bare `git rev-parse --show-toplevel` in the working
#   directory. Each branch keeps its own walk, so a call naming another branch
#   is not refused; one naming another flow than the branch's saved walk is.
#
# ROUNDS — a `round` node dispatches nothing. Arriving at it (the writer's
# outcome, or a `start`) OPENS the round: each gate's skip constructs are
# evaluated in `gates` order before anything is printed, and every gate not
# skipped is due, all dispatched at once as one SET. Each gate's outcome is
# recorded by its own `next --node <gate>`, in any order; until the last one
# the walker prints `wait`. The last outcome is the JOIN. A gate whose round
# file was refused is dispatched again first, as one set in the same round,
# even beside a held gate; once no refused gate is out, when any gate's outcome
# was `error` or `blocker` (HELD, not routed when recorded), the first held
# gate's binding is printed and the round is not closed; otherwise the round
# closes FAIL when a gate recorded FAIL (a skipped gate counts as passed), else
# PASS — with every gate skipped, at once on arrival — followed through the
# node's `outcomes` as an agent's outcome is. Two numbers are kept apart: the
# loop COUNTER (`counter.<name>`, the heartbeat's `{iteration}`) alone drives
# the cap and the review mode; the ROUND NUMBER names the round files, is the
# same index in every gate's folder, and carries on across the branch's
# planning history. A `start` at a round's writer or round node resumes the
# round number and the round's recorded verdicts from the round files on disk;
# convergence is never inferred from files.
#
# A REFUSED ROUND FILE records no verdict. A gate's `PASS` or `FAIL` whose
# --findings `check-round-file` would refuse marks the gate for re-dispatch,
# and the walker waits for the gates still out; with none out, every marked
# gate is dispatched again as one set, in the same round (ROUNDS). The third
# refusal of one gate in a round holds it as `error`. A refusal moves neither
# the round number nor the counter, and never reaches the writer.
#
# OUTPUT — stdout, `key: value` lines, in this order:
#
#   dispatch  action: dispatch / node: / agent: / prompt: (writer nodes) /
#             arg.iteration: (a round's writer, either variant: the round
#             number the write feeds) / arg.findings_file: (with `prompt:
#             revision`: one line per findings file of the closed round, in
#             `gates` order; `ui_writer`'s one) / arg.iteration: (a round gate:
#             the round number; any other reviewer: the next free index in its
#             findings folder) / arg.review_mode: full|converging (a round
#             gate: `full` while the counter is below the round node's
#             `convergingFrom`) / skip: <node> <skipped|passed-by-exclusion>,
#             round: <n> <PASS|FAIL> (<n> the round it closed) and ledger: <id>
#             lines for what the walk passed through /
#             heartbeat: <template, {iteration} = the counter>  (#<total_dispatches>)
#   set       one dispatch block per due gate, in `gates` order, back to back;
#             the passed-through skip: / round: / ledger: lines in the first
#             block only. A set of one gate is a single dispatch block. A set
#             re-dispatched after a refusal adds, among the first block's
#             passed-through lines, refused: <gate> attempt <n> of 3: <reason>
#             per gate in it
#   wait      action: wait / node: <round> / recorded: <gate> <outcome>, or
#             for a refused file refused: <gate> attempt <n> of 3: <reason> /
#             pending: <gate> per gate still out, in `gates` order; a gate
#             marked for re-dispatch is not out
#   binding   action: binding / binding: <name> / node: / then
#             <ask>               agent: / resume: <node>
#             <escalate>          agent: (none when node: is a round node) /
#                                 reason: <cap|error|blocker>, and for a cap:
#                                 findings_file: per file of the closing round /
#                                 rounds: <node> <its folder's FAIL files> (a
#                                 node recorded `skipped` omitted) / evidence
#                                 lines / summary: ({cap}; {open_gates} the
#                                 closing round's FAIL gates, `, `-joined);
#                                 at a join with a held outcome, node: and
#                                 agent: are the first held gate's in `gates`
#                                 order, reason: its outcome, then held: <gate>
#                                 <outcome> per held gate, one refused: line
#                                 per gate held by refusal, and no round: line
#             <terminal_handoff>  report: <key> <value> per recorded key
#             then its skip: / round: / ledger: lines.
#
# EXIT CODES — the command's, as `devscene-flow-host/README.md` → `## The
# command line` gives them, plus this script's own refusals:
#
#   0  an action was printed; for check-round-file, the named round file is
#      valid and nothing is printed
#   1  refusal: a usage error; a step the walk refuses (an undeclared outcome,
#      a gate not pending, a missing `--node`, a finished walk, an `--entry`
#      outside the flow's entries, an unresolvable phase flag, no run-mode
#      record); `next` or `current` with no saved walk (a re-entry's "no saved
#      walk"); no `<this script's dir>/flows/<flow>.graph.json`
#   2  a fault: not inside a git repository; a graph that does not load or
#      declares another flow; a lock not acquired within 120 s; any other
#      failure, `internal error: <type>: <message>` among them. This script's
#      own: lib/harness-run-lib.sh predates this walker; the flow host's
#      environment is not provisioned (HAND-OFF)
#   3  check-round-file only: the named round file is invalid or absent. That
#      command's usage refusals stay 1 and its faults 2
#   Every non-zero exit prints one `flow-walker: <cause>` line on stderr and
#   nothing on stdout. A fault after `start` or `next` saved the walk leaves it
#   saved.
#
# HAND-OFF — what this script does, in order, and nothing else:
#
#   1. Sources lib/harness-run-lib.sh from beside itself. Every layout name
#      below comes from that library's declared mirror (THE FLOW HOST'S
#      ENVIRONMENT, its six `HR_FLOW_HOST_*` names); this script spells none.
#      A library that cannot be sourced, defines no `hr_repo_root` or
#      `hr_state_dir`, or leaves one of the six names unset or empty predates
#      this walker: exit 2, for every verb.
#   2. For `start`, `next` and `current`: deletes
#      `<root>/<stateDir>/.flow_walker_state` when it is a regular file and not
#      a symbolic link — the bash walker's flat state, which would stand where
#      the command keeps its per-branch directory — and prints nothing about
#      it. When the root or `stateDir` does not resolve, deletes nothing and
#      leaves the cause to the command.
#   3. Refuses with exit 2, running nothing, when `uv` is not on PATH, the
#      environment's marker file is absent, or its `bin/devscene-flow-walker`
#      is not executable; the one stderr line names
#      `bash <scripts_dir>/flow-host-provision.sh`, run outside the sandbox —
#      the same remedy the provisioning line and `doctor`'s `flow-host` check
#      print.
#   4. Unsets `VIRTUAL_ENV`, then, with <py> = <this script's dir>/python:
#
#        UV_PROJECT_ENVIRONMENT=<py>/.venv \
#        PYTHONPATH=<py>/devscene-flow-host/src:<py>/graphscene/src \
#        PYTHONDONTWRITEBYTECODE=1 \
#        exec uv run --frozen --no-sync --no-cache --project <py>/devscene-flow-host \
#          devscene-flow-walker <arguments> [--flows <this script's dir>/flows]
#
#      `--flows` is appended for `start`, `next` and `current` only, because
#      `check-round-file` refuses a flag it does not take; every other argument
#      passes through unchanged, and the command's stdout, stderr and exit
#      status are the caller's answer.
#
#   NO ENVIRONMENT VARIABLE CHOOSES WHAT RUNS. The environment, the project and
#   every source path come from this script's own directory, never from the
#   caller's environment, and an inherited `PYTHONPATH` is replaced: the
#   watcher's planning driver runs this script outside the sandbox, and an
#   unsandboxed script takes the path of every trust input from a location the
#   session cannot write (`<state_dir>/lessons.md` → `## Trust checks`). Run
#   from the main checkout, everything it executes sits under
#   `<scripts_dir>/python/`, which the generated profile write-protects.
#
#   THE SHIPPED SOURCES LEAD `PYTHONPATH` because a run copy's environment is
#   built from the main checkout's packages as non-editable wheels; putting
#   the sources beside this script first makes the code that runs the code
#   `init` shipped here. `PYTHONDONTWRITEBYTECODE=1` keeps Python from writing
#   `__pycache__` beside those sources, which sit in a committed tree no
#   ignore rule covers, so a unit commit's untracked listing would otherwise
#   pick the bytecode up.
#
#   `--no-cache` IS ALWAYS PASSED because inside Claude Code's sandbox `uv`
#   cannot initialise its cache and exits 2 without it; `--no-sync` builds
#   nothing, so the cache is never needed.
#
#   THE WALK'S STATE, LOCKS AND RECORDS ARE THE COMMAND'S, under
#   `<state_dir>/.flow_walker_state/` (`devscene-flow-host/README.md` →
#   `## What it reads, answers and keeps`).
#
# REPRO — in a throwaway fixture, never in a checkout:
#
#   d=$(mktemp -d); git -C "$d" init -q -b feat_x; cd "$d"
#   npx devscene init     # writes <scripts_dir>/ and, with uv, builds <scripts_dir>/python/.venv
#   printf 'verdict: PASS\n' > p0.md
#   bash <scripts_dir>/flow-walker.sh start --flow task_plan_writing --branch feat_x --skipped none
#     -> exit 0, action: dispatch, node: plan_writer, prompt: initial, arg.iteration: 0
#   mv <scripts_dir>/python/.venv <scripts_dir>/python/.venv.off
#   bash <scripts_dir>/flow-walker.sh current --flow task_plan_writing --branch feat_x
#     -> exit 2, nothing on stdout, stderr flow-walker: the flow host is not
#        provisioned (...): run bash <scripts_dir>/flow-host-provision.sh outside the sandbox
#   mv <scripts_dir>/python/.venv.off <scripts_dir>/python/.venv
#   bash <scripts_dir>/flow-walker.sh check-round-file --findings absent.md
#     -> exit 3, stderr flow-walker: absent.md: no single verdict line (no `--flows` error)
#   bash <scripts_dir>/flow-walker.sh check-round-file --findings p0.md   -> exit 0, no output
#   rm -rf <state_dir>/.flow_walker_state; printf 'flow=x\n' > <state_dir>/.flow_walker_state
#   bash <scripts_dir>/flow-walker.sh current --flow task_plan_writing --branch feat_x
#     -> exit 1, flow-walker: no walk in progress at <root>/<state_dir>/.flow_walker_state/feat_x.json: ...;
#        the flat <state_dir>/.flow_walker_state is gone

set -uo pipefail

fw_given="$(dirname "${BASH_SOURCE[0]}")"
fw_dir="$(cd "$fw_given" && pwd)"
fw_lib="$fw_dir/lib/harness-run-lib.sh"

fw_predates() {
  printf 'flow-walker: %s predates this walker (%s): delete that file and re-run devscene init, which writes the current copy\n' "$fw_lib" "$1" >&2
  exit 2
}

# shellcheck source=/dev/null
{ [ -r "$fw_lib" ] && . "$fw_lib"; } || fw_predates "it cannot be sourced"
for fw_fn in hr_repo_root hr_state_dir; do
  declare -F "$fw_fn" >/dev/null || fw_predates "it defines no $fw_fn"
done
for fw_name in HR_FLOW_HOST_DIRNAME HR_FLOW_HOST_PROJECT HR_FLOW_HOST_GRAPHSCENE \
  HR_FLOW_HOST_ENV_DIRNAME HR_FLOW_HOST_SOURCE_DIRNAME HR_FLOW_HOST_ENV_MARKER; do
  [ -n "${!fw_name-}" ] || fw_predates "it sets no $fw_name"
done

fw_py="$fw_dir/$HR_FLOW_HOST_DIRNAME"
fw_env="$fw_py/$HR_FLOW_HOST_ENV_DIRNAME"
fw_project="$fw_py/$HR_FLOW_HOST_PROJECT"
fw_sources="$fw_project/$HR_FLOW_HOST_SOURCE_DIRNAME:$fw_py/$HR_FLOW_HOST_GRAPHSCENE/$HR_FLOW_HOST_SOURCE_DIRNAME"

fw_flows=()
case "${1-}" in
  start|next|current)
    fw_flows=(--flows "$fw_dir/flows")
    if fw_root="$(hr_repo_root)" && fw_state_dir="$(hr_state_dir "$fw_root")"; then
      fw_flat="$fw_root/$fw_state_dir/.flow_walker_state"
      if [ -f "$fw_flat" ] && [ ! -L "$fw_flat" ]; then
        rm -f "$fw_flat"
      fi
    fi
    ;;
esac

fw_missing=""
if ! command -v uv >/dev/null 2>&1; then
  fw_missing="uv is not on PATH"
elif [ ! -f "$fw_env/$HR_FLOW_HOST_ENV_MARKER" ]; then
  fw_missing="no environment at $fw_env"
elif [ ! -x "$fw_env/bin/devscene-flow-walker" ]; then
  fw_missing="$fw_env has no devscene-flow-walker"
fi
if [ -n "$fw_missing" ]; then
  printf 'flow-walker: the flow host is not provisioned (%s): run bash %s/flow-host-provision.sh outside the sandbox\n' "$fw_missing" "$fw_given" >&2
  exit 2
fi

unset VIRTUAL_ENV
UV_PROJECT_ENVIRONMENT="$fw_env" PYTHONPATH="$fw_sources" PYTHONDONTWRITEBYTECODE=1 \
  exec uv run --frozen --no-sync --no-cache --project "$fw_project" \
  devscene-flow-walker "$@" ${fw_flows[@]+"${fw_flows[@]}"}
