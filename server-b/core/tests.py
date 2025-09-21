from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
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


class ServerAUserGuideTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='doc_user', password='pass'
        )

    def test_user_guide_requires_login(self):
        response = self.client.get(reverse('server_a_user_guide'))
        login_url = resolve_url(settings.LOGIN_URL)
        expected_redirect = f"{login_url}?next={reverse('server_a_user_guide')}"
        self.assertRedirects(
            response,
            expected_redirect,
            fetch_redirect_response=False,
        )

    def test_user_guide_page_is_accessible_for_authenticated_user(self):
        self.client.login(username='doc_user', password='pass')
        response = self.client.get(reverse('server_a_user_guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'راهنمای کاربری API درگاه پیامک سرور A')

    def test_user_guide_includes_endpoint_details(self):
        self.client.login(username='doc_user', password='pass')
        response = self.client.get(reverse('server_a_user_guide'))
        self.assertContains(response, 'http://localhost:8001')
        self.assertContains(response, 'POST /api/v1/sms/send')

    def test_user_guide_uses_tabbed_layout(self):
        self.client.login(username='doc_user', password='pass')
        response = self.client.get(reverse('server_a_user_guide'))
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'data-tab-target="server-a"')
        self.assertContains(response, 'data-tab-panel="server-a"')

