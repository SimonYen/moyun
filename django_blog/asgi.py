"""ASGI entrypoint: HTTP only (SSE transport, no WebSocket scope)."""
import os
import sys
from pathlib import Path

# 云沙箱只安装 requirements.txt，没有 src-layout 包的可编辑安装。
SRC_DIR = Path(__file__).resolve().parent.parent / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_blog.settings')

from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402

application = ASGIStaticFilesHandler(django_asgi_app)
