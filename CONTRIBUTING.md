# Contributing

Thanks for looking. This is a small, deliberately boring tool: a fail-closed gate that
other people's automation depends on. Changes are judged on whether they keep that gate
honest.

## Run the checks

```bash
tests/run.sh
```

That is the whole local gate, and it is what CI runs: `bash -n` and `shellcheck` on every
shell script, the `unittest` suite in `tests/`, and the two-worktree demo. It must pass on
macOS and Linux. Install `shellcheck` first (`brew install shellcheck`,
`apt install shellcheck`) — `tests/run.sh` skips the lint with a notice when it is absent,
but CI does not.

## Ground rules

* **Standard library only.** `bin/handoff-seam` imports nothing outside the Python 3.8+
  standard library, and the shell adapters target bash 3.2 (stock macOS). A pull request
  that adds a third-party dependency, a build step, or a package manifest will be declined.
  The point is that this runs anywhere `git` and `python3` already do.
* **Fail closed.** Ambiguity is a refusal, never a pass. If you cannot fingerprint
  something completely, refuse it — see the submodule handling for the shape.
* **Never surface prose on a failed verification.** Diagnoses name seam fields and paths.
  The handoff body is printed only after every field matches.
* **The seam schema is a compatibility surface.** Adding, removing, or repurposing a field
  changes `schema_version` and needs a migration story, not just a code change.
* **Tests come with the change.** New behavior needs a case in `tests/test_seam.py`; a bug
  fix needs the case that fails without it. Tests are hermetic — throwaway repositories,
  isolated `git` config, no network.
* **Document what a user sees.** README covers behavior, THREAT_MODEL.md covers the
  security boundary, CHANGELOG.md gets an entry under `## Unreleased`.

## Pull requests

1. Branch from `main`.
2. Keep the change focused; unrelated refactors make the gate harder to review.
3. Run `tests/run.sh` and paste the result in the description.
4. Open the pull request against `main`. CI must be green on both operating systems.

Behavior questions, platform reports, and "this refused something it should have accepted"
cases are welcome as issues. Security reports go through [SECURITY.md](SECURITY.md), not
the issue tracker.
