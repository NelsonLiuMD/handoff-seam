# Changelog

## 0.1.0 — 2026-08-11

Initial release.

* Core CLI (`bin/handoff-seam`): `capture`, `seal`, `verify`, `read` with a
  fail-closed exit-code contract (0 match / 1 drift / 2 structural).
* Seam schema v1: physical worktree root, git common dir, per-worktree git
  dir, full ref or detached state, full commit OID (SHA-1 and SHA-256
  repositories), dirty flag, and a status/diff/untracked content fingerprint.
* Claude Code plugin adapter: `/handoff-seam:seal`, `/handoff-seam:verify`
  skills, a read-only `SessionStart` verdict hook, and the CLI on the plugin
  `PATH`. No model invocation, no transcript access.
* Adversarial test suite and a two-worktree demo proving wrong-worktree
  rejection before any prose is surfaced; CI on macOS and Ubuntu.
