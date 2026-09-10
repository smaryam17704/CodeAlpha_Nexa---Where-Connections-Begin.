from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from posts.models import Post

User = get_user_model()


def make_image(name='test.jpg'):
    tiny_gif = (
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc\x00\x00\x00,\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    )
    name = f"{name.rsplit('.', 1)[0]}.gif"
    return SimpleUploadedFile(name, tiny_gif, content_type='image/gif')


class SearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='searchtester', password='StrongPass123')
        self.other = User.objects.create_user(username='findme', password='StrongPass123')
        self.client.login(username='searchtester', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'a design post', 'image': make_image()})

    def test_people_search(self):
        resp = self.client.get(reverse('core:search'), {'q': 'findme'})
        self.assertContains(resp, 'findme')

    def test_post_search(self):
        resp = self.client.get(reverse('core:search'), {'q': 'design'})
        self.assertContains(resp, 'post-grid-item')

    def test_hashtag_search(self):
        self.client.post(reverse('posts:create'), {'caption': 'about #design work', 'image': make_image('d2.jpg')})
        resp = self.client.get(reverse('core:search'), {'q': 'design'})
        self.assertContains(resp, '#design')

    def test_search_results_are_paginated(self):
        for i in range(15):
            self.client.post(reverse('posts:create'), {'caption': f'design item {i}', 'image': make_image(f's{i}.jpg')})
        resp = self.client.get(reverse('core:search'), {'q': 'design'})
        self.assertContains(resp, 'posts_page=2')

    def test_empty_query_shows_prompt_not_results(self):
        resp = self.client.get(reverse('core:search'))
        self.assertContains(resp, 'Search Nexa')

    def test_no_results_state(self):
        resp = self.client.get(reverse('core:search'), {'q': 'zzz_nonexistent_zzz'})
        self.assertContains(resp, 'No results found')

    def test_private_account_posts_excluded_from_post_search_for_strangers(self):
        self.other.profile.visibility = 'private'
        self.other.profile.save()
        self.client.logout()
        self.client.login(username='findme', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'secret design post', 'image': make_image('priv.jpg')})
        self.client.logout()
        self.client.login(username='searchtester', password='StrongPass123')
        resp = self.client.get(reverse('core:search'), {'q': 'secret'})
        self.assertNotContains(resp, 'post-grid-item')


class ExploreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='exploretester', password='StrongPass123')
        self.client.login(username='exploretester', password='StrongPass123')

    def test_explore_returns_real_content(self):
        other = User.objects.create_user(username='creator', password='StrongPass123')
        self.client.logout()
        self.client.login(username='creator', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'explore me', 'image': make_image()})
        self.client.logout()
        self.client.login(username='exploretester', password='StrongPass123')
        resp = self.client.get(reverse('core:explore'))
        self.assertContains(resp, 'post-grid-item')

    def test_explore_paginates(self):
        other = User.objects.create_user(username='prolific', password='StrongPass123')
        self.client.logout()
        self.client.login(username='prolific', password='StrongPass123')
        for i in range(30):
            self.client.post(reverse('posts:create'), {'caption': f'item {i}', 'image': make_image(f'e{i}.jpg')})
        self.client.logout()
        self.client.login(username='exploretester', password='StrongPass123')
        resp = self.client.get(reverse('core:explore'))
        self.assertContains(resp, 'page=2')


class SettingsPersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='settingsuser', password='StrongPass123')
        self.client.login(username='settingsuser', password='StrongPass123')

    def test_theme_persists(self):
        self.client.post(reverse('core:update_theme'), {'theme': 'dark'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.theme_preference, 'dark')

    def test_notification_preferences_persist(self):
        self.client.post(reverse('core:update_notification_preferences'), {
            'notify_on_like': 'false', 'notify_on_comment': 'true', 'notify_on_follow': 'false',
        })
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.notify_on_like)
        self.assertTrue(self.user.profile.notify_on_comment)
        self.assertFalse(self.user.profile.notify_on_follow)

    def test_notification_preferences_persist_after_logout_login(self):
        self.client.post(reverse('core:update_notification_preferences'), {
            'notify_on_like': 'false', 'notify_on_comment': 'false', 'notify_on_follow': 'false',
        })
        self.client.logout()
        self.client.login(username='settingsuser', password='StrongPass123')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.notify_on_like)

    def test_privacy_setting_persists(self):
        self.client.post(reverse('core:update_privacy'), {'visibility': 'private'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.visibility, 'private')

    def test_privacy_setting_rejects_invalid_value(self):
        resp = self.client.post(reverse('core:update_privacy'), {'visibility': 'super-secret'})
        self.assertEqual(resp.status_code, 400)


class SecurityTests(TestCase):
    def test_csrf_enforced_on_post_endpoints(self):
        from django.test import Client
        strict_client = Client(enforce_csrf_checks=True)
        user = User.objects.create_user(username='csrftest', password='StrongPass123')
        strict_client.login(username='csrftest', password='StrongPass123')
        resp = strict_client.post(reverse('core:update_theme'), {'theme': 'dark'})
        self.assertEqual(resp.status_code, 403)

    def test_authentication_enforced_on_all_major_protected_routes(self):
        protected_urls = [
            reverse('core:home'), reverse('core:explore'), reverse('core:search'),
            reverse('core:activity'), reverse('core:settings'), reverse('posts:create'),
            reverse('social:saved_posts'), reverse('notifications:list'),
        ]
        for url in protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f'{url} should redirect unauthenticated users')
