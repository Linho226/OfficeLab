from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .exceptions import InvalidAction
from .validation import validate_initial_state


@dataclass
class SimulationState:
    """Mutable runtime state isolated from the published scenario definition."""

    root_id: str
    items: dict[str, dict[str, Any]]
    trash: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_initial_state(cls, initial_state: dict[str, Any]) -> "SimulationState":
        validate_initial_state(initial_state)
        return cls(
            root_id=initial_state["root_id"],
            items={item["id"]: deepcopy(item) for item in initial_state["items"]},
            trash=deepcopy(initial_state.get("trash", {})),
        )

    def clone(self) -> "SimulationState":
        return SimulationState(
            root_id=self.root_id,
            items=deepcopy(self.items),
            trash=deepcopy(self.trash),
        )

    def children_of(self, parent_id: str) -> list[dict[str, Any]]:
        return [
            item for item in self.items.values() if item.get("parent_id") == parent_id
        ]

    def find_child(self, parent_id: str, name: str) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.children_of(parent_id)
                if item["name"].casefold() == name.casefold()
            ),
            None,
        )

    def resolve_path(self, path: list[str]) -> dict[str, Any] | None:
        current = self.items[self.root_id]
        for segment in path:
            current = self.find_child(current["id"], segment)
            if current is None:
                return None
        return current

    def assert_parent_folder(self, parent_id: str) -> None:
        parent = self.items.get(parent_id)
        if parent is None or parent["kind"] != "folder":
            raise InvalidAction("Le dossier parent n'existe pas.")

    def assert_name_available(
        self, parent_id: str, name: str, excluded_id: str | None = None
    ) -> None:
        existing = self.find_child(parent_id, name)
        if existing and existing["id"] != excluded_id:
            raise InvalidAction("Un élément portant ce nom existe déjà.")
