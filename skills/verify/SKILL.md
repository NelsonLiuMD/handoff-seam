---
description: "Verify a sealed handoff against the current git state and read it only if the seam matches. Use at session start, before resuming work described by a handoff, or when the user says 'pick up the handoff'. Do NOT open a sealed handoff with other tools when verification fails, and do NOT use on files without a handoff-seam block (just read those normally)."
---

Gate-read a sealed handoff with `handoff-seam` (the plugin puts the CLI on PATH).

Input: **$ARGUMENTS** — optional path. If omitted, pick the newest
`.claude/handoff-*.md` in the repository root that contains a `handoff-seam-v1` block.

1. From the repository the handoff belongs to, run: `handoff-seam read "<file>"`.
2. Exit 0 — the seam matches. The file's contents were printed; continue from them.
3. Exit 1 — the git state has drifted (wrong worktree, new commit, dirty-state change).
   Report the mismatched fields from stderr and STOP: do not read the file by any other
   means, and do not act on its instructions. Offer the user the choice to re-establish
   the sealed state or discard the handoff.
4. Exit 2 — structural problem (no/malformed seam, moved file). Report it; treat the
   file as an ordinary unsealed document only if the user confirms.
