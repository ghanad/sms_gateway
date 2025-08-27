# server-b/providers/forms.py
import json
from django import forms
from django.utils.text import slugify
from .models import SmsProvider
from . import widgets

class PlaceholderJsonTextarea(widgets.Textarea):
    """
    """
    def render(self, name, value, attrs=None, renderer=None):
        if value in ('{}', '[]'):
            value = ''
        return super().render(name, value, attrs, renderer)

# ==============================================================================

class SmsProviderForm(forms.ModelForm):
    class Meta:
        model = SmsProvider
        fields = '__all__'
        help_texts = {
            'priority': 'Higher means higher priority (0-100).'
        }
        widgets = {
            'name': widgets.TextInput(attrs={'placeholder': 'e.g. Magfa 3000991'}),
            'slug': widgets.TextInput(attrs={'placeholder': 'e.g. magfa-3000991'}),
            'send_url': widgets.TextInput(attrs={'placeholder': 'https://sms.magfa.com/api/http/sms/v2/send'}),
            'balance_url': widgets.TextInput(attrs={'placeholder': 'https://sms.magfa.com/api/http/sms/v2/balance'}),
            'default_sender': widgets.TextInput(attrs={'placeholder': 'e.g. 3000991'}),
            'auth_type': widgets.Select(attrs={'data-placeholder': 'Select auth type'}),

            'auth_config': PlaceholderJsonTextarea(attrs={
                'rows': 4,
                'placeholder': (
                    'e.g.\n'
                    'BASIC: { "username": "u", "password_env": "...", "domain": "d" }\n'
                    'API_KEY_HEADER: { "key": "...", "header_name": "Authorization" }\n'
                    'API_KEY_QUERY: { "key": "...", "param_name": "api_key" }\n'
                    'OAUTH2_CLIENT: { "token_url": "...", "client_id": "...", "client_secret_env": "...", "scope": "..." }'
                )
            }),
            'headers': PlaceholderJsonTextarea(attrs={
                'rows': 4,
                'placeholder': (
                    '{\n'
                    '  "accept": "application/json",\n'
                    '  "cache-control": "no-cache",\n'
                    '  "Content-Type": "application/json"\n'
                    '}'
                )
            }),
            'query_params': PlaceholderJsonTextarea(attrs={
                'rows': 4,
                'placeholder': '{ "api_key": "xxxx" }'
            }),

            'timeout_seconds': widgets.TextInput(attrs={'type': 'number', 'placeholder': '10'}),
            'priority': widgets.TextInput(attrs={
                'type': 'number',
                'placeholder': '0–100',
                'min': 0, 'max': 100, 'step': 1,
            }),
            'is_active': widgets.CheckboxInput(attrs={'title': 'Enable/disable this provider'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'provider_type' in self.fields:
            self.fields['provider_type'].required = False


    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('name') or '')
        return slug

    def clean(self):
        cleaned_data = super().clean()
        provider_type = cleaned_data.get('provider_type')
        priority = cleaned_data.get('priority')
        default_sender = cleaned_data.get('default_sender')

        if provider_type and priority is not None:
            qs = SmsProvider.objects.filter(provider_type=provider_type, priority=priority)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('priority', 'Priority must be unique within this provider type.')

        if provider_type and default_sender:
            qs2 = SmsProvider.objects.filter(provider_type=provider_type, default_sender=default_sender)
            if self.instance.pk:
                qs2 = qs2.exclude(pk=self.instance.pk)
            if qs2.exists():
                self.add_error('default_sender', 'This sender is already configured for this provider type.')
        return cleaned_data

class SendTestSmsForm(forms.Form):
    recipient = forms.CharField(
        label="Recipient",
        max_length=20,
        widget=widgets.TextInput(attrs={'placeholder': 'e.g. +11234567890'})
    )
    message = forms.CharField(
        label="Message",
        widget=widgets.Textarea(attrs={'rows': 4, 'placeholder': 'Enter your message'})
    )
