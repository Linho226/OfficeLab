from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from simulations.domain import (
    InvalidAction,
    SimulationEngine,
    load_scenario,
)
from simulations.domain.state import SimulationState


SCENARIO_PATH = (
    Path(__file__).resolve().parents[1]
    / "scenarios"
    / "files_001_v2.json"
)


class HistoryTests(SimpleTestCase):

    def setUp(self):
        scenario = load_scenario(SCENARIO_PATH)

        scenario = replace(
            scenario,
            allowed_actions=scenario.allowed_actions | {
                "folder.created",
                "file.created",
                "item.renamed",
                "item.moved",
                "item.copied",
                "item.trashed",
                "item.restored",
                "trash.emptied",
                "history.undo",
                "history.redo",
            },
        )

        self.engine = SimulationEngine.start(scenario)
        self.sequence = 0

    def event(self, action, **payload):
        self.sequence += 1
        return {
            "id": f"history-event-{self.sequence}",
            "type": action,
            "payload": payload,
        }

    def apply(self, action, **payload):
        return self.engine.apply(
            self.event(action, **payload)
        )

    def create_folder(self, item_id="formation", parent_id="documents"):
        self.apply(
            "folder.created",
            item_id=item_id,
            parent_id=parent_id,
            name=item_id,
        )

    def test_01_undo_redo_creation(self):
        self.create_folder()

        self.assertIn("formation", self.engine.state.items)
        self.assertIn(
            "folder.created",
            self.engine.observed_actions,
        )

        self.apply("history.undo")

        self.assertNotIn("formation", self.engine.state.items)
        self.assertNotIn(
            "folder.created",
            self.engine.observed_actions,
        )

        self.apply("history.redo")

        self.assertIn("formation", self.engine.state.items)
        self.assertIn(
            "folder.created",
            self.engine.observed_actions,
        )

    def test_02_undo_redo_rename(self):
        self.create_folder()

        self.apply(
            "item.renamed",
            item_id="formation",
            name="Formation 2026",
        )

        self.assertEqual(
            self.engine.state.items["formation"]["name"],
            "Formation 2026",
        )

        self.apply("history.undo")

        self.assertEqual(
            self.engine.state.items["formation"]["name"],
            "formation",
        )

        self.apply("history.redo")

        self.assertEqual(
            self.engine.state.items["formation"]["name"],
            "Formation 2026",
        )

    def test_03_undo_redo_move(self):
        self.create_folder()

        self.apply(
            "item.moved",
            item_id="formation",
            parent_id="images",
        )

        self.assertEqual(
            self.engine.state.items["formation"]["parent_id"],
            "images",
        )

        self.apply("history.undo")

        self.assertEqual(
            self.engine.state.items["formation"]["parent_id"],
            "documents",
        )

        self.apply("history.redo")

        self.assertEqual(
            self.engine.state.items["formation"]["parent_id"],
            "images",
        )

    def test_04_undo_redo_recursive_copy(self):
        self.create_folder()

        self.apply(
            "file.created",
            item_id="rapport",
            parent_id="formation",
            name="rapport.txt",
        )

        before = set(self.engine.state.items)

        self.apply(
            "item.copied",
            item_id="formation",
            parent_id="images",
            new_item_id="formation-copie",
        )

        copied_ids = set(self.engine.state.items) - before

        self.assertEqual(len(copied_ids), 2)
        self.assertIn("formation-copie", copied_ids)

        self.apply("history.undo")

        self.assertEqual(
            set(self.engine.state.items),
            before,
        )

        self.apply("history.redo")

        self.assertEqual(
            set(self.engine.state.items),
            before | copied_ids,
        )

    def test_05_undo_redo_trash(self):
        self.create_folder()

        self.apply(
            "item.trashed",
            item_id="formation",
        )

        self.assertNotIn(
            "formation",
            self.engine.state.items,
        )
        self.assertIn(
            "formation",
            self.engine.state.trash,
        )

        self.apply("history.undo")

        self.assertIn(
            "formation",
            self.engine.state.items,
        )
        self.assertNotIn(
            "formation",
            self.engine.state.trash,
        )

        self.apply("history.redo")

        self.assertNotIn(
            "formation",
            self.engine.state.items,
        )
        self.assertIn(
            "formation",
            self.engine.state.trash,
        )

    def test_06_undo_redo_empty_trash(self):
        self.create_folder()

        self.apply(
            "item.trashed",
            item_id="formation",
        )

        self.apply("trash.emptied")

        self.assertEqual(
            self.engine.state.trash,
            {},
        )

        self.apply("history.undo")

        self.assertIn(
            "formation",
            self.engine.state.trash,
        )

        self.apply("history.redo")

        self.assertEqual(
            self.engine.state.trash,
            {},
        )

    def test_07_new_action_clears_redo(self):
        self.create_folder("premier")
        self.create_folder("deuxieme")

        self.apply("history.undo")

        self.assertNotIn(
            "deuxieme",
            self.engine.state.items,
        )

        self.create_folder("troisieme")

        self.assertEqual(
            self.engine.redo_stack,
            [],
        )

        with self.assertRaises(InvalidAction):
            self.apply("history.redo")

    def test_08_empty_history_rejected(self):
        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.apply("history.undo")

        with self.assertRaises(InvalidAction):
            self.apply("history.redo")

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )

    def test_09_undo_event_is_idempotent(self):
        self.create_folder()

        event = self.event("history.undo")

        self.assertTrue(
            self.engine.apply(event)
        )

        before = self.engine.checkpoint()

        self.assertFalse(
            self.engine.apply(event)
        )

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )

    def test_10_checkpoint_restores_history(self):
        self.create_folder()

        checkpoint = self.engine.checkpoint()

        restored_state = SimulationState.from_initial_state({
            "root_id": self.engine.state.root_id,
            "items": checkpoint["items"],
            "trash": checkpoint["trash"],
        })

        restored = SimulationEngine(
            scenario=self.engine.scenario,
            state=restored_state,
            processed_event_ids=set(
                checkpoint["processed_event_ids"]
            ),
            observed_actions=set(
                checkpoint["observed_actions"]
            ),
            undo_stack=checkpoint["undo_stack"],
            redo_stack=checkpoint["redo_stack"],
        )

        self.assertIn(
            "formation",
            restored.state.items,
        )

        restored.apply({
            "id": "restored-undo",
            "type": "history.undo",
            "payload": {},
        })

        self.assertNotIn(
            "formation",
            restored.state.items,
        )

        restored.apply({
            "id": "restored-redo",
            "type": "history.redo",
            "payload": {},
        })

        self.assertIn(
            "formation",
            restored.state.items,
        )

    def test_11_history_is_limited_to_20(self):
        for number in range(25):
            self.create_folder(f"dossier-{number}")

        self.assertEqual(
            len(self.engine.undo_stack),
            20,
        )

        for _ in range(20):
            self.apply("history.undo")

        self.assertEqual(
            len(self.engine.undo_stack),
            0,
        )

        with self.assertRaises(InvalidAction):
            self.apply("history.undo")

        for number in range(5):
            self.assertIn(
                f"dossier-{number}",
                self.engine.state.items,
            )

    def test_12_failed_action_preserves_history(self):
        self.create_folder()

        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.apply(
                "folder.created",
                item_id="formation",
                parent_id="documents",
                name="Autre dossier",
            )

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )

    def test_13_old_scenario_rejects_undo(self):
        old_scenario = load_scenario(SCENARIO_PATH)
        old_engine = SimulationEngine.start(old_scenario)

        with self.assertRaises(InvalidAction):
            old_engine.apply({
                "id": "old-undo",
                "type": "history.undo",
                "payload": {},
            })


    def test_14_old_scenario_does_not_record_history(self):
        """Une ancienne mission ne stocke pas d'historique inutile."""

        scenario = load_scenario(SCENARIO_PATH)
        engine = SimulationEngine.start(scenario)

        engine.apply({
            "id": "create-without-history",
            "type": "folder.created",
            "payload": {
                "item_id": "sans-historique",
                "parent_id": "documents",
                "name": "Sans historique",
            },
        })

        self.assertIn("sans-historique", engine.state.items)
        self.assertEqual(engine.undo_stack, [])
        self.assertEqual(engine.redo_stack, [])
        self.assertEqual(engine.checkpoint()["undo_stack"], [])
        self.assertIn("folder.created", engine.observed_actions)
