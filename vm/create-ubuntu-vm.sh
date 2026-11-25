#!/usr/bin/env bash
# Creates and starts an Ubuntu ARM64 desktop VM (GNOME) with Lima.
# Usage: vm/create-ubuntu-vm.sh 24.04|22.04
# The VM is named studio-ubuntu-<release> and mounts this repository read-only at the same path.
set -euo pipefail

release="${1:-}"
case "$release" in
  24.04 | 22.04) ;;
  *) echo "Usage: $0 24.04|22.04" >&2; exit 2 ;;
esac

repo="$(cd "$(dirname "$0")/.." && pwd)"
name="studio-ubuntu-${release/./}"

if limactl list --quiet | grep -qx "$name"; then
  echo "$name already exists; starting it." >&2
else
  # Lima only takes `base` from a template file, so layer the shared desktop
  # template over the Ubuntu image in a throwaway one.
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  cat >"$tmp/$name.yaml" <<YAML
base:
  - template:_images/ubuntu-${release}
  - $repo/vm/lima/ubuntu-desktop.yaml
mounts:
  - location: "$repo"
    writable: false
YAML
  limactl create --tty=false --name "$name" "$tmp/$name.yaml"
fi

# The first start installs the desktop (≈ 1–2 GB of packages) and can take 10–20 minutes.
limactl start --tty=false --timeout 40m "$name"
