import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_gateway_project.settings')

app = Celery('sms_gateway_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


