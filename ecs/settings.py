# Django settings for ecs project.

import os, sys, platform, logging
from datetime import timedelta
from urllib.parse import urlparse

from sentry_sdk.integrations.logging import LoggingIntegration

# root dir of project
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# import and execute ECS_SETTINGS from environment as python code if they exist
if os.getenv('ECS_SETTINGS'):
    exec(os.getenv('ECS_SETTINGS'))

ECS_VERSION = 'v2.4.3'

# absolute URL prefix w/out trailing slash
if os.getenv('ECS_DOMAIN'):
    DOMAIN = os.getenv('ECS_DOMAIN')
    ABSOLUTE_URL_PREFIX = 'https://{}'.format(DOMAIN)
else:
    DOMAIN = "localhost"
    ABSOLUTE_URL_PREFIX = "http://" + DOMAIN + ":8000"

# This is used by the EthicsCommission model to identify the system
ETHICS_COMMISSION_UUID = os.getenv('ECS_COMMISSION_UUID', 'ecececececececececececececececec')
ECS_REQUIRE_CLIENT_CERTS = os.getenv('ECS_REQUIRE_CLIENT_CERTS', '').lower() == 'true'
ECS_USERSWITCHER_ENABLED = os.getenv('ECS_USERSWITCHER_ENABLED', 'true').lower() == 'true'

ALLOWED_HOSTS = [DOMAIN]

# Production settings
if os.getenv('ECS_PROD', 'false').lower() == 'true':
    PDFAS_SERVICE = ABSOLUTE_URL_PREFIX + '/pdf-as-web/'
    SECURE_PROXY_SSL = True
    DEBUG = False
# Default development settings
else:
    # PDF Signing will use fake signing if PDFAS_SERVICE is "mock:"
    PDFAS_SERVICE = 'mock:'
    DEBUG = True
    EMAIL_HOST = 'localhost'
    EMAIL_PORT = 1025

if os.getenv('ECS_EMAIL_ENABLED', 'true').lower() == 'true':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Django keys
if os.getenv('ECS_SECRET_KEY'):
    SECRET_KEY = os.getenv('ECS_SECRET_KEY')
else:
    SECRET_KEY = 'ptn5xj+85fvd=d4u@i1-($z*otufbvlk%x1vflb&!5k94f$i3w'
if os.getenv('ECS_REGISTRATION_SECRET'):
    REGISTRATION_SECRET = os.getenv('ECS_REGISTRATION_SECRET')
else:
    REGISTRATION_SECRET = '!brihi7#cxrd^twvj$r=398mdp4neo$xa-rm7b!8w1jfa@7zu_'
if os.getenv('ECS_PASSWORD_RESET_SECRET'):
    PASSWORD_RESET_SECRET = os.getenv('ECS_PASSWORD_RESET_SECRET')
else:
    PASSWORD_RESET_SECRET = 'j2obdvrb-hm$$x949k*f5gk_2$1x%2etxhd!$+*^qs8$4ra3=a'

ECS_CHANGED = os.getenv('BUILD_TIME', 'unknown')
ECS_DISABLE_REGISTER = os.getenv('ECS_DISABLE_REGISTER', '').lower() == 'true'
ECS_DISABLE_EMAIL_DELIVERY = os.getenv('ECS_DISABLE_EMAIL_DELIVERY', '').lower() == 'true'

# Database configuration with development fallback
DATABASES = {}
if os.getenv('DATABASE_URL'):
    url = urlparse(os.getenv('DATABASE_URL'))
    DATABASES['default'] = {
        'NAME': url.path[1:] or '',
        'ENGINE': 'django.db.backends.postgresql',
        'USER': url.username,
        'PASSWORD': url.password,
        'HOST': url.hostname or '',
        'PORT': url.port or '5432',
        'ATOMIC_REQUESTS': True
    }
else:
    DATABASES['default'] = {
        'NAME': 'test-ecs',
        'ENGINE': 'django.db.backends.postgresql',
        'USER': 'test-ecs',
        'PASSWORD': 'test-ecs',
        'HOST': 'localhost',
        'PORT': '5432',
        'ATOMIC_REQUESTS': True,
    }

# Local time zone for this installation. See http://en.wikipedia.org/wiki/List_of_tz_zones_by_name,
# although not all choices may be available on all operating systems.
TIME_ZONE = 'Europe/Vienna'
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'de-AT'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# workaround: we can not use the django gettext function in the settings
# because it depends on the settings.
gettext = lambda s: s

# path where django searches for *.mo files
LOCALE_PATHS = (os.path.join(PROJECT_DIR, "locale"),)

# declare supported languages for i18n. English is the internal project language.
# We do not want to expose our internal denglish to the end-user, so disable english
# in the settings
LANGUAGES = (
    ('de-AT', gettext('German')),
)

# default site id, some thirdparty libraries expect it to be set
SITE_ID = 1

STATIC_ROOT = os.path.join(PROJECT_DIR, 'static')
STATIC_URL = '/static/'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# start of url matching
ROOT_URLCONF = 'ecs.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'ecs.wsgi.application'

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# additional fixture search paths. implicitly used by every app the needs fixtures
FIXTURE_DIRS = [os.path.join(PROJECT_DIR, "fixtures")]

# django.contrib.messages
MESSAGE_STORE = 'django.contrib.messages.storage.session.SessionStorage'

# Session Settings
SESSION_COOKIE_AGE = 28800               # logout after 8 hours of inactivity
SESSION_SAVE_EVERY_REQUEST = True        # so, every "click" on the pages resets the expiry time
SESSION_EXPIRE_AT_BROWSER_CLOSE = True   # session cookie expires at close of browser

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(PROJECT_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.static",
                "django.template.context_processors.request",
                'django.template.context_processors.csrf',
                "django.contrib.messages.context_processors.messages",
                "ecs.core.context_processors.ecs_settings",
            ]
        },
    },
]

MIDDLEWARE = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'ecs.utils.forceauth.ForceAuth',
    'ecs.userswitcher.middleware.UserSwitcherMiddleware',
    'ecs.pki.middleware.ClientCertMiddleware',
    #'ecs.TestMiddleware',
    'ecs.users.middleware.GlobalUserMiddleware',
    'ecs.tasks.middleware.RelatedTasksMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'ecs.utils.current_user.CurrentUserMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    'compressor',
    'reversion',
    'django_countries',
    # 'raven.contrib.django.raven_compat',
    'widget_tweaks',

    'ecs.core',
    'ecs.checklists',
    'ecs.votes',
    'ecs.utils',
    'ecs.docstash',
    'ecs.userswitcher',
    'ecs.workflow',
    'ecs.tasks',
    'ecs.communication',
    'ecs.dashboard',
    'ecs.bootstrap',
    'ecs.billing',
    'ecs.users',
    'ecs.documents',
    'ecs.meetings',
    'ecs.notifications',
    'ecs.authorization',
    'ecs.integration',
    'ecs.boilerplate',
    'ecs.scratchpad',
    'ecs.pki',
    'ecs.statistics',
    'ecs.tags',
)

# authenticate with email address
AUTHENTICATION_BACKENDS = ('ecs.users.backends.EmailAuthBackend',)

# Force Django to always use real files, not an InMemoryUploadedFile.
# The document processing pipeline depends on the file objects having
# a fileno().
FILE_UPLOAD_HANDLERS = (
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('ECS_LOG_LEVEL', 'WARNING'),
    },
    'loggers': {
        'django': {
            'level': 'NOTSET',
        },
        'django.db.backends': {
            # All SQL queries are logged with level DEBUG. Settings the logger
            # level to INFO prevents those messages from being propagated to
            # the root logger.
            'level': 'INFO',
        },
        'django.template': {
            'level': 'ERROR'
        },
        'django.utils.autoreload': {
            'level': 'INFO'
        }
    },
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2500

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# ecs settings
##############

# used by ecs.pki
ECS_CA_ROOT = os.path.join(PROJECT_DIR, 'data', 'ca')

# users in these groups receive messages even when they are not related to studies
ECS_MEETING_AGENDA_RECEIVER_GROUPS = (
    'Resident Board Member', 'Omniscient Board Member',
)
ECS_MEETING_PROTOCOL_RECEIVER_GROUPS = (
    'Meeting Protocol Receiver', 'Resident Board Member',
    'Omniscient Board Member',
)

ECS_AMG_MPG_VOTE_RECEIVERS = (os.getenv('ECS_VOTE_RECEIVERS', 'BASG.EKVoten@ages.at'), )

ECS_MEETING_GRACE_PERIOD = timedelta(days=5)

# authorization
AUTHORIZATION_CONFIG = 'ecs.auth_conf'

# registration/login settings
LOGIN_REDIRECT_URL = '/dashboard/'

# directory where to store zipped submission patientinformation and submission form pdfs
ECS_DOWNLOAD_CACHE_DIR = os.path.realpath(os.path.join(PROJECT_DIR, 'volatile', 'ecs-cache'))
ECS_DOWNLOAD_CACHE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days

# Storage Vault settings
STORAGE_VAULT = os.path.join(PROJECT_DIR, 'data', 'storage-vault')

if os.getenv('SMTP_URL'):
    url = urlparse(os.getenv('SMTP_URL'))
    EMAIL_HOST = url.hostname
    EMAIL_PORT = url.port or 25
    EMAIL_HOST_USER = url.username or ''
    EMAIL_HOST_PASSWORD = url.password or ''

SMTPD_CONFIG = {
    'listen_addr': ('0.0.0.0', 8025),
    'domain': DOMAIN,
    'store_exceptions': False,
}


# thirdparty settings
######################

# ### celery ### default uses memory transport and always eager

CELERY_IMPORTS = (
    'ecs.communication.tasks',
    'ecs.core.tasks',
    'ecs.core.tests.test_tasks',
    'ecs.documents.tasks',
    'ecs.integration.tasks',
    'ecs.meetings.tasks',
    'ecs.tasks.tasks',
    'ecs.users.tasks',
    'ecs.votes.tasks',
)
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle' # Maybe?
CELERY_ACCEPT_CONTENT = (CELERY_TASK_SERIALIZER,)
# try to propagate exceptions back to caller
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = 'Europe/Vienna'

if os.getenv('REDIS_URL'):
    CELERY_BROKER_URL = os.getenv('REDIS_URL')
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'fanout_prefix': True,
        'fanout_patterns': True
    }
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
    CELERY_TASK_ALWAYS_EAGER = False
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            # Remove last to characters because of the '/0'
            'LOCATION': os.getenv('REDIS_URL')[:-2],
            'KEY_PREFIX': 'django'
        }
    }
else:
    # dont use queueing backend but consume it right away
    CELERY_TASK_ALWAYS_EAGER = True
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    }

# ### django_compressor ###
COMPRESS_ENABLED = True
COMPRESS_PRECOMPILERS = (
    (
        'text/x-scss',
        'pyscss -I {} -o {{outfile}} {{infile}}'.format(
            os.path.join(STATIC_ROOT, 'css'))
    ),
)


# settings override
###################
#these are local fixes, they default to a sane value if unset

#ECS_WORDING = True/False defaults to False if empty
# activates django-rosetta

# overwrite settings from local_settings.py if it exists
try:
    from ecs.local_settings import *
except ImportError:
    pass

DEFAULT_FROM_EMAIL = SERVER_EMAIL = 'noreply@{}'.format(DOMAIN)

# https
if 'SECURE_PROXY_SSL' in locals() and SECURE_PROXY_SSL:
  CSRF_COOKIE_SECURE= True
  SESSION_COOKIE_SECURE = True
  SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# sentry
if os.getenv('ECS_SENTRY_DSN', '') != '':
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=os.getenv('ECS_SENTRY_DSN'),
        integrations=[DjangoIntegration(), LoggingIntegration(
            level=logging.FATAL,        # Capture info and above as breadcrumbs
            event_level=logging.FATAL   # Send records as events
        ),],

        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production,
        traces_sample_rate=0,
        send_default_pii=True,

        # By default the SDK will try to use the SENTRY_RELEASE
        # environment variable, or infer a git commit
        # SHA as release, however you may want to set
        # something more human-readable.
        # release="myapp@1.0.0",
    )


if not ECS_USERSWITCHER_ENABLED:
    MIDDLEWARE = tuple(item for item in MIDDLEWARE if item != 'ecs.userswitcher.middleware.UserSwitcherMiddleware')

# django rosetta activation
if 'ECS_WORDING' in locals() and ECS_WORDING:
    INSTALLED_APPS +=('rosetta',) # anywhere

# hack some settings for test and runserver
if 'test' in sys.argv:
    CELERY_TASK_ALWAYS_EAGER = True
    INSTALLED_APPS += ('ecs.workflow.tests',)

if 'runserver' in sys.argv:
    logging.basicConfig(
        level = logging.DEBUG,
        format = '%(asctime)s %(levelname)s %(message)s',
    )
