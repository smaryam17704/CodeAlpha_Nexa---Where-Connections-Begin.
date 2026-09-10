from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from posts.models import Hashtag, Post

User = get_user_model()


def make_image(name='test.jpg'):
    # Minimal valid 1x1 GIF bytes, served with an image/jpeg content_type is fine for
    # Django's ImageField validation which only inspects the actual pixel data via Pillow.
    tiny_gif = (
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc\x00\x00\x00,\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    )
    name = f"{name.rsplit('.', 1)[0]}.gif"
    return SimpleUploadedFile(name, tiny_gif, content_type='image/gif')


def make_media(media_type, name=None):
    if media_type == 'video':
        name = name or 'clip.mp4'
        content = b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2'
        content_type = 'video/mp4'
    elif media_type == 'audio':
        name = name or 'sound.wav'
        content = b'RIFF\x24\x00\x00\x00WAVEfmt '
        content_type = 'audio/wav'
    elif media_type == 'document':
        name = name or 'notes.txt'
        content = b'Nexa multimedia document\n'
        content_type = 'text/plain'
    else:
        return make_image(name or 'test.gif')
    return SimpleUploadedFile(name, content, content_type=content_type)


class PostCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='StrongPass123')
        self.client.login(username='alice', password='StrongPass123')

    def test_authenticated_user_can_create_post(self):
        resp = self.client.post(reverse('posts:create'), {
            'caption': 'Hello #nexa world', 'image': make_image(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Post.objects.filter(author=self.user).exists())

    def test_hashtag_extracted_and_linked(self):
        self.client.post(reverse('posts:create'), {
            'caption': 'Testing #nexa and #ConnectBeyond', 'image': make_image(),
        })
        post = Post.objects.get(author=self.user)
        names = set(post.hashtags.values_list('name', flat=True))
        self.assertEqual(names, {'nexa', 'connectbeyond'})

    def test_unauthenticated_user_cannot_create_post(self):
        self.client.logout()
        resp = self.client.post(reverse('posts:create'), {
            'caption': 'nope', 'image': make_image(),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)
        self.assertFalse(Post.objects.filter(caption='nope').exists())

    def test_multimedia_posts_store_the_selected_media_field(self):
        for media_type in ('video', 'audio', 'document'):
            response = self.client.post(reverse('posts:create'), {
                'media_type': media_type,
                media_type: make_media(media_type),
                'caption': f'{media_type} #nexa',
            })
            self.assertEqual(response.status_code, 302)
            post = Post.objects.get(media_type=media_type)
            self.assertEqual(post.media_type, media_type)
            self.assertTrue(getattr(post, media_type))
            self.assertEqual(post.caption, f'{media_type} #nexa')
            self.assertTrue(post.hashtags.filter(name='nexa').exists())

    def test_feed_renders_each_multimedia_type_with_the_correct_element(self):
        for media_type in ('video', 'audio', 'document'):
            self.client.post(reverse('posts:create'), {
                'media_type': media_type,
                media_type: make_media(media_type),
            })
        response = self.client.get(reverse('posts:feed'))
        self.assertContains(response, '<video', html=False)
        self.assertContains(response, '<audio', html=False)
        self.assertContains(response, 'post-document-card')
        self.assertNotIn('<img class="post-media" src="/media/posts/', response.content.decode())

    def test_post_detail_renders_document_actions(self):
        self.client.post(reverse('posts:create'), {
            'media_type': 'document',
            'document': make_media('document', 'brief.txt'),
        })
        post = Post.objects.get(media_type='document')
        response = self.client.get(reverse('posts:detail', kwargs={'pk': post.pk}))
        self.assertContains(response, 'post-document-card')
        self.assertContains(response, 'Open')
        self.assertContains(response, 'Download')

    def test_profile_grid_uses_a_media_thumbnail_for_non_images(self):
        self.client.post(reverse('posts:create'), {
            'media_type': 'audio',
            'audio': make_media('audio'),
        })
        response = self.client.get(reverse('accounts:profile', kwargs={'username': self.user.username}))
        self.assertContains(response, 'post-thumb-fallback')
        self.assertContains(response, 'AUDIO')

    def test_unsupported_extension_is_rejected(self):
        response = self.client.post(reverse('posts:create'), {
            'media_type': 'image',
            'image': SimpleUploadedFile('payload.exe', b'MZ executable', content_type='application/octet-stream'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(author=self.user).exists())
        self.assertContains(response, 'valid image', status_code=200)

    def test_mismatched_media_type_is_rejected(self):
        response = self.client.post(reverse('posts:create'), {
            'media_type': 'video',
            'image': make_image(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(author=self.user).exists())
        self.assertContains(response, 'does not match', status_code=200)

    @override_settings(NEXA_IMAGE_MAX_SIZE=1)
    def test_oversized_file_is_rejected(self):
        response = self.client.post(reverse('posts:create'), {
            'media_type': 'image',
            'image': make_image(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(author=self.user).exists())
        self.assertContains(response, 'too large', status_code=200)


class PostOwnershipTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='StrongPass123')
        self.intruder = User.objects.create_user(username='intruder', password='StrongPass123')
        self.client.login(username='owner', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'mine', 'image': make_image()})
        self.post = Post.objects.get(author=self.owner)
        self.client.logout()

    def test_owner_can_edit(self):
        self.client.login(username='owner', password='StrongPass123')
        resp = self.client.post(reverse('posts:edit', kwargs={'pk': self.post.pk}), {'caption': 'updated'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, 'updated')

    def test_non_owner_cannot_edit(self):
        self.client.login(username='intruder', password='StrongPass123')
        self.client.post(reverse('posts:edit', kwargs={'pk': self.post.pk}), {'caption': 'hacked'}, follow=True)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, 'mine')

    def test_owner_can_delete(self):
        self.client.login(username='owner', password='StrongPass123')
        resp = self.client.post(reverse('posts:delete', kwargs={'pk': self.post.pk}),
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.client.login(username='intruder', password='StrongPass123')
        resp = self.client.post(reverse('posts:delete', kwargs={'pk': self.post.pk}),
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())


class HashtagPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tagger', password='StrongPass123')
        self.client.login(username='tagger', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'about #django', 'image': make_image()})

    def test_hashtag_page_shows_tagged_posts(self):
        resp = self.client.get(reverse('posts:hashtag', kwargs={'name': 'django'}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'post-grid-item')
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)

    def test_hashtag_page_paginates(self):
        for i in range(15):
            self.client.post(reverse('posts:create'), {'caption': f'post {i} #django', 'image': make_image(f'p{i}.jpg')})
        resp = self.client.get(reverse('posts:hashtag', kwargs={'name': 'django'}))
        self.assertContains(resp, 'page=2')
