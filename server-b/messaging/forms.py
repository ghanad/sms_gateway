from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from providers.models import SmsProvider

from .models import MessageStatus


User = get_user_model()


class DateTimePickerInput(forms.DateTimeInput):
    input_type = "datetime-local"


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return f"{full_name} ({obj.username})"
        return obj.username


class MessageFilterForm(forms.Form):
    user = UserChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="User",
        widget=forms.Select(
            attrs={
                "class": "input",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=list(MessageStatus.choices),
        label="Status",
        widget=forms.Select(
            attrs={
                "class": "input",
            }
        ),
    )
    provider = forms.ModelChoiceField(
        queryset=SmsProvider.objects.all(),
        required=False,
        label="Provider",
        widget=forms.Select(
            attrs={
                "class": "input",
            }
        ),
    )
    date_from = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=DateTimePickerInput(
            attrs={
                "class": "input",
                "placeholder": "From",
                "step": 60,
            }
        ),
        label="From date & time",
    )
    date_to = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=DateTimePickerInput(
            attrs={
                "class": "input",
                "placeholder": "To",
                "step": 60,
            }
        ),
        label="To date & time",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.order_by("username")
        self.fields["user"].empty_label = "All users"
        self.fields["status"].choices = [
            ("", "All statuses"),
            *MessageStatus.choices,
        ]
        self.fields["provider"].empty_label = "All providers"

    def clean_status(self):
        status = self.cleaned_data.get("status")
        return status or None

    def get_date_from_datetime(self):
        date_from = self.cleaned_data.get("date_from")
        if not date_from:
            return None
        if timezone.is_naive(date_from):
            date_from = timezone.make_aware(date_from, timezone.get_current_timezone())
        return date_from

    def get_date_to_datetime(self):
        date_to = self.cleaned_data.get("date_to")
        if not date_to:
            return None
        if timezone.is_naive(date_to):
            date_to = timezone.make_aware(date_to, timezone.get_current_timezone())
        return date_to

    def get_active_filters(self):
        if not self.is_bound:
            return {}
        if not self.is_valid():
            return {}

        active = {}
        for field_name in ["user", "status", "provider", "date_from", "date_to"]:
            value = self.cleaned_data.get(field_name)
            if value:
                active[field_name] = value
        return active
