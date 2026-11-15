import re
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import escape

from djust import LiveView
from djust.components.components.image_lightbox import ImageLightbox
from djust.decorators import event_handler
from imagehost.models import Image

from .models import Post, Tag


def _published():
    return (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related("author")
        .prefetch_related("tags")
    )


class HomeView(LiveView):
    """Landing page: hero + latest posts + tag cloud."""

    template_name = "blog/home.html"

    def mount(self, request, **kwargs):
        self._posts = list(_published()[:6])
        self._tags = list(
            Tag.objects.annotate(n=Count("posts")).filter(n__gt=0).order_by("-n", "name")
        )
        self.total: int = _published().count()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(posts=self._posts, tags=self._tags, total=self.total)
        return context


class PostListView(LiveView):
    """Post archive with live search + tag filter (no page reload)."""

    template_name = "blog/post_list.html"
    login_required = False  # public blog archive

    def mount(self, request, **kwargs):
        self.query: str = ""
        self.tag_slug: str = kwargs.get("tag_slug", "") or ""
        self._refresh()

    def _filtered(self) -> List[Post]:
        qs = _published()
        if self.tag_slug:
            qs = qs.filter(tags__slug=self.tag_slug)
        if self.query:
            qs = qs.filter(
                Q(title__icontains=self.query)
                | Q(excerpt__icontains=self.query)
                | Q(content__icontains=self.query)
            )
        return list(qs[:60])

    def _refresh(self) -> None:
        self._posts = self._filtered()
        self._tags = list(
            Tag.objects.annotate(n=Count("posts")).filter(n__gt=0).order_by("-n", "name")
        )

    @event_handler()
    def search(self, value: str = "", **kwargs):
        """Live search-as-you-type (dj-input, debounced client-side)."""
        self.query = (value or "").strip()
        self._refresh()

    @event_handler()
    def filter_tag(self, tag: str = "", **kwargs):
        """Toggle a tag filter chip."""
        self.tag_slug = "" if self.tag_slug == tag else tag
        self._refresh()

    @event_handler()
    def clear_filters(self, **kwargs):
        self.query = ""
        self.tag_slug = ""
        self._refresh()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            posts=self._posts,
            tags=self._tags,
            query=self.query,
            tag_slug=self.tag_slug,
        )
        return context


class PostDetailView(LiveView):
    """Single post; body is rendered server-side from Markdown."""

    template_name = "blog/post_detail.html"
    login_required = False  # public post page

    def mount(self, request, **kwargs):
        slug = kwargs.get("slug", "")
        if not slug:
            # djust 的 SSE stream 把 /djust/sse/<uuid>/ 当作页面 URL 传给
            # dispatch_mount，resolve() 解析不到 slug，mount 会抛 Http404 并导致
            # 客户端报「Failed to load view」、点赞等事件失效。
            # EventSource 与 message POST 都带 Referer（真实文章页），据此兜底。
            match = re.search(r"/posts/([^/?#]+)", urlparse(request.META.get("HTTP_REFERER", "")).path)
            if match:
                slug = unquote(match.group(1))
        self._post = get_object_or_404(_published(), slug=slug)
        self.likes: int = self._post.likes

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        related = list(
            _published().exclude(pk=self._post.pk).order_by("-published_at")[:3]
        )
        context.update(post=self._post, likes=self.likes, related_posts=related)
        return context

    @event_handler()
    def like(self, **kwargs):
        self.likes += 1
        self._post.likes = self.likes
        self._post.save(update_fields=["likes"])


# 图床图片在文章里的引用：/media/images/<32hex>.<ext>，URL 恒定不变。
IMG_REF_RE = re.compile(r'/media/(images/[0-9a-f]{32}\.(?:png|jpg|gif|webp))', re.I)
UNCATEGORIZED = '__none__'


def _gallery_data():
    """按「引用图片的文章 → 文章标签」给图床图片归类。

    图片与文章不建外键：关系从正文里的 /media/ 引用反推，导入导出无需额外字段，
    文章改标签后相册自动跟着变。未被已发布文章引用的图片归入「未归档」。
    """
    refs: Dict[str, List[Dict[str, Any]]] = {}
    published = Post.objects.filter(status=Post.Status.PUBLISHED).prefetch_related('tags')
    for post in published:
        tags = [{'slug': t.slug, 'name': t.name} for t in post.tags.all()]
        seen = set()
        for match in IMG_REF_RE.finditer(post.content or ''):
            relpath = match.group(1).lower()
            if relpath in seen:
                continue
            seen.add(relpath)
            refs.setdefault(relpath, []).append({
                'title': post.title, 'url': post.get_absolute_url(), 'tags': tags,
            })

    items = []
    for img in Image.objects.all():
        origins = refs.get(img.relpath.lower(), [])
        tag_map = {}
        for ref in origins:
            for tag in ref['tags']:
                tag_map[tag['slug']] = tag['name']
        tags = [{'slug': s, 'name': n} for s, n in sorted(tag_map.items(), key=lambda x: x[1])]
        first = origins[0] if origins else None
        items.append({
            'id': str(img.id),
            'url': img.url,
            'name': img.name,
            'size_kb': round(img.size / 1024, 1),
            'date': timezone.localtime(img.uploaded_at).strftime('%Y.%m.%d'),
            'tags': tags,
            'tag_text': ' · '.join(t['name'] for t in tags) if tags else '未归档',
            'tag_pills': ''.join(
                '<span class="tag-pill">%s</span>' % escape(t['name']) for t in tags
            ),
            'origin': first['title'] if first else '',
            'origin_url': first['url'] if first else '',
            'caption': '%s · %s' % (img.name, first['title'] if first else '未归档'),
        })

    counts: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for item in items:
        if not item['tags']:
            counts[UNCATEGORIZED] = counts.get(UNCATEGORIZED, 0) + 1
        for tag in item['tags']:
            counts[tag['slug']] = counts.get(tag['slug'], 0) + 1
            names[tag['slug']] = tag['name']
    categories = [
        {'slug': slug, 'name': name, 'count': counts[slug]}
        for slug, name in sorted(names.items(), key=lambda x: (-counts[x[0]], x[1]))
    ]
    if counts.get(UNCATEGORIZED):
        categories.append({
            'slug': UNCATEGORIZED, 'name': '未归档', 'count': counts[UNCATEGORIZED],
        })
    return items, categories


class GalleryView(LiveView):
    """图床相册：按文章分类筛选，点击缩略图打开 djust ImageLightbox。"""

    template_name = "blog/gallery.html"
    login_required = False

    def mount(self, request, **kwargs):
        self.tag_slug: str = ""
        self.active: int = -1  # -1 = lightbox 关闭

    def _visible(self, items):
        if not self.tag_slug:
            return items
        if self.tag_slug == UNCATEGORIZED:
            return [i for i in items if not i['tags']]
        return [i for i in items if any(t['slug'] == self.tag_slug for t in i['tags'])]

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        items, categories = _gallery_data()
        visible = [dict(it, index=n) for n, it in enumerate(self._visible(items))]
        total = len(visible)
        # 筛选变化后旧索引可能越界，统一在这里收敛。
        if not 0 <= self.active < total:
            self.active = -1
        lightbox = ImageLightbox(
            images=[
                {'src': it['url'], 'alt': it['name'], 'caption': it['caption']}
                for it in visible
            ],
            active=max(self.active, 0),
            open=self.active >= 0,
            close_event='close_lightbox',
            navigate_event='lightbox_navigate',
            custom_class='gf-lightbox',
        )
        current_name = '全部'
        for cat in categories:
            if cat['slug'] == self.tag_slug:
                current_name = cat['name']
                break
        context.update(
            items=visible, categories=categories, tag_slug=self.tag_slug,
            total=total, all_count=len(items), lightbox_html=lightbox.render(),
            current_name=current_name,
        )
        return context

    @event_handler()
    def filter_gallery(self, tag: str = "", **kwargs):
        self.tag_slug = "" if self.tag_slug == tag else tag
        self.active = -1

    @event_handler()
    def open_lightbox(self, index: int = 0, **kwargs):
        try:
            self.active = int(index)
        except (TypeError, ValueError):
            self.active = 0

    @event_handler()
    def close_lightbox(self, **kwargs):
        self.active = -1

    @event_handler()
    def lightbox_navigate(self, value: int = 0, **kwargs):
        items, _ = _gallery_data()
        total = len(self._visible(items))
        if total:
            try:
                self.active = int(value) % total
            except (TypeError, ValueError):
                self.active = 0


def about(request):
    """关于页：纯静态内容，不需要 LiveView / SSE。"""
    return render(request, 'blog/about.html')
