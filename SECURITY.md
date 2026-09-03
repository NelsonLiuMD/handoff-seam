# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest release (`v0.1.0`) | Yes |
| Any earlier release | No |

Fixes land on `main` first; releases are cut from there.

## Reporting a vulnerability

Report privately through GitHub's private vulnerability reporting, which is enabled
on this repository:

**<https://github.com/NelsonLiuMD/handoff-seam/security/advisories/new>**

Please do not open a public issue for a security report. Include the affected commit
or release, the platform and `git` version, steps to reproduce, and what the issue
lets an attacker do.

**Response target: an acknowledgement within 7 days.** This is a single-maintainer
project, so please allow reasonable time for a fix before disclosing publicly. You
will be credited in the advisory unless you ask otherwise.

## Scope

`handoff-seam` is **drift detection, not authentication**. It protects a cooperating
future session from acting on handoff prose that no longer describes reality; it does
not authenticate an author. [THREAT_MODEL.md](THREAT_MODEL.md) is the normative
statement of that boundary, and a report is judged against it.

In scope — these are bugs, and security bugs:

* A false pass: `verify` or `read` reporting a match when the physical git state has
  actually drifted (wrong worktree, different commit or ref, changed dirty state).
* Prose disclosure on a refusal: any path where a failed verification surfaces the
  handoff body on stdout, in a diagnosis, in `--json`, or through the `SessionStart`
  hook, which must emit a verdict only.
* Escaping the documented refusals: bypassing the `handoff_path` binding, the
  exactly-one-seam-block rule, the submodule refusal, or the size and deadline caps.
* A refusal quoting the file back: a diagnosis, `--json` reason, or hook verdict
  that carries attacker-chosen bytes out of an untrusted manifest. Those messages
  reach an agent's context, so they must stay bounded and self-authored.
* Writing anywhere but the handoff file being sealed, or mutating the repository.
* Crash, hang, or resource exhaustion reachable from a hostile handoff file or
  repository state within the documented caps.

Out of scope — documented design, not vulnerabilities:

* A local actor with write access editing the prose and re-running `seal`. The seam
  carries no secret and no signature. Sign the sealed file if you need authenticity.
* Post-seal edits to the prose. The sealed file is excluded from its own fingerprint,
  because sealing would otherwise invalidate the seam it just wrote.
* A compromised `git` binary, or a hostile filesystem racing the `realpath` and
  device/inode checks.
* Sensitive content a user wrote into a handoff. Sealing adds git metadata; it does
  not sanitize prose, and the sealed file is exactly as sensitive as what went in.
* Windows behavior, which is unsupported in v0.1.

## Automated protections

* GitHub Actions are pinned to full commit SHAs; Dependabot proposes bumps weekly.
* CI runs the adversarial suite, shellcheck, and the wrong-worktree demo on both
  `ubuntu-latest` and `macos-latest`; workflow permissions are read-only.
* The tool makes no network calls, reads no credential material, and CI requests no
  repository secrets. The only third-party dependencies are the pinned actions.
