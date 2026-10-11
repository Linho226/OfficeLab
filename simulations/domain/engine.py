from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, uuid5

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
    undo_stack: list[dict[str, Any]] = field(default_factory=list)
    redo_stack: list[dict[str, Any]] = field(default_factory=list)

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
            "item.deleted": self._delete_item,
            "folder.created": self._create_folder,
            "file.created": self._create_file,
            "item.renamed": self._rename_item,
            "item.moved": self._move_item,
            "item.copied": self._copy_item,
            "item.trashed": self._trash_item,
            "item.restored": self._restore_item,
            "trash.emptied": self._empty_trash,
            "history.undo": self._undo,
            "history.redo": self._redo,
        }
        handler = handlers.get(action)
        if handler is None:
            raise InvalidAction("Cette action n'est pas encore prise en charge.")

        if action in {"history.undo", "history.redo"}:
            handler(payload)
        else:
            # N'enregistrer l'historique que si l'annulation est autorisée.
            history_enabled = "history.undo" in self.scenario.allowed_actions
            before = self._history_snapshot() if history_enabled else None

            # Une action invalide ne doit pas modifier les piles.
            handler(payload)

            if before is not None:
                self.undo_stack.append(before)

                if len(self.undo_stack) > 20:
                    del self.undo_stack[:-20]

                # Une nouvelle action invalide la chaîne Rétablir.
                self.redo_stack.clear()

            self.observed_actions.add(action)

        self.processed_event_ids.add(event_id)
        return True

    def checkpoint(self) -> dict[str, Any]:
        return {
            "items": deepcopy(list(self.state.items.values())),
            "trash": deepcopy(self.state.trash),
            "undo_stack": deepcopy(self.undo_stack),
            "redo_stack": deepcopy(self.redo_stack),
            "processed_event_ids": sorted(self.processed_event_ids),
            "observed_actions": sorted(self.observed_actions),
        }


    def _history_snapshot(self) -> dict[str, Any]:
        """Photographie complète de l'état pédagogique courant."""

        return {
            "items": deepcopy(list(self.state.items.values())),
            "trash": deepcopy(self.state.trash),
            "observed_actions": sorted(self.observed_actions),
        }

    def _restore_history_snapshot(
        self, snapshot: dict[str, Any]
    ) -> None:
        """Restaurer les fichiers, la corbeille et les actions observées."""

        restored = SimulationState.from_initial_state({
            "root_id": self.state.root_id,
            "items": deepcopy(snapshot["items"]),
            "trash": deepcopy(snapshot.get("trash", {})),
        })

        self.state = restored
        self.observed_actions = set(
            snapshot.get("observed_actions", [])
        )

    def _undo(self, payload: dict[str, Any]) -> None:
        """Annuler la dernière opération réussie."""

        if not self.undo_stack:
            raise InvalidAction(
                "Aucune opération à annuler."
            )

        previous = self.undo_stack[-1]
        current = self._history_snapshot()

        # Valider l'état précédent avant de modifier les piles.
        restored = SimulationState.from_initial_state({
            "root_id": self.state.root_id,
            "items": deepcopy(previous["items"]),
            "trash": deepcopy(previous.get("trash", {})),
        })

        self.undo_stack.pop()
        self.redo_stack.append(current)

        if len(self.redo_stack) > 20:
            del self.redo_stack[:-20]

        self.state = restored
        self.observed_actions = set(
            previous.get("observed_actions", [])
        )

    def _redo(self, payload: dict[str, Any]) -> None:
        """Rétablir la dernière opération annulée."""

        if not self.redo_stack:
            raise InvalidAction(
                "Aucune opération à rétablir."
            )

        following = self.redo_stack[-1]
        current = self._history_snapshot()

        # Valider l'état suivant avant de modifier les piles.
        restored = SimulationState.from_initial_state({
            "root_id": self.state.root_id,
            "items": deepcopy(following["items"]),
            "trash": deepcopy(following.get("trash", {})),
        })

        self.redo_stack.pop()
        self.undo_stack.append(current)

        if len(self.undo_stack) > 20:
            del self.undo_stack[:-20]

        self.state = restored
        self.observed_actions = set(
            following.get("observed_actions", [])
        )

    def _create_folder(self, payload: dict[str, Any]) -> None:
        self._create_item(payload, kind="folder")

    def _create_file(self, payload: dict[str, Any]) -> None:
        self._create_item(payload, kind="file")

    def _create_item(self, payload: dict[str, Any], kind: str) -> None:
        item_id = payload.get("item_id")
        parent_id = payload.get("parent_id")
        name = _validated_name(payload.get("name"))
        if not item_id or item_id in self._reserved_item_ids():
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


    def _copy_item(self, payload: dict[str, Any]) -> None:
        source = self._editable_item(payload["item_id"])
        parent_id = payload["parent_id"]
        new_id = payload["new_item_id"]

        self.state.assert_parent_folder(parent_id)

        if new_id in self._reserved_item_ids():
            raise InvalidAction(
                "L'identifiant de la copie existe déjà."
            )

        if source["kind"] == "folder" and (
            source["id"] == parent_id
            or self._is_descendant(parent_id, source["id"])
        ):
            raise InvalidAction(
                "Impossible de copier un dossier dans lui-même."
            )

        # Construire l'arborescence avant toute modification
        subtree = [source]
        index = 0

        while index < len(subtree):
            subtree.extend(
                self.state.children_of(subtree[index]["id"])
            )
            index += 1

            if len(subtree) > 250:
                raise InvalidAction(
                    "Le dossier contient trop d'éléments."
                )

        # Résoudre les conflits de noms
        proposed = source["name"]

        if self.state.find_child(parent_id, proposed):
            stem, sep, suffix = proposed.rpartition(".")

            if not stem or not sep:
                stem, suffix = proposed, ""
            else:
                suffix = "." + suffix

            index = 1

            while True:
                number = "" if index == 1 else f" {index}"
                candidate = (
                    f"{stem} (copie{number}){suffix}"
                )

                if len(candidate) > 255:
                    raise InvalidAction(
                        "Le nom de la copie serait trop long."
                    )

                if not self.state.find_child(
                    parent_id, candidate
                ):
                    proposed = candidate
                    break

                index += 1

        # Générer les identifiants de la copie
        mapping = {source["id"]: new_id}

        for old in subtree[1:]:
            mapping[old["id"]] = str(
                uuid5(
                    NAMESPACE_URL,
                    f"officelab:{new_id}:{old['id']}"
                )
            )

        if (
            len(set(mapping.values())) != len(mapping)
            or set(mapping.values()) & self._reserved_item_ids()
        ):
            raise InvalidAction(
                "Collision d'identifiants lors de la copie."
            )

        # Construire les nouveaux éléments
        copies = {}

        for old in subtree:
            item = deepcopy(old)

            item["id"] = mapping[old["id"]]
            item["parent_id"] = (
                parent_id
                if old is source
                else mapping[old["parent_id"]]
            )

            if old is source:
                item["name"] = proposed

            copies[item["id"]] = item

        # Appliquer la copie seulement après validation
        self.state.items.update(copies)


    def _trash_item(self, payload: dict[str, Any]) -> None:
        """Déplacer un élément et son arborescence dans la corbeille."""

        item = self._editable_item(payload["item_id"])

        subtree = [item]
        index = 0

        while index < len(subtree):
            subtree.extend(
                self.state.children_of(subtree[index]["id"])
            )
            index += 1

            if len(subtree) > 1000:
                raise InvalidAction(
                    "Trop d'éléments à placer dans la corbeille."
                )

        # Préparer les données avant de modifier l'état.
        snapshot = {
            "items": deepcopy(subtree),
            "original_parent_id": item["parent_id"],
        }

        # Retirer les éléments actifs.
        for child in subtree:
            del self.state.items[child["id"]]

        # Conserver l'arborescence dans la corbeille.
        self.state.trash[item["id"]] = snapshot

    def _restore_item(self, payload: dict[str, Any]) -> None:
        """Restaurer un élément supprimé et ses descendants."""

        item_id = payload["item_id"]
        entry = self.state.trash.get(item_id)

        if entry is None:
            raise InvalidAction(
                "Cet élément n'existe pas dans la corbeille."
            )

        items = deepcopy(entry["items"])
        original_parent = entry["original_parent_id"]

        if not items or items[0]["id"] != item_id:
            raise InvalidAction(
                "Les données de restauration sont incohérentes."
            )

        self.state.assert_parent_folder(original_parent)

        # Contrôler les conflits d'identifiants.
        for item in items:
            if item["id"] in self.state.items:
                raise InvalidAction(
                    "Un identifiant existe déjà dans le dossier actif."
                )

        # Contrôler les conflits de noms.
        self.state.assert_name_available(
            original_parent,
            items[0]["name"],
        )

        # Vérifier l'intégrité de l'arborescence restaurée.
        temporary = {
            item["id"]: item
            for item in items
        }

        if len(temporary) != len(items):
            raise InvalidAction(
                "La corbeille contient des identifiants dupliqués."
            )

        for child in items[1:]:
            parent = temporary.get(child["parent_id"])

            if parent is None or parent["kind"] != "folder":
                raise InvalidAction(
                    "L'arborescence de restauration est invalide."
                )

        # Ne modifier l'état qu'après toutes les validations.
        self.state.items.update(temporary)
        del self.state.trash[item_id]

    def _empty_trash(self, payload: dict[str, Any]) -> None:
        """Supprimer définitivement tous les éléments de la corbeille."""

        self.state.trash.clear()


    def _reserved_item_ids(self) -> set[str]:
        """Identifiants réservés dans les fichiers actifs et la corbeille."""

        reserved = set(self.state.items)

        for entry in self.state.trash.values():
            reserved.update(
                item["id"] for item in entry["items"]
            )

        return reserved

    def _editable_item(self, item_id: str | None) -> dict[str, Any]:
        item = self.state.items.get(item_id)
        if item is None or item_id == self.state.root_id:
            raise InvalidAction("L'élément demandé n'existe pas ou est protégé.")
        return item

    def _delete_item(self, payload: dict[str, Any]) -> None:
        item = self._editable_item(payload["item_id"])
        # Empty folders only: an accidental removal cannot erase a whole tree.
        if self.state.children_of(item["id"]):
            raise InvalidAction("Ce dossier contient des éléments. Déplacez-les avant de le supprimer.")
        del self.state.items[item["id"]]

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
