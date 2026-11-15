from django.urls import path

from .views import GalleryView, HomeView, PostDetailView, PostListView, about

app_name = 'blog'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('about/', about, name='about'),
    path('gallery/', GalleryView.as_view(), name='gallery'),
    path('posts/', PostListView.as_view(), name='post_list'),
    path('posts/<slug:slug>/', PostDetailView.as_view(), name='post_detail'),
    path('tags/<slug:tag_slug>/', PostListView.as_view(), name='tag_detail'),
]
