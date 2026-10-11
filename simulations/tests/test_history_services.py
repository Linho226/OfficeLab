import json
from pathlib import Path

from django.test import TestCase

from simulations.domain import InvalidAction
from simulations.models import (
    Checkpoint,
    Scenario,
    ScenarioVersion,
    SimulationEvent,
)
from simulations.services import record_event, start_attempt


SCENARIO_PATH = (
    Path(__file__).resolve().parents[1]
    / "scenarios"
    / "files_001_v2.json"
)


class HistoryServiceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        definition = json.loads(
            SCENARIO_PATH.read_text(encoding="utf-8")
        )

        definition["scenario"]["allowed_actions"].extend([
            "history.undo",
            "history.redo",
        ])

        scenario_data = definition["scenario"]

        scenario = Scenario.objects.create(
            code=scenario_data["code"],
            title=scenario_data["title"],
            runtime=scenario_data["runtime"],
        )

        cls.version = ScenarioVersion.objects.create(
            scenario=scenario,
            version=scenario_data["version"],
            schema_version=definition["schema_version"],
            definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
        )

    def setUp(self):
        self.attempt, _ = start_attempt(self.version)

    def action(self, event_id, action_type, **payload):
        return record_event(
            self.attempt.id,
            client_event_id=event_id,
            event_type=action_type,
            payload=payload,
        )

    def latest_state(self):
        return self.attempt.checkpoints.first().state

    def test_01_undo_redo_survives_database_reload(self):
        self.action(
            "create-folder",
            "folder.created",
            item_id="formation",
            parent_id="documents",
            name="Formation",
        )

        state = self.latest_state()
        self.assertEqual(len(state["undo_stack"]), 1)

        # record_event recharge le moteur depuis le checkpoint Django.
        self.action("undo-folder", "history.undo")

        state = self.latest_state()
        ids = {item["id"] for item in state["items"]}

        self.assertNotIn("formation", ids)
        self.assertEqual(len(state["redo_stack"]), 1)

        self.action("redo-folder", "history.redo")

        state = self.latest_state()
        ids = {item["id"] for item in state["items"]}

        self.assertIn("formation", ids)
        self.assertEqual(len(state["undo_stack"]), 1)
        self.assertEqual(len(state["redo_stack"]), 0)

        self.assertEqual(
            Checkpoint.objects.filter(attempt=self.attempt).count(),
            4,
        )

    def test_02_new_action_after_undo_blocks_redo(self):
        self.action(
            "create-first",
            "folder.created",
            item_id="premier",
            parent_id="documents",
            name="Premier",
        )

        self.action("undo-first", "history.undo")

        self.action(
            "create-second",
            "folder.created",
            item_id="deuxieme",
            parent_id="documents",
            name="Deuxième",
        )

        state_before = self.latest_state()

        self.assertEqual(state_before["redo_stack"], [])

        events_before = SimulationEvent.objects.filter(
            attempt=self.attempt
        ).count()

        with self.assertRaises(InvalidAction):
            self.action("invalid-redo", "history.redo")

        self.assertEqual(self.latest_state(), state_before)

        self.assertEqual(
            SimulationEvent.objects.filter(
                attempt=self.attempt
            ).count(),
            events_before,
        )
