"""URL configuration for django_blog."""
from django.urls import include, path
from django.views.generic import RedirectView

from djust.admin_ext import site as admin_site
from djust.sse import sse_urlpatterns

from blog.admin_account import admin_account
from blog.admin_dashboard import admin_dashboard
from blog.admin_data import data_page, export_blog, import_blog
from blog.admin_editor import admin_post_edit
from blog.admin_lists import (
    admin_logout, admin_post_delete, admin_post_list,
    admin_tag_delete, admin_tag_edit, admin_tag_list,
)
from blog.admin_login import admin_login
from imagehost.views import (
    delete_image, export_images, import_images, serve_media, upload_image,
)

# djust admin 残留页面（LiveView 登录页等）的标题也统一用站名
admin_site.site_title = '墨韵 · 后台'
admin_site.site_header = '墨韵 · 后台'

urlpatterns = [
    # 浏览器默认请求根路径的 favicon，指到静态资源（后台页面未逐个写 link）
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico')),
    # 运行时媒体文件（ASGIStaticFilesHandler 只服务 /static/）
    path('media/<path:path>', serve_media),
    # 原生页面优先于 admin_site 内的 LiveView 页面
    # 列表/标签/删除页也改走原生：djust 的 admin LiveView 在 SSE mount 鉴权失败时
    # 会 navigate 到登录页，而已登录用户访问原生登录页又会跳回 /admin/（自动跳转）。
    path('admin/logout/', admin_logout),
    path('admin/login/', admin_login),
    path('admin/', admin_dashboard),
    path('admin/account/', admin_account),
    path('admin/blog/post/add/', admin_post_edit),
    path('admin/blog/post/', admin_post_list),
    path('admin/blog/post/<int:object_id>/delete/', admin_post_delete),
    path('admin/blog/post/<path:object_id>/change/', admin_post_edit),
    path('admin/blog/tag/add/', admin_tag_edit),
    path('admin/blog/tag/', admin_tag_list),
    path('admin/blog/tag/<int:object_id>/change/', admin_tag_edit),
    path('admin/blog/tag/<int:object_id>/delete/', admin_tag_delete),
    path('admin/data/', data_page),
    path('admin/data/blog/export/', export_blog),
    path('admin/data/blog/import/', import_blog),
    path('admin/data/images/export/', export_images),
    path('admin/data/images/import/', import_images),
    path('admin/data/images/upload/', upload_image),
    path('admin/data/images/<uuid:image_id>/delete/', delete_image),
    path('admin/', admin_site.urls),
    path('djust/api/', include('djust.api.urls')),
    path('djust/', include((sse_urlpatterns, 'djust_sse'))),
    path('_theming/', include('djust.theming.urls')),
    path('', include('blog.urls')),
]
