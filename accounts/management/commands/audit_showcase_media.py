from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, UnidentifiedImageError

from accounts.models import Profile
from posts.models import Post


class Command(BaseCommand):
    help = "Audit local media referenced by the showcase database."

    def handle(self, *args, **options):
        missing = []
        invalid = []
        counts = {"image": 0, "video": 0, "audio": 0, "document": 0, "avatars": 0}
        for profile in Profile.objects.filter(user__email__endswith="@showcase.nexa.local"):
            path = self._path(profile.avatar.name if profile.avatar else "")
            counts["avatars"] += 1
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(f"profile:{profile.user_id}:{path}")
        for post in Post.objects.filter(author__email__endswith="@showcase.nexa.local"):
            field = post.media_file
            path = self._path(field.name if field else "")
            counts[post.media_type] = counts.get(post.media_type, 0) + 1
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(f"post:{post.id}:{path}")
                continue
            try:
                self._validate(post.media_type, path)
            except (OSError, ValueError, UnidentifiedImageError) as exc:
                invalid.append(f"post:{post.id}:{path} ({exc})")
        if missing or invalid:
            raise CommandError(f"media audit failed: missing={len(missing)} invalid={len(invalid)}")
        self.stdout.write(self.style.SUCCESS(
            "media audit passed: " + ", ".join(f"{key}={value}" for key, value in counts.items())
        ))

    def _path(self, name):
        return Path(settings.MEDIA_ROOT) / name

    def _validate(self, media_type, path):
        signature = path.read_bytes()[:12]
        if media_type == "image":
            with Image.open(path) as image:
                if image.width < 32 or image.height < 32:
                    raise ValueError("image dimensions are too small")
                image.verify()
        elif media_type == "video" and b"ftyp" not in path.read_bytes()[:64]:
            raise ValueError("missing MP4 signature")
        elif media_type == "audio" and signature[:4] != b"RIFF":
            raise ValueError("missing WAV signature")
        elif media_type == "document" and signature[:4] != b"%PDF":
            raise ValueError("missing PDF signature")