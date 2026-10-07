import json
from copy import deepcopy
from pathlib import Path

from django.test import SimpleTestCase

from simulations.domain import InvalidAction, InvalidScenario, SimulationEngine, evaluate
from simulations.domain.scenario import parse_scenario


SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


class ScenarioValidationTests(SimpleTestCase):
    def setUp(self):
        self.definition = json.loads((SCENARIOS / "files_001_v2.json").read_text())

    def test_invalid_field_types_raise_domain_errors(self):
        for field, value in (
            ("runtime", []), ("version", True), ("completion", []),
            ("instructions", "Une instruction"), ("hints", [None]),
            ("allowed_actions", [[]]), ("criteria", None), ("initial_state", []),
        ):
            with self.subTest(field=field):
                definition = deepcopy(self.definition)
                definition["scenario"][field] = value
                with self.assertRaises(InvalidScenario):
                    parse_scenario(definition)

    def test_invalid_criteria_are_rejected_before_execution(self):
        for field, value in (
            ("operator", "unknown"), ("operator", []), ("params", None),
            ("params", {"path": "Documents", "kind": "folder"}),
            ("params", {"path": [[]], "kind": "folder"}),
            ("params", {"path": [], "kind": []}),
            ("points", True), ("code", []),
        ):
            with self.subTest(field=field, value=value):
                definition = deepcopy(self.definition)
                definition["scenario"]["criteria"][0][field] = value
                with self.assertRaises(InvalidScenario):
                    parse_scenario(definition)

    def test_invalid_completion_and_unknown_actions_are_rejected(self):
        for completion in (
            {"minimum_score": True},
            {"minimum_score": 80, "required_criteria": [[]]},
            {"minimum_score": 80, "required_criteria": ["unknown"]},
        ):
            definition = deepcopy(self.definition)
            definition["scenario"]["completion"] = completion
            with self.subTest(completion=completion), self.assertRaises(InvalidScenario):
                parse_scenario(definition)
        self.definition["scenario"]["allowed_actions"] = ["unknown"]
        with self.assertRaises(InvalidScenario):
            parse_scenario(self.definition)

    def test_invalid_trees_are_rejected(self):
        for field, value in (
            ("id", []), ("id", "root"), ("parent_id", {}),
            ("parent_id", "missing"), ("parent_id", "documents"),
            ("parent_id", None), ("name", "Images"), ("kind", []),
        ):
            definition = deepcopy(self.definition)
            definition["scenario"]["initial_state"]["items"][1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidScenario):
                parse_scenario(definition)

    def test_cycle_and_file_parent_are_rejected(self):
        for file_parent in (False, True):
            definition = deepcopy(self.definition)
            items = definition["scenario"]["initial_state"]["items"]
            items[1]["parent_id"] = "images"
            if file_parent:
                items[2]["kind"] = "file"
            else:
                items[2]["parent_id"] = "documents"
            with self.subTest(file_parent=file_parent), self.assertRaises(InvalidScenario):
                parse_scenario(definition)

    def test_parser_does_not_keep_references_to_input(self):
        scenario = parse_scenario(self.definition)
        self.definition["scenario"]["initial_state"]["items"].clear()
        self.definition["scenario"]["criteria"][0]["params"].clear()
        self.assertEqual(len(scenario.initial_state["items"]), 4)
        self.assertIn("path", scenario.criteria[0].params)


class EventValidationTests(SimpleTestCase):
    def setUp(self):
        self.scenario = parse_scenario(json.loads((SCENARIOS / "files_001_v2.json").read_text()))

    def test_malformed_events_never_mutate_state(self):
        good = {
            "id": "event-1", "type": "file.created",
            "payload": {"item_id": "report", "parent_id": "documents", "name": "rapport.txt"},
        }
        cases = [None, [], {**good, "id": []}, {**good, "type": {}}, {**good, "payload": []}]
        for field in ("item_id", "parent_id", "name"):
            for value in (None, [], {}, 42, True, "", " " * 2, "x" * 256):
                cases.append({**good, "payload": {**good["payload"], field: value}})
        cases.append({**good, "payload": {**good["payload"], "unexpected": "data"}})
        for candidate in cases:
            engine = SimulationEngine.start(self.scenario)
            before = engine.checkpoint()
            with self.subTest(candidate=candidate), self.assertRaises(InvalidAction):
                engine.apply(candidate)
            self.assertEqual(engine.checkpoint(), before)

    def test_name_points_are_independent_of_location_and_versioned(self):
        for version, expected_score in ((1, 30), (2, 55)):
            definition = json.loads((SCENARIOS / f"files_001_v{version}.json").read_text())
            scenario = parse_scenario(definition)
            engine = SimulationEngine.start(scenario)
            for item_id, name, action in (
                ("formation", "Formation", "folder.created"),
                ("report", "RAPPORT.TXT", "file.created"),
            ):
                engine.apply({"id": item_id, "type": action, "payload": {
                    "item_id": item_id, "parent_id": "documents", "name": name,
                }})
            result = evaluate(scenario, engine.state, engine.observed_actions)
            with self.subTest(version=version):
                self.assertEqual(result.score, expected_score)
                self.assertFalse(result.passed)
                criteria = {criterion.code: criterion for criterion in result.criteria}
                self.assertEqual(criteria["report_exists"].passed, version == 2)
                self.assertFalse(criteria["report_location"].passed)

    def test_folder_named_report_does_not_earn_file_points(self):
        engine = SimulationEngine.start(self.scenario)
        engine.apply({"id": "folder", "type": "folder.created", "payload": {
            "item_id": "report", "parent_id": "documents", "name": "rapport.txt",
        }})
        result = evaluate(self.scenario, engine.state)
        self.assertFalse(next(c for c in result.criteria if c.code == "report_exists").passed)
