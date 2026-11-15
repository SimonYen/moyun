import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


class Image(models.Model):
    """图床里的一张图片；文件落在 MEDIA_ROOT/images/，URL 稳定不变。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text='原始文件名')
    relpath = models.CharField(max_length=255, unique=True)
    mime = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='uploaded_images',
    )

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name

    @property
    def url(self):
        return settings.MEDIA_URL + self.relpath
