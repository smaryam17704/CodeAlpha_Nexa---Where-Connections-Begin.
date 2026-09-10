import re
import os
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError

from .validation import MEDIA_TYPES, validate_media_upload
HASHTAG_RE = re.compile(r'#(\w+)')


def post_media_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f'posts/{uuid4().hex}{suffix}'


class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'#{self.name}'

    def get_absolute_url(self):
        return reverse('posts:hashtag', kwargs={'name': self.name})

    @staticmethod
    def normalize(raw):
        return raw.strip().lstrip('#').lower()


class Post(models.Model):
    MEDIA_TYPE_CHOICES = [(media_type, media_type.title()) for media_type in MEDIA_TYPES]

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    caption = models.TextField(max_length=2200, blank=True)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, default='image')
    image = models.ImageField(upload_to=post_media_upload_to, blank=True, null=True)
    video = models.FileField(upload_to=post_media_upload_to, blank=True, null=True)
    audio = models.FileField(upload_to=post_media_upload_to, blank=True, null=True)
    document = models.FileField(upload_to=post_media_upload_to, blank=True, null=True)
    document_name = models.CharField(max_length=255, blank=True)
    media_size = models.PositiveBigIntegerField(blank=True, null=True)
    hashtags = models.ManyToManyField(Hashtag, blank=True, related_name='posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return f'Post({self.id}) by {self.author}'

    def get_absolute_url(self):
        return reverse('posts:detail', kwargs={'pk': self.pk})

    def clean(self):
        super().clean()
        media_fields = {
            'image': self.image,
            'video': self.video,
            'audio': self.audio,
            'document': self.document,
        }
        selected = media_fields.get(self.media_type)
        errors = {}
        if self.media_type not in MEDIA_TYPES:
            errors['media_type'] = 'Please select a supported media type.'
        elif not selected:
            errors[self.media_type] = f'Please select a {self.media_type} file.'
        else:
            try:
                validate_media_upload(self.media_type, selected)
            except ValidationError as exc:
                errors[self.media_type] = exc.messages
        for field_name, value in media_fields.items():
            if field_name != self.media_type and value:
                errors[field_name] = 'Only the file for the selected media type may be uploaded.'
        if errors:
            raise ValidationError(errors)

    @property
    def media_file(self):
        return getattr(self, self.media_type, None)

    @property
    def media_display_name(self):
        if self.media_type == 'document' and self.document_name:
            return self.document_name
        media_file = self.media_file
        return os.path.basename(media_file.name) if media_file else ''

    @property
    def media_extension(self):
        return Path(self.media_display_name).suffix.upper().lstrip('.')

    def save(self, *args, **kwargs):
        media_file = self.media_file
        if media_file:
            if self.media_type == 'document' and not self.document_name:
                self.document_name = os.path.basename(media_file.name)
            try:
                self.media_size = media_file.size
            except (OSError, ValueError):
                pass
        super().save(*args, **kwargs)

    def extract_and_set_hashtags(self):
        names = {Hashtag.normalize(t) for t in HASHTAG_RE.findall(self.caption)}
        names = {n for n in names if n}
        tag_objs = []
        for name in names:
            tag, _ = Hashtag.objects.get_or_create(name=name)
            tag_objs.append(tag)
        self.hashtags.set(tag_objs)

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def is_saved_by(self, user):
        if not user.is_authenticated:
            return False
        return self.saved_by.filter(user=user).exists()


def visible_posts_qs(user):
    """Posts queryset that respects profile privacy: excludes posts from
    private accounts unless the viewer is the author or an approved follower."""
    from django.db.models import Q
    from social.models import Follow
    if not user.is_authenticated:
        return Post.objects.filter(author__profile__visibility='public')
    following_ids = Follow.objects.filter(follower=user, status='accepted').values_list('following_id', flat=True)
    return Post.objects.filter(
        Q(author__profile__visibility='public') | Q(author=user) | Q(author_id__in=following_ids)
    )
