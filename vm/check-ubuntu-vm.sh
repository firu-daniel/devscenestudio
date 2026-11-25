#!/usr/bin/env bash
# Prints what Issue #4 records for a Linux VM: release, glibc, kernel, GPU driver and session type.
# Usage: vm/check-ubuntu-vm.sh studio-ubuntu-2404|studio-ubuntu-2204
set -euo pipefail
name="${1:?Usage: $0 <instance name>}"

limactl shell "$name" bash -s <<'GUEST'
set -u
echo "release:  $(. /etc/os-release && echo "$PRETTY_NAME") ($(uname -m))"
echo "kernel:   $(uname -r)"
echo "glibc:    $(ldd --version | head -1 | awk '{print $NF}')"
echo "gnome:    $(gnome-shell --version 2>/dev/null || echo 'not installed')"
echo "gpu:      $(ls /sys/class/drm 2>/dev/null | tr '\n' ' ') driver=$(basename "$(readlink -f /sys/class/drm/card0/device/driver 2>/dev/null)" 2>/dev/null)"
echo "sessions:"
loginctl list-sessions --no-legend | while read -r id _ user _; do
  printf '  %s user=%s type=%s class=%s\n' "$id" "$user" \
    "$(loginctl show-session "$id" -p Type --value)" "$(loginctl show-session "$id" -p Class --value)"
done
GUEST
echo "lima:     $(limactl --version)"
echo "host:     macOS $(sw_vers -productVersion), $(sysctl -n machdep.cpu.brand_string)"
