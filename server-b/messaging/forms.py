from datetime import datetime, time

from django import forms
from django.utils import timezone

from providers.models import SmsProvider

from .models import MessageStatus


class MessageFilterForm(forms.Form):
    username = forms.CharField(required=False, label="Username")
    status = forms.ChoiceField(
        required=False,
        choices=[("", "---------")] + list(MessageStatus.choices),
        label="Status",
    )
    provider = forms.ModelChoiceField(
        queryset=SmsProvider.objects.all(),
        required=False,
        label="Provider",
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="From date",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="To date",
    )

    def clean_status(self):
        status = self.cleaned_data.get("status")
        return status or None

    def get_date_from_datetime(self):
        date_from = self.cleaned_data.get("date_from")
        if not date_from:
            return None
        start = datetime.combine(date_from, time.min)
        if timezone.is_naive(start):
            start = timezone.make_aware(start, timezone.get_current_timezone())
        return start

    def get_date_to_datetime(self):
        date_to = self.cleaned_data.get("date_to")
        if not date_to:
            return None
        end = datetime.combine(date_to, time.max)
        if timezone.is_naive(end):
            end = timezone.make_aware(end, timezone.get_current_timezone())
        return end
