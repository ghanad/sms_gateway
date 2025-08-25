
# server-b/providers/forms.py
import json
from django import forms
from django.utils.text import slugify
from .models import SmsProvider
# ===> این import بسیار مهم است <===
from . import widgets

# ==============================================================================
# ویجت نهایی: از ویجت سفارشی شما ارث‌بری می‌کند تا استایل‌ها حفظ شوند
# ==============================================================================
class PlaceholderJsonTextarea(widgets.Textarea):  # <--- تغییر کلیدی اینجاست
    """
    این ویجت از ویجت پایه شما (widgets.Textarea) ارث‌بری می‌کند تا تمام
    استایل‌های پیش‌فرض (مانند کلاس CSS) را به ارث ببرد.
    همچنین منطق لازم برای نمایش placeholder در JSONField را پیاده‌سازی می‌کند.
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
        widgets = {
            # این ویجت‌ها از قبل درست بودند
            'name': widgets.TextInput(attrs={'placeholder': 'e.g. Magfa 3000991'}),
            'slug': widgets.TextInput(attrs={'placeholder': 'e.g. magfa-3000991'}),
            'provider_type': widgets.Select(attrs={'data-placeholder': 'Select provider type'}),
            'send_url': widgets.TextInput(attrs={'placeholder': 'https://sms.magfa.com/api/http/sms/v2/send'}),
            'balance_url': widgets.TextInput(attrs={'placeholder': 'https://sms.magfa.com/api/http/sms/v2/balance'}),
            'default_sender': widgets.TextInput(attrs={'placeholder': 'e.g. 3000991'}),
            'auth_type': widgets.Select(attrs={'data-placeholder': 'Select auth type'}),

            # ===> استفاده از ویجت نهایی و اصلاح‌شده <===
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
                'placeholder': '0–100 (higher = higher priority)',
                'min': 0, 'max': 100, 'step': 1,
            }),
            'is_active': widgets.CheckboxInput(attrs={'title': 'Enable/disable this provider'}),
        }

    # بقیه فرم بدون تغییر باقی می‌ماند
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('name') or '')
        return slug

    def clean(self):
        cleaned = super().clean()
        provider_type = cleaned.get('provider_type')
        priority = cleaned.get('priority')
        default_sender = cleaned.get('default_sender')

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
        return cleaned
