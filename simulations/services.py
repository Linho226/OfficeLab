from __future__ import annotations

from dataclasses import asdict
from typing import Any

from django.db import transaction
from django.utils import timezone

from simulations.domain import (
    InvalidAction,
    SimulationEngine,
    SimulationState,
    evaluate,
)
from simulations.domain.scenario import parse_scenario
from simulations.domain.validation import is_identifier, validate_event
from simulations.models import (
    Attempt,
    Checkpoint,
    EvaluationResult,
    ScenarioVersion,
    SimulationEvent,
)


@transaction.atomic
def start_attempt(
    scenario_version: ScenarioVersion, user=None
) -> tuple[Attempt, dict[str, Any]]:
    if scenario_version.status != ScenarioVersion.Status.PUBLISHED:
        raise InvalidAction("Seule une version publiée peut être démarrée.")

    scenario = parse_scenario(scenario_version.definition)
    engine = SimulationEngine.start(scenario)
    attempt = Attempt.objects.create(
        scenario_version=scenario_version,
        user=user,
    )
    Checkpoint.objects.create(
        attempt=attempt,
        sequence=0,
        state=engine.checkpoint(),
    )
    return attempt, engine.checkpoint()


@transaction.atomic
def record_event(
    attempt_id,
    *,
    client_event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> tuple[SimulationEvent, dict[str, Any], bool]:
    event_payload = {"id": client_event_id, "type": event_type, "payload": payload}
    validate_event(event_payload)
    attempt = (
        Attempt.objects.select_for_update()
        .select_related("scenario_version")
        .get(pk=attempt_id)
    )
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise InvalidAction("Cette tentative n'accepte plus de nouvelles actions.")

    existing = attempt.events.filter(client_event_id=client_event_id).first()
    if existing:
        if existing.event_type != event_type or existing.payload != payload:
            raise InvalidAction("Cet identifiant d'événement a déjà été utilisé pour une autre action.")
        checkpoint = attempt.checkpoints.get(sequence=existing.sequence)
        return existing, checkpoint.state, False

    engine, current_sequence = _restore_engine(attempt)
    engine.apply(event_payload)
    next_sequence = current_sequence + 1
    event = SimulationEvent.objects.create(
        attempt=attempt,
        client_event_id=client_event_id,
        sequence=next_sequence,
        event_type=event_type,
        payload=payload,
    )
    checkpoint_state = engine.checkpoint()
    Checkpoint.objects.create(
        attempt=attempt,
        sequence=next_sequence,
        state=checkpoint_state,
    )
    attempt.save(update_fields=("updated_at",))
    return event, checkpoint_state, True


@transaction.atomic
def check_attempt(attempt_id):
    """Evaluate a snapshot without closing the attempt or recording a grade."""
    attempt = Attempt.objects.select_for_update().select_related("scenario_version").get(pk=attempt_id)
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise InvalidAction("Cette tentative est déjà terminée.")
    engine, sequence = _restore_engine(attempt)
    result = evaluate(engine.scenario, engine.state, engine.observed_actions)
    return {
        "attempt_id": str(attempt.id), "score": result.score, "passed": result.passed,
        "criteria": [asdict(item) for item in result.criteria], "sequence": sequence,
    }


@transaction.atomic
def restart_attempt(attempt_id):
    attempt = Attempt.objects.select_for_update().select_related("scenario_version__scenario").get(pk=attempt_id)
    scenario = attempt.scenario_version.scenario
    version = scenario.versions.filter(status=ScenarioVersion.Status.PUBLISHED).order_by("-version").first()
    if not scenario.is_active or version is None:
        raise InvalidAction("Cette mission n'est plus disponible pour une nouvelle tentative.")
    if attempt.status == Attempt.Status.ABANDONED:
        raise InvalidAction("Cette tentative a déjà été recommencée. Retrouvez-la dans vos exercices.")
    new_attempt, checkpoint = start_attempt(version, user=attempt.user)
    if attempt.status == Attempt.Status.IN_PROGRESS:
        attempt.status = Attempt.Status.ABANDONED
        attempt.save(update_fields=["status", "updated_at"])
    return new_attempt, checkpoint


@transaction.atomic
def submit_attempt(attempt_id) -> EvaluationResult:
    attempt = (
        Attempt.objects.select_for_update()
        .select_related("scenario_version")
        .get(pk=attempt_id)
    )
    if hasattr(attempt, "evaluation"):
        return attempt.evaluation
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise InvalidAction("Cette tentative ne peut pas être soumise.")

    engine, _ = _restore_engine(attempt)
    result = evaluate(
        engine.scenario,
        engine.state,
        engine.observed_actions,
    )
    criteria = [asdict(item) for item in result.criteria]
    evaluation = EvaluationResult.objects.create(
        attempt=attempt,
        score=result.score,
        passed=result.passed,
        criteria=criteria,
    )
    attempt.score = result.score
    attempt.status = (
        Attempt.Status.PASSED if result.passed else Attempt.Status.FAILED
    )
    attempt.submitted_at = timezone.now()
    attempt.save(
        update_fields=("score", "status", "submitted_at", "updated_at")
    )
    return evaluation


@transaction.atomic
def request_hint(attempt_id, *, client_event_id):
    if not is_identifier(client_event_id):
        raise InvalidAction("L'identifiant de la demande d'indice est invalide.")
    attempt = Attempt.objects.select_for_update().select_related("scenario_version").get(pk=attempt_id)
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise InvalidAction("Cette tentative n'accepte plus de demandes d'indice.")
    existing = attempt.events.filter(client_event_id=client_event_id).first()
    if existing:
        if existing.event_type != "hint.requested":
            raise InvalidAction("Cet identifiant est déjà utilisé pour une autre action.")
        return existing
    engine, sequence = _restore_engine(attempt)
    level = attempt.events.filter(event_type="hint.requested").count() + 1
    if level > len(engine.scenario.hints):
        raise InvalidAction("Tous les indices disponibles ont déjà été consultés.")
    event = SimulationEvent.objects.create(
        attempt=attempt, client_event_id=client_event_id, sequence=sequence + 1,
        event_type="hint.requested", payload={"level": level},
    )
    engine.processed_event_ids.add(client_event_id)
    Checkpoint.objects.create(attempt=attempt, sequence=sequence + 1, state=engine.checkpoint())
    attempt.save(update_fields=["updated_at"])
    return event


def _restore_engine(attempt: Attempt) -> tuple[SimulationEngine, int]:
    scenario = parse_scenario(attempt.scenario_version.definition)
    latest = attempt.checkpoints.order_by("-sequence").first()
    if latest is None:
        raise InvalidAction("Aucun checkpoint valide n'est disponible.")

    checkpoint = latest.state
    engine = SimulationEngine(
        scenario=scenario,
        state=SimulationState.from_initial_state(
            {
                "root_id": scenario.initial_state["root_id"],
                "items": checkpoint["items"],
                "trash": checkpoint.get("trash", {}),
            }
        ),
        processed_event_ids=set(checkpoint.get("processed_event_ids", [])),
        observed_actions=set(checkpoint.get("observed_actions", [])),
        undo_stack=checkpoint.get("undo_stack", []),
        redo_stack=checkpoint.get("redo_stack", []),
    )
    return engine, latest.sequence
