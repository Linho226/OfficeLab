from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from simulations.api.serializers import RecordEventSerializer
from simulations.domain import InvalidAction
from simulations.models import Attempt, Scenario, ScenarioVersion
from simulations.services import record_event, request_hint, start_attempt, submit_attempt


class ScenarioDetailView(APIView):
    def get(self, request, code):
        scenario = get_object_or_404(Scenario, code=code, is_active=True)
        version = (
            scenario.versions.filter(status=ScenarioVersion.Status.PUBLISHED)
            .order_by("-version")
            .first()
        )
        if version is None:
            raise ValidationError("Aucune version publiée n'est disponible.")

        definition = version.definition["scenario"]
        return Response(
            {
                "code": scenario.code,
                "title": scenario.title,
                "runtime": scenario.runtime,
                "version": version.version,
                "schema_version": version.schema_version,
                "locale": definition["locale"],
                "instructions": definition["instructions"],
                "initial_state": definition["initial_state"],
                "allowed_actions": definition["allowed_actions"],
                "hints_count": len(definition["hints"]),
            }
        )


class AttemptListView(APIView):
    def get(self, request, code):
        attempts = Attempt.objects.filter(
            user=request.user, scenario_version__scenario__code=code,
            status=Attempt.Status.IN_PROGRESS,
        ).select_related("scenario_version").order_by("-updated_at", "-started_at")
        return Response([{
            "id": str(attempt.id), "updated_at": attempt.updated_at,
            "version": attempt.scenario_version.version,
        } for attempt in attempts])

    def post(self, request, code):
        scenario = get_object_or_404(Scenario, code=code, is_active=True)
        version = (
            scenario.versions.filter(status=ScenarioVersion.Status.PUBLISHED)
            .order_by("-version")
            .first()
        )
        if version is None:
            raise ValidationError("Aucune version publiée n'est disponible.")

        try:
            attempt, checkpoint = start_attempt(version, user=request.user)
        except InvalidAction as error:
            raise ValidationError(str(error)) from error
        return Response(
            _attempt_payload(attempt, checkpoint),
            status=status.HTTP_201_CREATED,
        )


class AttemptDetailView(APIView):
    def get(self, request, attempt_id):
        attempt = _owned_attempt(request.user, attempt_id)
        checkpoint = attempt.checkpoints.order_by("-sequence").first()
        if checkpoint is None:
            raise ValidationError("Aucun checkpoint n'est disponible.")
        return Response(_attempt_payload(attempt, checkpoint.state))


class AttemptEventView(APIView):
    def post(self, request, attempt_id):
        attempt = _owned_attempt(request.user, attempt_id)
        serializer = RecordEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            event, checkpoint, applied = record_event(
                attempt.id,
                **serializer.validated_data,
            )
        except InvalidAction as error:
            raise ValidationError(str(error)) from error
        return Response(
            {
                "event": {
                    "client_event_id": event.client_event_id,
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                },
                "applied": applied,
                "checkpoint": checkpoint,
            },
            status=status.HTTP_201_CREATED if applied else status.HTTP_200_OK,
        )


class AttemptSubmitView(APIView):
    def post(self, request, attempt_id):
        attempt = _owned_attempt(request.user, attempt_id)
        try:
            evaluation = submit_attempt(attempt.id)
        except InvalidAction as error:
            raise ValidationError(str(error)) from error
        return Response(
            {
                "attempt_id": str(attempt.id),
                "score": evaluation.score,
                "passed": evaluation.passed,
                "criteria": evaluation.criteria,
                "engine_version": evaluation.engine_version,
            }
        )


class HintRequestSerializer(serializers.Serializer):
    client_event_id = serializers.CharField(max_length=100)


class AttemptHintView(APIView):
    def post(self, request, attempt_id):
        attempt = _owned_attempt(request.user, attempt_id)
        serializer = HintRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            request_hint(attempt.id, **serializer.validated_data)
        except InvalidAction as error:
            raise ValidationError(str(error)) from error
        return Response(_hint_payload(attempt))


def _owned_attempt(user, attempt_id):
    attempt = get_object_or_404(
        Attempt.objects.select_related("scenario_version__scenario"),
        pk=attempt_id,
    )
    if attempt.user_id != user.id:
        raise PermissionDenied("Cette tentative appartient à un autre utilisateur.")
    return attempt


def _attempt_payload(attempt, checkpoint):
    definition = attempt.scenario_version.definition["scenario"]
    evaluation = getattr(attempt, "evaluation", None)
    return {
        "id": str(attempt.id),
        "scenario": {
            "code": attempt.scenario_version.scenario.code,
            "version": attempt.scenario_version.version,
            "title": definition["title"],
            "instructions": definition["instructions"],
            "initial_state": definition["initial_state"],
        },
        "status": attempt.status,
        "score": attempt.score,
        "checkpoint": checkpoint,
        "evaluation": None if evaluation is None else {
            "attempt_id": str(attempt.id), "score": evaluation.score,
            "passed": evaluation.passed, "criteria": evaluation.criteria,
            "engine_version": evaluation.engine_version,
        },
        **_hint_payload(attempt),
    }


def _hint_payload(attempt):
    hints = attempt.scenario_version.definition["scenario"]["hints"]
    levels = attempt.events.filter(event_type="hint.requested").values_list("payload", flat=True)
    return {
        "hints": [{"level": payload["level"], "text": hints[payload["level"] - 1]} for payload in levels],
        "hints_count": len(hints),
    }
