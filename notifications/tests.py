from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification
from posts.models import Post

User = get_user_model()


def make_image(name='test.jpg'):
    tiny_gif = (
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc\x00\x00\x00,\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    )
    name = f"{name.rsplit('.', 1)[0]}.gif"
    return SimpleUploadedFile(name, tiny_gif, content_type='image/gif')


class NotificationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='StrongPass123')
        self.bob = User.objects.create_user(username='bob', password='StrongPass123')
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'hi', 'image': make_image()})
        self.post = Post.objects.get(author=self.alice)
        self.client.logout()
        self.client.login(username='bob', password='StrongPass123')

    def test_like_notification_generated(self):
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, actor=self.bob, notification_type='like').exists())

    def test_comment_notification_generated(self):
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'nice'})
        self.assertTrue(Notification.objects.filter(recipient=self.alice, actor=self.bob, notification_type='comment').exists())

    def test_follow_notification_generated(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, actor=self.bob, notification_type='follow').exists())

    def test_no_self_notification_on_own_like(self):
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertFalse(Notification.objects.filter(recipient=self.alice, actor=self.alice).exists())

    def test_unread_marked_read_on_visiting_list(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=False).count(), 1)
        self.client.get(reverse('notifications:list'))
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=False).count(), 0)

    def test_mark_all_read_endpoint(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=False).count(), 0)

    def test_notifications_are_paginated(self):
        for _ in range(25):
            u = User.objects.create_user(username=f'liker{_}', password='StrongPass123')
            from social.models import Like
            Like.objects.create(user=u, post=self.post)
            Notification.objects.create(recipient=self.alice, actor=u, notification_type='like', post=self.post)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.get(reverse('notifications:list'))
        self.assertContains(resp, 'page=2')
