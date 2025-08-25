from django import forms
from .models import SmsProvider
from . import widgets

class SmsProviderForm(forms.ModelForm):
    class Meta:
        model = SmsProvider
        fields = '__all__'
        widgets = {
            'name': widgets.TextInput(),
            'slug': widgets.TextInput(),
            'send_url': widgets.TextInput(),
            'balance_url': widgets.TextInput(),
            'default_sender': widgets.TextInput(),
            'auth_type': widgets.Select(),
            'auth_config': widgets.Textarea(attrs={'rows': 4}),
            'headers': widgets.Textarea(attrs={'rows': 4}),
            'query_params': widgets.Textarea(attrs={'rows': 4}),
            'timeout_seconds': widgets.TextInput(attrs={'type': 'number'}),
            'priority': widgets.TextInput(attrs={'type': 'number'}),
            'is_active': widgets.CheckboxInput(),
        }
