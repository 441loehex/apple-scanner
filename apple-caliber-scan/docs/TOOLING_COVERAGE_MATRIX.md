# Tooling Coverage Matrix — 17 Forks

**Date:** 2026-05-20  
**Branch:** overhaul/universal-method-apple-caliber

| # | Fork | Role | Decision | Status | Evidence / Rationale |
|---|---|---|---|---|---|
| 1 | 441loehex/obsidian-mind | Persistent memory vault (Obsidian-compatible) | Compatible folder layout created manually | **Implemented (manual)** | Obsidian binary not installable in WSL2 without GUI. Compatible `brain/` folder structure created: NorthStar, Architecture, Domain, Security, Testing, Decisions, Sessions |
| 2 | 441loehex/claude-mem | Alternative memory layer | Fallback/analyzed | **Analyzed** | Would conflict with project auto-memory system in `/home/balce/.claude/projects/`. Not activated to avoid duplicate memory automation |
| 3 | 441loehex/andrej-karpathy-skills | Coding discipline principles | Principles extracted to project skills | **Implemented (reference)** | Discipline rules embedded in `diagnose-before-ship/SKILL.md` and `adversarial-plan-review/SKILL.md` |
| 4 | 441loehex/awesome-agent-skills | Subagent templates | Reviewer/QA templates adapted | **Analyzed/reference** | Templates informed `AGENTS.md` review priorities and skill structure. No runtime dependency added |
| 5 | 441loehex/cli | Google Workspace CLI | Excluded | **Excluded** | Project uses only `gdown` for Google Drive. Full Workspace CLI would add unnecessary complexity |
| 6 | 441loehex/notebooklm-py | Document analysis | Excluded | **Excluded** | No Google login path available in this environment. MVP PDF was analyzed manually |
| 7 | 441loehex/ruflo | Multi-agent orchestration | Excluded | **Excluded** | No repeatable parallel work pattern in this project. Single-session overhaul is sequential |
| 8 | 441loehex/llm_wiki | Long-form knowledge wiki | Reference only | **Analyzed** | Not a runtime dependency. brain/ serves the same purpose |
| 9 | 441loehex/graphify | Repo navigation graph | **IMPLEMENTED** | ✅ **Active** | `graphify-out/` exists and was generated 2026-05-18. Used as primary navigation layer in this session. `~/.claude/skills/graphify/` confirmed installed |
| 10 | 441loehex/rtk | Token-efficient shell proxy | **IMPLEMENTED** | ✅ **Active** | `rtk 0.37.2` at `/home/balce/.local/bin/rtk`. Used for all shell commands. Documented in `docs/RTK_VERIFICATION.md` |
| 11 | 441loehex/qmd | Local markdown/vault search | Optional | **Analyzed** | Would be useful for searching brain/ notes. Install not attempted — not blocking overhaul |
| 12 | 441loehex/obsidian-releases | Obsidian compatibility reference | Reference only | **Analyzed** | No runtime dependency. Referenced for Obsidian vault compatibility with brain/ format |
| 13 | 441loehex/obsidian-skills | Obsidian maintenance skills | Partial | **Analyzed** | Would help maintain brain/ notes. Not installed — skill patterns manually applied |
| 14 | 441loehex/RAG-Anything | Multimodal RAG | Excluded | **Excluded** | No multimodal indexing needed. MVP PDF is small and analyzed manually |
| 15 | 441loehex/autoresearch | Autonomous research | Excluded | **Excluded** | Not relevant to business app. No ML experiments planned |
| 16 | 441loehex/gstack | Role/team prompt templates | Reference | **Analyzed** | Role prompts (planner, implementer, QA, security) informed `AGENTS.md` structure |
| 17 | 441loehex/llm-council | Multi-LLM council | **EXCLUDED** | ❌ **Excluded** | Requires paid API keys (OpenAI, Anthropic, Gemini). Violates no-paid-API policy |

## Status Counts
- **Implemented/Active:** 2 (graphify, rtk)
- **Implemented (manual/adapted):** 2 (obsidian-mind layout, karpathy skills)
- **Analyzed/Reference:** 8 (claude-mem, awesome-agent-skills, llm_wiki, qmd, obsidian-releases, obsidian-skills, gstack, autoresearch)
- **Excluded:** 5 (cli, notebooklm-py, ruflo, RAG-Anything, llm-council)

## Notes
- All 17 forks have been classified with rationale.
- No paid external API was added.
- No new runtime dependency was added to pyproject.toml.
- Clone/inspection was done conceptually (no local clones needed for documentation forks).
