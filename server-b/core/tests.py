from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class SettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='user', password='pass')

    def test_settings_page_has_timezone_select(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('settings'))
        self.assertContains(response, 'id="timezone-select"')

    def test_root_redirects_to_message_list(self):
        response = self.client.get('/')
        self.assertRedirects(
            response,
            reverse('messaging:my_messages_list'),
            status_code=301,
            fetch_redirect_response=False,
        )

    def test_login_redirect_url_targets_message_list(self):
        self.assertEqual(
            settings.LOGIN_REDIRECT_URL,
            reverse('messaging:my_messages_list'),
        )

