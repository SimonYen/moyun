from django.utils import timezone

from djust.admin_ext import DjustModelAdmin, action, display, register

from .models import Post, Tag


@register(Tag)
class TagAdmin(DjustModelAdmin):
    list_display = ('name', 'slug', 'post_count')
    search_fields = ('name', 'slug')
    ordering = ('name',)

    @display(description='Posts')
    def post_count(self, obj: Tag) -> int:
        return obj.posts.count()


@register(Post)
class PostAdmin(DjustModelAdmin):
    list_display = ('title', 'author', 'status', 'tag_list', 'published_at')
    list_display_links = ('title',)
    list_filter = ('status', 'tags')
    search_fields = ('title', 'content', 'excerpt')
    ordering = ('-published_at', '-created_at')
    readonly_fields = ('created_at', 'updated_at', 'published_at', 'likes')
    actions = ['make_published', 'make_draft', 'delete_selected']
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'excerpt', 'content', 'tags', 'status'),
        }),
        ('Stats & timestamps', {
            'fields': ('likes', 'created_at', 'updated_at', 'published_at'),
        }),
    )

    @display(description='Tags')
    def tag_list(self, obj: Post) -> str:
        return ', '.join(tag.name for tag in obj.tags.all()) or '—'

    @action(description='Publish selected posts')
    def make_published(self, request, queryset) -> str:
        updated = queryset.filter(status=Post.Status.DRAFT).update(
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        return f'{updated} post(s) published.'

    @action(description='Unpublish selected posts')
    def make_draft(self, request, queryset) -> str:
        updated = queryset.filter(status=Post.Status.PUBLISHED).update(
            status=Post.Status.DRAFT,
        )
        return f'{updated} post(s) moved to draft.'
