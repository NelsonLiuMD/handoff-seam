#!/usr/bin/env bash
# Demonstrate the core claim: two worktrees sharing the same commit are NOT the
# same place. The wrong physical worktree is rejected before any prose is shown.
set -euo pipefail

bin=$(cd "$(dirname "$0")/.." && pwd -P)/bin/handoff-seam
tmp=$(mktemp -d "${TMPDIR:-/tmp}/handoff-seam-demo.XXXXXX")
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

# Hermetic git: nothing from the host's config leaks into the demo.
export HOME="$tmp" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=demo GIT_AUTHOR_EMAIL=demo@example.invalid
export GIT_COMMITTER_NAME=demo GIT_COMMITTER_EMAIL=demo@example.invalid

repo_a="$tmp/repo-a"
repo_b="$tmp/repo-b"

git init -q -b main "$repo_a"
echo "shared content" >"$repo_a/file.txt"
git -C "$repo_a" add file.txt
git -C "$repo_a" commit -q -m "shared commit"
git -C "$repo_a" checkout -q --detach
git -C "$repo_a" worktree add -q --detach "$repo_b" HEAD

oid_a=$(git -C "$repo_a" rev-parse HEAD)
oid_b=$(git -C "$repo_b" rev-parse HEAD)
echo "repo-a HEAD: $oid_a"
echo "repo-b HEAD: $oid_b"
[ "$oid_a" = "$oid_b" ] || { echo "demo setup failed: commits differ" >&2; exit 1; }
echo "Same commit, same detached state, same clean tree — only the physical worktree differs."
echo

handoff="$repo_a/handoff-demo.md"
printf '# Handoff — demo\n\nSECRET-PLAN: this prose must only appear after verification.\n' >"$handoff"
echo "--- sealing $handoff from repo-a"
(cd "$repo_a" && "$bin" seal "$handoff" --session-id demo)
echo

echo "--- reading from the CORRECT worktree (repo-a): expect success"
correct_out="$tmp/correct.out"
(cd "$repo_a" && "$bin" read "$handoff") >"$correct_out"
grep -q "SECRET-PLAN" "$correct_out" || { echo "FAIL: prose missing on valid read" >&2; exit 1; }
echo "prose surfaced ($(wc -c <"$correct_out" | tr -d ' ') bytes)"
echo

echo "--- reading from the WRONG worktree (repo-b): expect fail-closed rejection"
wrong_out="$tmp/wrong.out"
wrong_err="$tmp/wrong.err"
rc=0
(cd "$repo_b" && "$bin" read "$handoff") >"$wrong_out" 2>"$wrong_err" || rc=$?
[ "$rc" -eq 1 ] || { echo "FAIL: expected exit 1, got $rc" >&2; cat "$wrong_err" >&2; exit 1; }
[ -s "$wrong_out" ] && { echo "FAIL: prose leaked to stdout despite rejection" >&2; exit 1; }
grep -q "worktree_root" "$wrong_err" || { echo "FAIL: rejection did not name worktree_root" >&2; exit 1; }
grep -q "SECRET-PLAN" "$wrong_err" && { echo "FAIL: prose leaked to stderr" >&2; exit 1; }
sed 's/^/    /' "$wrong_err"
echo
echo "PASS: identical commit accepted only in its own worktree; no prose surfaced on rejection."
