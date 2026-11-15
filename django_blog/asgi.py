"""ASGI entrypoint: HTTP + WebSocket (djust LiveView over /ws/live/).

WebSocket 路由按 djust 官方脚手架接法；SSE 路由仍保留在 urls.py，
所以 BLOG_USE_WEBSOCKET=0 可以直接回退 SSE，不需要改这个文件。
"""
import os
import sys
from pathlib import Path

# 发布平台只安装 requirements.txt，没有 src-layout 包的可编辑安装。
SRC_DIR = Path(__file__).resolve().parent.parent / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_blog.settings')

from django.core.asgi import get_asgi_application  # noqa: E402

# 必须先初始化 Django app registry，再 import 任何碰 models / consumer 的模块。
django_asgi_app = get_asgi_application()

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402
from django.urls import path  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from djust.websocket import LiveViewConsumer  # noqa: E402

# AllowedHostsOriginValidator 防 CSWSH；ALLOWED_HOSTS=['*'] 时放行所有 Origin。
application = ProtocolTypeRouter({
    "http": ASGIStaticFilesHandler(django_asgi_app),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter([
                path("ws/live/", LiveViewConsumer.as_asgi()),
            ])
        )
    ),
})
