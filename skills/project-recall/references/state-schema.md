# Project state schema

The canonical project state is `.codex/project-recall/state.json`. It is intentionally small, local-first, and human-editable.

## Fields

```json
{
  "schema_version": 1,
  "project_id": "stable-generated-id",
  "project_name": "Example project",
  "status": "active",
  "outcome": "What success looks like",
  "current_focus": "The single area currently being advanced",
  "next_action": "A concrete action that can be started immediately",
  "priority": {
    "now": [],
    "next": [],
    "later": []
  },
  "blockers": [],
  "waiting_for": [],
  "recent_decisions": [],
  "open_loops": [],
  "last_meaningful_activity": null,
  "last_checkpoint": "",
  "urgency": {
    "level": "normal",
    "due_at": null,
    "reason": ""
  },
  "energy_options": {
    "low": "",
    "normal": "",
    "deep": ""
  }
}
```

## Invariants

- `status` is one of `active`, `paused`, `waiting`, `blocked`, `completed`, or `archived`.
- `urgency.level` is one of `normal`, `high`, or `critical`.
- Timestamps use ISO 8601 with a timezone. A date-only `due_at` is also accepted.
- `last_meaningful_activity` changes only after work, a decision, a newly discovered blocker, or an intentional plan change. Opening, reading, or receiving a recap does not change it.
- `next_action` describes a physical or digital action, not an aspiration such as "continue development".
- `priority.now` should remain small. Prefer one item; use at most three when they are genuinely parallel constraints.
- `recent_decisions` contains conclusions and short reasons, not full meeting history.
- `open_loops` contains unresolved questions worth preserving. Ideas with no current relevance belong elsewhere.

## Recall tiers

Recall tiers use local calendar-day distance rather than elapsed hours:

- Same date: `today`
- 1–2 calendar days: `light`
- 3–9 calendar days: `standard`
- 10 or more calendar days: `full`
- Missing or invalid activity timestamp: `unknown`

These tiers control presentation length, not priority. A stale project can be intentionally paused; a project touched today can still be urgent.

## Updating safely

Before replacing a value, prefer evidence in this order:

1. The user's explicit current statement.
2. Current project files, Git state, tests, and external records the user placed in scope.
3. Existing project state.
4. Conversation inference, clearly marked as uncertain.

Preserve unknown values as empty or `null`; do not fill gaps with plausible guesses.
