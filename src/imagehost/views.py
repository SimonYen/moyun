"""图床：上传、访问、删除，以及图片的 ZIP 导入导出。"""
import hashlib
import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Image

MAX_SIZE = 5 * 1024 * 1024
MAX_FILES = 500
EXT = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp'}
MIME_BY_EXT = {'png': 'image/png', 'jpg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
RELPATH_RE = re.compile(r'^images/([0-9a-f]{32})\.(png|jpg|gif|webp)$')


def _staff(request):
    u = request.user
    return u.is_authenticated and u.is_active and u.is_staff


def _deny():
    return redirect('/admin/login/?next=/admin/data/')


def _back(msg):
    return redirect('/admin/data/?' + urlencode({'msg': msg}))


def _images_dir():
    d = Path(settings.MEDIA_ROOT).resolve() / 'images'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _full_path(relpath):
    if not RELPATH_RE.match(relpath or ''):
        raise ValueError('非法图片路径')
    return _images_dir() / Path(relpath).name


def sniff(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def upload_image(request):
    """接收 VDitor / 表单上传，返回 VDitor 约定的 succMap 结构。"""
    if not _staff(request):
        return JsonResponse({'msg': '需要登录', 'code': 401, 'data': {}}, status=401)
    if request.method != 'POST':
        return JsonResponse({'msg': '仅支持 POST', 'code': 405, 'data': {}}, status=405)

    upload = request.FILES.get('file') or request.FILES.get('file[]')
    if not upload:
        return JsonResponse({'msg': '没有收到文件', 'code': 1, 'data': {}}, status=400)
    if upload.size > MAX_SIZE:
        return JsonResponse({'msg': '图片不能超过 5MB', 'code': 1, 'data': {}}, status=400)

    data = upload.read()
    mime = sniff(data)
    if not mime:
        return JsonResponse({'msg': '只支持 PNG / JPEG / GIF / WebP', 'code': 1, 'data': {}}, status=400)

    digest = hashlib.sha256(data).hexdigest()
    existing = Image.objects.filter(sha256=digest).first()
    if existing:
        try:
            if _full_path(existing.relpath).exists():
                url = existing.url
                return JsonResponse({
                    'msg': '', 'code': 0,
                    'data': {'errFiles': [], 'succMap': {upload.name: url}},
                })
        except ValueError:
            pass

    relpath = 'images/%s.%s' % (uuid.uuid4().hex, EXT[mime])
    target = _full_path(relpath)
    target.write_bytes(data)
    Image.objects.create(
        name=upload.name[:255], relpath=relpath, mime=mime,
        size=len(data), sha256=digest,
        uploaded_by=request.user if request.user.is_authenticated else None,
    )
    return JsonResponse({
        'msg': '', 'code': 0,
        'data': {'errFiles': [], 'succMap': {upload.name: settings.MEDIA_URL + relpath}},
    })


def serve_media(request, path):
    """运行时图片访问：ASGIStaticFilesHandler 只服务 /static/，媒体文件需自己发。"""
    try:
        full = _full_path(path)
    except ValueError:
        raise Http404
    if not full.is_file():
        raise Http404
    ext = full.suffix.lstrip('.').lower()
    resp = FileResponse(full.open('rb'), content_type=MIME_BY_EXT.get(ext, 'application/octet-stream'))
    resp['Cache-Control'] = 'public, max-age=31536000, immutable'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@require_POST
def delete_image(request, image_id):
    if not _staff(request):
        return _deny()
    obj = Image.objects.filter(id=image_id).first()
    if obj:
        try:
            _full_path(obj.relpath).unlink(missing_ok=True)
        except ValueError:
            pass
        obj.delete()
    return _back('图片已删除')


def export_images(request):
    if not _staff(request):
        return _deny()
    buf = io.BytesIO()
    manifest = {
        'version': 1,
        'kind': 'blog-images',
        'exported_at': timezone.now().isoformat(),
        'images': [],
    }
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for img in Image.objects.all().order_by('uploaded_at'):
            full = _full_path(img.relpath)
            if not full.is_file():
                continue
            zf.write(full, 'files/' + img.relpath)
            manifest['images'].append({
                'id': str(img.id), 'name': img.name, 'relpath': img.relpath,
                'mime': img.mime, 'size': img.size, 'sha256': img.sha256,
                'uploaded_at': img.uploaded_at.isoformat(),
            })
        zf.writestr('images.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    resp = HttpResponse(buf.getvalue(), content_type='application/zip')
    resp['Content-Disposition'] = 'attachment; filename="images-%s.zip"' % timezone.now().strftime('%Y%m%d')
    return resp


def merge_images(data, user):
    """从图片 ZIP 字节恢复文件与记录。

    清单结构先校验：旧版备份 / 误选的文件 / 手改过的 JSON 都不应让页面 500。
    路径仍强制匹配 RELPATH_RE，杜绝 ZIP 路径穿越。
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        if 'images.json' not in names:
            raise ValueError('缺少 images.json，不是图片备份')
        manifest = json.loads(zf.read('images.json'))
        if not isinstance(manifest, dict):
            raise ValueError('备份格式不正确：images.json 应为对象')
        entries = manifest.get('images', [])
        if not isinstance(entries, list):
            raise ValueError('备份格式不正确：images 应为列表')
        entries = [e for e in entries if isinstance(e, dict)][:MAX_FILES]
        added = reused = 0
        for item in entries:
            relpath = item.get('relpath', '')
            if (not isinstance(relpath, str) or not RELPATH_RE.match(relpath)
                    or 'files/' + relpath not in names):
                continue
            blob = zf.read('files/' + relpath)
            mime = MIME_BY_EXT.get(Path(relpath).suffix.lstrip('.'))
            if len(blob) > MAX_SIZE or sniff(blob) != mime:
                continue
            target = _full_path(relpath)
            if not target.exists():
                target.write_bytes(blob)
            if Image.objects.filter(relpath=relpath).exists():
                reused += 1
                continue
            # id 来自外部文件，必须能解析成合法 UUID；坏值重新生成而不是抛 ValidationError
            raw_id = item.get('id')
            try:
                image_id = uuid.UUID(str(raw_id)) if raw_id else uuid.uuid4()
            except (ValueError, TypeError, AttributeError):
                image_id = uuid.uuid4()
            Image.objects.create(
                id=image_id, name=str(item.get('name') or target.name)[:255],
                relpath=relpath, mime=mime, size=len(blob),
                sha256=hashlib.sha256(blob).hexdigest(), uploaded_by=user,
            )
            added += 1
    return added, reused


@require_POST
def import_images(request):
    if not _staff(request):
        return _deny()
    upload = request.FILES.get('archive')
    if not upload:
        return _back('请选择 ZIP 文件')
    try:
        with transaction.atomic():
            added, reused = merge_images(upload.read(), request.user)
    except (zipfile.BadZipFile, ValueError, KeyError, TypeError, AttributeError,
            UnicodeDecodeError, json.JSONDecodeError, ValidationError,
            IntegrityError, OSError) as exc:
        return _back('导入失败：' + str(exc)[:80])
    return _back('图片导入完成：新增 %d 张，跳过 %d 张' % (added, reused))
