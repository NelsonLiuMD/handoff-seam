#!/usr/bin/env bash
# Local verification entry point: syntax, lint, unit tests, demo.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)

shell_files=(
  "$root/install.sh"
  "$root/uninstall.sh"
  "$root/tests/run.sh"
  "$root/demo/wrong-worktree.sh"
  "$root/hooks/verify-latest.sh"
)

echo "== bash -n"
for file in "${shell_files[@]}"; do bash -n "$file"; done

if command -v shellcheck >/dev/null 2>&1; then
  echo "== shellcheck"
  shellcheck "${shell_files[@]}"
else
  echo "== shellcheck not installed; skipping lint"
fi

echo "== unit + adversarial tests"
python3 -m unittest discover -s "$root/tests" -v

echo "== demo: wrong-worktree rejection"
"$root/demo/wrong-worktree.sh"

echo "== all checks passed"
