from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from simulations.models import Attempt, EvaluationResult


class ExplorerTrainingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_prototype', stdout=StringIO())
        cls.user = get_user_model().objects.create_user(username='learner')
        cls.other = get_user_model().objects.create_user(username='other')

    def setUp(self):
        self.client.force_authenticate(self.user)

    def begin(self, code):
        response = self.client.post(f'/api/v1/scenarios/{code}/attempts/', {}, format='json')
        self.assertEqual(response.status_code, 201)
        return response.data['id']

    def action(self, attempt_id, event_id, event_type, payload):
        return self.client.post(f'/api/v1/attempts/{attempt_id}/events/', {
            'client_event_id': event_id, 'event_type': event_type, 'payload': payload,
        }, format='json')

    def check(self, attempt_id):
        response = self.client.post(f'/api/v1/attempts/{attempt_id}/check/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_check_can_fail_then_pass_without_closing_or_recording_grade(self):
        attempt_id = self.begin('FILES-101')
        attempt = Attempt.objects.get(pk=attempt_id)
        original_updated_at = attempt.updated_at
        self.assertFalse(self.check(attempt_id)['passed'])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.IN_PROGRESS)
        self.assertEqual(attempt.updated_at, original_updated_at)
        self.assertIsNone(attempt.score)
        self.assertEqual(attempt.checkpoints.count(), 1)
        self.assertFalse(EvaluationResult.objects.exists())
        for item_id, parent, name in (
            ('formation', 'documents', 'Formation'),
            ('cours', 'formation', 'Cours'),
            ('exercices', 'formation', 'Exercices'),
        ):
            response = self.action(attempt_id, item_id, 'folder.created', {
                'item_id': item_id, 'parent_id': parent, 'name': name,
            })
            self.assertEqual(response.status_code, 201)
        self.assertEqual(self.check(attempt_id)['score'], 100)
        # A successful check is still practice, not a persisted award.
        catalog = self.client.get('/api/v1/scenarios/').data
        self.assertFalse(catalog[0]['passed'])
        self.assertFalse(EvaluationResult.objects.exists())
        # Modifying the result invalidates the next check, including after success.
        self.action(attempt_id, 'rename', 'item.renamed', {'item_id': 'cours', 'name': 'Erreur'})
        self.assertFalse(self.check(attempt_id)['passed'])
        self.action(attempt_id, 'fix', 'item.renamed', {'item_id': 'cours', 'name': 'Cours'})
        result = self.client.post(f'/api/v1/attempts/{attempt_id}/submit/', {}, format='json')
        self.assertTrue(result.data['passed'])
        self.client.post(f'/api/v1/attempts/{attempt_id}/submit/', {}, format='json')
        self.assertEqual(EvaluationResult.objects.count(), 1)
        catalog = self.client.get('/api/v1/scenarios/').data
        self.assertTrue(catalog[0]['passed'])
        self.assertEqual(catalog[0]['best_score'], 100)
        self.assertIsNone(catalog[0]['resume_id'])
        self.assertEqual(self.client.post(f'/api/v1/attempts/{attempt_id}/check/').status_code, 400)

    def test_rename_and_sort_missions_accept_expected_final_states(self):
        for code, actions in (
            ('FILES-102', [
                ('rename-a', 'item.renamed', {'item_id': 'document1', 'name': 'compte-rendu.txt'}),
                ('rename-b', 'item.renamed', {'item_id': 'notes', 'name': 'planning.txt'}),
            ]),
            ('FILES-103', [
                ('move-a', 'item.moved', {'item_id': 'photo', 'parent_id': 'images'}),
                ('move-b', 'item.moved', {'item_id': 'report', 'parent_id': 'documents'}),
            ]),
        ):
            with self.subTest(code=code):
                attempt_id = self.begin(code)
                self.assertFalse(self.check(attempt_id)['passed'])
                for event_id, event_type, payload in actions:
                    self.assertEqual(self.action(attempt_id, event_id, event_type, payload).status_code, 201)
                self.assertEqual(self.check(attempt_id)['score'], 100)
                self.assertTrue(self.check(attempt_id)['passed'])

    def test_catalog_and_saved_attempts_are_scoped_to_current_user(self):
        attempt_id = self.begin('FILES-103')
        catalog = self.client.get('/api/v1/scenarios/').data
        self.assertEqual([item['code'] for item in catalog], ['FILES-101', 'FILES-102', 'FILES-103'])
        self.assertEqual(catalog[2]['resume_id'], attempt_id)
        self.client.force_authenticate(self.other)
        self.assertTrue(all(item['resume_id'] is None for item in self.client.get('/api/v1/scenarios/').data))
        self.assertEqual(self.client.get('/api/v1/attempts/').data, [])
        for operation in ('check', 'restart'):
            self.assertEqual(self.client.post(f'/api/v1/attempts/{attempt_id}/{operation}/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/scenarios/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/attempts/').status_code, 403)

    def test_restart_creates_clean_attempt_preserving_history(self):
        attempt_id = self.begin('FILES-103')
        self.action(attempt_id, 'move', 'item.moved', {'item_id': 'photo', 'parent_id': 'images'})
        self.client.post(f'/api/v1/attempts/{attempt_id}/hint/', {'client_event_id': 'hint'}, format='json')
        restarted = self.client.post(f'/api/v1/attempts/{attempt_id}/restart/', {}, format='json')
        self.assertEqual(restarted.status_code, 201)
        self.assertNotEqual(restarted.data['id'], attempt_id)
        self.assertEqual(restarted.data['hints'], [])
        photo = next(item for item in restarted.data['checkpoint']['items'] if item['id'] == 'photo')
        self.assertEqual(photo['parent_id'], 'desktop')
        previous = Attempt.objects.get(pk=attempt_id)
        self.assertEqual(previous.status, Attempt.Status.ABANDONED)
        self.assertEqual(previous.events.count(), 2)
        self.assertEqual(previous.checkpoints.count(), 3)
        saved = self.client.get('/api/v1/attempts/').data
        self.assertEqual([item['id'] for item in saved], [restarted.data['id']])
        self.assertEqual(self.client.post(f'/api/v1/attempts/{attempt_id}/restart/').status_code, 400)

    def test_delete_is_safe_and_idempotent_and_respects_legacy_actions(self):
        attempt_id = self.begin('FILES-103')
        # Cannot remove root or a nonempty folder.
        for item_id in ('root', 'desktop'):
            self.assertEqual(self.action(attempt_id, item_id, 'item.deleted', {'item_id': item_id}).status_code, 400)
        self.assertEqual(self.action(attempt_id, 'delete', 'item.deleted', {'item_id': 'photo'}).status_code, 201)
        self.assertEqual(self.action(attempt_id, 'delete', 'item.deleted', {'item_id': 'photo'}).status_code, 200)
        self.assertEqual(Attempt.objects.get(pk=attempt_id).events.count(), 1)
        self.assertFalse(self.check(attempt_id)['passed'])
        legacy = self.begin('FILES-001')
        self.assertEqual(self.action(legacy, 'delete', 'item.deleted', {'item_id': 'images'}).status_code, 400)
        self.assertIn(legacy, [item['id'] for item in self.client.get('/api/v1/attempts/').data])

    def test_cycle_and_duplicate_moves_keep_checkpoint_unchanged(self):
        attempt_id = self.begin('FILES-101')
        self.action(attempt_id, 'folder', 'folder.created', {'item_id': 'folder', 'parent_id': 'documents', 'name': 'Formation'})
        before = self.client.get(f'/api/v1/attempts/{attempt_id}/').data['checkpoint']
        result = self.action(attempt_id, 'cycle', 'item.moved', {'item_id': 'documents', 'parent_id': 'folder'})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get(f'/api/v1/attempts/{attempt_id}/').data['checkpoint'], before)
