"""幂等初始化：全新环境创建管理员并生成示例文章与相册演示图片。"""
import os
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_blog.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from imagehost.models import Image  # noqa: E402

User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        'admin', 'admin@example.com',
        os.environ.get('BLOG_ADMIN_PASSWORD', 'admin12345'),
    )

# 图床为空时才生成演示图片（不覆盖用户已有数据）
if not os.environ.get('SKIP_DEMO_DATA') == '1' and not Image.objects.exists():
    exec(open('seed_gallery.py').read())

print('[bootstrap] 完成')
