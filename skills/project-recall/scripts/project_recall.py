#!/usr/bin/env python3
"""Local-first state and dashboard helper for the project-recall skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STATE_RELATIVE_PATH = Path(".codex") / "project-recall" / "state.json"
VALID_STATUSES = {"active", "paused", "waiting", "blocked", "completed", "archived"}
VALID_URGENCY = {"normal", "high", "critical"}
MEMORY_TIERS = {"auto": None, "clear": "light", "fuzzy": "standard", "blank": "full"}


class StateError(ValueError):
    """Raised when stored project-recall data is absent or invalid."""


def now_local() -> datetime:
    return datetime.now().astimezone()


def parse_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            chosen_time = time.max if end_of_day else time.min
            return datetime.combine(parsed_date, chosen_time).astimezone()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateError(f"invalid ISO 8601 timestamp: {value}") from exc
    return parsed.astimezone() if parsed.tzinfo is None else parsed


def project_id_for(path: Path) -> str:
    normalized = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def state_path(project_root: Path) -> Path:
    return project_root.resolve() / STATE_RELATIVE_PATH


def default_data_dir() -> Path:
    configured = os.environ.get("PROJECT_RECALL_DATA") or os.environ.get("PLUGIN_DATA")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex" / "project-recall").resolve()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def new_state(project_root: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id_for(project_root),
        "project_name": project_root.resolve().name,
        "status": "active",
        "outcome": "",
        "current_focus": "",
        "next_action": "",
        "priority": {"now": [], "next": [], "later": []},
        "blockers": [],
        "waiting_for": [],
        "recent_decisions": [],
        "open_loops": [],
        "last_meaningful_activity": None,
        "last_checkpoint": "",
        "urgency": {"level": "normal", "due_at": None, "reason": ""},
        "energy_options": {"low": "", "normal": "", "deep": ""},
    }


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError(f"state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"expected a JSON object in {path}")
    return data


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for field in ("project_id", "project_name"):
        if not isinstance(state.get(field), str) or not state.get(field):
            errors.append(f"{field} must be a non-empty string")
    if state.get("status") not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    for field in ("outcome", "current_focus", "next_action", "last_checkpoint"):
        if not isinstance(state.get(field), str):
            errors.append(f"{field} must be a string")
    for field in ("blockers", "waiting_for", "recent_decisions", "open_loops"):
        value = state.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{field} must be a list of strings")

    priority = state.get("priority")
    if not isinstance(priority, dict):
        errors.append("priority must be an object")
    else:
        for lane in ("now", "next", "later"):
            items = priority.get(lane)
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                errors.append(f"priority.{lane} must be a list of strings")

    urgency = state.get("urgency")
    if not isinstance(urgency, dict):
        errors.append("urgency must be an object")
    else:
        if urgency.get("level") not in VALID_URGENCY:
            errors.append(f"urgency.level must be one of: {', '.join(sorted(VALID_URGENCY))}")
        try:
            parse_datetime(urgency.get("due_at"), end_of_day=True)
        except StateError as exc:
            errors.append(str(exc))
        if not isinstance(urgency.get("reason", ""), str):
            errors.append("urgency.reason must be a string")

    activity = state.get("last_meaningful_activity")
    if activity is not None:
        try:
            parse_datetime(activity)
        except StateError as exc:
            errors.append(str(exc))

    energy = state.get("energy_options")
    if not isinstance(energy, dict):
        errors.append("energy_options must be an object")
    else:
        for level in ("low", "normal", "deep"):
            if not isinstance(energy.get(level, ""), str):
                errors.append(f"energy_options.{level} must be a string")
    return errors


def load_valid_state(project_root: Path) -> dict[str, Any]:
    state = load_json(state_path(project_root))
    errors = validate_state(state)
    if errors:
        raise StateError("; ".join(errors))
    return state


def calendar_day_gap(activity: datetime | None, current: datetime) -> int | None:
    if activity is None:
        return None
    local_activity = activity.astimezone(current.tzinfo)
    return max(0, (current.date() - local_activity.date()).days)


def recall_tier(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days == 0:
        return "today"
    if days <= 2:
        return "light"
    if days <= 9:
        return "standard"
    return "full"


def urgency_summary(state: dict[str, Any], current: datetime) -> dict[str, Any]:
    urgency = state["urgency"]
    due = parse_datetime(urgency.get("due_at"), end_of_day=True)
    days_until_due = None
    overdue = False
    if due is not None:
        local_due = due.astimezone(current.tzinfo)
        days_until_due = (local_due.date() - current.date()).days
        overdue = local_due < current

    explicit = urgency.get("level", "normal")
    if state["status"] in {"completed", "archived"}:
        band = "inactive"
    elif explicit == "critical" or overdue or (days_until_due is not None and days_until_due <= 2):
        band = "critical"
    elif explicit == "high" or (days_until_due is not None and days_until_due <= 7):
        band = "soon"
    else:
        band = "normal"
    return {
        "band": band,
        "explicit_level": explicit,
        "due_at": urgency.get("due_at"),
        "days_until_due": days_until_due,
        "overdue": overdue,
        "reason": urgency.get("reason", ""),
    }


def inspect_project(
    project_root: Path,
    current: datetime | None = None,
    memory: str = "auto",
) -> dict[str, Any]:
    current = current or now_local()
    if memory not in MEMORY_TIERS:
        raise StateError(f"memory must be one of: {', '.join(MEMORY_TIERS)}")
    state = load_valid_state(project_root)
    activity = parse_datetime(state.get("last_meaningful_activity"))
    days = calendar_day_gap(activity, current)
    automatic_tier = recall_tier(days)
    selected_tier = MEMORY_TIERS[memory] or automatic_tier
    return {
        "project_root": str(project_root.resolve()),
        "state_path": str(state_path(project_root)),
        "recall_tier": selected_tier,
        "automatic_recall_tier": automatic_tier,
        "recall_basis": "time" if memory == "auto" else "memory_override",
        "memory_level": memory,
        "calendar_days_since_activity": days,
        "urgency": urgency_summary(state, current),
        "state": state,
    }


def registry_path(data_dir: Path) -> Path:
    return data_dir / "registry.json"


def load_registry(data_dir: Path) -> dict[str, Any]:
    path = registry_path(data_dir)
    if not path.exists():
        return {"schema_version": 1, "projects": []}
    registry = load_json(path)
    if registry.get("schema_version") != 1 or not isinstance(registry.get("projects"), list):
        raise StateError(f"invalid registry: {path}")
    return registry


def register_project(project_root: Path, data_dir: Path) -> dict[str, Any]:
    state = load_valid_state(project_root)
    registry = load_registry(data_dir)
    entry = {
        "project_id": state["project_id"],
        "project_name": state["project_name"],
        "project_root": str(project_root.resolve()),
        "registered_at": now_local().isoformat(timespec="seconds"),
    }
    existing = next(
        (item for item in registry["projects"] if item.get("project_id") == state["project_id"]),
        None,
    )
    if existing:
        entry["registered_at"] = existing.get("registered_at", entry["registered_at"])
        existing.update(entry)
    else:
        registry["projects"].append(entry)
    registry["projects"].sort(key=lambda item: item.get("project_name", "").casefold())
    atomic_write_json(registry_path(data_dir), registry)
    return entry


def dashboard(data_dir: Path, current: datetime | None = None) -> dict[str, Any]:
    current = current or now_local()
    registry = load_registry(data_dir)
    projects: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for entry in registry["projects"]:
        root = Path(entry.get("project_root", ""))
        try:
            summary = inspect_project(root, current)
        except (StateError, OSError) as exc:
            unavailable.append({**entry, "error": str(exc)})
            continue
        state = summary["state"]
        projects.append(
            {
                "project_id": state["project_id"],
                "project_name": state["project_name"],
                "project_root": str(root.resolve()),
                "status": state["status"],
                "recall_tier": summary["recall_tier"],
                "calendar_days_since_activity": summary["calendar_days_since_activity"],
                "urgency": summary["urgency"],
                "current_focus": state["current_focus"],
                "next_action": state["next_action"],
                "blockers": state["blockers"],
                "waiting_for": state["waiting_for"],
                "energy_options": state["energy_options"],
            }
        )

    urgency_rank = {"critical": 0, "soon": 1, "normal": 2, "inactive": 3}
    status_rank = {"active": 0, "blocked": 1, "waiting": 2, "paused": 3, "completed": 4, "archived": 5}
    projects.sort(
        key=lambda item: (
            urgency_rank[item["urgency"]["band"]],
            status_rank[item["status"]],
            -(item["calendar_days_since_activity"] or 0),
            item["project_name"].casefold(),
        )
    )
    return {
        "generated_at": current.isoformat(timespec="seconds"),
        "projects": projects,
        "unavailable": unavailable,
    }


def compact_state_for_tier(summary: dict[str, Any]) -> dict[str, Any]:
    state = summary["state"]
    tier = summary["recall_tier"]
    compact = {
        "project_name": state["project_name"],
        "status": state["status"],
        "outcome": state["outcome"],
        "last_checkpoint": state["last_checkpoint"],
        "current_focus": state["current_focus"],
        "next_action": state["next_action"],
        "urgency": summary["urgency"],
    }
    if tier in {"today", "light"}:
        return compact
    compact.update(
        {
            "priority_now": state["priority"]["now"],
            "blockers": state["blockers"],
            "waiting_for": state["waiting_for"],
        }
    )
    if tier in {"standard", "unknown"}:
        return compact
    compact.update(
        {
            "priority_next": state["priority"]["next"],
            "recent_decisions": state["recent_decisions"],
            "open_loops": state["open_loops"],
            "energy_options": state["energy_options"],
        }
    )
    return compact


def build_session_context(project_root: Path, current: datetime | None = None) -> str | None:
    try:
        summary = inspect_project(project_root, current)
    except StateError:
        return None
    tier = summary["recall_tier"]
    instruction = {
        "today": "If asked to resume, briefly say where work paused and offer a next-step choice.",
        "light": "If asked to resume, use at most three short, user-facing lines: where work paused and one easy next step.",
        "standard": "If asked to resume, explain in the user's language what was finished, what remains, and the easiest next step.",
        "full": "If asked to resume, rebuild the human story of the project, then offer one gentle re-entry step.",
        "unknown": "Recency is unknown. Give a compact, user-facing recap and label uncertainty.",
    }[tier]
    instruction += (
        " Always begin with a one- or two-sentence project coordinate: the overall purpose and the linear path from what is done, through the current stage, to the next major stage."
        " Orientation is not execution: stop after the recap and ask what the user wants. "
        "Do not edit files, run project commands or tests, or begin the saved next action unless the user explicitly asks to start work. "
        "Use this injected context directly; do not rescan the repository during orientation."
    )
    if summary["urgency"]["band"] in {"critical", "soon"}:
        instruction += " Surface the time-sensitive item briefly even if the project was active today."
    context = {
        "project_recall": {
            "recall_tier": tier,
            "calendar_days_since_activity": summary["calendar_days_since_activity"],
            "instruction": instruction,
            "state": compact_state_for_tier(summary),
        }
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def render_markdown_dashboard(result: dict[str, Any]) -> str:
    lines = ["# Project Recall Dashboard", ""]
    if not result["projects"]:
        lines.append("No available registered projects.")
    for project in result["projects"]:
        days = project["calendar_days_since_activity"]
        recency = "unknown recency" if days is None else f"{days} day(s) since meaningful activity"
        lines.extend(
            [
                f"## {project['project_name']}",
                f"- Status: {project['status']}",
                f"- Attention: {project['urgency']['band']}",
                f"- Recall: {project['recall_tier']} ({recency})",
                f"- Focus: {project['current_focus'] or 'Not recorded'}",
                f"- Next: {project['next_action'] or 'Not recorded'}",
                "",
            ]
        )
    if result["unavailable"]:
        lines.extend(["## Unavailable", ""])
        for item in result["unavailable"]:
            lines.append(f"- {item.get('project_name', 'Unknown')}: {item['error']}")
    return "\n".join(lines).rstrip() + "\n"


def parse_now(value: str | None) -> datetime:
    parsed = parse_datetime(value) if value else now_local()
    assert parsed is not None
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "register", "validate", "inspect"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-root", default=".")
        if command in {"init", "register"}:
            child.add_argument("--data-dir")
        if command == "init":
            child.add_argument(
                "--from-file",
                help="Initialize from a complete state JSON file; project id and name are derived locally",
            )
        if command == "inspect":
            child.add_argument("--now", help="ISO 8601 timestamp for deterministic inspection")
            child.add_argument(
                "--memory",
                choices=tuple(MEMORY_TIERS),
                default="auto",
                help="Override time-based detail: clear, fuzzy, or blank",
            )
            child.add_argument("--format", choices=("json", "compact"), default="json")
    dashboard_parser = subparsers.add_parser("dashboard")
    dashboard_parser.add_argument("--data-dir")
    dashboard_parser.add_argument("--now", help="ISO 8601 timestamp for deterministic output")
    dashboard_parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    subparsers.add_parser("hook", help="Read a Codex SessionStart event from stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            root = Path(args.project_root).resolve()
            path = state_path(root)
            if path.exists():
                raise StateError(f"refusing to overwrite existing state: {path}")
            state = load_json(Path(args.from_file).resolve()) if args.from_file else new_state(root)
            state["schema_version"] = SCHEMA_VERSION
            state["project_id"] = project_id_for(root)
            state["project_name"] = root.name
            errors = validate_state(state)
            if errors:
                raise StateError("; ".join(errors))
            atomic_write_json(path, state)
            data_dir = Path(args.data_dir).resolve() if args.data_dir else default_data_dir()
            entry = register_project(root, data_dir)
            print(json.dumps({"created": str(path), "registered": entry}, ensure_ascii=True, indent=2))
            return 0
        if args.command == "register":
            root = Path(args.project_root).resolve()
            data_dir = Path(args.data_dir).resolve() if args.data_dir else default_data_dir()
            print(json.dumps(register_project(root, data_dir), ensure_ascii=True, indent=2))
            return 0
        if args.command == "validate":
            state = load_json(state_path(Path(args.project_root)))
            errors = validate_state(state)
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=True, indent=2))
            return 0 if not errors else 1
        if args.command == "inspect":
            result = inspect_project(
                Path(args.project_root), parse_now(args.now), memory=args.memory
            )
            output = result if args.format == "json" else compact_state_for_tier(result)
            print(json.dumps(output, ensure_ascii=True, indent=2))
            return 0
        if args.command == "dashboard":
            data_dir = Path(args.data_dir).resolve() if args.data_dir else default_data_dir()
            result = dashboard(data_dir, parse_now(args.now))
            if args.format == "json":
                print(json.dumps(result, ensure_ascii=True, indent=2))
            else:
                print(render_markdown_dashboard(result), end="")
            return 0
        if args.command == "hook":
            try:
                event = json.load(sys.stdin)
            except json.JSONDecodeError:
                return 0
            context = build_session_context(Path(event.get("cwd") or os.getcwd()))
            if context:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "SessionStart",
                                "additionalContext": context,
                            }
                        },
                        ensure_ascii=True,
                    )
                )
            return 0
    except (StateError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
