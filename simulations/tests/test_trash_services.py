import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from simulations.domain import InvalidAction
from simulations.models import (
    Attempt,
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


class TrashServiceIntegrationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        definition = json.loads(
            SCENARIO_PATH.read_text(encoding="utf-8")
        )

        data = definition["scenario"]

        # Scénario temporaire destiné uniquement aux tests.
        # Aucune version publiée existante n'est modifiée.
        definition["scenario"]["allowed_actions"].extend([
            "item.trashed",
            "item.restored",
            "trash.emptied",
        ])

        scenario = Scenario.objects.create(
            code=data["code"],
            title=data["title"],
            runtime=data["runtime"],
        )

        cls.version = ScenarioVersion.objects.create(
            scenario=scenario,
            version=data["version"],
            schema_version=definition["schema_version"],
            definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    def setUp(self):
        self.attempt, _ = start_attempt(self.version)

        self.action(
            "setup-folder",
            "folder.created",
            item_id="formation",
            parent_id="documents",
            name="Formation",
        )

        self.action(
            "setup-file",
            "file.created",
            item_id="rapport",
            parent_id="formation",
            name="rapport.txt",
        )

    def action(self, event_id, event_type, **payload):
        return record_event(
            self.attempt.id,
            client_event_id=event_id,
            event_type=event_type,
            payload=payload,
        )

    def latest_state(self):
        self.attempt.refresh_from_db()
        return self.attempt.checkpoints.first().state

    def test_01_trash_persisted_in_database(self):
        self.action(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        )

        state = self.latest_state()

        active_ids = {
            item["id"] for item in state["items"]
        }

        self.assertNotIn("formation", active_ids)
        self.assertNotIn("rapport", active_ids)

        self.assertIn("formation", state["trash"])
        self.assertEqual(
            len(state["trash"]["formation"]["items"]),
            2,
        )

        self.assertEqual(
            Checkpoint.objects.filter(
                attempt=self.attempt
            ).count(),
            4,
        )

    def test_02_restore_after_database_reload(self):
        self.action(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        )

        # Simuler la reprise depuis la base.
        self.attempt = Attempt.objects.get(
            pk=self.attempt.pk
        )

        self.action(
            "restore-folder",
            "item.restored",
            item_id="formation",
        )

        state = self.latest_state()

        active = {
            item["id"]: item
            for item in state["items"]
        }

        self.assertIn("formation", active)
        self.assertIn("rapport", active)

        self.assertEqual(
            active["rapport"]["parent_id"],
            "formation",
        )

        self.assertEqual(state["trash"], {})

    def test_03_failed_restore_preserves_database(self):
        self.action(
            "trash-file",
            "item.trashed",
            item_id="rapport",
        )

        self.action(
            "replacement",
            "file.created",
            item_id="replacement",
            parent_id="formation",
            name="rapport.txt",
        )

        checkpoints_before = Checkpoint.objects.filter(
            attempt=self.attempt
        ).count()

        events_before = SimulationEvent.objects.filter(
            attempt=self.attempt
        ).count()

        state_before = self.latest_state()

        with self.assertRaises(InvalidAction):
            self.action(
                "restore-conflict",
                "item.restored",
                item_id="rapport",
            )

        self.assertEqual(
            self.latest_state(),
            state_before,
        )

        self.assertEqual(
            Checkpoint.objects.filter(
                attempt=self.attempt
            ).count(),
            checkpoints_before,
        )

        self.assertEqual(
            SimulationEvent.objects.filter(
                attempt=self.attempt
            ).count(),
            events_before,
        )

    def test_04_duplicate_event_is_idempotent(self):
        first_event, first_state, first_applied = self.action(
            "trash-file",
            "item.trashed",
            item_id="rapport",
        )

        second_event, second_state, second_applied = self.action(
            "trash-file",
            "item.trashed",
            item_id="rapport",
        )

        self.assertTrue(first_applied)
        self.assertFalse(second_applied)

        self.assertEqual(
            first_event.pk,
            second_event.pk,
        )

        self.assertEqual(
            first_state,
            second_state,
        )

        self.assertEqual(
            Checkpoint.objects.filter(
                attempt=self.attempt
            ).count(),
            4,
        )
