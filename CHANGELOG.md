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
  (exit 2, and in `--json` reasons). The key-set check still runs first, so a
  manifest this build cannot fully validate stays a structural refusal.
* A `--session-id` mismatch reports `code: "session_id"` rather than
  `code: "drift"`, because its `current` holds the value the caller required,
  not captured repository state.
* The `SessionStart` hook reads its verdict through `verify --json` and renders
  the drifted fields as a list. Same verdict semantics, same silence about the
  prose.
* CI: `actions/checkout` pinned to a full commit SHA, plus job `timeout-minutes`
  and `concurrency` cancellation.

### Fixed

* Refusal messages no longer quote a value out of the handoff manifest. A
  `schema_version` is rendered as a decimal of at most 20 characters or as the
  fixed token `non-integer` / `out-of-range`, so a hostile file cannot push
  arbitrary text through a diagnosis into an agent's context by way of the
  `SessionStart` hook.
* An unreadable or missing path is now a structural refusal (exit 2) with a
  one-line message, in both output modes. It previously escaped `main` as an
  `OSError` traceback and exited 1, the drift code, breaking the `--json`
  guarantees on a case that is not drift at all. Any unexpected exception is
  likewise reported as exit 2 naming only the exception class.

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
