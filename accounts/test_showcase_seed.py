from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Profile
from notifications.models import Notification
from posts.models import Post
from social.models import Comment, Follow, Like, SavedPost


class ShowcaseSeedCommandTests(TestCase):
    def test_dry_run_reports_the_full_showcase_plan(self):
        output = StringIO()
        call_command("seed_showcase", "--dry-run", stdout=output)
        self.assertIn("users=250", output.getvalue())
        self.assertIn("posts=720", output.getvalue())
        self.assertIn("image_posts=600", output.getvalue())
        self.assertIn("video_posts=50", output.getvalue())

    def test_small_seed_creates_database_backed_records_and_real_media(self):
        call_command(
            "seed_showcase", "--users", "12", "--posts", "24",
            "--follows", "30", "--likes", "80", "--comments", "40", "--saves", "12",
            stdout=StringIO(),
        )
        self.assertEqual(Profile.objects.count(), 12)
        self.assertEqual(Post.objects.count(), 24)
        self.assertEqual(Follow.objects.count(), 30)
        self.assertEqual(Like.objects.count(), 80)
        self.assertEqual(Comment.objects.count(), 40)
        self.assertEqual(SavedPost.objects.count(), 12)
        self.assertGreater(Notification.objects.count(), 0)
        self.assertEqual(Profile.objects.filter(avatar__endswith=".jpg").count(), 12)
        self.assertGreater(Post.objects.filter(media_type="image").count(), 0)
        self.assertTrue(all(Path(profile.avatar.path).is_file() for profile in Profile.objects.all()))
        self.assertTrue(all(Path(post.media_file.path).is_file() for post in Post.objects.all()))
        call_command("audit_showcase_media", stdout=StringIO())