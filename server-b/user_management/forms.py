from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm # Import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Profile # Import the Profile model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    api_key = forms.CharField(max_length=255, required=True, help_text="API Key for the user.")
    daily_quota = forms.IntegerField(required=False, initial=0, help_text="Daily SMS quota for the user (0 means no quota).")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('is_staff', 'api_key', 'daily_quota',) # Added 'is_staff', removed 'is_superuser'

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        # The signal should have created the profile, now update its api_key and daily_quota
        user.profile.api_key = self.cleaned_data['api_key']
        user.profile.daily_quota = self.cleaned_data['daily_quota']
        if commit:
            user.profile.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    api_key = forms.CharField(max_length=255, required=True, help_text="API Key for the user.")
    daily_quota = forms.IntegerField(required=False, help_text="Daily SMS quota for the user (0 means no quota).")

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'api_key', 'daily_quota',) # Added 'is_staff', removed 'is_superuser'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['api_key'].initial = self.instance.profile.api_key
            self.fields['daily_quota'].initial = self.instance.profile.daily_quota # Set initial value for daily_quota
        # Remove password fields
        if 'password' in self.fields:
            del self.fields['password']
        if 'password1' in self.fields:
            del self.fields['password1']
        if 'password2' in self.fields:
            del self.fields['password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        if hasattr(user, 'profile'):
            user.profile.api_key = self.cleaned_data['api_key']
            user.profile.daily_quota = self.cleaned_data['daily_quota'] # Save daily_quota
            if commit:
                user.profile.save()
        return user