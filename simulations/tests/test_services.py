import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from simulations.domain import InvalidAction
from simulations.models import (
    Attempt,
    Checkpoint,
    EvaluationResult,
    Scenario,
    ScenarioVersion,
    SimulationEvent,
)
from simulations.services import record_event, start_attempt, submit_attempt


SCENARIO_PATH = (
    Path(__file__).resolve().parents[1] / "scenarios" / "files_001_v2.json"
)


class AttemptServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        definition = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        scenario_data = definition["scenario"]
        cls.scenario = Scenario.objects.create(
            code=scenario_data["code"],
            title=scenario_data["title"],
            runtime=scenario_data["runtime"],
        )
        cls.version = ScenarioVersion.objects.create(
            scenario=cls.scenario,
            version=scenario_data["version"],
            schema_version=definition["schema_version"],
            definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_start_attempt_creates_initial_checkpoint(self):
        attempt, checkpoint = start_attempt(self.version)

        self.assertEqual(attempt.status, Attempt.Status.IN_PROGRESS)
        self.assertEqual(attempt.checkpoints.count(), 1)
        self.assertEqual(checkpoint["processed_event_ids"], [])

    def test_unpublished_scenario_cannot_be_started(self):
        self.version.status = ScenarioVersion.Status.DRAFT

        with self.assertRaisesMessage(
            InvalidAction, "Seule une version publiée peut être démarrée."
        ):
            start_attempt(self.version)

    def test_events_are_persisted_and_duplicate_is_idempotent(self):
        attempt, _ = start_attempt(self.version)
        arguments = {
            "client_event_id": "evt-1",
            "event_type": "folder.created",
            "payload": {
                "item_id": "formation",
                "parent_id": "documents",
                "name": "Formation",
            },
        }

        first_event, first_state, first_applied = record_event(attempt.id, **arguments)
        second_event, second_state, second_applied = record_event(
            attempt.id, **arguments
        )

        self.assertTrue(first_applied)
        self.assertFalse(second_applied)
        self.assertEqual(first_event.pk, second_event.pk)
        self.assertEqual(first_state, second_state)
        self.assertEqual(SimulationEvent.objects.count(), 1)
        self.assertEqual(Checkpoint.objects.count(), 2)

    def test_attempt_can_resume_and_pass_after_several_transactions(self):
        attempt, _ = start_attempt(self.version)
        events = [
            (
                "evt-1",
                "folder.created",
                {
                    "item_id": "formation",
                    "parent_id": "documents",
                    "name": "Formation",
                },
            ),
            (
                "evt-2",
                "file.created",
                {
                    "item_id": "exercise",
                    "parent_id": "documents",
                    "name": "exercice.txt",
                },
            ),
            (
                "evt-3",
                "item.renamed",
                {"item_id": "exercise", "name": "rapport.txt"},
            ),
            (
                "evt-4",
                "item.moved",
                {"item_id": "exercise", "parent_id": "formation"},
            ),
        ]
        for event_id, event_type, payload in events:
            record_event(
                attempt.id,
                client_event_id=event_id,
                event_type=event_type,
                payload=payload,
            )

        evaluation = submit_attempt(attempt.id)
        attempt.refresh_from_db()

        self.assertTrue(evaluation.passed)
        self.assertEqual(evaluation.score, 100)
        self.assertEqual(attempt.status, Attempt.Status.PASSED)
        self.assertEqual(attempt.events.count(), 4)
        self.assertEqual(attempt.checkpoints.count(), 5)

    def test_submission_is_idempotent_and_closes_attempt(self):
        attempt, _ = start_attempt(self.version)

        first = submit_attempt(attempt.id)
        second = submit_attempt(attempt.id)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(EvaluationResult.objects.count(), 1)
        with self.assertRaisesMessage(
            InvalidAction, "Cette tentative n'accepte plus de nouvelles actions."
        ):
            record_event(
                attempt.id,
                client_event_id="late-event",
                event_type="folder.created",
                payload={
                    "item_id": "late",
                    "parent_id": "documents",
                    "name": "Tardif",
                },
            )
