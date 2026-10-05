# Privacy and security

Project Recall is local-first. The bundled helper uses Python's standard library and does not perform network requests, telemetry, account access, or subprocess execution.

## Files it reads

- The current project's `.codex/project-recall/state.json` during recall, validation, dashboard rendering, or the session-start hook.
- The user-level `registry.json` during dashboard rendering and registration.
- A complete JSON state supplied with `init --from-file`, when the user explicitly chooses that option.

The skill instructions may ask the agent to inspect project files only after the user explicitly starts project work. The fast recall path tells the agent not to rescan the repository.

## Files it writes

- `.codex/project-recall/state.json` during initialization and checkpoints.
- `registry.json` during initialization or explicit registration.

Writes use an atomic temporary-file replacement. Initialization refuses to overwrite an existing project state.

## Hook trust boundary

The optional Codex `SessionStart` hook runs:

```text
python <plugin-root>/skills/project-recall/scripts/project_recall.py hook
```

It accepts the hook event on standard input, reads state only for the event's current working directory, and emits additional model context on standard output. If no valid state exists, it exits quietly. It does not edit the project or registry.

Only install the plugin or approve the hook from a repository and revision you trust. The standalone skill works without this hook.

## Sensitive content

Recall state may contain private goals, blockers, decisions, deadlines, and local paths. By default it remains on the local machine, but a project-level state file can still be committed accidentally. Add this path to the target repository's ignore rules unless sharing is intentional:

```text
.codex/project-recall/
```

For an alternate registry location, set `PROJECT_RECALL_DATA` or pass `--data-dir` to supported commands.

