from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import InvalidAction, InvalidScenario
from .validation import ACTION_FIELDS, is_identifier, is_name, is_text, validate_initial_state


SUPPORTED_SCHEMA_VERSION = "1.0"
SUPPORTED_RUNTIMES = {"file_manager"}


@dataclass(frozen=True)
class CriterionDefinition:
    code: str
    operator: str
    points: int
    params: dict[str, Any]
    feedback: str


@dataclass(frozen=True)
class ScenarioDefinition:
    schema_version: str
    code: str
    version: int
    title: str
    runtime: str
    locale: str
    instructions: tuple[str, ...]
    initial_state: dict[str, Any]
    allowed_actions: frozenset[str]
    criteria: tuple[CriterionDefinition, ...]
    hints: tuple[str, ...]
    minimum_score: int
    required_criteria: frozenset[str]


def load_scenario(path: str | Path) -> ScenarioDefinition:
    """Load and validate a versioned scenario from a JSON file."""
    with Path(path).open(encoding="utf-8") as scenario_file:
        payload = json.load(scenario_file)
    return parse_scenario(payload)


def parse_scenario(payload: dict[str, Any]) -> ScenarioDefinition:
    if not isinstance(payload, dict):
        raise InvalidScenario("Le scénario doit être un objet JSON.")
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise InvalidScenario("Version de schéma non prise en charge.")

    data = payload.get("scenario")
    if not isinstance(data, dict):
        raise InvalidScenario("La propriété scenario est obligatoire.")

    required_fields = {
        "code",
        "version",
        "title",
        "runtime",
        "locale",
        "instructions",
        "initial_state",
        "allowed_actions",
        "criteria",
        "hints",
        "completion",
    }
    missing = required_fields.difference(data)
    if missing:
        raise InvalidScenario(
            f"Champs obligatoires absents : {', '.join(sorted(missing))}."
        )

    for field in ("code", "title", "runtime", "locale"):
        if not is_text(data[field]):
            raise InvalidScenario(f"Le champ {field} doit être un texte non vide.")
    if not is_identifier(data["code"]):
        raise InvalidScenario("Le code du scénario est invalide.")
    if data["runtime"] not in SUPPORTED_RUNTIMES:
        raise InvalidScenario("Runtime de scénario non pris en charge.")
    if type(data["version"]) is not int or data["version"] < 1:
        raise InvalidScenario("La version du scénario doit être un entier positif.")

    completion = data["completion"]
    if not isinstance(completion, dict):
        raise InvalidScenario("Les conditions de réussite doivent être un objet JSON.")
    minimum_score = completion.get("minimum_score")
    if type(minimum_score) is not int or not 0 <= minimum_score <= 100:
        raise InvalidScenario("Le score minimum doit être compris entre 0 et 100.")

    for field in ("instructions", "hints", "allowed_actions"):
        _text_list(data[field], field)
    if not data["instructions"] or not data["allowed_actions"]:
        raise InvalidScenario("Les consignes et les actions ne peuvent pas être vides.")
    if not set(data["allowed_actions"]).issubset(ACTION_FIELDS):
        raise InvalidScenario("Une action du scénario n'est pas prise en charge.")
    if not isinstance(data["criteria"], list):
        raise InvalidScenario("Les critères doivent être une liste.")
    try:
        validate_initial_state(data["initial_state"])
    except InvalidAction as error:
        raise InvalidScenario(str(error)) from error

    criteria = tuple(_parse_criterion(item) for item in data["criteria"])
    for criterion in criteria:
        if (
            criterion.operator == "action_observed"
            and criterion.params["action"] not in data["allowed_actions"]
        ):
            raise InvalidScenario("Un critère observe une action non autorisée.")
    criterion_codes = {criterion.code for criterion in criteria}
    if len(criterion_codes) != len(criteria):
        raise InvalidScenario("Les codes de critères doivent être uniques.")
    if sum(criterion.points for criterion in criteria) != 100:
        raise InvalidScenario("Le total des critères doit être égal à 100 points.")

    required = completion.get("required_criteria", [])
    _text_list(required, "required_criteria")
    required_criteria = frozenset(required)
    unknown_required = required_criteria.difference(criterion_codes)
    if unknown_required:
        raise InvalidScenario("Un critère obligatoire est inconnu.")

    return ScenarioDefinition(
        schema_version=payload["schema_version"],
        code=data["code"],
        version=data["version"],
        title=data["title"],
        runtime=data["runtime"],
        locale=data["locale"],
        instructions=tuple(data["instructions"]),
        initial_state=deepcopy(data["initial_state"]),
        allowed_actions=frozenset(data["allowed_actions"]),
        criteria=criteria,
        hints=tuple(data["hints"]),
        minimum_score=minimum_score,
        required_criteria=required_criteria,
    )


def _parse_criterion(data: dict[str, Any]) -> CriterionDefinition:
    required = {"code", "operator", "points", "params", "feedback"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise InvalidScenario("Définition de critère incomplète.")
    if type(data["points"]) is not int or data["points"] < 0:
        raise InvalidScenario("Les points d'un critère doivent être positifs.")
    if not is_identifier(data["code"]) or not is_text(data["feedback"], 2000):
        raise InvalidScenario("Le code ou le feedback d'un critère est invalide.")
    operator, params = data["operator"], data["params"]
    supported = {
        "item_at_path": {"path", "kind"},
        "item_named": {"name", "kind"},
        "children_exactly": {"path", "names"},
        "action_observed": {"action"},
        "always": set(),
    }
    if not isinstance(operator, str) or operator not in supported:
        raise InvalidScenario("Opérateur de critère inconnu.")
    if not isinstance(params, dict) or set(params) != supported[operator]:
        raise InvalidScenario("Les paramètres du critère sont incomplets ou inconnus.")
    for field in ("path", "names"):
        if field in params:
            _text_list(params[field], field)
            if not all(is_name(name) for name in params[field]):
                raise InvalidScenario("Un nom dans les paramètres du critère est invalide.")
    if "kind" in params and params["kind"] not in ("file", "folder"):
        raise InvalidScenario("Le type d'élément du critère est invalide.")
    if "name" in params and not is_name(params["name"]):
        raise InvalidScenario("Le nom attendu par le critère est invalide.")
    if "action" in params and (
        not is_identifier(params["action"]) or params["action"] not in ACTION_FIELDS
    ):
        raise InvalidScenario("L'action observée par le critère est inconnue.")
    return CriterionDefinition(
        code=data["code"],
        operator=data["operator"],
        points=data["points"],
        params=deepcopy(data["params"]),
        feedback=data["feedback"],
    )


def _text_list(value, field):
    if not isinstance(value, list) or not all(is_text(item, 2000) for item in value):
        raise InvalidScenario(f"Le champ {field} doit être une liste de textes non vides.")
