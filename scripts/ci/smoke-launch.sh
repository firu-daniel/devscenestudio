#!/usr/bin/env bash
# Launches a Linux build headless under Xvfb and checks it starts and shows its window.
# Usage: scripts/ci/smoke-launch.sh <label> <executable>
# Writes smoke/<label>.log and smoke/<label>.png; exits non-zero on a crash or no window.
set -uo pipefail
label="${1:?label}"; exe="${2:?executable}"
mkdir -p smoke
log="smoke/$label.log"

export DISPLAY=:99
Xvfb "$DISPLAY" -screen 0 1280x800x24 >/dev/null 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null' EXIT
sleep 1

"$exe" >"$log" 2>&1 &
app_pid=$!

window=""
for _ in $(seq 1 20); do
  sleep 1
  if ! kill -0 "$app_pid" 2>/dev/null; then break; fi
  window="$(xdotool search --name 'DevScene Studio' 2>/dev/null | head -1)"
  [ -n "$window" ] && break
done

alive=yes
kill -0 "$app_pid" 2>/dev/null || alive=no
import -window root "smoke/$label.png" 2>/dev/null || true
kill "$app_pid" 2>/dev/null
wait "$app_pid" 2>/dev/null

echo "--- $label log ---"; cat "$log"
if [ "$alive" = no ]; then echo "::error::$label build exited during launch"; exit 1; fi
if [ -z "$window" ]; then echo "::error::$label build showed no 'DevScene Studio' window within 20 s"; exit 1; fi
echo "$label: running with window $window"
