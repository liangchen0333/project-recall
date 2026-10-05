# Project Recall

Project Recall is a local-first Agent Skill for returning to long-running work without first reconstructing the whole project in your head. It is designed for people whose sense of project continuity is unreliable—especially after context switches, low-energy days, or a long gap.

It remembers a small, structured checkpoint per project, adapts recap depth to either time away or the user's stated memory clarity, and keeps **orientation separate from execution**. Asking for a recap never authorizes the agent to start editing the project.

The current release is Codex-first. The core skill and Python helper are portable; the automatic session-start context injection and in-chat follow-up buttons are Codex integrations.

## What it feels like

Invoke `Recall · 项目回忆`, then choose:

- `清楚 · 简短` — just reconnect the last stopping point.
- `模糊 · 标准` — recap what is done, what remains, and the easiest next step.
- `断片 · 完整` — rebuild the project story and give one gentle re-entry step.

Every recap includes a short **项目坐标**: what the project is for, what foundation is already done, which stage it is in now, and what major stage comes next. The agent then stops and waits for a separate instruction such as `开始下一步`.

For an overview across projects, `$project-recall 今日驾驶舱` shows urgent, waiting, and stale projects without treating “old” as “urgent.”

## Features

- Structured project memory in `.codex/project-recall/state.json`
- Recall depths for today, 1–2 days, 3–9 days, and 10+ days
- Manual memory override: clear, fuzzy, or blank
- Separate urgency, staleness, status, and effort signals
- Lightweight checkpoints based on the current conversation
- User-level project registry and cross-project dashboard
- Optional Codex `SessionStart` context injection
- No third-party Python dependencies and no network access

## Architecture

```text
plugin.json                         Portable plugin manifest
hooks/hooks.json                    Optional Codex session-start hook
skills/project-recall/
  SKILL.md                          Behavior, triggers, and safety boundary
  agents/openai.yaml                Codex skill-picker metadata
  assets/project-state.template.json
  references/state-schema.md
  scripts/project_recall.py         Deterministic local state helper
evals/trigger-cases.json            Trigger and non-trigger scenarios
tests/test_project_recall.py        Helper and packaging tests
```

This deliberately uses progressive disclosure: the agent sees the short skill description first, loads `SKILL.md` only when relevant, and reads the schema reference only for setup or state updates.

## Requirements

- Python 3.10 or newer
- An Agent Skills-compatible host for the core skill
- Codex Desktop/runtime for the bundled picker metadata and session hook

## Install

### Codex skill only

Copy `skills/project-recall` into your Codex skills directory:

```text
~/.codex/skills/project-recall/
```

Restart Codex after installation. This gives you explicit recall, checkpoint, setup, and dashboard commands. It does **not** enable the automatic session-start hook, because hooks belong to the plugin bundle rather than the standalone skill directory.

### Full Codex plugin bundle

The repository root is laid out as a portable plugin (`plugin.json`, `skills/`, and `hooks/`). Install it through a trusted local or Git-backed Codex plugin marketplace. Review and approve the hook when Codex asks: it launches the bundled Python helper at session start and injects read-only context only when the current project already has a state file.

For a skill-only installation, ask Codex to install the skill from `https://github.com/liangchen0333/project-recall/tree/main/skills/project-recall`.

Before publishing a marketplace listing, complete the identity and release items in [docs/release-checklist.md](docs/release-checklist.md).

## Quick start

In a project you want to track:

```powershell
python path\to\project-recall\scripts\project_recall.py init --project-root .
```

On macOS or Linux, use `python3` if that is how Python is exposed:

```bash
python3 path/to/project-recall/scripts/project_recall.py init --project-root .
```

Initialization creates `.codex/project-recall/state.json` without overwriting an existing file and registers the project in the local dashboard. Fill the generated state through the skill (`$project-recall setup this project`) or edit the JSON directly using [the schema guide](skills/project-recall/references/state-schema.md).

Useful phrases:

| Phrase | Effect |
| --- | --- |
| `$project-recall` | Open the three-choice memory picker |
| `$project-recall 回忆这个项目：断片` | Full recap in the same turn |
| `$project-recall 今天先到这里` | Save a lightweight checkpoint |
| `$project-recall 今日驾驶舱` | Read-only overview of registered projects |
| `开始下一步` | Separately authorize the proposed project work |

A bare `继续` deliberately does not trigger Project Recall, because it is too common during ordinary work.

## Interaction contract

| Input or event | Extra choice turn | Reads recall state | Writes recall state | May start project work |
| --- | --- | --- | --- | --- |
| Session startup/resume hook | No | Current project only | No | No |
| Select `Recall · 项目回忆` | Yes; three buttons | No, until a choice | No | No |
| Direct recall with clarity | No | Current project | No | No |
| Bare `继续` | No recall trigger | No | No | Only already-authorized work |
| `$project-recall 今天先到这里` | No | Current project + conversation | Yes | No |
| `$project-recall 今日驾驶舱` | No | Registry + registered states | No | No |
| `开始下一步` after recap | No | As needed for that task | Normal project changes | Yes |

## Data and privacy

Project Recall is local-first and makes no network requests. It stores:

- Per-project state: `<project>/.codex/project-recall/state.json`
- Default registry: `~/.codex/project-recall/registry.json`
- Plugin-managed data: the directory supplied through `PLUGIN_DATA`, when present

The state can contain project goals, blockers, decisions, and paths. Treat it as potentially sensitive. Add `.codex/project-recall/` to the target project's `.gitignore` unless you intentionally want to share that memory with collaborators. See [docs/privacy-and-security.md](docs/privacy-and-security.md) for the complete trust boundary.

## Development

Run the test suite with the standard library only:

```text
python -m unittest discover -s tests -v
```

The prompt-level trigger scenarios in [evals/trigger-cases.json](evals/trigger-cases.json) cover explicit, implicit, contextual, and negative cases. They are human/model evaluation fixtures; the deterministic Python tests do not claim to prove model behavior.

## Compatibility

| Capability | Generic Agent Skills host | Codex |
| --- | --- | --- |
| Explicit recall/checkpoint instructions | Yes | Yes |
| Python state helper | Yes, with Python | Yes |
| Skill picker metadata | Host-dependent | Yes |
| `:codex-followup` choice buttons | No | Yes |
| Automatic `SessionStart` injection | No | Yes, as plugin hook |
| Cross-project dashboard | Yes, if invoked | Yes |

## Project status

Version 0.6.0 is release-candidate quality for local use. The canonical repository is `liangchen0333/project-recall`, released under the MIT License. Publishing now only requires creating the repository and release tag.

## License

MIT © 2026 liangchen0333. See [LICENSE](LICENSE).
