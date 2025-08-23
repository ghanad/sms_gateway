import uuid
from django.db import models


class Provider(models.Model):
    class AuthType(models.TextChoices):
        BASIC = 'basic', 'Basic'
        APIKEY = 'apikey', 'API Key'
        BEARER = 'bearer', 'Bearer'
        NONE = 'none', 'None'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50)
    base_url = models.URLField()
    endpoint_send = models.CharField(max_length=200)
    auth_type = models.CharField(max_length=20, choices=AuthType.choices, default=AuthType.NONE)
    basic_username = models.CharField(max_length=200, blank=True)
    basic_password = models.CharField(max_length=200, blank=True)
    default_sender = models.CharField(max_length=20, blank=True)
    extra_headers = models.JSONField(blank=True, null=True)
    timeout_ms = models.IntegerField(default=5000)
    retries = models.IntegerField(default=3)
    retry_backoff_ms = models.IntegerField(default=1000)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
