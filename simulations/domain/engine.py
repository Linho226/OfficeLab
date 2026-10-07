from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .exceptions import InvalidAction
from .scenario import ScenarioDefinition
from .state import SimulationState
from .validation import validate_event


@dataclass
class SimulationEngine:
    scenario: ScenarioDefinition
    state: SimulationState
    processed_event_ids: set[str] = field(default_factory=set)
    observed_actions: set[str] = field(default_factory=set)

    @classmethod
    def start(cls, scenario: ScenarioDefinition) -> "SimulationEngine":
        return cls(
            scenario=scenario,
            state=SimulationState.from_initial_state(scenario.initial_state),
        )

    def apply(self, event: dict[str, Any]) -> bool:
        """Apply one event. Return False when an event was already processed."""
        validate_event(event)
        event_id = event.get("id")
        action = event.get("type")
        payload = event.get("payload", {})

        if not event_id or not action:
            raise InvalidAction("Un événement doit avoir un identifiant et un type.")
        if event_id in self.processed_event_ids:
            return False
        if action not in self.scenario.allowed_actions:
            raise InvalidAction("Cette action n'est pas autorisée par le scénario.")

        handlers = {
            "folder.created": self._create_folder,
            "file.created": self._create_file,
            "item.renamed": self._rename_item,
            "item.moved": self._move_item,
        }
        handler = handlers.get(action)
        if handler is None:
            raise InvalidAction("Cette action n'est pas encore prise en charge.")

        handler(payload)
        self.processed_event_ids.add(event_id)
        self.observed_actions.add(action)
        return True

    def checkpoint(self) -> dict[str, Any]:
        return {
            "items": deepcopy(list(self.state.items.values())),
            "processed_event_ids": sorted(self.processed_event_ids),
            "observed_actions": sorted(self.observed_actions),
        }

    def _create_folder(self, payload: dict[str, Any]) -> None:
        self._create_item(payload, kind="folder")

    def _create_file(self, payload: dict[str, Any]) -> None:
        self._create_item(payload, kind="file")

    def _create_item(self, payload: dict[str, Any], kind: str) -> None:
        item_id = payload.get("item_id")
        parent_id = payload.get("parent_id")
        name = _validated_name(payload.get("name"))
        if not item_id or item_id in self.state.items:
            raise InvalidAction("L'identifiant du nouvel élément est invalide.")
        self.state.assert_parent_folder(parent_id)
        self.state.assert_name_available(parent_id, name)
        self.state.items[item_id] = {
            "id": item_id,
            "parent_id": parent_id,
            "name": name,
            "kind": kind,
        }

    def _rename_item(self, payload: dict[str, Any]) -> None:
        item = self._editable_item(payload.get("item_id"))
        name = _validated_name(payload.get("name"))
        self.state.assert_name_available(item["parent_id"], name, item["id"])
        item["name"] = name

    def _move_item(self, payload: dict[str, Any]) -> None:
        item = self._editable_item(payload.get("item_id"))
        parent_id = payload.get("parent_id")
        self.state.assert_parent_folder(parent_id)
        if item["id"] == parent_id or self._is_descendant(parent_id, item["id"]):
            raise InvalidAction("Un dossier ne peut pas être déplacé dans lui-même.")
        self.state.assert_name_available(parent_id, item["name"], item["id"])
        item["parent_id"] = parent_id

    def _editable_item(self, item_id: str | None) -> dict[str, Any]:
        item = self.state.items.get(item_id)
        if item is None or item_id == self.state.root_id:
            raise InvalidAction("L'élément demandé n'existe pas ou est protégé.")
        return item

    def _is_descendant(self, candidate_id: str, ancestor_id: str) -> bool:
        current = self.state.items.get(candidate_id)
        while current and current.get("parent_id"):
            if current["parent_id"] == ancestor_id:
                return True
            current = self.state.items.get(current["parent_id"])
        return False


def _validated_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidAction("Le nom ne peut pas être vide.")
    name = value.strip()
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise InvalidAction("Le nom contient un caractère interdit.")
    return name
