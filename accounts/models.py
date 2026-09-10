from django.conf import settings
from django.db import models
from django.urls import reverse


class Interest(models.Model):
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=80, blank=True)
    bio = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    interests = models.ManyToManyField(Interest, blank=True, related_name='profiles')
    onboarding_step = models.PositiveSmallIntegerField(default=0)
    onboarding_complete = models.BooleanField(default=False)
    theme_preference = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')],
        default='system',
    )
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')
    notify_on_like = models.BooleanField(default=True)
    notify_on_comment = models.BooleanField(default=True)
    notify_on_follow = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username

    def get_display_name(self):
        return self.display_name or self.user.username

    def get_absolute_url(self):
        return reverse('accounts:profile', kwargs={'username': self.user.username})

    @property
    def follower_count(self):
        return self.user.followers.filter(status='accepted').count()

    @property
    def following_count(self):
        return self.user.following.filter(status='accepted').count()

    @property
    def post_count(self):
        return self.user.posts.count()

    def is_private(self):
        return self.visibility == 'private'

    def can_be_viewed_by(self, viewer):
        """Server-side authorization: private profiles are only visible to
        the owner and to users the owner already follows back (i.e. approved followers)."""
        if not self.is_private():
            return True
        if not viewer.is_authenticated:
            return False
        if viewer == self.user:
            return True
        from social.models import Follow
        return Follow.objects.filter(follower=viewer, following=self.user, status='accepted').exists()
