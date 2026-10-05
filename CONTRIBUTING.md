# Contributing

Thanks for helping make Project Recall calmer and more dependable.

## Design constraints

- Orientation never authorizes execution.
- A bare `continue` / `继续` must not activate recall.
- Staleness and urgency remain separate.
- The fast recall path must avoid repository rescans and unnecessary tool calls.
- Personal state stays local unless the user deliberately shares it.
- Recaps are written for the user, not as internal agent notes.

Behavioral changes should document five things: trigger, number of turns, state reads, state writes, and whether project execution becomes authorized.

## Tests

```text
python -m unittest discover -s tests -v
```

When changing triggers or response behavior, also add or update a case in `evals/trigger-cases.json`. Prompt-level cases require evaluation in a compatible host; unit tests cover only deterministic helper and package behavior.

## Pull requests

Keep changes focused. Explain any compatibility impact on generic Agent Skills hosts versus Codex-specific features, and do not include real project state or registry files in fixtures.

