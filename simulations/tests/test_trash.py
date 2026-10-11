from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from simulations.domain import (
    InvalidAction,
    SimulationEngine,
    load_scenario,
)
from simulations.domain.state import SimulationState


SCENARIO = (
    Path(__file__).resolve().parents[1]
    / "scenarios"
    / "files_001_v2.json"
)


def make_event(event_id, action, **payload):
    return {
        "id": event_id,
        "type": action,
        "payload": payload,
    }


class TrashTests(SimpleTestCase):

    def setUp(self):
        scenario = load_scenario(SCENARIO)

        scenario = replace(
            scenario,
            allowed_actions=scenario.allowed_actions | {
                "item.trashed",
                "item.restored",
                "trash.emptied",
            },
        )

        self.engine = SimulationEngine.start(scenario)

        self.engine.apply(make_event(
            "setup-folder",
            "folder.created",
            item_id="formation",
            parent_id="documents",
            name="Formation",
        ))

        self.engine.apply(make_event(
            "setup-file",
            "file.created",
            item_id="rapport",
            parent_id="formation",
            name="rapport.txt",
        ))

    def test_01_trash_file(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        self.assertNotIn("rapport", self.engine.state.items)
        self.assertIn("rapport", self.engine.state.trash)

    def test_02_restore_file(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        self.engine.apply(make_event(
            "restore-1",
            "item.restored",
            item_id="rapport",
        ))

        self.assertIn("rapport", self.engine.state.items)
        self.assertNotIn("rapport", self.engine.state.trash)

        self.assertEqual(
            self.engine.state.items["rapport"]["parent_id"],
            "formation",
        )

    def test_03_trash_folder_recursively(self):
        self.engine.apply(make_event(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        ))

        self.assertNotIn("formation", self.engine.state.items)
        self.assertNotIn("rapport", self.engine.state.items)

        entry = self.engine.state.trash["formation"]

        self.assertEqual(len(entry["items"]), 2)

    def test_04_restore_folder_recursively(self):
        self.engine.apply(make_event(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        ))

        self.engine.apply(make_event(
            "restore-folder",
            "item.restored",
            item_id="formation",
        ))

        self.assertIn("formation", self.engine.state.items)
        self.assertIn("rapport", self.engine.state.items)

        self.assertEqual(
            self.engine.state.items["rapport"]["parent_id"],
            "formation",
        )

    def test_05_empty_trash(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        self.engine.apply(make_event(
            "empty-1",
            "trash.emptied",
        ))

        self.assertEqual(self.engine.state.trash, {})

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "restore-1",
                "item.restored",
                item_id="rapport",
            ))

    def test_06_restore_conflicting_name(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        self.engine.apply(make_event(
            "create-1",
            "file.created",
            item_id="nouveau",
            parent_id="formation",
            name="rapport.txt",
        ))

        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "restore-1",
                "item.restored",
                item_id="rapport",
            ))

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )

    def test_07_restore_missing_parent(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        self.engine.apply(make_event(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        ))

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "restore-1",
                "item.restored",
                item_id="rapport",
            ))

    def test_08_checkpoint_preserves_trash(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        checkpoint = self.engine.checkpoint()

        restored = SimulationState.from_initial_state({
            "root_id": self.engine.state.root_id,
            "items": checkpoint["items"],
            "trash": checkpoint["trash"],
        })

        self.assertEqual(
            restored.trash,
            self.engine.state.trash,
        )

        self.assertEqual(
            restored.items,
            self.engine.state.items,
        )

    def test_09_duplicate_event_is_idempotent(self):
        event = make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        )

        self.assertTrue(self.engine.apply(event))
        self.assertFalse(self.engine.apply(event))

        self.assertEqual(
            len(self.engine.state.trash),
            1,
        )

    def test_10_old_scenario_blocks_trash(self):
        old_scenario = load_scenario(SCENARIO)
        old_engine = SimulationEngine.start(old_scenario)

        with self.assertRaises(InvalidAction):
            old_engine.apply(make_event(
                "old-trash",
                "item.trashed",
                item_id="documents",
            ))

    def test_11_reject_identifier_reuse_in_trash(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "create-duplicate",
                "file.created",
                item_id="rapport",
                parent_id="images",
                name="nouveau.txt",
            ))

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )

    def test_12_reject_copy_identifier_reuse(self):
        self.engine.apply(make_event(
            "trash-1",
            "item.trashed",
            item_id="rapport",
        ))

        scenario = replace(
            self.engine.scenario,
            allowed_actions=self.engine.scenario.allowed_actions
            | {"item.copied"},
        )

        self.engine.scenario = scenario

        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "copy-duplicate",
                "item.copied",
                item_id="formation",
                parent_id="images",
                new_item_id="rapport",
            ))

        self.assertEqual(
            self.engine.checkpoint(),
            before,
        )


    def test_13_nested_identifier_protected(self):
        """Un fichier contenu dans un dossier supprimé garde son ID réservé."""

        self.engine.apply(make_event(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        ))

        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.engine.apply(make_event(
                "duplicate-child",
                "file.created",
                item_id="rapport",
                parent_id="images",
                name="nouveau.txt",
            ))

        self.assertEqual(self.engine.checkpoint(), before)

    def test_14_restore_after_checkpoint(self):
        """Une nouvelle instance peut restaurer la corbeille sauvegardée."""

        self.engine.apply(make_event(
            "trash-folder",
            "item.trashed",
            item_id="formation",
        ))

        checkpoint = self.engine.checkpoint()

        restored_state = SimulationState.from_initial_state({
            "root_id": self.engine.state.root_id,
            "items": checkpoint["items"],
            "trash": checkpoint["trash"],
        })

        new_engine = SimulationEngine(
            scenario=self.engine.scenario,
            state=restored_state,
            processed_event_ids=set(
                checkpoint["processed_event_ids"]
            ),
            observed_actions=set(
                checkpoint["observed_actions"]
            ),
        )

        new_engine.apply(make_event(
            "restore-after-restart",
            "item.restored",
            item_id="formation",
        ))

        self.assertIn("formation", new_engine.state.items)
        self.assertIn("rapport", new_engine.state.items)
        self.assertEqual(new_engine.state.trash, {})

        self.assertEqual(
            new_engine.state.items["rapport"]["parent_id"],
            "formation",
        )
