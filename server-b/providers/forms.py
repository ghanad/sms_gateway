# server-b/providers/forms.py
from django import forms
from .models import SmsProvider
from . import widgets

class SmsProviderForm(forms.ModelForm):
    class Meta:
        model = SmsProvider
        fields = '__all__'
        widgets = {
            # Text inputs
            'name': widgets.TextInput(attrs={'class': 'input'}),
            'slug': widgets.TextInput(attrs={'class': 'input'}),
            'send_url': widgets.TextInput(attrs={'class': 'input'}),
            'balance_url': widgets.TextInput(attrs={'class': 'input'}),
            'default_sender': widgets.TextInput(attrs={'class': 'input'}),
            # Selects / Textareas
            'auth_type': widgets.Select(attrs={'class': 'field'}),
            'auth_config': widgets.Textarea(attrs={'class': 'field', 'rows': 4}),
            'headers': widgets.Textarea(attrs={'class': 'field', 'rows': 4}),
            'query_params': widgets.Textarea(attrs={'class': 'field', 'rows': 4}),
            # Numbers / flags
            'timeout_seconds': widgets.TextInput(attrs={'type': 'number', 'class': 'input'}),
            'priority': widgets.TextInput(attrs={'type': 'number', 'class': 'input'}),
            'is_active': widgets.CheckboxInput(attrs={'class': 'checkbox'}),
        }

