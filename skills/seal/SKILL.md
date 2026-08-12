---
description: "Seal a session handoff file to the exact current git state so a future session can fail-closed-verify it before trusting the prose. Use when ending a session, writing a handoff/resume note, or when the user says 'seal this handoff'. Do NOT use outside a git worktree, on an already-sealed file, or to bypass a failed verification."
---

Seal a handoff file with `handoff-seam` (the plugin puts the CLI on PATH).

Input: **$ARGUMENTS** — optional path to an existing handoff file. If omitted:

1. Write the handoff prose first, to `.claude/handoff-YYYY-MM-DD-<topic>.md` at the
   repository root (create `.claude/` if needed). Keep it factual and short:
   `# Handoff — <date> — <topic>`, then `## Goal`, `## State`, `## Next steps`,
   `## Gotchas`. Do not write a "Resume seam" section yourself — the sealer owns it.
2. Run: `handoff-seam seal "<file>"` (add `--session-id <id>` if the user gave one).
3. The command prints a re-entry one-liner on stdout. Surface it to the user verbatim
   in a fenced bash block — it is how the next session verifies before reading.

If sealing fails, report the exact stderr and stop. Never hand-edit or reconstruct the
`handoff-seam-v1` block; re-run `seal` on a clean prose file instead.
