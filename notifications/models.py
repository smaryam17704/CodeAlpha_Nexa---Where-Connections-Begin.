from django.conf import settings
from django.db import models

NOTIFICATION_TYPES = [
    ('like', 'Like'),
    ('comment', 'Comment'),
    ('follow', 'Follow'),
    ('follow_request', 'Follow request'),
    ('follow_accept', 'Follow accepted'),
]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='actions')
    notification_type = models.CharField(max_length=15, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    comment = models.ForeignKey('social.Comment', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    follow = models.ForeignKey('social.Follow', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'])]

    def __str__(self):
        return f'{self.actor} {self.notification_type} -> {self.recipient}'

    def verb(self):
        return {
            'like': 'liked your post',
            'comment': 'commented on your post',
            'follow': 'started following you',
            'follow_request': 'requested to follow you',
            'follow_accept': 'accepted your follow request',
        }.get(self.notification_type, '')
