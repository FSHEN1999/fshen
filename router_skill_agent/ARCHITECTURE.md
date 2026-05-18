# Router + Skill Agent Architecture

## Purpose

The framework is a local operating layer for DPU tasks. It chooses a small, well-scoped skill for a user request, executes it when safe, verifies the result, and records the run.

It deliberately avoids opaque autonomy for DPU-sensitive flows. External calls and production-sensitive actions must be opt-in.

## Flow

```text
User task
  -> Planner
  -> Router
  -> Safety Gate
  -> Skill Executor
  -> Verifier
  -> Memory
```

## Components

### Planner

Implemented in `agent.py`.

Current behavior is conservative:

- split simple chained tasks by `然后`, `再`, `&&`, `;`
- infer expected verification mode
- attach `--run` arguments only to a single-step plan

This keeps the planner deterministic. A future LLM planner can be added only after the skill schema and safety gate are stable.

### Router

Implemented in `router.py`.

It loads `skills/*/SKILL.md`, parses frontmatter, and returns ranked candidates.

Each route includes:

- score
- confidence
- risk
- required inputs
- missing inputs
- executable flag
- blocked reason
- scoring reasons

### Safety Gate

The router blocks execution when:

- score is below threshold
- required input is missing
- skill risk exceeds allowed risk
- candidates are ambiguous and `--force` is not set

### Skill Executor

Two execution modes:

- `script`: run `skills/<name>/scripts/run.py`
- `instruction`: return `SKILL.md` content for a human or higher-level agent

Scripts run from the DPU repository root so they can safely reuse existing project files.

### Verifier

Implemented in `agent.py`.

Current verification modes:

- skill selected
- return code zero
- JSON-like output
- HTTP 200 output
- non-empty output
- instruction loaded

Each skill can later define a stronger verifier contract.

### Memory

Implemented as append-only JSONL:

```text
memory/runs.jsonl
```

This is intentionally simple so the run log can later be indexed by the existing DPU RAG.

## Production Hardening Checklist

- Add per-skill verifier definitions.
- Add argument binding by input name rather than positional `--run` args.
- Add a `--dry-run` mode for every non-read-only skill.
- Add a formal `prod_sensitive` approval path.
- Index `memory/runs.jsonl` into DPU RAG.
- Add tests for route scoring, ambiguity, missing inputs, and risk blocking.

