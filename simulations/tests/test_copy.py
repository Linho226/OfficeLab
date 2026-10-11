from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from simulations.domain import (
    InvalidAction,
    SimulationEngine,
    load_scenario,
)


SCENARIO = (
    Path(__file__).resolve().parents[1]
    / "scenarios"
    / "files_001_v2.json"
)


def event(event_id, action, **payload):
    return {
        "id": event_id,
        "type": action,
        "payload": payload,
    }


class FileCopyTests(SimpleTestCase):

    def setUp(self):
        scenario = load_scenario(SCENARIO)

        scenario = replace(
            scenario,
            allowed_actions=scenario.allowed_actions | {"item.copied"},
        )

        self.engine = SimulationEngine.start(scenario)

        self.engine.apply(event(
            "setup-1",
            "folder.created",
            item_id="formation",
            parent_id="documents",
            name="Formation",
        ))

        self.engine.apply(event(
            "setup-2",
            "file.created",
            item_id="rapport",
            parent_id="formation",
            name="rapport.txt",
        ))

    def copy(self, event_id="copy-1", **changes):
        payload = {
            "item_id": "rapport",
            "parent_id": "images",
            "new_item_id": "rapport-copie",
        }
        payload.update(changes)

        return self.engine.apply(
            event(event_id, "item.copied", **payload)
        )

    def test_copy_file_preserves_original(self):
        self.assertTrue(self.copy())

        original = self.engine.state.items["rapport"]
        copied = self.engine.state.items["rapport-copie"]

        self.assertEqual(original["parent_id"], "formation")
        self.assertEqual(copied["parent_id"], "images")
        self.assertEqual(copied["name"], "rapport.txt")

    def test_copy_folder_recursively(self):
        self.copy(
            item_id="formation",
            new_item_id="formation-copie",
        )

        folder = self.engine.state.items["formation-copie"]

        self.assertEqual(folder["kind"], "folder")

        children = self.engine.state.children_of("formation-copie")

        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["name"], "rapport.txt")
        self.assertNotEqual(children[0]["id"], "rapport")

    def test_copy_same_folder_renames(self):
        self.copy(parent_id="formation")

        copied = self.engine.state.items["rapport-copie"]

        self.assertEqual(copied["name"], "rapport (copie).txt")

    def test_copy_into_itself_is_rejected(self):
        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.copy(
                item_id="formation",
                parent_id="formation",
                new_item_id="formation-copie",
            )

        self.assertEqual(self.engine.checkpoint(), before)

    def test_duplicate_identifier_is_rejected(self):
        before = self.engine.checkpoint()

        with self.assertRaises(InvalidAction):
            self.copy(new_item_id="rapport")

        self.assertEqual(self.engine.checkpoint(), before)

    def test_duplicate_event_is_idempotent(self):
        self.assertTrue(self.copy())
        self.assertFalse(self.copy())

        copies = [
            item for item in self.engine.state.items.values()
            if item["id"] == "rapport-copie"
        ]

        self.assertEqual(len(copies), 1)
