from pathlib import Path

from django.test import SimpleTestCase

from simulations.domain import InvalidAction, SimulationEngine, evaluate, load_scenario


SCENARIO_PATH = (
    Path(__file__).resolve().parents[1] / "scenarios" / "files_001_v2.json"
)


def event(event_id, event_type, **payload):
    return {"id": event_id, "type": event_type, "payload": payload}


class FileManagerEngineTests(SimpleTestCase):
    def setUp(self):
        self.scenario = load_scenario(SCENARIO_PATH)
        self.engine = SimulationEngine.start(self.scenario)

    def test_expected_workflow_reaches_a_passing_score(self):
        self.engine.apply(
            event(
                "evt-1",
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Formation",
            )
        )
        self.engine.apply(
            event(
                "evt-2",
                "file.created",
                item_id="exercise",
                parent_id="documents",
                name="exercice.txt",
            )
        )
        self.engine.apply(
            event(
                "evt-3",
                "item.renamed",
                item_id="exercise",
                name="rapport.txt",
            )
        )
        self.engine.apply(
            event(
                "evt-4",
                "item.moved",
                item_id="exercise",
                parent_id="formation",
            )
        )

        result = evaluate(
            self.scenario, self.engine.state, self.engine.observed_actions
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.score, 100)

    def test_direct_creation_is_accepted_when_final_state_is_correct(self):
        self.engine.apply(
            event(
                "evt-1",
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Formation",
            )
        )
        self.engine.apply(
            event(
                "evt-2",
                "file.created",
                item_id="report",
                parent_id="formation",
                name="rapport.txt",
            )
        )

        result = evaluate(
            self.scenario, self.engine.state, self.engine.observed_actions
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.score, 100)
        self.assertNotIn("item.renamed", self.engine.observed_actions)

    def test_wrong_file_location_does_not_pass(self):
        self.engine.apply(
            event(
                "evt-1",
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Formation",
            )
        )
        self.engine.apply(
            event(
                "evt-2",
                "file.created",
                item_id="report",
                parent_id="documents",
                name="rapport.txt",
            )
        )

        result = evaluate(
            self.scenario, self.engine.state, self.engine.observed_actions
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.score, 55)

    def test_replayed_event_is_idempotent(self):
        new_folder = event(
            "evt-1",
            "folder.created",
            item_id="formation",
            parent_id="documents",
            name="Formation",
        )

        self.assertTrue(self.engine.apply(new_folder))
        self.assertFalse(self.engine.apply(new_folder))
        self.assertEqual(len(self.engine.state.children_of("documents")), 1)

    def test_duplicate_name_is_rejected_without_changing_state(self):
        self.engine.apply(
            event(
                "evt-1",
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Formation",
            )
        )

        with self.assertRaisesMessage(
            InvalidAction, "Un élément portant ce nom existe déjà."
        ):
            self.engine.apply(
                event(
                    "evt-2",
                    "folder.created",
                    item_id="other",
                    parent_id="documents",
                    name="formation",
                )
            )

        self.assertEqual(len(self.engine.state.children_of("documents")), 1)

    def test_checkpoint_contains_state_and_idempotency_information(self):
        self.engine.apply(
            event(
                "evt-1",
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Formation",
            )
        )

        checkpoint = self.engine.checkpoint()

        self.assertIn("evt-1", checkpoint["processed_event_ids"])
        self.assertIn("folder.created", checkpoint["observed_actions"])
        self.assertTrue(
            any(item["id"] == "formation" for item in checkpoint["items"])
        )
