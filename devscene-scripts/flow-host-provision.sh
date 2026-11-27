#!/usr/bin/env bash
# flow-host-provision.sh — build the flow walker's Python environment,
# `<scriptsDir>/python/.venv`, for the checkout this script sits in, from the
# packages `init` wrote under `<scriptsDir>/python/`. The sync itself is
# `lib/harness-run-lib.sh` → `hr_flow_host_provision`; this script only places
# its own checkout and calls it with that checkout's scripts directory twice.
#
# WHO RUNS IT. `init`, a person, and the remedy `doctor` prints. It is not
# agent-invocable, and that is a calling convention: it owes no
# `DENY_SCRIPT_BASENAMES` entry, by the argument `scripts/python-service.sh` →
# `WHO RUNS lock, sync AND provision` makes. It runs outside any sandbox.
# Inside one it fails closed, because the sandbox refuses the network and the
# shared `uv` cache (measured: `uv` exits 2 with `Failed to initialize cache at
# ~/.cache/uv`), and it changes nothing outside `<scriptsDir>/python/.venv`.
#
# IT TAKES NO ARGUMENT, so nothing a session writes chooses which tree is built
# (`harness-runs/lessons.md` → `## Trust checks`). A run copy's environment is
# built by `setup-worktree.sh`, which calls the library function directly.
#
# Usage: flow-host-provision.sh
#
# Exit map:
#
#   0  provisioned
#   1  the library or the configuration could not be read, no `uv` on PATH, no
#      flow host under `<scriptsDir>/python/`, or the sync failed. The first
#      two print this script's `… refusing to provision` line on stderr, the
#      other three a `flow-host: provision: failed …` line
#   2  an argument was given (usage)
#
# REPRO — reproduce each exit by hand, against a throwaway fixture:
#
#   w=$(mktemp -d); d="$w/demo"; git init -q -b trunk "$d"
#   printf '%s' '{"version":1,"defaultBranch":"trunk","scriptsDir":"scripts","layers":[]}' > "$d/devscene.config.json"
#   mkdir -p "$d/scripts/lib" "$d/scripts/python/devscene-flow-host" "$w/bin"
#   # copy this script + lib/ to "$d/scripts"
#   : > "$d/scripts/python/devscene-flow-host/pyproject.toml"
#   printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$UV_PROJECT_ENVIRONMENT $*" > "%s/uv.args"\n' "$w" > "$w/bin/uv"
#   chmod +x "$w/bin/uv"
#
#   provisioned     PATH="$w/bin:$PATH" bash "$d/scripts/flow-host-provision.sh"
#                   -> exit 0, `flow-host: provisioned $d/scripts/python/.venv`;
#                      "$w/uv.args" holds that environment, then
#                      `sync --frozen --no-dev --no-editable --project $d/scripts/python/devscene-flow-host`
#   usage           bash "$d/scripts/flow-host-provision.sh" x; echo $?     -> 2
#   sync failed     printf '#!/usr/bin/env bash\nexit 3\n' > "$w/bin/uv"; re-run
#                   -> exit 1, `flow-host: provision: failed (exit 3)`
#   no flow host    rm -r "$d/scripts/python"; re-run with the stub -> exit 1,
#                   `flow-host: provision: failed — no flow host at …`
#   no uv           a PATH with no `uv` on it (links to bash, git, jq, dirname
#                   only); re-run -> exit 1, `flow-host: provision: failed — uv
#                   is not on PATH; …` naming this script
#   unresolvable    printf 'x' > "$d/devscene.config.json"; re-run -> exit 1

set -uo pipefail

if [ "$#" -ne 0 ]; then
  echo "flow-host-provision.sh: takes no argument" >&2
  echo "  usage: flow-host-provision.sh" >&2
  exit 2
fi

hr_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/harness-run-lib.sh"
if [ ! -r "$hr_lib" ]; then
  echo "flow-host-provision.sh: cannot read '$hr_lib' — refusing to provision" >&2
  exit 1
fi
# shellcheck source=lib/harness-run-lib.sh
. "$hr_lib"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Not git's discovery out of $script_dir, which a leftover <scriptsDir>/.git would stop.
top="$(hr_script_root "$script_dir")" || top=""
if [ -z "$top" ]; then
  echo "flow-host-provision.sh: '$script_dir' is not inside a git repository — refusing to provision" >&2
  exit 1
fi

cfg_status=0
hr_config_load "$top" || cfg_status=$?
scripts_rel=""
[ "$cfg_status" -ne 0 ] || scripts_rel="$(hr_scripts_dir "$top")" || scripts_rel=""
if [ -z "$scripts_rel" ]; then
  echo "flow-host-provision.sh: cannot resolve '$top/devscene.config.json' — refusing to provision" >&2
  echo "  (no configuration there, invalid JSON, more than one document, no defaultBranch, or jq missing/older than 1.5)" >&2
  exit 1
fi
if [ "$scripts_rel" = "." ]; then
  scripts_abs="$top"
else
  scripts_abs="$top/$scripts_rel"
fi

hr_flow_host_provision "$scripts_abs" "$scripts_abs"
exit $?
