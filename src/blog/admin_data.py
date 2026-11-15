"""数据管理页与博客数据（文章 + 标签）的 JSON 导入导出。"""
import json
from datetime import datetime
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from imagehost.models import Image

from .models import Post, Tag


def _staff(request):
    u = request.user
    return u.is_authenticated and u.is_active and u.is_staff


def _back(msg):
    return redirect('/admin/data/?' + urlencode({'msg': msg}))


def _iso(value):
    return value.isoformat() if value else None


def data_page(request):
    if not _staff(request):
        return redirect('/admin/login/?next=/admin/data/')

    images = [{
        'id': str(img.id), 'name': img.name, 'url': img.url,
        'size_kb': round(img.size / 1024, 1),
        'uploaded_at': timezone.localtime(img.uploaded_at).strftime('%Y-%m-%d %H:%M'),
    } for img in Image.objects.all()[:60]]

    return render(request, 'djust_admin/data.html', {
        'username': request.user.get_username(),
        'msg': request.GET.get('msg', ''),
        'images': images,
        'image_count': Image.objects.count(),
        'post_count': Post.objects.count(),
        'tag_count': Tag.objects.count(),
    })


def export_blog(request):
    if not _staff(request):
        return redirect('/admin/login/?next=/admin/data/')

    payload = {
        'version': 1,
        'kind': 'blog-posts',
        'exported_at': timezone.now().isoformat(),
        'tags': [{'name': t.name, 'slug': t.slug} for t in Tag.objects.all()],
        'posts': [{
            'title': p.title,
            'slug': p.slug,
            'author': p.author.get_username(),
            'excerpt': p.excerpt,
            'content': p.content,
            'status': p.status,
            'tags': list(p.tags.values_list('name', flat=True)),
            'created_at': _iso(p.created_at),
            'updated_at': _iso(p.updated_at),
            'published_at': _iso(p.published_at),
        } for p in Post.objects.all().order_by('created_at')],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    resp = HttpResponse(body, content_type='application/json; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="blog-%s.json"' % timezone.now().strftime('%Y%m%d')
    return resp


def merge_blog(payload, user):
    """按 slug 合并文章。返回 (新建, 更新)。

    备份可能来自旧版本或被用户误选（例如把 ZIP 选进 JSON 导入框），因此结构
    一律先校验，非法就抛 ValueError 交给视图转成友好提示，绝不让页面 500。
    """
    if not isinstance(payload, dict):
        raise ValueError('备份格式不正确：顶层应为对象')
    if payload.get('kind') != 'blog-posts':
        raise ValueError('不是博客数据备份（kind 不匹配）')
    tags = payload.get('tags', [])
    posts = payload.get('posts', [])
    if not isinstance(tags, list) or not isinstance(posts, list):
        raise ValueError('备份格式不正确：tags / posts 应为列表')
    if any(not isinstance(x, dict) for x in tags + posts):
        raise ValueError('备份格式不正确：列表元素应为对象')

    for t in tags:
        name = str(t.get('name') or '').strip()
        if name:
            Tag.objects.get_or_create(
                name=name[:50], defaults={'slug': str(t.get('slug') or '')[:50]}
            )

    created = updated = 0
    for item in posts:
        title = str(item.get('title') or '').strip()
        slug = str(item.get('slug') or '').strip()
        if not title or not slug:
            continue
        author = get_user_model().objects.filter(
            username=str(item.get('author') or '')
        ).first() or user
        post = Post.objects.filter(slug=slug).first()
        if post is None:
            post = Post(slug=slug, author=author)
            created += 1
        else:
            updated += 1
        post.title = title[:200]
        post.excerpt = str(item.get('excerpt') or '')
        post.content = str(item.get('content') or '')
        status = item.get('status')
        post.status = status if status in Post.Status.values else Post.Status.DRAFT
        # 旧版备份里的 likes 字段直接忽略（点赞功能已移除）
        post.save()

        tag_names = item.get('tags', [])
        if not isinstance(tag_names, list):
            tag_names = []
        tag_ids = [Tag.objects.get_or_create(name=str(n)[:50])[0].pk
                   for n in tag_names if isinstance(n, str) and n.strip()]
        post.tags.set(tag_ids)

        # 自动字段允许显式回填，保留原发布时间；单字段坏掉只跳过该字段
        fields = []
        for key in ('created_at', 'updated_at', 'published_at'):
            raw = item.get(key)
            if not isinstance(raw, str):
                continue
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                continue
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            setattr(post, key, dt)
            fields.append(key)
        if fields:
            post.save(update_fields=fields)
    return created, updated


@require_POST
def import_blog(request):
    if not _staff(request):
        return redirect('/admin/login/?next=/admin/data/')
    upload = request.FILES.get('archive')
    if not upload:
        return _back('请选择 JSON 备份文件')
    try:
        payload = json.loads(upload.read().decode('utf-8'))
        with transaction.atomic():
            created, updated = merge_blog(payload, request.user)
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError,
            json.JSONDecodeError, ValidationError, IntegrityError) as exc:
        return _back('导入失败：' + str(exc)[:80])
    return _back('博客导入完成：新建 %d 篇，更新 %d 篇' % (created, updated))
