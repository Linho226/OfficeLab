from __future__ import annotations

from dataclasses import dataclass

from .exceptions import InvalidScenario
from .scenario import CriterionDefinition, ScenarioDefinition
from .state import SimulationState


@dataclass(frozen=True)
class CriterionResult:
    code: str
    passed: bool
    points_awarded: int
    points_available: int
    feedback: str | None


@dataclass(frozen=True)
class EvaluationResult:
    score: int
    passed: bool
    criteria: tuple[CriterionResult, ...]


def evaluate(
    scenario: ScenarioDefinition,
    state: SimulationState,
    observed_actions: set[str] | None = None,
) -> EvaluationResult:
    observed_actions = observed_actions or set()
    results = tuple(
        _evaluate_criterion(criterion, state, observed_actions)
        for criterion in scenario.criteria
    )
    score = sum(result.points_awarded for result in results)
    passed_codes = {result.code for result in results if result.passed}
    passed = (
        score >= scenario.minimum_score
        and scenario.required_criteria.issubset(passed_codes)
    )
    return EvaluationResult(score=score, passed=passed, criteria=results)


def _evaluate_criterion(
    criterion: CriterionDefinition,
    state: SimulationState,
    observed_actions: set[str],
) -> CriterionResult:
    operators = {
        "item_at_path": lambda: _item_at_path(state, criterion.params),
        "item_named": lambda: any(
            item["kind"] == criterion.params["kind"]
            and item["name"].casefold() == criterion.params["name"].casefold()
            for item in state.items.values()
        ),
        "action_observed": lambda: criterion.params["action"] in observed_actions,
        "children_exactly": lambda: _children_exactly(state, criterion.params),
        "always": lambda: True,
    }
    operation = operators.get(criterion.operator)
    if operation is None:
        raise InvalidScenario(f"Opérateur inconnu : {criterion.operator}.")

    passed = operation()
    return CriterionResult(
        code=criterion.code,
        passed=passed,
        points_awarded=criterion.points if passed else 0,
        points_available=criterion.points,
        feedback=None if passed else criterion.feedback,
    )


def _item_at_path(state: SimulationState, params: dict) -> bool:
    item = state.resolve_path(params["path"])
    return item is not None and item["kind"] == params["kind"]


def _children_exactly(state: SimulationState, params: dict) -> bool:
    parent = state.resolve_path(params["path"])
    if parent is None:
        return False
    actual = {item["name"].casefold() for item in state.children_of(parent["id"])}
    expected = {name.casefold() for name in params["names"]}
    return actual == expected
