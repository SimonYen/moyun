"""相册演示数据：5 张国风示意图 + 2 篇带标签的示例文章。

只在图床为空时生成，避免覆盖用户自己上传的图片或改过的文章。
全新部署时由 bootstrap.py 调用；设 SKIP_DEMO_DATA=1 可完全关闭。
图片用标准库直接生成 PNG，不依赖 Pillow。
"""
import hashlib
import math
import os
import struct
import sys
import uuid
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_blog.settings')

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from blog.models import Post, Tag  # noqa: E402
from imagehost.models import Image  # noqa: E402

W, H = 480, 360
PALETTES = [
    ('宣纸远山.png', (242, 237, 225), (43, 47, 54), (255, 253, 245), (179, 57, 44), 0.0),
    ('松烟墨色.png', (232, 225, 211), (58, 65, 72), (248, 243, 232), (179, 57, 44), 0.8),
    ('青花瓷白.png', (244, 246, 244), (42, 92, 170), (255, 255, 255), (166, 58, 42), 1.6),
    ('釉下钴蓝.png', (230, 238, 243), (30, 68, 126), (250, 252, 255), (166, 58, 42), 2.4),
    ('敦煌遗韵.png', (239, 224, 190), (166, 58, 42), (232, 200, 122), (78, 123, 98), 3.2),
]


def _chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))


def _png(base, ink, moon, seal, phase):
    """宣纸渐变 + 圆月 + 远山 + 水波 + 朱砂印的抽象国风示意图。"""
    ridge = [H * 0.60 + math.sin(x / W * math.pi * 1.8 + phase) * H * 0.07
             for x in range(W)]
    dark = tuple(int(c * 0.68) for c in ink)
    moon_r = (min(W, H) * 0.15) ** 2
    cx, cy = W * 0.72, H * 0.31
    raw = bytearray()
    for y in range(H):
        k = (y / H) * 0.45
        bg = tuple(int(base[i] * (1 - k) + ink[i] * k) for i in range(3))
        row = bytearray([0])
        for x in range(W):
            r, g, b = bg
            if (x - cx) ** 2 + (y - cy) ** 2 < moon_r:
                r, g, b = moon
            if y > ridge[x]:
                r, g, b = ink
            if y > ridge[x] + H * 0.11:
                r, g, b = dark
            if y > H * 0.83 and (y + int(x * 0.05)) % 13 < 2:
                r, g, b = moon
            if W * 0.07 < x < W * 0.07 + 28 and H * 0.76 < y < H * 0.76 + 28:
                r, g, b = seal
            row += bytes((r, g, b))
        raw += row
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + _chunk(b'IEND', b''))


def _post(slug, title, tag_slug, tag_name, excerpt, urls):
    tag, _ = Tag.objects.get_or_create(slug=tag_slug, defaults={'name': tag_name})
    body = [excerpt, '']
    for name, url in urls:
        body.append('![%s](%s)' % (name.rsplit('.', 1)[0], url))
        body.append('')
    post, _ = Post.objects.update_or_create(
        slug=slug,
        defaults={
            'title': title, 'author': get_user_model().objects.get(username='admin'),
            'excerpt': excerpt, 'content': '\n'.join(body),
            'status': Post.Status.PUBLISHED,
        },
    )
    post.tags.set([tag])


def main():
    if os.environ.get('SKIP_DEMO_DATA') == '1':
        print('[seed_gallery] SKIP_DEMO_DATA=1，跳过演示数据')
        return
    if Image.objects.exists():
        print('[seed_gallery] 图床已有数据，跳过演示数据')
        return

    out = Path(settings.MEDIA_ROOT) / 'images'
    out.mkdir(parents=True, exist_ok=True)
    user = get_user_model().objects.filter(username='admin').first()
    urls = {}
    for name, base, ink, moon, seal, phase in PALETTES:
        blob = _png(base, ink, moon, seal, phase)
        relpath = 'images/%s.png' % uuid.uuid4().hex
        (out / Path(relpath).name).write_bytes(blob)
        Image.objects.create(
            name=name, relpath=relpath, mime='image/png', size=len(blob),
            sha256=hashlib.sha256(blob).hexdigest(), uploaded_by=user,
        )
        urls[name] = settings.MEDIA_URL + relpath

    _post('album-shui-mo', '水墨小景 · 相册示例', 'shui-mo', '水墨',
          '两幅宣纸与松烟墨的示意小景，用来演示图床相册按文章标签归档。',
          [(n, urls[n]) for n in ('宣纸远山.png', '松烟墨色.png')])
    _post('album-qing-hua', '青花器物 · 相册示例', 'qing-hua', '青花',
          '两幅瓷白与钴蓝的示意小景，属于另一个分类，可在相册里切换查看。',
          [(n, urls[n]) for n in ('青花瓷白.png', '釉下钴蓝.png')])
    print('[seed_gallery] 已生成 %d 张图片与 2 篇示例文章' % len(urls))


if __name__ == '__main__':
    main()
