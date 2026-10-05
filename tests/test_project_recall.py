from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "project-recall"
    / "scripts"
    / "project_recall.py"
)
SPEC = importlib.util.spec_from_file_location("project_recall", SCRIPT)
assert SPEC and SPEC.loader
project_recall = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_recall)


class ProjectRecallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "example-project"
        self.root.mkdir()
        self.data_dir = Path(self.temp.name) / "registry"
        self.state = project_recall.new_state(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_state(self) -> None:
        project_recall.atomic_write_json(project_recall.state_path(self.root), self.state)

    def test_recall_tiers_use_calendar_days(self) -> None:
        self.state["last_meaningful_activity"] = "2026-10-02T00:01:00+00:00"
        self.write_state()
        cases = [
            ("2026-10-02T23:59:00+00:00", "today"),
            ("2026-10-04T09:00:00+00:00", "light"),
            ("2026-10-05T09:00:00+00:00", "standard"),
            ("2026-10-12T09:00:00+00:00", "full"),
        ]
        for timestamp, expected in cases:
            with self.subTest(timestamp=timestamp):
                result = project_recall.inspect_project(self.root, datetime.fromisoformat(timestamp))
                self.assertEqual(result["recall_tier"], expected)

    def test_staleness_does_not_create_urgency(self) -> None:
        self.state["last_meaningful_activity"] = "2026-01-01T09:00:00+00:00"
        self.write_state()
        result = project_recall.inspect_project(
            self.root, datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        )
        self.assertEqual(result["recall_tier"], "full")
        self.assertEqual(result["urgency"]["band"], "normal")

    def test_memory_clarity_overrides_elapsed_time(self) -> None:
        self.state["last_meaningful_activity"] = "2026-10-02T08:00:00+00:00"
        self.write_state()
        now = datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        cases = [("clear", "light"), ("fuzzy", "standard"), ("blank", "full")]
        for memory, expected in cases:
            with self.subTest(memory=memory):
                result = project_recall.inspect_project(self.root, now, memory=memory)
                self.assertEqual(result["recall_tier"], expected)
                self.assertEqual(result["automatic_recall_tier"], "today")
                self.assertEqual(result["recall_basis"], "memory_override")

    def test_due_date_can_be_urgent_even_today(self) -> None:
        self.state["last_meaningful_activity"] = "2026-10-02T08:00:00+00:00"
        self.state["urgency"]["due_at"] = "2026-10-03"
        self.write_state()
        result = project_recall.inspect_project(
            self.root, datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        )
        self.assertEqual(result["recall_tier"], "today")
        self.assertEqual(result["urgency"]["band"], "critical")

    def test_registry_dashboard_reads_project_state(self) -> None:
        self.state["last_meaningful_activity"] = "2026-10-01T09:00:00+00:00"
        self.state["next_action"] = "Open src/main.py and add the parser test."
        self.write_state()
        project_recall.register_project(self.root, self.data_dir)
        result = project_recall.dashboard(
            self.data_dir, datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        )
        self.assertEqual(len(result["projects"]), 1)
        self.assertEqual(result["projects"][0]["recall_tier"], "light")
        self.assertEqual(result["projects"][0]["next_action"], self.state["next_action"])

    def test_dashboard_cli_round_trips_non_ascii_text(self) -> None:
        self.state["current_focus"] = "确认中文项目进度"
        self.write_state()
        project_recall.register_project(self.root, self.data_dir)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = project_recall.main(
                [
                    "dashboard",
                    "--data-dir",
                    str(self.data_dir),
                    "--format",
                    "json",
                    "--now",
                    "2026-10-02T09:00:00+00:00",
                ]
            )
        self.assertEqual(exit_code, 0)
        raw = output.getvalue()
        self.assertIn("\\u", raw)
        parsed = json.loads(raw)
        self.assertEqual(parsed["projects"][0]["current_focus"], "确认中文项目进度")

    def test_init_refuses_to_overwrite(self) -> None:
        self.write_state()
        with redirect_stderr(io.StringIO()):
            exit_code = project_recall.main(
                ["init", "--project-root", str(self.root), "--data-dir", str(self.data_dir)]
            )
        self.assertEqual(exit_code, 2)

    def test_hook_context_is_progressively_disclosed(self) -> None:
        self.state.update(
            {
                "outcome": "Ship the parser",
                "current_focus": "Parser tests",
                "next_action": "Add the invalid-input case",
                "last_meaningful_activity": "2026-09-20T09:00:00+00:00",
            }
        )
        self.write_state()
        context = project_recall.build_session_context(
            self.root, datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        )
        assert context
        payload = json.loads(context)["project_recall"]
        self.assertEqual(payload["recall_tier"], "full")
        self.assertIn("Orientation is not execution", payload["instruction"])
        self.assertIn("Do not edit files", payload["instruction"])
        self.assertIn("outcome", payload["state"])
        self.assertIn("open_loops", payload["state"])

    def test_short_context_still_contains_project_coordinate_material(self) -> None:
        self.state.update(
            {
                "outcome": "Ship the parser",
                "last_checkpoint": "Tokenization works; expression parsing is next.",
                "last_meaningful_activity": "2026-10-02T08:00:00+00:00",
            }
        )
        self.write_state()
        context = project_recall.build_session_context(
            self.root, datetime.fromisoformat("2026-10-02T09:00:00+00:00")
        )
        assert context
        payload = json.loads(context)["project_recall"]
        self.assertEqual(payload["recall_tier"], "today")
        self.assertEqual(payload["state"]["outcome"], "Ship the parser")
        self.assertIn("Tokenization works", payload["state"]["last_checkpoint"])
        self.assertIn("project coordinate", payload["instruction"])

    def test_packaging_json_files_are_valid(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        manifest = json.loads((repository / "plugin.json").read_text(encoding="utf-8"))
        hooks = json.loads(
            (repository / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        evals = json.loads(
            (repository / "evals" / "trigger-cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "project-recall")
        self.assertEqual(manifest["author"]["name"], "liangchen0333")
        self.assertEqual(
            manifest["repository"], "https://github.com/liangchen0333/project-recall"
        )
        self.assertEqual(manifest["license"], "MIT")
        self.assertIn("SessionStart", hooks["hooks"])
        self.assertTrue(any(not case["should_trigger"] for case in evals["cases"]))

    def test_skill_metadata_and_negative_trigger_are_present(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        skill = (repository / "skills" / "project-recall" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        agent = (
            repository / "skills" / "project-recall" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: project-recall\n"))
        self.assertIn('bare "continue"', skill)
        self.assertIn("display_name", agent)


if __name__ == "__main__":
    unittest.main()
