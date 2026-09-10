from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification
from posts.models import Post
from social.models import Comment, Follow, Like, SavedPost

User = get_user_model()


def make_image(name='test.jpg'):
    tiny_gif = (
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc\x00\x00\x00,\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    )
    name = f"{name.rsplit('.', 1)[0]}.gif"
    return SimpleUploadedFile(name, tiny_gif, content_type='image/gif')


class SocialTestBase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='StrongPass123')
        self.bob = User.objects.create_user(username='bob', password='StrongPass123')
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'hello', 'image': make_image()})
        self.post = Post.objects.get(author=self.alice)
        self.client.logout()
        self.client.login(username='bob', password='StrongPass123')


class LikeTests(SocialTestBase):
    def test_like_works(self):
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['liked'])
        self.assertEqual(Like.objects.filter(post=self.post, user=self.bob).count(), 1)

    def test_unlike_works(self):
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertFalse(resp.json()['liked'])
        self.assertEqual(Like.objects.filter(post=self.post, user=self.bob).count(), 0)

    def test_duplicate_like_prevented_by_toggle(self):
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(Like.objects.filter(post=self.post, user=self.bob).count(), 1)

    def test_database_uniqueness_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=self.alice, post=self.post)
                Like.objects.create(user=self.alice, post=self.post)

    def test_like_notification_created_when_enabled(self):
        self.assertTrue(self.alice.profile.notify_on_like)
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type='like').exists())

    def test_like_notification_suppressed_when_disabled(self):
        self.alice.profile.notify_on_like = False
        self.alice.profile.save()
        self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertFalse(Notification.objects.filter(recipient=self.alice, notification_type='like').exists())


class CommentTests(SocialTestBase):
    def test_add_comment(self):
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'nice!'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Comment.objects.filter(post=self.post, author=self.bob, content='nice!').exists())

    def test_delete_own_comment(self):
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'temp'})
        comment = Comment.objects.get(post=self.post, author=self.bob)
        resp = self.client.post(reverse('social:delete_comment', kwargs={'pk': comment.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_cannot_delete_another_users_comment(self):
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'bob comment'})
        comment = Comment.objects.get(post=self.post, author=self.bob)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.post(reverse('social:delete_comment', kwargs={'pk': comment.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_malicious_comment_content_stored_and_rendered_safely(self):
        payload = '<script>alert("x")</script>'
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': payload})
        comment = Comment.objects.get(post=self.post, author=self.bob)
        self.assertEqual(comment.content, payload)  # stored verbatim
        resp = self.client.get(reverse('posts:detail', kwargs={'pk': self.post.pk}))
        # Django auto-escaping means the raw <script> tag must not appear unescaped in the HTML.
        self.assertNotContains(resp, '<script>alert("x")</script>')
        self.assertContains(resp, '&lt;script&gt;')

    def test_comment_notification_created_when_enabled(self):
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hey'})
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type='comment').exists())

    def test_comment_notification_suppressed_when_disabled(self):
        self.alice.profile.notify_on_comment = False
        self.alice.profile.save()
        self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hey'})
        self.assertFalse(Notification.objects.filter(recipient=self.alice, notification_type='comment').exists())

    def test_load_more_comments_endpoint_paginates(self):
        for i in range(15):
            Comment.objects.create(author=self.bob, post=self.post, content=f'comment {i}')
        resp = self.client.get(reverse('social:load_comments', kwargs={'pk': self.post.pk}), {'page': 1})
        data = resp.json()
        self.assertEqual(len(data['comments']), 10)
        self.assertTrue(data['has_next'])
        resp2 = self.client.get(reverse('social:load_comments', kwargs={'pk': self.post.pk}), {'page': 2})
        self.assertEqual(len(resp2.json()['comments']), 5)
        self.assertFalse(resp2.json()['has_next'])


class FollowTests(SocialTestBase):
    def test_follow_works(self):
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertTrue(resp.json()['following'])
        self.assertEqual(resp.json()['status'], 'accepted')
        self.assertTrue(Follow.objects.filter(follower=self.bob, following=self.alice, status='accepted').exists())

    def test_unfollow_works(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertFalse(resp.json()['following'])
        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.alice).exists())

    def test_duplicate_follow_prevented(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertEqual(Follow.objects.filter(follower=self.bob, following=self.alice).count(), 1)

    def test_self_follow_prevented(self):
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'bob'}))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.bob).exists())

    def test_follow_notification_suppressed_when_disabled(self):
        self.alice.profile.notify_on_follow = False
        self.alice.profile.save()
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertFalse(Notification.objects.filter(recipient=self.alice, notification_type='follow').exists())


class FollowRequestTests(SocialTestBase):
    """Private accounts must go through a pending follow-request workflow
    instead of becoming an approved follower immediately."""

    def setUp(self):
        super().setUp()
        self.alice.profile.visibility = 'private'
        self.alice.profile.save()

    def test_public_profile_follow_is_still_immediate(self):
        # Sanity check: the private-account workflow must not affect public accounts.
        self.alice.profile.visibility = 'public'
        self.alice.profile.save()
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertEqual(resp.json()['status'], 'accepted')
        self.assertTrue(resp.json()['following'])

    def test_private_profile_creates_pending_request(self):
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'pending')
        self.assertFalse(resp.json()['following'])
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        self.assertEqual(follow.status, 'pending')

    def test_pending_request_does_not_grant_follower_access(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertFalse(self.alice.profile.can_be_viewed_by(self.bob))
        self.assertEqual(self.alice.profile.follower_count, 0)

    def test_duplicate_pending_request_prevented(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.client.logout()
        self.client.login(username='bob', password='StrongPass123')
        # Calling again while pending cancels the request (toggle semantics),
        # it must not create a second row either way.
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertEqual(Follow.objects.filter(follower=self.bob, following=self.alice).count(), 0)

    def test_request_or_create_helper_is_idempotent_while_pending(self):
        # Calling the creation helper twice for the same pair must never
        # produce two rows — this is the actual "no duplicate pending
        # request" guarantee, independent of the toggle-button semantics.
        follow1, created1 = Follow.request_or_create(self.bob, self.alice)
        follow2, created2 = Follow.request_or_create(self.bob, self.alice)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(follow1.pk, follow2.pk)
        self.assertEqual(Follow.objects.filter(follower=self.bob, following=self.alice).count(), 1)

    def test_owner_can_accept_request(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.post(reverse('social:accept_follow_request', kwargs={'pk': follow.pk}))
        self.assertEqual(resp.status_code, 200)
        follow.refresh_from_db()
        self.assertEqual(follow.status, 'accepted')

    def test_accepted_request_becomes_valid_follower(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('social:accept_follow_request', kwargs={'pk': follow.pk}))
        self.assertTrue(self.alice.profile.can_be_viewed_by(self.bob))
        self.assertEqual(self.alice.profile.follower_count, 1)

    def test_owner_can_reject_request(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.post(reverse('social:reject_follow_request', kwargs={'pk': follow.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Follow.objects.filter(pk=follow.pk).exists())

    def test_rejected_requester_is_not_a_follower(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('social:reject_follow_request', kwargs={'pk': follow.pk}))
        self.assertFalse(self.alice.profile.can_be_viewed_by(self.bob))

    def test_only_target_owner_can_accept_or_reject(self):
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        follow = Follow.objects.get(follower=self.bob, following=self.alice)
        # bob (the requester, not the owner) tries to accept his own request.
        resp = self.client.post(reverse('social:accept_follow_request', kwargs={'pk': follow.pk}))
        self.assertEqual(resp.status_code, 404)
        follow.refresh_from_db()
        self.assertEqual(follow.status, 'pending')

    def test_pending_requester_cannot_access_restricted_content(self):
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        self.client.post(reverse('posts:create'), {'caption': 'private pic', 'image': make_image('priv.jpg')})
        private_post = Post.objects.filter(author=self.alice).latest('created_at')
        self.client.logout()
        self.client.login(username='bob', password='StrongPass123')
        self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        resp = self.client.get(reverse('posts:detail', kwargs={'pk': private_post.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_self_follow_request_prevented(self):
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'alice'}))
        self.assertEqual(resp.status_code, 400)

    def test_existing_showcase_style_follow_defaults_to_accepted(self):
        # Rows created directly via the ORM (as the showcase seed does) default
        # to accepted status, so pre-existing follows are not downgraded.
        carol = User.objects.create_user(username='carol', password='StrongPass123')
        follow = Follow.objects.create(follower=carol, following=self.alice)
        self.assertEqual(follow.status, 'accepted')
        self.assertTrue(self.alice.profile.can_be_viewed_by(carol))


class SavedPostTests(SocialTestBase):
    def test_save_works(self):
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertTrue(resp.json()['saved'])
        self.assertTrue(SavedPost.objects.filter(user=self.bob, post=self.post).exists())

    def test_unsave_works(self):
        self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertFalse(resp.json()['saved'])

    def test_saved_posts_are_user_specific(self):
        self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.client.logout()
        self.client.login(username='alice', password='StrongPass123')
        resp = self.client.get(reverse('social:saved_posts'))
        self.assertNotContains(resp, 'post-grid-item')  # alice has nothing saved


class PrivatePostAuthorizationTests(SocialTestBase):
    """Fix #2: server-side authorization for interactions with private posts.
    The UI may hide buttons, but the endpoints themselves must independently
    enforce that only the owner or an approved follower can like/save/comment."""

    def setUp(self):
        super().setUp()
        # self.post was created by alice while bob was the acting client in
        # SocialTestBase.setUp(); make alice's account private for these tests.
        self.alice.profile.visibility = 'private'
        self.alice.profile.save()
        self.stranger = User.objects.create_user(username='stranger', password='StrongPass123')
        self.approved_follower = User.objects.create_user(username='follower1', password='StrongPass123')
        Follow.objects.create(follower=self.approved_follower, following=self.alice, status='accepted')
        self.pending_requester = User.objects.create_user(username='pending1', password='StrongPass123')
        Follow.objects.create(follower=self.pending_requester, following=self.alice, status='pending')

    def _login(self, username):
        self.client.logout()
        self.client.login(username=username, password='StrongPass123')

    # ---- LIKE ----
    def test_owner_can_like_own_private_post(self):
        self._login('alice')
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['liked'])

    def test_approved_follower_can_like_private_post(self):
        self._login('follower1')
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['liked'])

    def test_stranger_cannot_like_private_post(self):
        self._login('stranger')
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.stranger).exists())

    def test_pending_requester_cannot_like_private_post(self):
        self._login('pending1')
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.pending_requester).exists())

    # ---- SAVE ----
    def test_owner_can_save_own_private_post(self):
        self._login('alice')
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['saved'])

    def test_approved_follower_can_save_private_post(self):
        self._login('follower1')
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['saved'])

    def test_stranger_cannot_save_private_post(self):
        self._login('stranger')
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(SavedPost.objects.filter(post=self.post, user=self.stranger).exists())

    def test_pending_requester_cannot_save_private_post(self):
        self._login('pending1')
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(SavedPost.objects.filter(post=self.post, user=self.pending_requester).exists())

    # ---- COMMENT ----
    def test_owner_can_comment_on_own_private_post(self):
        self._login('alice')
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hi'})
        self.assertEqual(resp.status_code, 200)

    def test_approved_follower_can_comment_on_private_post(self):
        self._login('follower1')
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hi'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Comment.objects.filter(post=self.post, author=self.approved_follower).exists())

    def test_stranger_cannot_comment_on_private_post(self):
        self._login('stranger')
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hi'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Comment.objects.filter(post=self.post, author=self.stranger).exists())

    def test_pending_requester_cannot_comment_on_private_post(self):
        self._login('pending1')
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'hi'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Comment.objects.filter(post=self.post, author=self.pending_requester).exists())

    # ---- PUBLIC POST REGRESSION: none of the above should affect public posts ----
    def test_public_post_like_unaffected(self):
        self.alice.profile.visibility = 'public'
        self.alice.profile.save()
        self._login('stranger')
        resp = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['liked'])

    def test_public_post_save_unaffected(self):
        self.alice.profile.visibility = 'public'
        self.alice.profile.save()
        self._login('stranger')
        resp = self.client.post(reverse('social:toggle_save', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['saved'])

    def test_public_post_comment_unaffected(self):
        self.alice.profile.visibility = 'public'
        self.alice.profile.save()
        self._login('stranger')
        resp = self.client.post(reverse('social:add_comment', kwargs={'pk': self.post.pk}), {'content': 'nice'})
        self.assertEqual(resp.status_code, 200)
