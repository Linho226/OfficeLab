import json
from copy import deepcopy
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase

from simulations.models import Scenario, ScenarioVersion


class ScenarioVersionTests(TestCase):
    def setUp(self):
        self.definition = json.loads((
            Path(__file__).resolve().parents[1] / "scenarios" / "files_001_v2.json"
        ).read_text())
        self.scenario = Scenario.objects.create(
            code="FILES-001", title="Fichiers", runtime="file_manager"
        )
        self.version = ScenarioVersion.objects.create(
            scenario=self.scenario, version=2, schema_version="1.0",
            definition=self.definition,
        )

    def publish(self):
        self.version.status = ScenarioVersion.Status.PUBLISHED
        self.version.save(update_fields=["status"])
        self.version.refresh_from_db()

    def test_draft_can_be_edited_and_publication_is_timestamped(self):
        self.version.definition["scenario"]["title"] = "Titre corrigé"
        self.version.save()
        self.publish()
        self.assertIsNotNone(self.version.published_at)
        self.assertEqual(self.version.definition["scenario"]["title"], "Titre corrigé")

    def test_published_and_archived_definitions_cannot_be_changed(self):
        self.publish()
        for status in (ScenarioVersion.Status.PUBLISHED, ScenarioVersion.Status.ARCHIVED):
            self.version.status = status
            self.version.save(update_fields=["status"])
            for field, value in (
                ("definition", {**deepcopy(self.definition), "changed": True}),
                ("version", 3), ("schema_version", "2.0"), ("published_at", None),
                ("status", ScenarioVersion.Status.DRAFT),
            ):
                candidate = ScenarioVersion.objects.get(pk=self.version.pk)
                setattr(candidate, field, value)
                with self.subTest(status=status, field=field), self.assertRaises(ValidationError):
                    candidate.save()
                self.version.refresh_from_db()
                self.assertEqual(self.version.definition, self.definition)
                self.assertEqual(self.version.status, status)

    def test_queryset_writes_cannot_bypass_validation(self):
        self.publish()
        with self.assertRaises(ValidationError):
            ScenarioVersion.objects.filter(pk=self.version.pk).update(status="draft")
        with self.assertRaises(ValidationError):
            ScenarioVersion.objects.bulk_update([self.version], ["definition"])
        with self.assertRaises(ValidationError):
            ScenarioVersion.objects.bulk_create([self.version])

    def test_invalid_definition_cannot_be_saved_even_as_draft(self):
        self.version.definition["scenario"]["criteria"][0]["operator"] = "unknown"
        with self.assertRaises(ValidationError):
            self.version.save()
        self.version.refresh_from_db()
        self.assertEqual(self.version.definition["scenario"]["criteria"][0]["operator"], "item_at_path")

    def test_metadata_must_match_definition(self):
        self.version.version = 3
        with self.assertRaises(ValidationError):
            self.version.save()

    def test_stale_draft_cannot_overwrite_published_definition(self):
        stale = ScenarioVersion.objects.get(pk=self.version.pk)
        self.publish()
        stale.definition["scenario"]["title"] = "Ancien brouillon"
        with self.assertRaises(ValidationError):
            stale.save()

    def test_partial_save_cannot_desynchronize_version_and_definition(self):
        self.version.version = 3
        self.version.definition["scenario"]["version"] = 3
        with self.assertRaises(ValidationError):
            self.version.save(update_fields=["version"])
        self.version.refresh_from_db()
        self.assertEqual(self.version.version, 2)
        self.assertEqual(self.version.definition["scenario"]["version"], 2)
