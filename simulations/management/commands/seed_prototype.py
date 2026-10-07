import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from simulations.domain.scenario import parse_scenario
from simulations.models import Scenario, ScenarioVersion


class Command(BaseCommand):
    help = "Charge et publie les scénarios du prototype OfficeLab."

    @transaction.atomic
    def handle(self, *args, **options):
        scenario_path = (
            Path(__file__).resolve().parents[2]
            / "scenarios"
            / "files_001_v2.json"
        )
        definition = json.loads(scenario_path.read_text(encoding="utf-8"))
        parsed = parse_scenario(definition)

        scenario, _ = Scenario.objects.update_or_create(
            code=parsed.code,
            defaults={
                "title": parsed.title,
                "runtime": parsed.runtime,
                "is_active": True,
            },
        )
        version, created = ScenarioVersion.objects.get_or_create(
            scenario=scenario,
            version=parsed.version,
            defaults={
                "schema_version": parsed.schema_version,
                "definition": definition,
                "status": ScenarioVersion.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        if not created and (
            version.definition != definition
            or version.status != ScenarioVersion.Status.PUBLISHED
        ):
            raise CommandError(
                "La version existe avec une autre définition ou n'est pas publiée ; "
                "elle n'a pas été modifiée. Créez une nouvelle version si nécessaire."
            )
        self.stdout.write(
            self.style.SUCCESS(f"Scénario prêt : {scenario.code} v{version.version}")
        )
