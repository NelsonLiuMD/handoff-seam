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
* The `SessionStart` hook now hard-caps what it forwards into
  `additionalContext` at 2 KB, appending `[handoff-seam: diagnosis truncated]`
  when it clamps. This is defense in depth on top of the CLI's own bounds. The
  verdict word and the "do NOT trust its contents" warning lead the string, so a
  clamped context still carries the same instruction.
* A checked-out ref outside `refs/[A-Za-z0-9._/+-]{1,255}` can no longer be
  sealed — notably a branch name with non-ASCII characters or a space. `seal`
  and `capture` refuse it up front, naming the rule, rather than writing a
  manifest that `verify` would later reject. Widening the character class is a
  candidate for schema v2; it needs a bound that stays safe to render into an
  agent's context.
* CI: `actions/checkout` pinned to a full commit SHA, plus job `timeout-minutes`
  and `concurrency` cancellation.

### Fixed

* **Every string field in the handoff manifest is now bounded before it can
  reach a refusal message.** `handoff_path`, `worktree_root`, `git_common_dir`
  and `worktree_git_dir` must be absolute, at most 4096 bytes, and free of
  control characters; `branch_ref` must be `null` or `refs/` followed by 1–255
  characters from `[A-Za-z0-9._/+-]`; `head_oid`, `status_sha256` and
  `session_id` keep their existing patterns. A field that breaks a rule is a
  structural refusal (exit 2) naming only the field and the rule — for example
  `seam field 'worktree_root': not an absolute path` — never the value.

  Those five fields were previously interpolated raw into refusal messages, and
  the `SessionStart` hook renders such messages verbatim into an agent's
  `additionalContext`. A manifest carrying a 198 KB `worktree_root` put all
  198 KB of attacker-chosen text into that context; the same held for the other
  four fields. The `schema_version` bound added earlier in this same Unreleased
  section covered only that one field, so the note claiming refusal messages no
  longer quote the manifest was not true of the tool as a whole. It is now.
* A seam value that does legitimately reach a message or a `--json` reason goes
  through a single renderer: a value that passed validation is emitted capped at
  200 characters with an ellipsis, and anything else becomes the fixed token
  `<invalid>`. A valid-but-huge path can no longer bloat the context either.
* `capture` and `seal` apply the same bounds to the state they are about to
  seal, so a successful `seal` can no longer produce a file that `verify` then
  refuses structurally.
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
