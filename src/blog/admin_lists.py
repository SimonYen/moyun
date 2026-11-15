"""后台列表 / 标签 / 删除 / 退出登录：全部走原生视图，不依赖 djust LiveView 的 SSE 挂载。

原因：djust.admin_ext 的 ModelListView 在 SSE mount 时若鉴权判定失败，会推 navigate
到登录页且不注册 session；而原生登录页对已登录用户直接跳 /admin/，表现为「自动跳转」。
后台页面不需要实时交互，改成原生表单最稳定。
"""
import uuid
from urllib.parse import urlencode

from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from .models import Post, Tag


def _ok(request):
    return request.user.is_authenticated and request.user.is_active and request.user.is_staff


def _need_login(request):
    return redirect('/admin/login/?' + urlencode({'next': request.get_full_path()}))


def _base(request):
    return {'username': request.user.get_username()}


def _date(dt):
    if not dt:
        return ''
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')


def admin_post_list(request):
    if not _ok(request):
        return _need_login(request)

    rows = []
    for p in Post.objects.prefetch_related('tags').all():
        rows.append({
            'pk': p.pk,
            'title': p.title,
            'slug': p.slug,
            'status_label': '已发布' if p.status == Post.Status.PUBLISHED else '草稿',
            'badge_class': 'pub' if p.status == Post.Status.PUBLISHED else 'draft',
            'tags': '、'.join(t.name for t in p.tags.all()) or '—',
            'date': _date(p.updated_at),
            'view_url': '/posts/%s/' % p.slug,
            'edit_url': '/admin/blog/post/%d/change/' % p.pk,
            'del_url': '/admin/blog/post/%d/delete/' % p.pk,
        })

    ctx = _base(request)
    ctx.update({
        'rows': rows, 'count': len(rows),
        'empty_note': '还没有文章，点「＋ 写新文章」开始吧。' if not rows else '',
    })
    return render(request, 'djust_admin/post_list.html', ctx)


def admin_tag_list(request):
    if not _ok(request):
        return _need_login(request)

    rows = []
    for t in Tag.objects.all():
        rows.append({
            'pk': t.pk,
            'title': t.name,
            'slug': t.slug,
            'count': t.posts.count(),
            'edit_url': '/admin/blog/tag/%d/change/' % t.pk,
            'del_url': '/admin/blog/tag/%d/delete/' % t.pk,
            'view_url': '/tags/%s/' % t.slug,
        })

    ctx = _base(request)
    ctx.update({
        'rows': rows, 'count': len(rows),
        'empty_note': '还没有标签，点「＋ 新增标签」建一个吧。' if not rows else '',
    })
    return render(request, 'djust_admin/tag_list.html', ctx)


def admin_tag_edit(request, object_id=None):
    if not _ok(request):
        return _need_login(request)

    tag = None
    if object_id is not None:
        try:
            tag = Tag.objects.get(pk=object_id)
        except (Tag.DoesNotExist, ValueError):
            return redirect('/admin/blog/tag/')

    error = ''
    name = tag.name if tag else ''
    slug = tag.slug if tag else ''
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip() or slugify(name) or ('tag-' + uuid.uuid4().hex[:6])
        same_name = Tag.objects.filter(name=name)
        same_slug = Tag.objects.filter(slug=slug)
        if tag is not None:
            same_name = same_name.exclude(pk=tag.pk)
            same_slug = same_slug.exclude(pk=tag.pk)
        if not name:
            error = '标签名称不能为空。'
        elif same_name.exists():
            error = '已存在同名标签。'
        elif same_slug.exists():
            error = '该 slug 已被占用，请换一个。'
        else:
            if tag is None:
                tag = Tag(name=name, slug=slug)
            else:
                tag.name, tag.slug = name, slug
            tag.save()
            return redirect('/admin/blog/tag/')

    ctx = _base(request)
    ctx.update({
        'tag': tag, 'name': name, 'slug': slug, 'error': error,
        'page_title': '编辑标签' if tag else '新增标签',
    })
    return render(request, 'djust_admin/tag_edit.html', ctx)


def _delete(request, model, object_id, list_url, kind_name, title, hint):
    if not _ok(request):
        return _need_login(request)
    try:
        obj = model.objects.get(pk=object_id)
    except (model.DoesNotExist, ValueError):
        return redirect(list_url)

    if request.method == 'POST':
        obj.delete()
        return redirect(list_url)

    ctx = _base(request)
    ctx.update({
        'kind_name': kind_name,
        'title': title,
        'hint': hint,
        'cancel_url': list_url,
    })
    return render(request, 'djust_admin/confirm_delete.html', ctx)


def admin_post_delete(request, object_id):
    title = ''
    try:
        title = Post.objects.get(pk=object_id).title
    except (Post.DoesNotExist, ValueError):
        pass
    return _delete(request, Post, object_id, '/admin/blog/post/', '文章', title,
                   '文章正文与标签关联会一并移除，图床里的图片文件不受影响。')


def admin_tag_delete(request, object_id):
    title = ''
    try:
        title = Tag.objects.get(pk=object_id).name
    except (Tag.DoesNotExist, ValueError):
        pass
    return _delete(request, Tag, object_id, '/admin/blog/tag/', '标签', title,
                   '删除标签会解除它与文章的关联，文章本身不会被删除。')


def admin_logout(request):
    auth_logout(request)
    return redirect('/admin/login/')
