# Changelog

## Unreleased

### Added

* `--json` on `verify` and `read`, for callers that script this tool: stdout
  becomes exactly one JSON object (`verified`, `exit_code`, `reasons`, `seam`,
  `checked_at`) and stderr stays empty. `read --json` carries the file body in
  `content`, and only when the seam matches — a rejection has no `content` key.
  Exit codes and the human output are unchanged.
* `SECURITY.md` (private vulnerability reporting, 7-day acknowledgement target,
  and a scope statement anchored to `THREAT_MODEL.md`), `CONTRIBUTING.md`, and
  `.github/CODEOWNERS`.
* Dependabot config for GitHub Actions, the repository's only third-party
  dependency.

### Changed

* A seam whose `schema_version` is not `1` is now refused with
  `unsupported seam schema_version N (this build supports 1); upgrade handoff-seam`
  (exit 2, and in `--json` reasons). The version is checked before the key-set
  check, so a seam from a future build reports the skew instead of looking
  malformed.
* The `SessionStart` hook reads its verdict through `verify --json` and renders
  the drifted fields as a list. Same verdict semantics, same silence about the
  prose.
* CI: `actions/checkout` pinned to a full commit SHA, plus job `timeout-minutes`
  and `concurrency` cancellation.

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
