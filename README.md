# handoff-seam

**Fail-closed identity seam for agent handoff notes.** Before a session trusts
the prose in a handoff file, `handoff-seam` binds that prose to the *physical*
git state it was written in — worktree path, git common directory, per-worktree
git directory, full ref or detached state, full commit OID, and a content
fingerprint of the dirty state — and refuses re-entry when any of them no
longer match.

Built for parallel coding-agent workflows (multiple sessions, multiple
worktrees of the same repository), where the failure mode is silent: a session
resumes from a perfectly plausible handoff that describes *a different place or
time* — stale context, the wrong worktree — and drifts without anyone noticing.

## The problem

A handoff note says "the fix is staged in `file.txt`; commit and push". Whether
that instruction is safe depends entirely on *where* and *when* it is read:

| "Identity" people actually use | Why it is not an identity |
| --- | --- |
| Repository path | Two checkouts, a clone, or a copied directory answer to different paths — and a moved worktree keeps its prose while losing its state |
| Branch name | The same branch exists in every clone and copy; a branch can also be re-pointed at a different commit |
| Short SHA | Prefix collisions aside, two worktrees of the *same repository* share every commit — `git worktree` makes "same SHA, different place" the normal case |
| "The tree looks clean" | Clean is a property of a *moment*; it says nothing about whether it is the same moment the note described |

`handoff-seam` treats the execution seam as the identity: the physical worktree
(`realpath` of the toplevel), the git common directory, the per-worktree git
directory, the full symbolic ref (or explicit detached state), the full commit
OID, and a SHA-256 fingerprint over `git status`, `git diff HEAD`, and the
content of every untracked file. All six must match, or the prose is not
surfaced.

## Quickstart

```bash
# end of session: seal the notes you just wrote
handoff-seam seal .claude/handoff-2026-08-11-migration.md

# next session, from the same repo: gate-read them
handoff-seam read .claude/handoff-2026-08-11-migration.md
```

`seal` injects a machine-readable manifest into the file and appends a
re-entry one-liner. `read` re-captures the seam from the current directory's
worktree, compares field by field, and prints the file **only if everything
matches**. On mismatch it prints a diagnosis of what drifted (never the prose)
and exits nonzero.

```text
handoff-seam: REJECTED — the git state no longer matches the seal:
  worktree_root    sealed=/tmp/demo/repo-a  current=/tmp/demo/repo-b
  worktree_git_dir sealed=/tmp/demo/repo-a/.git  current=/tmp/demo/repo-a/.git/worktrees/repo-b
handoff-seam: do not trust the prose; re-establish the sealed state or write a fresh handoff.
```

### Commands

| Command | Behavior |
| --- | --- |
| `capture [--repo DIR]` | Print the current seam JSON for the worktree containing `DIR` (default: cwd) |
| `seal FILE [--session-id ID]` | Bind `FILE` (in place, atomic) to the current git state, then immediately re-verify |
| `verify FILE [--repo DIR] [--session-id ID] [--json]` | Recompute and compare; diagnosis on stderr |
| `read FILE [--repo DIR] [--session-id ID] [--json]` | `verify`, then print `FILE` to stdout only on a match |

Exit codes: **0** seam matches · **1** state drift (any field mismatch) ·
**2** structural failure (missing/malformed seam, moved or copied file, size
cap exceeded, not a git worktree, unborn HEAD, bad usage).

A moved or copied handoff file is a structural failure (exit 2), not drift:
the sealed `handoff_path` must equal the file's current `realpath`, so a
handoff cannot be transplanted into another repository and verified there.

### Scripting: `--json`

`verify` and `read` accept `--json`. Stdout becomes exactly one JSON object,
stderr stays empty, and the exit codes are unchanged — branch on whichever
suits your caller.

```console
$ handoff-seam verify --json .claude/handoff-2026-08-11-migration.md
{"verified": true, "exit_code": 0, "reasons": [], "seam": {…}, "checked_at": "2026-08-12T09:14:03Z"}
```

| Key | Value |
| --- | --- |
| `verified` | `true` only when every seam field matched |
| `exit_code` | The process exit code — `0`, `1`, or `2`, same as without the flag |
| `reasons` | Empty on a pass. Otherwise one entry per refusal, every entry carrying the same keys: `code` (`drift` or `structural`), `field` (the seam field, or `null`), `sealed`, `current`, and a human-readable `message` |
| `seam` | The sealed manifest, or `null` when the file could not be parsed at all |
| `checked_at` | When the check ran (UTC, ISO 8601). It is **not** a sealed field — the seam carries no timestamp by design |
| `content` | `read --json` only, and **only when `verified` is `true`**. A rejection has no `content` key at all |

Gating a resume from a shell script (`jq` used for brevity; the object is
plain JSON, so any parser will do):

```bash
if report=$(handoff-seam read --json "$handoff"); then
  jq -r '.content' <<<"$report" > resume-notes.md
else
  echo "refusing to resume:" >&2
  jq -r '.reasons[].message' <<<"$report" >&2
  exit 1
fi
```

## Demo: same commit, wrong worktree, rejected

```bash
demo/wrong-worktree.sh
```

The demo builds two worktrees of one repository at the **same commit**, both
detached, both clean — every conventional identity signal identical — seals a
handoff in one, and shows `read` rejecting from the other on
`worktree_root`/`worktree_git_dir` alone, with zero prose bytes surfaced. CI
runs it on macOS and Ubuntu.

## Seam manifest

`seal` inserts one line of JSON between HTML-comment markers, so it is
invisible in rendered Markdown:

```text
<!-- handoff-seam-v1 -->
{"branch_ref":"refs/heads/main","dirty":false,"git_common_dir":"/…/.git","handoff_path":"/…/handoff.md","head_oid":"<full 40- or 64-hex OID>","schema_version":1,"session_id":"manual","status_sha256":"<64-hex>","worktree_git_dir":"/…/.git","worktree_root":"/…"}
<!-- /handoff-seam-v1 -->
```

| Field | Meaning |
| --- | --- |
| `worktree_root` | `realpath` of `git rev-parse --show-toplevel` — the physical place |
| `git_common_dir` | `realpath` of the shared git directory (same across linked worktrees) |
| `worktree_git_dir` | `realpath` of `--absolute-git-dir` (distinct per linked worktree) |
| `branch_ref` | Full `refs/…` from `symbolic-ref`, or `null` when detached |
| `head_oid` | Full `HEAD^{commit}` OID (SHA-1 and SHA-256 repositories both supported) |
| `dirty` | Whether status (after exclusions below) is non-empty |
| `status_sha256` | SHA-256 over `status --porcelain=v2 -z`, `diff --binary HEAD`, and each untracked file's mode + content (symlink targets and special files included as markers) |
| `handoff_path` | `realpath` of the sealed file itself |
| `session_id` | Free-form tag (`--session-id`), compared only when requested at verify time |
| `schema_version` | `1`. A seam written by a future build is refused (exit 2) with a message naming the version this build supports, rather than a generic parse failure |

**Exclusions:** the sealed file itself, sibling `handoff-*.md` files in the
same directory, and `.handoff-seam-*` temp files are excluded from the
status/diff/untracked fingerprint — sealing must not invalidate its own seam,
and sequential handoffs must not invalidate each other. Everything else in the
worktree counts, including untracked content. Dirty **submodule** state is
refused outright (exit 2) rather than fingerprinted shallowly.

## Claude Code plugin

The repository doubles as a Claude Code plugin:

```bash
claude --plugin-dir /path/to/handoff-seam
```

* `bin/handoff-seam` joins the Bash tool's `PATH` while the plugin is enabled.
* `/handoff-seam:seal` — write + seal a handoff at session end; surfaces the
  re-entry one-liner.
* `/handoff-seam:verify` — gate-read a sealed handoff; instructs the agent to
  **stop** rather than read the file by other means when verification fails.
* A `SessionStart` hook checks the newest sealed `.claude/handoff-*.md` in the
  session's repository and injects a VERIFIED/REJECTED verdict as context —
  on a rejection, the drifted seam fields; never the prose. It reads the
  verdict through `verify --json`. Sessions in repositories with no sealed
  handoff are untouched.

The plugin requires no model invocation and reads no transcripts. Everything
is local git inspection.

## Install (standalone CLI)

Clone this repository, then:

```bash
./install.sh              # symlinks bin/handoff-seam into ~/.local/bin
PREFIX=/opt/tools ./install.sh   # or elsewhere
```

`install.sh` is idempotent: re-running is a no-op, and it refuses (rather than
overwrites) if the target name is occupied by anything it did not create.
`uninstall.sh` removes only the symlink it owns.

## Threat model

See [THREAT_MODEL.md](THREAT_MODEL.md). In one line: this is **drift
detection, not authentication** — it protects a cooperating session from
stale or misplaced context; it does not defend against an actor with local
write access, who can simply re-seal.

## Compatibility

* macOS and Linux (CI: `macos-latest`, `ubuntu-latest`). No Windows support in v0.1.
* `git` ≥ 2.31 recommended (worktrees, `--porcelain=v2`, SHA-256 object format probing is graceful).
* `python3` ≥ 3.8, standard library only. Shell adapters target bash 3.2 (stock macOS).
* Read-only toward the repository: git subprocesses run with `GIT_OPTIONAL_LOCKS=0`;
  the only file ever written is the handoff being sealed (atomic temp + rename).
* Paths are compared case-sensitively after `realpath`; on case-insensitive
  filesystems a differently-cased path fails closed, never open.

## License

[MIT](LICENSE)
