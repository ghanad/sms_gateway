# models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

class ProviderType(models.TextChoices):
    MAGFA = "magfa", _("Magfa")

class AuthType(models.TextChoices):
    NONE = "none", _("No Auth")
    BASIC = "basic", _("Basic Auth")
    API_KEY_HEADER = "api_key_header", _("API Key in Header")
    API_KEY_QUERY = "api_key_query", _("API Key in Query Param")
    OAUTH2_CLIENT = "oauth2_client", _("OAuth2 Client Credentials")

class SmsProvider(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(unique=True)

    provider_type = models.CharField(
        max_length=16, choices=ProviderType.choices, default=ProviderType.MAGFA
    )

    send_url = models.URLField()
    balance_url = models.URLField()

    default_sender = models.CharField(
        max_length=32,
        help_text="Line number (sender) represented by this provider instance."
    )

    # Auth & static request config
    auth_type = models.CharField(
        max_length=20, choices=AuthType.choices, default=AuthType.BASIC
    )
    auth_config = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Provider-specific auth data. Examples:\n"
            "- BASIC: {\"username\": \"u\", \"password_env\": \"MAGFA_PASSWORD\", \"domain\": \"d\"}\n"
            "- API_KEY_HEADER: {\"key\": \"...\", \"header_name\": \"Authorization\"}\n"
            "- API_KEY_QUERY: {\"key\": \"...\", \"param_name\": \"api_key\"}\n"
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
        help_text="Higher means higher priority (unique per provider_type)."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "name"]
        indexes = [
            models.Index(fields=["is_active", "slug"]),
            models.Index(fields=["provider_type", "is_active", "priority"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_type", "default_sender"],
                name="uq_provider_type_sender"
            ),
            models.UniqueConstraint(
                fields=["provider_type", "priority"],
                name="uq_priority_per_provider_type"
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        ac = self.auth_config or {}

        if not self.default_sender:
            raise ValidationError({"default_sender": "default_sender is required."})

        if self.auth_type == AuthType.BASIC:
            missing = [k for k in ["username"] if k not in ac]
            if "password" not in ac and "password_env" not in ac:
                missing.append("password or password_env")
            if missing:
                raise ValidationError({"auth_config": f"Missing for BASIC: {', '.join(missing)}"})

        if self.auth_type in (AuthType.API_KEY_HEADER, AuthType.API_KEY_QUERY):
            if "key" not in ac:
                raise ValidationError({"auth_config": "Missing: key"})

