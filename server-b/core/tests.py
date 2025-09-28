from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse


class ProfilePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='user', email='user@example.com', password='pass'
        )
        self.user.profile.api_key = 'test-key'
        self.user.profile.daily_quota = 25
        self.user.profile.save()

    def test_profile_page_requires_login(self):
        response = self.client.get(reverse('my_profile'))
        login_url = resolve_url(settings.LOGIN_URL)
        expected_redirect = f"{login_url}?next={reverse('my_profile')}"
        self.assertRedirects(
            response,
            expected_redirect,
            fetch_redirect_response=False,
        )

    def test_profile_page_displays_user_information(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('my_profile'))
        self.assertContains(response, 'My Profile')
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.user.email)
        self.assertContains(response, 'test-key')
        self.assertContains(response, str(self.user.profile.daily_quota))

    def test_profile_page_has_timezone_select(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('my_profile'))
        self.assertContains(response, 'id="timezone-select"')

    def test_profile_page_links_to_change_password(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('my_profile'))
        self.assertContains(response, reverse('account_change_password'))

    def test_profile_page_hides_admin_description(self):
        self.user.profile.description = 'Hidden admin notes'
        self.user.profile.save()
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('my_profile'))
        self.assertNotContains(response, 'Hidden admin notes')


class CoreRoutingTests(TestCase):
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
        self.assertContains(response, 'https://RESTAPI-IP')
        self.assertContains(response, 'POST /api/v1/sms/send')

    def test_user_guide_uses_tabbed_layout(self):
        self.client.login(username='doc_user', password='pass')
        response = self.client.get(reverse('server_a_user_guide'))
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'data-tab-target="server-a"')
        self.assertContains(response, 'data-tab-panel="server-a"')

