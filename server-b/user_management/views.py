import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, SetPasswordForm
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, time

from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from messaging.models import MessageStatus

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .utils import generate_server_a_config_data


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = "user_management/user_list.html"
    context_object_name = "users"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_form"] = UserCreationForm()
        context["update_form"] = UserChangeForm()
        return context


class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = "user_management/user_form.html"
    success_url = reverse_lazy("user_list")

    def form_valid(self, form):
        messages.success(self.request, "User created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error creating user. Please check the form.")
        return redirect(reverse_lazy("user_list"))


class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "user_management/user_form.html"
    success_url = reverse_lazy("user_list")

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error updating user. Please check the form.")
        return redirect(reverse_lazy("user_list"))


class UserDeleteView(StaffRequiredMixin, DeleteView):
    model = User
    template_name = "user_management/user_confirm_delete.html"
    success_url = reverse_lazy("user_list")

    def form_valid(self, form):
        messages.success(self.request, "User deleted successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error deleting user.")
        return redirect(reverse_lazy("user_list"))


@method_decorator(csrf_exempt, name="dispatch")
class ToggleUserStatusView(StaffRequiredMixin, View):
    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = not user.is_active
            user.save()
            return JsonResponse({"success": True, "is_active": user.is_active})
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User not found"}, status=404)
        except Exception as exc:  # pragma: no cover - unexpected errors
            return JsonResponse({"success": False, "error": str(exc)}, status=500)


class ConfigExportView(StaffRequiredMixin, View):
    """Allow administrators to export user and provider state for Server A."""

    filename = "config_cache.json"

    def get(self, request, *args, **kwargs):
        payload = generate_server_a_config_data()
        response = HttpResponse(
            json.dumps(payload, indent=2, sort_keys=True),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="{self.filename}"'
        return response


class UserPasswordChangeView(StaffRequiredMixin, PasswordChangeView):
    form_class = SetPasswordForm
    template_name = "user_management/password_change_form.html"
    success_url = reverse_lazy("user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user_to_change = get_object_or_404(User, pk=self.kwargs["pk"])
        kwargs["user"] = user_to_change
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "User password changed successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request, "Error changing user password. Please check the form."
        )
        return super().form_invalid(form)


@login_required
def my_profile(request):
    user = request.user
    profile = getattr(user, "profile", None)

    context = {
        "profile_api_key": getattr(profile, "api_key", ""),
        "profile_daily_quota": getattr(profile, "daily_quota", 0),
    }

    return render(request, "user_management/my_profile.html", context)


class UserStatsView(StaffRequiredMixin, TemplateView):
    template_name = "user_management/user_stats.html"

    def _parse_date(self, date_string, *, is_end=False):
        if not date_string:
            return None

        try:
            date_value = datetime.strptime(date_string, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

        base_time = time.max if is_end else time.min
        combined = datetime.combine(date_value, base_time)
        if timezone.is_naive(combined):
            combined = timezone.make_aware(combined, timezone.get_current_timezone())
        return combined

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_from = self._parse_date(self.request.GET.get("from"))
        date_to = self._parse_date(self.request.GET.get("to"), is_end=True)

        base_filter = Q()
        if date_from:
            base_filter &= Q(messages__created_at__gte=date_from)
        if date_to:
            base_filter &= Q(messages__created_at__lte=date_to)

        success_statuses = [
            MessageStatus.SENT_TO_PROVIDER,
            MessageStatus.DELIVERED,
        ]

        users = list(
            User.objects.all()
            .annotate(
                total_messages=Count("messages", filter=base_filter),
                successful_messages=Count(
                    "messages",
                    filter=base_filter & Q(messages__status__in=success_statuses),
                ),
                failed_messages=Count(
                    "messages",
                    filter=base_filter & Q(messages__status=MessageStatus.FAILED),
                ),
                total_cost=Sum("messages__cost", filter=base_filter),
                last_sent=Max("messages__created_at", filter=base_filter),
            )
            .order_by("username")
        )

        filter_values = {
            "from": self.request.GET.get("from", ""),
            "to": self.request.GET.get("to", ""),
        }

        active_filter_chips = []
        base_url = reverse("user_stats")
        query_dict = self.request.GET.copy()

        for key, label in (("from", "From"), ("to", "To")):
            value = filter_values[key]
            if not value:
                continue

            chip_query = query_dict.copy()
            chip_query.pop(key, None)
            query_string = chip_query.urlencode()
            remove_url = f"{base_url}?{query_string}" if query_string else base_url
            active_filter_chips.append(
                {
                    "label": label,
                    "value": value,
                    "remove_url": remove_url,
                }
            )

        context["user_stats"] = users
        context["filters"] = filter_values
        context["user_count"] = len(users)
        context["filter_panel_open"] = any(filter_values.values())
        context["active_filter_count"] = len(active_filter_chips)
        context["active_filters"] = bool(active_filter_chips)
        context["active_filter_chips"] = active_filter_chips
        return context
