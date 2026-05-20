---
name: update-memory-bible
description: Updates durable project memory after verified changes without storing secrets or bloating context.
---

At the end of each substantial change:

1. Summarize what changed (1-3 sentences, no secrets).
2. Link affected code files and test files.
3. Record decisions in `brain/Decisions/YYYY-MM-DD-<topic>.md`.
4. Record domain/security changes in relevant `brain/<topic>/` notes.
5. Do NOT store: raw logs, secrets, long diffs, full file contents.
6. Update `CLAUDE.md` only with permanent project rules, not session chatter.
7. Update `brain/Sessions/YYYY-MM-DD-<what>.md` with session summary.
8. Verify no secrets appear in any brain/ file before committing.
