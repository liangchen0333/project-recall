---
name: project-recall
description: Restore or checkpoint durable memory for a long-running project when the user explicitly asks to remember where they left off, save a stopping point, or review tracked projects. Do not trigger for a bare "continue" or ordinary continuation inside active work.
---

# Project Recall

Keep enough durable state that the user can return without reconstructing the project from chat history. Optimize for recognition, low-friction re-entry, and one small choice about what to do next.

This skill is an orientation layer, not permission to execute project work. A request such as "continue", "resume", or "what was I doing?" authorizes a recap only. Do not edit files, run project commands or tests, implement the recorded next action, or otherwise begin work until the user explicitly asks to start doing it.

Project state lives at `.codex/project-recall/state.json`. Treat it as a navigation aid, not proof: current files, Git state, tests, and explicit user statements take precedence.

## Select a mode

- **Checkpoint:** The user is pausing, wrapping up, switching projects, or asks to save progress.
- **Picker:** The user invokes the skill entry, asks to choose memory clarity, or says "打开回忆清晰度选择器" without already choosing clear, fuzzy, or blank. Show the three choice buttons only. Do not inspect project state yet.
- **Resume:** The user explicitly asks to remember where they were, invokes `$project-recall`, or asks for a re-entry card. A bare "continue", "继续", "接着", or similar phrase inside an active conversation is ordinary task continuation and must not select this mode. Resume ends after orientation and a choice; it never starts project work by itself.
- **Dashboard:** The user asks what is urgent, what projects exist, or what deserves attention today.
- **Setup:** The user explicitly asks to start tracking the current project.

For field definitions and update rules, read [references/state-schema.md](references/state-schema.md). Do not load it for a simple resume when the existing state is valid and self-explanatory.

## Setup

Run the bundled script from the project root:

```text
python <skill-dir>/scripts/project_recall.py init --project-root .
```

On systems where Python is exposed as `python3`, use that command instead. Initialization must not overwrite an existing state file. After setup, replace template values with facts supported by the project or supplied by the user.

## Checkpoint

1. Use the existing state and evidence already present in the current conversation. Do not rescan the repository, inspect Git history, or rerun tests solely to make a checkpoint.
2. Update only fields affected by the work. Preserve valid decisions and open loops.
3. Set `last_meaningful_activity` to the actual current timestamp only when meaningful work, a decision, a blocker, or a deliberate planning change occurred. Merely opening or inspecting the project does not count.
4. Make `next_action` directly executable and small enough to start without replanning. Name a file, function, document, command, or concrete decision when possible.
5. Distinguish completed work from unverified work. Do not infer progress from conversational confidence.
6. Make one focused state update, then run `validate`. Run `register` only for initial setup or when the project path/name changed.

Do not require the user to fill a form when the state can be derived safely. Ask only for a missing decision that materially changes the next action.

## Resume

Prefer project-recall context already injected at session start. This is the fast path: do not run commands, read project files, inspect Git, or validate the state again. If injected context is absent, run only:

```text
python <skill-dir>/scripts/project_recall.py inspect --project-root . --format json
```

Time away supplies a default, not a verdict. The user's stated memory clarity always overrides it. Map the choices this way:

- `清楚 / clear`: `light`
- `模糊 / fuzzy`: `standard`
- `断片 / blank`: `full`

When the user supplies a clarity level, run `inspect` with `--memory clear`, `--memory fuzzy`, or `--memory blank`. This also makes every detail level testable without changing timestamps or waiting several days. With no stated level, use the time-based `recall_tier` already injected by the hook.

Use the selected `recall_tier` to control how much to surface:

- `today`: give no recap unless asked; when asked, state where things paused and the smallest next choice.
- `light`: give current focus and one next action in at most three short lines.
- `standard`: explain what the user was trying to accomplish, what was finished, what remains, and the easiest next step.
- `full`: rebuild the story of the project: why it exists, what already works, where it paused, unresolved choices, and one gentle re-entry step.
- `unknown`: state that recency is unavailable and use a compact standard recap.

Urgency may justify a short alert even in the `today` tier. Staleness alone never makes a project urgent.

Every recap, even `today` or `clear`, begins with **项目坐标**: one or two sentences explaining what the whole project is for and its linear path—what foundation is already done, which stage it is in now, and what major stage comes next. This is orientation, not a percentage estimate.

Then write for the user, not for another agent. Use the user's language and concrete everyday wording. Translate internal fields into a short narrative instead of exposing labels such as `current_focus`, `checkpoint`, or implementation shorthand without explanation. Prefer this shape when a recap is needed:

- **你上次做到这里：** one or two concrete sentences about what now works.
- **还没有做：** the immediate unfinished part, plus a blocker only if it affects today's choice.
- **现在最容易接上的一步：** one small action and why it comes first.

Then stop and ask whether the user wants to start that step, see more background, choose a lower-energy action, or leave it for later. Do not say that work will begin next, and do not begin it in the same turn.

Do not verify stale state during orientation; label it as the saved memory if needed. Only compare it with current repository evidence after the user explicitly chooses to begin work.

## Memory clarity picker

When Picker mode applies, do not read state, run `inspect`, summarize the project, or narrate tool use. Ask one short question and emit exactly these three unescaped Markdown list items, not inside a code fence:

- :codex-followup[清楚 · 简短]{prompt="使用 $project-recall 回忆这个项目：清楚。只回忆，不开始工作。"}
- :codex-followup[模糊 · 标准]{prompt="使用 $project-recall 回忆这个项目：模糊。只回忆，不开始工作。"}
- :codex-followup[断片 · 完整]{prompt="使用 $project-recall 回忆这个项目：断片。只回忆，不开始工作。"}

The question can be `你现在对这个项目记得多清楚？`. Stop after the buttons. If the host does not render follow-up directives, show the same three choices as plain text instead.

## Dashboard

Run:

```text
python <skill-dir>/scripts/project_recall.py dashboard --format json
```

Present:

1. Truly time-sensitive or explicitly high-urgency items.
2. Waiting or blocked projects that need a decision or follow-up.
3. Stale projects separately, without implying they are urgent.
4. One recommended project and one concrete next action.

Keep the active choice set small. If energy information exists, optionally provide one lower-energy alternative. Respect `paused`, `waiting`, `completed`, and `archived` states; do not repeatedly promote them as active work.

Treat `$project-recall 今日驾驶舱` as a read-only cross-project dashboard that can run from any working directory. Read the user-level registry; do not initialize the current folder, modify project states, or begin project work. This mode is suitable for a dedicated pinned chat.

## Interaction principles

- Prefer one recommended action over an unranked list.
- Treat orientation and execution as separate turns. Ambiguous phrases such as "继续", "接着来", or "然后呢" mean orient me, not modify the project.
- Separate urgency, importance, staleness, and effort; they are not interchangeable.
- Use neutral terms such as "carried forward" or "not revisited" rather than blame-oriented language.
- Let the user correct, snooze, pause, or archive with one sentence.
- Do not fabricate deadlines, completion percentages, priorities, or remembered intent.
- Keep personal state local unless the user explicitly chooses to commit or sync it.
- Keep fast-path responses fast: no tool narration, repository audit, test run, or repeated skill/state reads when session context already contains enough information.

## Explicit shortcuts

Use these phrases as unambiguous interaction boundaries:

- `$project-recall 打开回忆清晰度选择器` — show three choice buttons without reading project state.
- `$project-recall 回忆这个项目` — use the time-based default and show orientation only.
- `$project-recall 回忆这个项目：清楚` — concise recap in the same turn, regardless of elapsed time.
- `$project-recall 回忆这个项目：模糊` — normal recap in the same turn, regardless of elapsed time.
- `$project-recall 回忆这个项目：断片` — full re-orientation in the same turn, regardless of elapsed time.
- `$project-recall 今日驾驶舱` — read-only cross-project dashboard from the global registry.
- `开始下一步` — after a recall card, authorize the proposed project work.
- `$project-recall 今天先到这里` — save a lightweight checkpoint without re-auditing the project.

Do not advertise bare "继续" as a project-recall shortcut.

## Fast checkpoint response

For phrases such as "今天先到这里", "收工", or "保存进度", derive the checkpoint from work already visible in the conversation. Update the state without redoing verification. Reply in two to four short lines: what was saved, where work paused, and the first step for next time. Mention uncertainty only when it changes that next step.

## Script commands

```text
project_recall.py init       # create state without overwriting
project_recall.py register   # add/update this project in the local registry
project_recall.py validate   # validate state shape and timestamps
project_recall.py inspect    # calculate recall tier and urgency
project_recall.py dashboard  # summarize registered projects
```

Use `--data-dir` to override the user-level registry location for tests or custom setups.
Use `inspect --memory clear|fuzzy|blank` to override the time-based recall tier without changing saved activity dates.
