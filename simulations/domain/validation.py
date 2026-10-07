"""Shared contracts for scenario data and logical events."""

from .exceptions import InvalidAction


ACTION_FIELDS = {
    "folder.created": {"item_id", "parent_id", "name"},
    "file.created": {"item_id", "parent_id", "name"},
    "item.renamed": {"item_id", "name"},
    "item.moved": {"item_id", "parent_id"},
}


def is_text(value, maximum=255):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def is_identifier(value):
    return is_text(value, 100) and value == value.strip()


def is_name(value):
    return (
        is_text(value)
        and value == value.strip()
        and value not in {".", ".."}
        and not any(character in value for character in ("/", "\\"))
        and not any(ord(character) < 32 for character in value)
    )


def validate_event(event):
    if not isinstance(event, dict):
        raise InvalidAction("Un événement doit être un objet JSON.")
    if not is_identifier(event.get("id")):
        raise InvalidAction("L'identifiant de l'événement est invalide.")
    action = event.get("type")
    if not is_identifier(action) or action not in ACTION_FIELDS:
        raise InvalidAction("Cette action n'est pas autorisée par le moteur.")
    payload = event.get("payload")
    if not isinstance(payload, dict) or set(payload) != ACTION_FIELDS[action]:
        raise InvalidAction("Les champs de l'action sont incomplets ou inconnus.")
    for field in ACTION_FIELDS[action] - {"name"}:
        if not is_identifier(payload[field]):
            raise InvalidAction(f"Le champ {field} doit être un identifiant texte valide.")
    if "name" in payload:
        name = payload["name"]
        if not isinstance(name, str) or not is_name(name.strip()):
            raise InvalidAction("Le nom est vide, trop long ou contient un caractère interdit.")


def validate_initial_state(initial_state):
    if not isinstance(initial_state, dict):
        raise InvalidAction("L'état initial doit être un objet JSON.")
    root_id = initial_state.get("root_id")
    raw_items = initial_state.get("items")
    if not is_identifier(root_id) or not isinstance(raw_items, list):
        raise InvalidAction("État initial du gestionnaire de fichiers invalide.")
    items = {}
    siblings = set()
    for item in raw_items:
        if not isinstance(item, dict) or not {"id", "parent_id", "name", "kind"}.issubset(item):
            raise InvalidAction("Un élément de l'état initial est incomplet.")
        item_id, parent_id = item["id"], item["parent_id"]
        if not is_identifier(item_id) or item_id in items:
            raise InvalidAction("Les identifiants de l'état initial sont invalides.")
        if item["kind"] not in ("folder", "file") or not is_name(item["name"]):
            raise InvalidAction("Le nom ou le type d'un élément est invalide.")
        if parent_id is not None and not is_identifier(parent_id):
            raise InvalidAction("L'identifiant du parent est invalide.")
        sibling = (parent_id, item["name"].casefold())
        if sibling in siblings:
            raise InvalidAction("Deux éléments du même dossier portent le même nom.")
        siblings.add(sibling)
        items[item_id] = item
    root = items.get(root_id)
    if root is None or root["kind"] != "folder" or root["parent_id"] is not None:
        raise InvalidAction("Le dossier racine est invalide.")
    for item_id, item in items.items():
        if item_id == root_id:
            continue
        parent = items.get(item["parent_id"])
        if parent is None or parent["kind"] != "folder":
            raise InvalidAction("Chaque élément doit appartenir à un dossier existant.")
        visited = {item_id}
        current = item
        while current["id"] != root_id:
            parent_id = current["parent_id"]
            if parent_id in visited or parent_id not in items:
                raise InvalidAction("L'arborescence contient un cycle ou un élément isolé.")
            visited.add(parent_id)
            current = items[parent_id]
