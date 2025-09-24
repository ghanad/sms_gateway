from pathlib import Path
import os
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Provide a default so tests can run without explicit environment configuration.
SECRET_KEY = os.environ.get('SECRET_KEY', 'insecure-test-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')


# Application definition

INSTALLED_APPS = [
    
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # allauth apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # My apps
    'sms_gateway',
    'user_management',
    'core',
    'providers',
    'messaging',
    'django_celery_beat',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'sms_gateway_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'sms_gateway_project' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sms_gateway_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Default to a local SQLite database if no DATABASE_URL environment variable is
# supplied. This allows the test suite to run without additional configuration.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# allauth settings
LOGIN_REDIRECT_URL = '/messages/my-messages/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGIN_METHODS = ['username']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_ALLOW_REGISTRATION = False
# Use ``*`` to mark required fields per django-allauth's SIGNUP_FIELDS format.
ACCOUNT_SIGNUP_FIELDS = ['username*', 'password1*']
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/5m',
}

# RabbitMQ settings
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'guest')

RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST', '/')
RABBITMQ_SMS_QUEUE = os.environ.get('RABBITMQ_SMS_QUEUE', 'sms_outbound_queue')
RABBITMQ_SMS_DLQ_USER_NOT_FOUND = os.environ.get(
    'RABBITMQ_SMS_DLQ_USER_NOT_FOUND', 'sms_dlq_user_not_found'
)
RABBITMQ_SMS_RETRY_WAIT_QUEUE = os.environ.get(
    'RABBITMQ_SMS_RETRY_WAIT_QUEUE', 'sms_retry_wait_queue'
)
RABBITMQ_SMS_RETRY_WAIT_TTL_MS = int(
    os.environ.get('RABBITMQ_SMS_RETRY_WAIT_TTL_MS', '5000')
)

CONFIG_EVENTS_EXCHANGE = os.environ.get('CONFIG_EVENTS_EXCHANGE', 'config_events_exchange')
CONFIG_STATE_EXCHANGE = os.environ.get('CONFIG_STATE_EXCHANGE', 'config_state_exchange')
CONFIG_STATE_SYNC_ENABLED = os.environ.get('CONFIG_STATE_SYNC_ENABLED', 'True').lower() in ('true', '1', 't')

# Ensure the vhost starts with a /
vhost_path = RABBITMQ_VHOST if RABBITMQ_VHOST.startswith('/') else f'/{RABBITMQ_VHOST}'
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}{vhost_path}',
)

CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'rpc://')
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_IMPORTS = (
    'core.state_broadcaster',
    'user_management.tasks',
)
CELERY_BEAT_SCHEDULE = {
    'dispatch-pending-messages': {
        'task': 'messaging.tasks.dispatch_pending_messages',
        'schedule': timedelta(seconds=10),
    },
    'update-provider-balance-metrics': {
        'task': 'providers.tasks.update_provider_balance_metrics',
        'schedule': timedelta(minutes=15),
    },
    'update-expected-config-fingerprint': {
        'task': 'user_management.tasks.update_expected_config_fingerprint_metric',
        'schedule': timedelta(seconds=60),
    },

}


if CONFIG_STATE_SYNC_ENABLED:
    CELERY_BEAT_SCHEDULE['publish-full-state'] = {
        'task': 'core.state_broadcaster.publish_full_state',
        'schedule': timedelta(seconds=60),
    }


csrf_trusted_origins_str = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted_origins_str.split(',') if origin.strip()]