from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth import get_user_model
from .models import Profile # Import the Profile model

User = get_user_model()

class CustomUserChangeForm(UserChangeForm):
    api_key = forms.CharField(max_length=255, required=False, help_text="API Key for the user.")

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'api_key')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['api_key'].initial = self.instance.profile.api_key

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        if hasattr(user, 'profile'):
            user.profile.api_key = self.cleaned_data['api_key']
            if commit:
                user.profile.save()
        return user