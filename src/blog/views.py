import re
from typing import Any, Dict
from urllib.parse import unquote, urlparse

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import escape
from django.utils.text import Truncator

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


def _tags_with_counts():
    return list(
        Tag.objects.annotate(n=Count("posts")).filter(n__gt=0).order_by("-n", "name")
    )


# LiveView 的实例属性会被 djust 整个 msgpack 序列化进内存 state，每个会话一份，
# 且每次 SSE 事件都要 load → 反序列化 → 执行 handler → 重渲染 → diff → save。
# 早期把 self._posts（含完整 Markdown 正文）和 self._tags 存在实例上，
# 实测首页/文章列表 state 达 118–135KB（框架阈值 100KB），是交互迟钝的主因。
# 现在实例上只留 query / tag_slug / slug 这类标量，列表一律在渲染时现查：
# SQLite 本地查询只要几毫秒，远比序列化上百 KB 便宜。
class HomeView(LiveView):
    """Landing page: hero + latest posts + tag cloud."""

    template_name = "blog/home.html"

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            posts=list(_published()[:6]),
            tags=_tags_with_counts(),
            total=_published().count(),
        )
        return context


# 文章列表每批加载几篇。桌面三列网格正好一行，手机端约一屏；
# 想减少滚动时的 SSE 往返，把这个常量调大即可。
POSTS_PER_PAGE = 3


def _post_card(post):
    """列表卡片只需要这几个字段，绝不要把 Post 实例放进 context。

    djust 会把整个 render context 序列化进 LiveView state（实测 6 篇 Post
    对象含 Markdown 正文约 24KB）。无限滚动会累积条目，若继续塞 model 实例，
    加载几十篇就会重新触发 Large LiveView state 警告并拖慢每次 SSE 事件。
    这里投影成纯标量 dict，每篇只有几百字节。
    """
    return {
        'pk': post.pk,
        'title': post.title,
        'url': post.get_absolute_url(),
        'date': (
            timezone.localtime(post.published_at).strftime('%Y.%m.%d')
            if post.published_at else ''
        ),
        'excerpt': Truncator(post.excerpt or post.content or '').chars(140),
        'tags': [t.name for t in post.tags.all()],
        'author': str(post.author),
    }


class PostListView(LiveView):
    """文章归档：实时搜索 + 标签筛选 + 滚动到底自动加载下一批。

    分页状态只有一个整数 loaded（已加载条数）。列表永远由数据库现查，
    不进实例属性，也不把 Post 对象放进 context / state。
    """

    template_name = "blog/post_list.html"
    login_required = False  # public blog archive

    def mount(self, request, **kwargs):
        self.query: str = ""
        self.tag_slug: str = kwargs.get("tag_slug", "") or ""
        self.loaded: int = POSTS_PER_PAGE

    def _filtered_qs(self):
        qs = _published()
        if self.tag_slug:
            qs = qs.filter(tags__slug=self.tag_slug)
        if self.query:
            qs = qs.filter(
                Q(title__icontains=self.query)
                | Q(excerpt__icontains=self.query)
                | Q(content__icontains=self.query)
            )
        # 一篇文章可挂多个标签，join 可能产生重复行，重复 data-key 会让
        # VDOM 降级成位置 diff。
        return qs.distinct()

    def _reset_paging(self):
        """筛选条件变了，回到第一批（等价于 stream_reset）。"""
        self.loaded = POSTS_PER_PAGE

    @event_handler()
    def load_more(self, **kwargs):
        """滚到底时由 #load-more-btn 的 dj-click 发过来，再取一批。

        已经到底时直接返回，不做任何改动，避免无效的 SSE 重渲染。
        """
        total = self._filtered_qs().count()
        if self.loaded >= total:
            return
        self.loaded = min(self.loaded + POSTS_PER_PAGE, total)

    @event_handler()
    def search(self, value: str = "", **kwargs):
        """Live search-as-you-type (dj-input, debounced client-side)."""
        self.query = (value or "").strip()
        self._reset_paging()

    @event_handler()
    def filter_tag(self, tag: str = "", **kwargs):
        """Toggle a tag filter chip."""
        self.tag_slug = "" if self.tag_slug == tag else tag
        self._reset_paging()

    @event_handler()
    def clear_filters(self, **kwargs):
        self.query = ""
        self.tag_slug = ""
        self._reset_paging()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        qs = self._filtered_qs()
        total = qs.count()
        # 每轮渲染都重新给出「已加载的全部条目」：卡片带 data-key，
        # VDOM 做 keyed diff，已有卡片保留 DOM 节点，只把新卡片 patch 进去。
        cards = [_post_card(p) for p in qs[:self.loaded]]

        # 用普通 context 变量，不用 streams.posts / dj-stream 容器：
        # djust 1.2.8 的 StreamsMixin 增量 op 在 SSE 下没有传输通道，
        # 客户端对 stream 容器是「只追加不删除」，筛选切换时旧卡片清不掉。
        # 普通列表 + data-key 由 VDOM 做 keyed diff，增删都正确。
        # 每轮重发的是已加载的全部卡片（纯标量 dict，几十篇也只有十几 KB），
        # 已有节点因 data-key 被保留，只有新增节点会被 patch 进 DOM。
        context = super().get_context_data(**kwargs)
        context.update(
            posts=cards,
            tags=_tags_with_counts(),
            query=self.query,
            tag_slug=self.tag_slug,
            total=total,
            shown=len(cards),
            has_more=self.loaded < total,
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
            # 客户端报「Failed to load view」。EventSource 与 message POST 都带
            # Referer（真实文章页），据此兜底。
            match = re.search(r"/posts/([^/?#]+)", urlparse(request.META.get("HTTP_REFERER", "")).path)
            if match:
                slug = unquote(match.group(1))
        # 只存 slug，不把整篇 Post（含 Markdown 正文）塞进 state
        self.slug = slug

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        post = get_object_or_404(_published(), slug=self.slug)
        related = list(
            _published().exclude(pk=post.pk).order_by("-published_at")[:3]
        )
        context.update(post=post, related_posts=related)
        return context


# 图床图片在文章里的引用：/media/images/<32hex>.<ext>，URL 恒定不变。
IMG_REF_RE = re.compile(r'/media/(images/[0-9a-f]{32}\.(?:png|jpg|gif|webp))', re.I)
UNCATEGORIZED = '__none__'


def _gallery_data():
    """按「引用图片的文章 → 文章标签」给图床图片归类。

    图片与文章不建外键：关系从正文里的 /media/ 引用反推，导入导出无需额外字段，
    文章改标签后相册自动跟着变。未被已发布文章引用的图片归入「未归档」。
    """
    refs: Dict[str, list] = {}
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
