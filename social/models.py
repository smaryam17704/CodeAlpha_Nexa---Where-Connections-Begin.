from django.conf import settings
from django.db import models
from django.db.models import Q, F, CheckConstraint


class Follow(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_ACCEPTED, 'Accepted')]

    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACCEPTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['follower', 'following'], name='unique_follow'),
            CheckConstraint(condition=~Q(follower=F('following')), name='no_self_follow'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.follower} -> {self.following} ({self.status})'

    def is_pending(self):
        return self.status == self.STATUS_PENDING

    def is_accepted(self):
        return self.status == self.STATUS_ACCEPTED

    @staticmethod
    def request_or_create(follower, target):
        """Create an accepted Follow immediately for a public target, or a
        pending follow request for a private target. This is a no-op
        (returns the existing row) if any relationship already exists —
        callers that need toggle/unfollow semantics should check for an
        existing row themselves before calling this. Returns (follow, created).
        """
        existing = Follow.objects.filter(follower=follower, following=target).first()
        if existing:
            return existing, False
        status = Follow.STATUS_PENDING if target.profile.is_private() else Follow.STATUS_ACCEPTED
        follow = Follow.objects.create(follower=follower, following=target, status=status)
        return follow, True


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_like'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} likes {self.post_id}'


class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, related_name='comments')
    content = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['post', 'created_at'])]

    def __str__(self):
        return f'{self.author}: {self.content[:30]}'


class SavedPost(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_saved_post'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} saved {self.post_id}'
