# Threat model

`handoff-seam` protects a **cooperating** future session from acting on
handoff prose that no longer describes reality. It is drift detection with a
fail-closed gate, not a cryptographic authentication system.

## What it defends against

| Threat | Mechanism |
| --- | --- |
| Resuming in the wrong worktree of the same repository (same commit, same branch state, same cleanliness) | `worktree_root` and `worktree_git_dir` are `realpath`-resolved physical identities and must match exactly |
| Resuming in a clone or copied directory that answers to the same branch/SHA | Physical paths differ; copied handoff files additionally fail the `handoff_path` binding (exit 2) |
| The branch moved, HEAD advanced, or the checkout was detached/re-attached since sealing | Full `head_oid` + full `branch_ref` (or explicit `null` for detached) comparison |
| Dirty-state drift: files modified, added, deleted, or untracked content changed since sealing | `status_sha256` fingerprints porcelain-v2 status, `diff --binary HEAD`, and every untracked file's mode and bytes |
| A handoff file moved, renamed, or transplanted into another repository | Sealed `handoff_path` must equal the file's current `realpath`, inside the sealed `worktree_root` |
| Accidental double-sealing, hand-built or truncated seam blocks, oversized files | Exactly-one-block rule, exact key set, type/regex validation, 256 KiB cap — all structural failures, exit 2 |
| Symlink swap / file-type swap while reading or sealing | `O_NOFOLLOW`, regular-file checks, dev/ino re-checks, atomic temp + rename with a pre-replace identity check |
| Shallow submodule ambiguity | Dirty submodule state is refused (exit 2) instead of being fingerprinted incompletely |
| Fingerprinting hanging or exploding | 30 s capture deadline; 2 MB status / 25 MB diff / 25 MB untracked caps — exceeding any is a refusal, never a partial fingerprint |

## What it explicitly does NOT defend against

* **A malicious local actor.** Anyone with write access to the worktree can
  edit the prose and re-run `seal`. The seam has no secret and no signature;
  it binds prose to state, it does not authenticate an author. If you need
  authenticity, sign the sealed file (e.g. `gpg --clearsign`, `ssh-keygen -Y
  sign`) on top.
* **Post-seal edits to the handoff prose itself.** The sealed file is excluded
  from its own fingerprint (sealing would otherwise self-invalidate), so a
  later edit to the prose is not detected. The seam answers "is the *world*
  still the one described", not "are these *bytes* the ones written". A
  prose-integrity hash is a candidate for schema v2.
* **A compromised `git` binary or hostile filesystem** (FUSE tricks, racing
  bind-mounts). The dev/ino and `realpath` checks raise the bar; they do not
  make a hostile kernel-adjacent environment safe.
* **Secrets in the prose.** The seam adds only git metadata, but the handoff
  body is user-authored; sealing does not sanitize it. The verdict surfaces
  emit seam fields and paths, never prose — but the sealed file itself is as
  sensitive as what you wrote into it.
* **Clock or ordering claims.** The seam proves state equality, not when the
  seal happened. There is no timestamp field by design (nothing verifies it).

## Trust boundary

Everything is local: git subprocesses (`GIT_OPTIONAL_LOCKS=0`, read-only),
`lstat`/`open` on files inside the worktree, and the single sealed file write.
No network, no model invocation, no transcript access, no state outside the
repository being sealed.
