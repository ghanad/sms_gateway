from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class SettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='user', password='pass')

    def test_settings_page_has_timezone_select(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('settings'))
        self.assertContains(response, 'id="timezone-select"')

    def test_dashboard_has_no_timezone_select(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'id="timezone-select"')

