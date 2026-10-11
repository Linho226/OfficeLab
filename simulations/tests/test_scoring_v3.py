"""Notations cohérentes pour FILES-001 v3, conservation historique de v2."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from simulations.models import Attempt, ScenarioVersion
from simulations.services import check_attempt, record_event, start_attempt, submit_attempt


class ScoringVersion3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_prototype", stdout=StringIO())
        cls.v2 = ScenarioVersion.objects.get(scenario__code="FILES-001", version=2)
        cls.v3 = ScenarioVersion.objects.get(scenario__code="FILES-001", version=3)

    def test_initial_score_is_zero_on_v3_but_v2_remains_intact(self):
        self.assertEqual(self.v2.definition["scenario"]["criteria"][-1]["code"], "submission")
        self.assertEqual(self.v2.definition["scenario"]["criteria"][-1]["points"], 5)
        attempt, _ = start_attempt(self.v3)
        result = check_attempt(attempt.id)
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])
        self.assertEqual(attempt.status, Attempt.Status.IN_PROGRESS)
        self.assertIsNone(attempt.score)

    def test_complete_v3_scores_100_and_submit_persists_it(self):
        attempt, _ = start_attempt(self.v3)
        actions = [
            ("v3-1", "folder.created", {"item_id": "formation", "parent_id": "documents", "name": "Formation"}),
            ("v3-2", "file.created", {"item_id": "exercise", "parent_id": "documents", "name": "exercice.txt"}),
            ("v3-3", "item.renamed", {"item_id": "exercise", "name": "rapport.txt"}),
            ("v3-4", "item.moved", {"item_id": "exercise", "parent_id": "formation"}),
        ]
        for client_event_id, event_type, payload in actions:
            record_event(attempt.id, client_event_id=client_event_id, event_type=event_type, payload=payload)
        preview = check_attempt(attempt.id)
        self.assertEqual(preview["score"], 100)
        self.assertTrue(preview["passed"])
        self.assertFalse(any(c["code"] == "submission" for c in preview["criteria"]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.IN_PROGRESS)
        self.assertIsNone(attempt.score)
        evaluation = submit_attempt(attempt.id)
        self.assertEqual(evaluation.score, 100)
        self.assertTrue(evaluation.passed)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.PASSED)
        self.assertEqual(attempt.score, 100)
