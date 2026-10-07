from django.contrib import admin

from simulations.models import (
    Attempt,
    Checkpoint,
    EvaluationResult,
    Scenario,
    ScenarioVersion,
    SimulationEvent,
)


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "runtime", "is_active")
    list_filter = ("runtime", "is_active")
    search_fields = ("code", "title")


@admin.register(ScenarioVersion)
class ScenarioVersionAdmin(admin.ModelAdmin):
    list_display = ("scenario", "version", "status", "published_at")
    list_filter = ("status", "schema_version")
    readonly_fields = ("created_at",)


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "scenario_version", "user", "status", "score", "started_at")
    list_filter = ("status",)
    readonly_fields = ("id", "started_at", "updated_at", "submitted_at")


admin.site.register(SimulationEvent)
admin.site.register(Checkpoint)
admin.site.register(EvaluationResult)
