#!/usr/bin/env bash
# Remove the PREFIX/bin/handoff-seam symlink — only if this checkout owns it.
set -euo pipefail

prefix="${PREFIX:-$HOME/.local}"
repo_root=$(cd "$(dirname "$0")" && pwd -P)
source_bin="$repo_root/bin/handoff-seam"
target="$prefix/bin/handoff-seam"

if [ ! -e "$target" ] && [ ! -L "$target" ]; then
  echo "nothing to remove: $target"
  exit 0
fi

if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_bin" ]; then
  rm "$target"
  echo "removed: $target"
  exit 0
fi

echo "uninstall.sh: refusing — $target was not installed from this checkout" >&2
exit 1
