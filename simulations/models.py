import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from django.utils import timezone

from simulations.domain.exceptions import InvalidScenario
from simulations.domain.scenario import parse_scenario


class Scenario(models.Model):
    code = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    runtime = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} — {self.title}"


class ScenarioVersionQuerySet(models.QuerySet):
    """Version writes must pass through model validation, including scripts."""

    def update(self, **kwargs):
        raise ValidationError("Modifiez les versions avec save() pour appliquer leur validation.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Modifiez les versions avec save() pour appliquer leur validation.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Créez les versions avec save() pour appliquer leur validation.")


class ScenarioVersion(models.Model):
    objects = ScenarioVersionQuerySet.as_manager()

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publiée"
        ARCHIVED = "archived", "Archivée"

    scenario = models.ForeignKey(
        Scenario, related_name="versions", on_delete=models.PROTECT
    )
    version = models.PositiveIntegerField()
    schema_version = models.CharField(max_length=20)
    definition = models.JSONField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scenario_id", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("scenario", "version"),
                name="unique_scenario_version",
            )
        ]

    def clean(self):
        super().clean()
        if self.pk:
            previous = type(self).objects.using(self._state.db).filter(pk=self.pk).first()
            if previous and (
                previous.status in (self.Status.PUBLISHED, self.Status.ARCHIVED)
                or previous.published_at is not None
            ):
                immutable_fields = (
                    "scenario_id",
                    "version",
                    "schema_version",
                    "definition",
                    "published_at",
                )
                if any(
                    getattr(previous, field) != getattr(self, field)
                    for field in immutable_fields
                ):
                    raise ValidationError(
                        "Une version publiée ne peut plus être modifiée."
                    )
                if self.status == self.Status.DRAFT:
                    raise ValidationError("Une version publiée ne peut pas redevenir un brouillon.")

        try:
            parsed = parse_scenario(self.definition)
        except InvalidScenario as error:
            raise ValidationError({"definition": str(error)}) from error
        if parsed.version != self.version or parsed.schema_version != self.schema_version:
            raise ValidationError(
                "La définition doit correspondre à la version et au schéma enregistrés."
            )
        if self.scenario_id and (
            parsed.code != self.scenario.code or parsed.runtime != self.scenario.runtime
        ):
            raise ValidationError("La définition doit correspondre au code et au moteur du scénario.")
        if self.status == self.Status.DRAFT and self.published_at is not None:
            raise ValidationError("Un brouillon ne peut pas avoir de date de publication.")
        if self.status == self.Status.ARCHIVED and self.published_at is None:
            raise ValidationError("Une version doit être publiée avant d'être archivée.")

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            previous = None
            if self.pk:
                # Serialize publication and edits on databases supporting row locks.
                previous = (
                    type(self).objects.using(using)
                    .select_for_update().filter(pk=self.pk).first()
                )
            if self.status == self.Status.PUBLISHED and self.published_at is None:
                self.published_at = timezone.now()
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"published_at"}
            candidate = self
            if previous is not None and kwargs.get("update_fields") is not None:
                # Validate what will actually be stored, not unsaved attributes
                # excluded by a partial update.
                candidate = previous
                for field in kwargs["update_fields"]:
                    attribute = self._meta.get_field(field).attname
                    setattr(candidate, attribute, getattr(self, attribute))
            candidate.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scenario.code} v{self.version}"


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "En cours"
        SUBMITTED = "submitted", "Soumise"
        PASSED = "passed", "Réussie"
        FAILED = "failed", "Échouée"
        ABANDONED = "abandoned", "Abandonnée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(
        ScenarioVersion, related_name="attempts", on_delete=models.PROTECT
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="simulation_attempts",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("scenario_version", "status")),
        ]


class SimulationEvent(models.Model):
    attempt = models.ForeignKey(
        Attempt, related_name="events", on_delete=models.CASCADE
    )
    client_event_id = models.CharField(max_length=100)
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "client_event_id"),
                name="unique_attempt_client_event",
            ),
            models.UniqueConstraint(
                fields=("attempt", "sequence"),
                name="unique_attempt_event_sequence",
            ),
        ]


class Checkpoint(models.Model):
    attempt = models.ForeignKey(
        Attempt, related_name="checkpoints", on_delete=models.CASCADE
    )
    sequence = models.PositiveIntegerField()
    state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "sequence"),
                name="unique_attempt_checkpoint_sequence",
            )
        ]


class EvaluationResult(models.Model):
    attempt = models.OneToOneField(
        Attempt, related_name="evaluation", on_delete=models.CASCADE
    )
    score = models.PositiveSmallIntegerField()
    passed = models.BooleanField()
    criteria = models.JSONField(default=list)
    engine_version = models.CharField(max_length=50, default="prototype-0.1")
    evaluated_at = models.DateTimeField(auto_now_add=True)
