from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

class AuthType(models.TextChoices):
    NONE = "none", _("No Auth")
    BASIC = "basic", _("Basic Auth")
    API_KEY_HEADER = "api_key_header", _("API Key in Header")
    API_KEY_QUERY = "api_key_query", _("API Key in Query Param")
    OAUTH2_CLIENT = "oauth2_client", _("OAuth2 Client Credentials")

class SmsProvider(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(unique=True)

    # Required endpoints
    send_url = models.URLField()
    balance_url = models.URLField()

    # Optional defaults
    default_sender = models.CharField(
        max_length=32, blank=True,
        help_text="Optional default sender (line number) for this provider."
    )

    # Auth & static request config
    auth_type = models.CharField(
        max_length=20, choices=AuthType.choices, default=AuthType.BASIC
    )
    auth_config = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Provider-specific auth data. Examples:\n"
            "- BASIC: {\"username\": \"u\", \"password_env\": \"MAGFA_PASSWORD\", \"domain\": \"d\"}"
            "- API_KEY_HEADER: {\"key\": \"...\", \"header_name\": \"Authorization\"}"
            "- API_KEY_QUERY: {\"key\": \"...\", \"param_name\": \"api_key\"}"
            "- OAUTH2_CLIENT: {\"token_url\": \"...\", \"client_id\": \"...\", \"client_secret_env\": \"...\", \"scope\": \"...\"}"
        )
    )
    headers = models.JSONField(default=dict, blank=True,
                               help_text="Static headers to send with every request.")
    query_params = models.JSONField(default=dict, blank=True,
                                    help_text="Static query params to append to every request.")

    timeout_seconds = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Provider priority, from 0 (lowest) to 100 (highest)."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "slug"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Minimal validation depending on auth_type."""
        ac = self.auth_config or {}
        if self.auth_type == AuthType.BASIC:
            missing = [k for k in ["username"] if k not in ac]
            # password can be provided via "password" or "password_env"
            if "password" not in ac and "password_env" not in ac:
                missing.append("password or password_env")
            if missing:
                raise ValidationError({"auth_config": f"Missing for BASIC: {', '.join(missing)}"})

        if self.auth_type in (AuthType.API_KEY_HEADER, AuthType.API_KEY_QUERY):
            if "key" not in ac:
                raise ValidationError({"auth_config": "Missing: key"})

