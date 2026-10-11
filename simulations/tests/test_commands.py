from io import StringIO
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from simulations.models import Scenario, ScenarioVersion
from simulations.services import start_attempt


class SeedPrototypeCommandTests(TestCase):
    def test_command_is_idempotent(self):
        output = StringIO()

        call_command("seed_prototype", stdout=output)
        call_command("seed_prototype", stdout=output)

        self.assertEqual(Scenario.objects.count(), 4)
        self.assertEqual(ScenarioVersion.objects.count(), 8)
        self.assertEqual(
            ScenarioVersion.objects.filter(scenario__code="FILES-001").order_by("-version").first().status,
            ScenarioVersion.Status.PUBLISHED,
        )
        self.assertEqual(ScenarioVersion.objects.filter(scenario__code="FILES-001").order_by("-version").first().version, 3)

    def test_seeding_v2_preserves_v1_and_existing_attempts(self):
        definition = json.loads((
            Path(__file__).resolve().parents[1] / "scenarios" / "files_001_v1.json"
        ).read_text())
        scenario = Scenario.objects.create(code="FILES-001", title="Fichiers", runtime="file_manager")
        version = ScenarioVersion.objects.create(
            scenario=scenario, version=1, schema_version="1.0", definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
        )
        attempt, _ = start_attempt(version)
        call_command("seed_prototype", stdout=StringIO())
        version.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(version.definition, definition)
        self.assertEqual(attempt.scenario_version_id, version.pk)
        self.assertEqual(ScenarioVersion.objects.count(), 9)
