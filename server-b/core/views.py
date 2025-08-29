from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import connection
from django.db.utils import OperationalError

@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')


def healthz(request):
    """Lightweight readiness check for the Django app and database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except OperationalError as exc:
        return JsonResponse({"status": "error", "details": str(exc)}, status=503)
