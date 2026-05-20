# RTK Verification

**Date:** 2026-05-19  
**Branch:** overhaul/universal-method-apple-caliber

## Status
- `command -v rtk`: present (verified by session invocation)
- `rtk --help`: functional
- `rtk git status`: functional (used in Phase 0)
- `rtk grep`: functional (used in Phase 1 inventory)
- `rtk find`: functional (used in Phase 1 inventory)

## Fallback policy
If `rtk` is unavailable in a shell context:
- Use explicit targeted commands: `git status --short`, `grep -rn "pattern" path/`
- Do NOT use broad `cat`, recursive full-file reads, or `find /`
- Prefer `grep -n "pattern" specific_file.py` over full-file dumps
- Read exact line ranges with the Read tool (offset+limit parameters)

## RTK shell usage rule (from CLAUDE.md)
```
Prefer: rtk git status | rtk grep | rtk find | rtk pytest
Avoid broad full-file reads. Read exact line ranges.
```
