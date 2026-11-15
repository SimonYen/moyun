"""Django settings for django_blog."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 配置一律从环境变量读取，默认值写在 start.sh 里；此处再兜底一次，保证只装依赖也能跑
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-do-not-use-in-production')
DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()] or ['*']
LOGIN_URL = '/admin/login/'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'https://*.app.workbuddy.host,http://localhost,http://127.0.0.1',
    ).split(',')
    if o.strip()
]

INSTALLED_APPS = [
    'djust.admin_ext',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'djust',
    'djust.theming',
    'djust.components',
    'blog',
    'imagehost',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'blog.auth_eager.EagerUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'blog.theme_cookie.ThemeModeCookieMiddleware',
]

ROOT_URLCONF = 'django_blog.urls'
ASGI_APPLICATION = 'django_blog.asgi.application'
LIVEVIEW_ALLOWED_MODULES = ['blog.views', 'djust']

TEMPLATES = [
    {
        'BACKEND': 'djust.template_backend.DjustTemplateBackend',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'builtins': ['djust.admin_ext.templatetags.djust_admin_tags'],
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'djust.theming.context_processors.theme_context',
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'builtins': ['djust.admin_ext.templatetags.djust_admin_tags'],
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'djust.theming.context_processors.theme_context',
            ],
        },
    },
]

LIVEVIEW_CONFIG = {
    'use_websocket': False,
    'theme': {
        'pack': 'cn_shuimo',
        'default_mode': 'light',
        'enable_dark_mode': True,
        'persist_in_session': True,
        'cookie_namespace': 'blog_gf',
    },
}

DJUST_THEMES = ['blog.guofeng_themes']

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'},
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
