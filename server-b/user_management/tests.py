from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class UserToggleActiveViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.client.force_login(self.staff)

    def test_toggle_user_active(self):
        self.assertTrue(self.user.is_active)
        response = self.client.get(reverse("user_toggle", args=[self.user.pk]))
        self.assertRedirects(response, reverse("user_list"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class UserUpdateViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.client.force_login(self.staff)

    def test_edit_user_displays_form_with_user_data(self):
        response = self.client.get(reverse("user_update", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_management/user_form.html")
        form = response.context["form"]
        self.assertEqual(form.instance, self.user)
