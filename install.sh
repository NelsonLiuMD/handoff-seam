#!/usr/bin/env bash
# Symlink bin/handoff-seam into PREFIX/bin (default ~/.local/bin).
# Idempotent: re-running is a no-op; refuses to overwrite anything it did not create.
set -euo pipefail

prefix="${PREFIX:-$HOME/.local}"
repo_root=$(cd "$(dirname "$0")" && pwd -P)
source_bin="$repo_root/bin/handoff-seam"
target="$prefix/bin/handoff-seam"

[ -x "$source_bin" ] || { echo "install.sh: missing executable $source_bin" >&2; exit 1; }
mkdir -p "$prefix/bin"

if [ -L "$target" ]; then
  current=$(readlink "$target")
  if [ "$current" = "$source_bin" ]; then
    echo "already installed: $target -> $source_bin"
    exit 0
  fi
  echo "install.sh: refusing — $target is a symlink to $current, not this checkout" >&2
  exit 1
elif [ -e "$target" ]; then
  echo "install.sh: refusing — $target exists and was not created by this installer" >&2
  exit 1
fi

ln -s "$source_bin" "$target"
echo "installed: $target -> $source_bin"
case ":$PATH:" in
  *":$prefix/bin:"*) ;;
  *) echo "note: $prefix/bin is not on your PATH" ;;
esac
