#!/bin/sh
set -e
cd "$(dirname "$0")"

# ── 配置（优先读环境变量，读不到用默认值）────────────────────────────────
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
export PORT="${PORT:-8000}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-dev-secret-key-do-not-use-in-production}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export DJANGO_CSRF_TRUSTED_ORIGINS="${DJANGO_CSRF_TRUSTED_ORIGINS:-https://*.app.workbuddy.host,http://localhost,http://127.0.0.1}"
export BLOG_ADMIN_PASSWORD="${BLOG_ADMIN_PASSWORD:-admin12345}"
export SKIP_DEMO_DATA="${SKIP_DEMO_DATA:-}"

# 使用 venv python（如果存在），否则使用系统 python
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

# settings.py 自行从环境变量读取；不要在这里改写源文件（占位符替换一次后永久消失）

# 发布平台会把名为 dist/ 的目录当作构建产物过滤掉，而 VDitor 的 cdn 参数
# 固定拼接 /dist/。上传时用 _bundle/ 存放，启动时还原为 dist/。
if [ -d static/vditor/_bundle ] && [ ! -f static/vditor/dist/index.min.js ]; then
    mkdir -p static/vditor/dist
    cp -r static/vditor/_bundle/. static/vditor/dist/
fi

# 初始化数据库 + 管理员 + 示例数据
# 注意：djust 在生产模式下有 3 个既有检查 ERROR（ALLOWED_HOSTS='*'、占位 SECRET_KEY、未配 CHANNEL_LAYERS）
# 因此迁移必须加 --skip-checks，否则所有 manage.py 命令都会失败
$PYTHON manage.py migrate --noinput --skip-checks >/dev/null 2>&1 || true
$PYTHON bootstrap.py >/dev/null 2>&1 || true

# 清理旧进程（重新部署时防端口占用）
if command -v pkill >/dev/null 2>&1; then
    pkill -9 -f "python -m granian" 2>/dev/null || true
fi
sleep 1

# 启动：asginl（Django 不实现 ASGI lifespan）+ no-ws（纯 SSE，无需 WS）
exec $PYTHON -m granian \
    --interface asginl \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --no-ws \
    django_blog.asgi:application
