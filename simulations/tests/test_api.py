import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from simulations.models import Attempt, Scenario, ScenarioVersion


SCENARIO_PATH = (
    Path(__file__).resolve().parents[1] / "scenarios" / "files_001_v2.json"
)


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication"
        ],
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated"
        ],
    }
)
class SimulationApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        definition = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        scenario_data = definition["scenario"]
        cls.scenario = Scenario.objects.create(
            code=scenario_data["code"],
            title=scenario_data["title"],
            runtime=scenario_data["runtime"],
        )
        ScenarioVersion.objects.create(
            scenario=cls.scenario,
            version=scenario_data["version"],
            schema_version=definition["schema_version"],
            definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="awa", password="strong-test-password"
        )
        cls.other_user = user_model.objects.create_user(
            username="moussa", password="strong-test-password"
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_authentication_is_required(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/scenarios/FILES-001/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_session_login_and_logout(self):
        self.client.force_authenticate(user=None)

        anonymous = self.client.get("/api/v1/auth/session/")
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "awa", "password": "strong-test-password"},
            format="json",
        )
        authenticated = self.client.get("/api/v1/auth/session/")
        logout_response = self.client.post("/api/v1/auth/logout/", {}, format="json")

        self.assertFalse(anonymous.data["authenticated"])
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertTrue(authenticated.data["authenticated"])
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_published_scenario_can_be_read(self):
        response = self.client.get("/api/v1/scenarios/FILES-001/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "FILES-001")
        self.assertNotIn("criteria", response.data)

    def test_complete_attempt_workflow(self):
        start_response = self.client.post(
            "/api/v1/scenarios/FILES-001/attempts/", {}, format="json"
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt_id = start_response.data["id"]

        events = [
            (
                "evt-1",
                "folder.created",
                {
                    "item_id": "formation",
                    "parent_id": "documents",
                    "name": "Formation",
                },
            ),
            (
                "evt-2",
                "file.created",
                {
                    "item_id": "exercise",
                    "parent_id": "documents",
                    "name": "exercice.txt",
                },
            ),
            (
                "evt-3",
                "item.renamed",
                {"item_id": "exercise", "name": "rapport.txt"},
            ),
            (
                "evt-4",
                "item.moved",
                {"item_id": "exercise", "parent_id": "formation"},
            ),
        ]
        for event_id, event_type, payload in events:
            response = self.client.post(
                f"/api/v1/attempts/{attempt_id}/events/",
                {
                    "client_event_id": event_id,
                    "event_type": event_type,
                    "payload": payload,
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        detail_response = self.client.get(f"/api/v1/attempts/{attempt_id}/")
        submit_response = self.client.post(
            f"/api/v1/attempts/{attempt_id}/submit/", {}, format="json"
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertTrue(submit_response.data["passed"])
        self.assertEqual(submit_response.data["score"], 100)

    def test_replayed_event_returns_existing_result(self):
        start_response = self.client.post(
            "/api/v1/scenarios/FILES-001/attempts/", {}, format="json"
        )
        attempt_id = start_response.data["id"]
        body = {
            "client_event_id": "evt-1",
            "event_type": "folder.created",
            "payload": {
                "item_id": "formation",
                "parent_id": "documents",
                "name": "Formation",
            },
        }

        first = self.client.post(
            f"/api/v1/attempts/{attempt_id}/events/", body, format="json"
        )
        second = self.client.post(
            f"/api/v1/attempts/{attempt_id}/events/", body, format="json"
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertFalse(second.data["applied"])

    def test_user_cannot_read_another_users_attempt(self):
        attempt_response = self.client.post(
            "/api/v1/scenarios/FILES-001/attempts/", {}, format="json"
        )
        self.client.force_authenticate(self.other_user)

        response = self.client.get(
            f"/api/v1/attempts/{attempt_response.data['id']}/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_action_returns_a_client_error(self):
        start_response = self.client.post(
            "/api/v1/scenarios/FILES-001/attempts/", {}, format="json"
        )

        response = self.client.post(
            f"/api/v1/attempts/{start_response.data['id']}/events/",
            {
                "client_event_id": "evt-invalid",
                "event_type": "computer.exploded",
                "payload": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cette action n'est pas autorisée", str(response.data))

    def test_malformed_payloads_return_400_without_persisting_changes(self):
        response = self.client.post("/api/v1/scenarios/FILES-001/attempts/", {}, format="json")
        attempt = Attempt.objects.get(pk=response.data["id"])
        original = attempt.checkpoints.get().state
        for action, payload in (
            ("file.created", {"item_id": ["bad"], "parent_id": "documents", "name": "x.txt"}),
            ("folder.created", {"item_id": "new", "parent_id": {}, "name": "Test"}),
            ("item.renamed", {"item_id": [], "name": "Test"}),
            ("item.moved", {"item_id": "documents", "parent_id": []}),
            ("file.created", {"item_id": "new", "parent_id": "documents"}),
        ):
            with self.subTest(action=action, payload=payload):
                response = self.client.post(f"/api/v1/attempts/{attempt.id}/events/", {
                    "client_event_id": "bad-event", "event_type": action, "payload": payload,
                }, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(attempt.events.count(), 0)
                self.assertEqual(attempt.checkpoints.count(), 1)
                self.assertEqual(attempt.checkpoints.get().state, original)

    def test_reusing_event_id_with_different_payload_is_rejected(self):
        response = self.client.post("/api/v1/scenarios/FILES-001/attempts/", {}, format="json")
        attempt_id = response.data["id"]
        body = {"client_event_id": "same", "event_type": "folder.created", "payload": {
            "item_id": "formation", "parent_id": "documents", "name": "Formation",
        }}
        path = f"/api/v1/attempts/{attempt_id}/events/"
        self.assertEqual(self.client.post(path, body, format="json").status_code, 201)
        body["payload"]["name"] = "Autre"
        self.assertEqual(self.client.post(path, body, format="json").status_code, 400)
        self.assertEqual(Attempt.objects.get(pk=attempt_id).events.count(), 1)

    def begin(self):
        response = self.client.post('/api/v1/scenarios/FILES-001/attempts/', {}, format='json')
        self.assertEqual(response.status_code, 201)
        return response.data['id']

    def hint(self, attempt_id, event_id):
        return self.client.post(f'/api/v1/attempts/{attempt_id}/hint/', {
            'client_event_id': event_id,
        }, format='json')

    def test_resume_list_contains_only_owned_in_progress_attempts(self):
        own = self.begin()
        completed = self.begin()
        self.client.post(f'/api/v1/attempts/{completed}/submit/', {}, format='json')
        self.client.force_authenticate(self.other_user)
        other = self.begin()
        self.assertEqual(self.hint(own, 'forbidden').status_code, 403)
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/scenarios/FILES-001/attempts/')
        self.assertEqual([item['id'] for item in response.data], [own])
        self.assertEqual(self.client.get(f'/api/v1/attempts/{other}/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/scenarios/FILES-001/attempts/').status_code, 403)
        self.assertEqual(self.hint(own, 'anonymous').status_code, 403)

    def test_hints_are_progressive_persistent_and_idempotent(self):
        attempt_id = self.begin()
        original = self.client.get(f'/api/v1/attempts/{attempt_id}/').data
        self.assertEqual(original['hints'], [])
        first = self.hint(attempt_id, 'hint-1')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.data['hints']), 1)
        self.assertEqual(first.data['hints'][0]['level'], 1)
        self.assertEqual(self.hint(attempt_id, 'hint-1').data, first.data)
        second = self.hint(attempt_id, 'hint-2')
        self.assertEqual(len(second.data['hints']), 2)
        # Replaying the first request must not reveal an additional hint.
        self.assertEqual(self.hint(attempt_id, 'hint-1').data, second.data)
        self.client.force_authenticate(self.other_user)
        self.client.force_authenticate(self.user)
        restored = self.client.get(f'/api/v1/attempts/{attempt_id}/').data
        self.assertEqual(restored['hints'], second.data['hints'])
        self.assertEqual(restored['checkpoint']['items'], original['checkpoint']['items'])
        attempt = Attempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.events.count(), 2)
        self.assertEqual(attempt.checkpoints.count(), 3)

    def test_hint_limits_and_submission_lock(self):
        attempt_id = self.begin()
        for level in range(1, 4):
            self.assertEqual(self.hint(attempt_id, f'hint-{level}').status_code, 200)
        self.assertEqual(self.hint(attempt_id, 'exhausted').status_code, 400)
        self.assertEqual(Attempt.objects.get(pk=attempt_id).events.count(), 3)
        self.client.post(f'/api/v1/attempts/{attempt_id}/submit/', {}, format='json')
        self.assertEqual(self.hint(attempt_id, 'after-submit').status_code, 400)
        saved = self.client.get(f'/api/v1/attempts/{attempt_id}/').data
        self.assertEqual(len(saved['hints']), 3)

    def test_hints_do_not_change_score_or_break_following_actions(self):
        attempt_id = self.begin()
        self.hint(attempt_id, 'help')
        for item_id, kind, parent, name in (
            ('formation', 'folder.created', 'documents', 'Formation'),
            ('report', 'file.created', 'formation', 'rapport.txt'),
        ):
            response = self.client.post(f'/api/v1/attempts/{attempt_id}/events/', {
                'client_event_id': item_id, 'event_type': kind,
                'payload': {'item_id': item_id, 'parent_id': parent, 'name': name},
            }, format='json')
            self.assertEqual(response.status_code, 201)
        result = self.client.post(f'/api/v1/attempts/{attempt_id}/submit/', {}, format='json')
        self.assertEqual(result.data['score'], 100)
        self.assertTrue(result.data['passed'])
        restored = self.client.get(f'/api/v1/attempts/{attempt_id}/').data
        self.assertEqual(restored['evaluation'], result.data)
        self.assertEqual(list(Attempt.objects.get(pk=attempt_id).events.values_list('sequence', flat=True)), [1, 2, 3])

    def test_hint_ids_cannot_collide_with_file_events(self):
        attempt_id = self.begin()
        self.hint(attempt_id, 'shared')
        body = {'client_event_id': 'shared', 'event_type': 'folder.created', 'payload': {
            'item_id': 'folder', 'parent_id': 'documents', 'name': 'Test',
        }}
        path = f'/api/v1/attempts/{attempt_id}/events/'
        self.assertEqual(self.client.post(path, body, format='json').status_code, 400)
        body['client_event_id'] = 'file-event'
        self.assertEqual(self.client.post(path, body, format='json').status_code, 201)
        self.assertEqual(self.hint(attempt_id, 'file-event').status_code, 400)

    def test_resume_uses_original_version_even_after_new_publication(self):
        attempt_id = self.begin()
        previous = ScenarioVersion.objects.get(version=2)
        definition = json.loads(json.dumps(previous.definition))
        definition['scenario']['version'] = 3
        definition['scenario']['instructions'] = ['Nouvelle consigne']
        definition['scenario']['hints'] = ['Nouvel indice']
        ScenarioVersion.objects.create(
            scenario=self.scenario, version=3, schema_version='1.0', definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
        )
        previous.status = ScenarioVersion.Status.ARCHIVED
        previous.save(update_fields=['status'])
        restored = self.client.get(f'/api/v1/attempts/{attempt_id}/').data
        self.assertEqual(restored['scenario']['version'], 2)
        self.assertEqual(restored['scenario']['instructions'], previous.definition['scenario']['instructions'])
        self.assertEqual(self.hint(attempt_id, 'old-hint').data['hints'][0]['text'], previous.definition['scenario']['hints'][0])
        self.assertEqual(self.client.get('/api/v1/scenarios/FILES-001/').data['version'], 3)

    def test_invalid_hint_request_creates_no_event(self):
        attempt_id = self.begin()
        for value in ('', [], {}, 'x' * 101):
            self.assertEqual(self.hint(attempt_id, value).status_code, 400)
        attempt = Attempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.events.count(), 0)
        self.assertEqual(attempt.checkpoints.count(), 1)

    def test_scenario_without_hints_rejects_request_without_side_effects(self):
        previous = ScenarioVersion.objects.get(version=2)
        definition = json.loads(json.dumps(previous.definition))
        definition['scenario']['version'] = 3
        definition['scenario']['hints'] = []
        ScenarioVersion.objects.create(
            scenario=self.scenario, version=3, schema_version='1.0', definition=definition,
            status=ScenarioVersion.Status.PUBLISHED,
        )
        attempt_id = self.begin()
        self.assertEqual(self.hint(attempt_id, 'none').status_code, 400)
        attempt = Attempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.events.count(), 0)
        self.assertEqual(attempt.checkpoints.count(), 1)
