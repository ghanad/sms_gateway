from django.apps import AppConfig
from django.conf import settings
import os
import sys


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Start background tasks once Django is ready."""
        # Avoid running twice with the reloader in development
        if "test" in sys.argv:
            return
        if os.environ.get("RUN_MAIN") == "true" or not settings.DEBUG:
            from .state_broadcaster import start_periodic_broadcast

            start_periodic_broadcast()
