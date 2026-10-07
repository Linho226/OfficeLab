from django.conf import settings
from django.test import SimpleTestCase


class ProjectSettingsTests(SimpleTestCase):
    def test_french_is_the_default_language(self):
        self.assertEqual(settings.LANGUAGE_CODE, "fr-fr")

    def test_ouagadougou_is_the_default_timezone(self):
        self.assertEqual(settings.TIME_ZONE, "Africa/Ouagadougou")
