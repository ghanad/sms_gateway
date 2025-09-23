from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm


User = get_user_model()


def _ensure_input_class(form_field: forms.Field) -> None:
    widget = form_field.widget
    if getattr(widget, "input_type", None) == "checkbox":
        return

    classes = widget.attrs.get("class", "")
    class_list = classes.split()
    if "input" not in class_list:
        class_list.append("input")
    widget.attrs["class"] = " ".join(class_list).strip()


class CustomUserCreationForm(UserCreationForm):
    api_key = forms.CharField(
        max_length=255,
        required=True,
        help_text="API Key for the user.",
    )
    daily_quota = forms.IntegerField(
        required=False,
        initial=0,
        help_text="Daily SMS quota for the user (0 means no quota).",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "input"}),
        help_text="Optional notes visible only to administrators.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + (
            "is_staff",
            "api_key",
            "daily_quota",
            "description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            _ensure_input_class(field)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()

        profile = getattr(user, "profile", None)
        if profile is not None:
            profile.api_key = self.cleaned_data["api_key"]
            profile.daily_quota = self.cleaned_data.get("daily_quota") or 0
            profile.description = (self.cleaned_data.get("description") or "").strip()
            if commit:
                profile.save()

        return user


class CustomUserChangeForm(UserChangeForm):
    api_key = forms.CharField(
        max_length=255,
        required=True,
        help_text="API Key for the user.",
    )
    daily_quota = forms.IntegerField(
        required=False,
        help_text="Daily SMS quota for the user (0 means no quota).",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "input"}),
        help_text="Optional notes visible only to administrators.",
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "api_key",
            "daily_quota",
            "description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            _ensure_input_class(field)
        profile = getattr(self.instance, "profile", None)
        if profile is not None:
            self.fields["api_key"].initial = profile.api_key
            self.fields["daily_quota"].initial = profile.daily_quota
            self.fields["description"].initial = profile.description

        for field_name in ("password", "password1", "password2"):
            if field_name in self.fields:
                del self.fields[field_name]

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()

        profile = getattr(user, "profile", None)
        if profile is not None:
            profile.api_key = self.cleaned_data["api_key"]
            profile.daily_quota = self.cleaned_data.get("daily_quota") or 0
            profile.description = (self.cleaned_data.get("description") or "").strip()
            if commit:
                profile.save()

        return user
