from datetime import timedelta
from pathlib import Path
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.models import Interest, Profile
from notifications.models import Notification
from posts.models import Hashtag, Post
from social.models import Comment, Follow, Like, SavedPost


User = get_user_model()
SHOWCASE_EMAIL_DOMAIN = "@showcase.nexa.local"
PASSWORD_HASH = None

HASHTAGS = [
    "travel", "photography", "books", "food", "design", "technology",
    "fitness", "nature", "lifestyle", "creativity", "study", "architecture",
    "coding", "weekend", "coffee", "wellness", "music", "gaming", "art",
    "streetphoto", "reading", "homemade", "citywalks", "workspace", "hiking",
]

FIRST_NAMES = [
    "Maya", "Arjun", "Nora", "Adrian", "Zoya", "Leila", "Ishan", "Mira",
    "Theo", "Sana", "Ravi", "Elena", "Noah", "Aanya", "Luca", "Tara",
    "Amara", "Kabir", "Iris", "Dev", "Anika", "Jonah", "Meera", "Owen",
    "Kiara", "Eli", "Freya", "Neil", "Ari", "Rhea", "Mateo", "Diya",
    "Samira", "Kian", "Alina", "Yusuf", "Cleo", "Nikhil", "Eva", "Aarav",
    "Lina", "Ezra", "Pia", "Rohan", "Mina", "Soren", "Aisha", "Theo",
    "Nia", "Julian",
]
LAST_NAMES = [
    "Fern", "Mehta", "Hart", "Vale", "Rao", "Khan", "Brooks", "Sen",
    "Marlow", "Patel", "Stone", "Bose", "Rivera", "Shah", "Ellis", "Das",
    "Wong", "Nair", "Morris", "Kapoor", "Lane", "Iyer", "Frost", "Roy",
    "Bennett", "Dutta", "Hayes", "Sethi", "Cole", "Menon", "Reed", "Malik",
    "Cruz", "Sarkar", "Dean", "Joshi", "Flynn", "Bhat", "Moore", "Pillai",
    "Grant", "Thomas", "Kaur", "Mistry", "Young", "Ghosh", "Kim", "Singh",
    "Davis", "Verma",
]

INTEREST_NAMES = [
    "Technology", "Design", "Photography", "Music", "Travel", "Gaming",
    "Movies", "Books", "Food", "Fitness", "Art", "Science",
]
TOPICS = [
    ("travel", "a train window, a quiet lane, a weekend map, a hill trail"),
    ("food", "a warm plate, a market stall, a recipe, a tiny bakery"),
    ("photography", "a frame, a shadow, a reflection, a late afternoon"),
    ("technology", "a small build, a desk setup, a useful shortcut, a new tool"),
    ("books", "a chapter, a margin note, a reading corner, a borrowed novel"),
    ("fitness", "a morning run, a stretch, a long walk, a steady routine"),
    ("art", "a sketchbook, a color study, a work in progress, a new texture"),
    ("nature", "a balcony plant, a monsoon sky, a garden path, a wildflower"),
    ("lifestyle", "a slow morning, a Sunday reset, a favorite corner, a small ritual"),
    ("architecture", "a doorway, an old facade, a clean line, a sunlit staircase"),
]
PLACES = [
    "the old market", "a blue-hour street", "the riverside", "a neighborhood café",
    "the studio window", "a quiet rooftop", "the library steps", "the park after rain",
    "a coastal road", "the corner table",
]
CAPTION_FRAGMENTS = [
    "Keeping this one for the days that need a little more color.",
    "The best details were the ones I almost walked past.",
    "A small reminder that ordinary afternoons can be worth saving.",
    "Not a grand plan, just a good hour and a camera nearby.",
    "I came back with a full notebook and no regrets.",
    "Somewhere between practical and playful is my favorite place to work.",
    "This is the kind of pause that makes the rest of the week feel possible.",
    "A little messy, very local, and exactly what I was looking for.",
]
COMMENT_STARTERS = [
    "The light in this is lovely.", "Adding this place to my list.",
    "That detail in the corner is perfect.", "This made me want to go outside.",
    "What did you use for this?", "I like how calm this feels.",
    "The colors are so good together.", "This is a great weekend idea.",
    "Saving this for later.", "That sounds like a story in itself.",
    "The texture here is wonderful.", "This feels very much like today.",
]


def _slug(value):
    return "".join(character.lower() if character.isalnum() else "." for character in value).strip(".")


def _distribution(total):
    if total == 720:
        return 600, 50, 35, 35
    document = round(total * 0.05)
    audio = round(total * 0.05)
    video = round(total * 0.07)
    return max(0, total - document - audio - video), video, audio, document


class Command(BaseCommand):
    help = "Populate Nexa with a deterministic synthetic showcase community."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=250)
        parser.add_argument("--posts", type=int, default=720)
        parser.add_argument("--follows", type=int, default=1300)
        parser.add_argument("--likes", type=int, default=35000)
        parser.add_argument("--comments", type=int, default=3000)
        parser.add_argument("--saves", type=int, default=400)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        counts = {key: options[key] for key in ("users", "posts", "follows", "likes", "comments", "saves")}
        if any(value < 0 for value in counts.values()):
            raise CommandError("Showcase counts cannot be negative.")
        image_count, video_count, audio_count, document_count = _distribution(counts["posts"])
        message = (
            "showcase plan: users={users} profiles={users} posts={posts} "
            "image_posts={images} video_posts={videos} audio_posts={audio} "
            "document_posts={documents} follows={follows} likes={likes} "
            "comments={comments} saves={saves}"
        ).format(
            images=image_count,
            videos=video_count,
            audio=audio_count,
            documents=document_count,
            **counts,
        )
        if options["dry_run"]:
            self.stdout.write(message)
            return

        existing = User.objects.filter(email__endswith=SHOWCASE_EMAIL_DOMAIN)
        if existing.exists() and not options["reset"]:
            self.stdout.write(self.style.WARNING(
                "Showcase data already exists; use --reset to replace it. No changes made."
            ))
            return
        if options["reset"]:
            self._reset_showcase()
        result = self._seed(counts, image_count, video_count, audio_count, document_count)
        self.stdout.write(self.style.SUCCESS(
            "Seeded showcase: " + ", ".join(f"{key}={value}" for key, value in result.items())
        ))

    def _reset_showcase(self):
        showcase_users = User.objects.filter(email__endswith=SHOWCASE_EMAIL_DOMAIN)
        deleted_users = showcase_users.count()
        showcase_users.delete()
        Hashtag.objects.filter(name__in=HASHTAGS, posts__isnull=True).delete()
        self.stdout.write(f"Removed {deleted_users} prior showcase users.")

    def _seed(self, counts, image_count, video_count, audio_count, document_count):
        rng = random.Random(20260910)
        now = timezone.now()
        base_time = now - timedelta(days=120)
        media_root = Path("media")

        with transaction.atomic():
            interests = self._ensure_interests()
            users = self._create_users(counts["users"])
            profiles = self._create_profiles(users, interests, media_root, rng)
            posts = self._create_posts(
                users, counts["posts"], image_count, video_count, audio_count,
                document_count, base_time, media_root,
            )
            hashtags = self._create_hashtags(posts)
            follows = self._create_follows(users, counts["follows"], base_time)
            likes = self._create_likes(users, posts, counts["likes"], base_time)
            comments = self._create_comments(users, posts, counts["comments"], base_time)
            saves = self._create_saves(users, posts, counts["saves"], base_time)
            notifications = self._create_notifications(follows, likes, comments)
        return {
            "users": len(users), "profiles": len(profiles), "posts": len(posts),
            "hashtags": hashtags, "follows": follows, "likes": likes,
            "comments": comments, "saves": saves, "notifications": notifications,
        }

    def _ensure_interests(self):
        return [
            Interest.objects.get_or_create(name=name, defaults={"icon": ""})[0]
            for name in INTEREST_NAMES
        ]

    def _create_users(self, count):
        global PASSWORD_HASH
        if PASSWORD_HASH is None:
            from django.contrib.auth.hashers import make_password
            PASSWORD_HASH = make_password("ShowcasePass!2026")
        users = []
        used = set()
        for index in range(count):
            first = FIRST_NAMES[index % len(FIRST_NAMES)]
            last = LAST_NAMES[(index * 7 + index // len(FIRST_NAMES)) % len(LAST_NAMES)]
            base = _slug(f"{first}.{last}")
            username = base
            suffix = 2
            while username in used:
                username = f"{base}.{suffix}"
                suffix += 1
            used.add(username)
            users.append(User(
                username=username,
                first_name=first,
                last_name=last,
                email=f"{username}{SHOWCASE_EMAIL_DOMAIN}",
                password=PASSWORD_HASH,
                is_active=True,
            ))
        return User.objects.bulk_create(users, batch_size=500)

    def _create_profiles(self, users, interests, media_root, rng):
        profiles = []
        for index, user in enumerate(users):
            profile = Profile(
                user=user,
                display_name=f"{user.first_name} {user.last_name}",
                bio=self._bio(index),
                avatar=f"avatars/showcase_avatar_{index + 1:03d}.jpg",
                onboarding_step=4,
                onboarding_complete=True,
                theme_preference=("dark" if index % 9 == 0 else "system"),
                visibility=("private" if index % 17 == 0 else "public"),
            )
            profiles.append(profile)
        profiles = Profile.objects.bulk_create(profiles, batch_size=500)
        through = Profile.interests.through
        links = []
        for index, profile in enumerate(profiles):
            count = 1 + (index % 4)
            for offset in range(count):
                links.append(through(profile_id=profile.id, interest_id=interests[(index + offset * 3) % len(interests)].id))
        through.objects.bulk_create(links, ignore_conflicts=True, batch_size=500)
        return profiles

    def _bio(self, index):
        bios = [
            "Collecting good light, useful ideas, and recipes worth repeating.",
            "Making room for small adventures between ordinary deadlines.",
            "Designer, list-maker, and enthusiastic walker of side streets.",
            "Reading slowly, building often, and trying to leave things better.",
            "Notes from a curious corner of the internet.",
            "Mostly here for thoughtful work and very good coffee.",
            "A quiet archive of places, plates, pages, and projects.",
            "Learning in public, one sketch and one question at a time.",
        ]
        return "" if index % 23 == 0 else bios[index % len(bios)]

    def _create_posts(self, users, total, image_count, video_count, audio_count, document_count, base_time, media_root):
        posts = []
        media_types = (["image"] * image_count + ["video"] * video_count +
                       ["audio"] * audio_count + ["document"] * document_count)
        for index in range(total):
            media_type = media_types[index]
            topic, subject_options = TOPICS[index % len(TOPICS)]
            subject = subject_options.split(", ")[(index * 3) % 4]
            caption = self._caption(index, topic, subject)
            created = base_time + timedelta(minutes=index * 17 + (index * index) % 91)
            post = Post(
                author=users[(index * 11 + index // 9) % len(users)],
                caption=caption,
                media_type=media_type,
                created_at=created,
                updated_at=created,
            )
            if media_type == "image":
                post.image = f"posts/showcase_image_{index + 1:03d}.jpg"
            elif media_type == "video":
                post.video = f"posts/showcase/videos/showcase_video_{index - image_count + 1:03d}.mp4"
            elif media_type == "audio":
                post.audio = f"posts/showcase/audio/showcase_audio_{index - image_count - video_count + 1:03d}.wav"
            else:
                number = index - image_count - video_count - audio_count + 1
                post.document = f"posts/showcase/documents/showcase_document_{number:03d}.pdf"
                post.document_name = f"Nexa field notes {number:03d}.pdf"
            media_path = Path(media_root) / str(post.media_file)
            post.media_size = media_path.stat().st_size if media_path.exists() else None
            posts.append(post)
        return Post.objects.bulk_create(posts, batch_size=500)

    def _caption(self, index, topic, subject):
        place = PLACES[(index * 5) % len(PLACES)]
        ending = CAPTION_FRAGMENTS[index % len(CAPTION_FRAGMENTS)]
        styles = [
            f"{subject.title()} near {place}. {ending}",
            f"A note from {place}: {subject} and a little time to notice it. {ending}",
            f"Today’s favorite detail: {subject} at {place}. {ending}",
            f"Somewhere in the middle of {place}, I found {subject}. {ending}",
        ]
        caption = styles[index % len(styles)]
        if index % 3 != 1:
            caption += f" #{topic} #{HASHTAGS[(index * 7 + 4) % len(HASHTAGS)]}"
        if index % 11 == 0:
            caption += f" #{HASHTAGS[(index * 13 + 9) % len(HASHTAGS)]}"
        return caption

    def _create_hashtags(self, posts):
        tag_objects = {name: Hashtag.objects.get_or_create(name=name)[0] for name in HASHTAGS}
        through = Post.hashtags.through
        links = []
        for index, post in enumerate(posts):
            names = [HASHTAGS[index % len(HASHTAGS)]]
            if index % 3 != 1:
                names.append(HASHTAGS[(index * 7 + 4) % len(HASHTAGS)])
            if index % 11 == 0:
                names.append(HASHTAGS[(index * 13 + 9) % len(HASHTAGS)])
            for name in set(names):
                links.append(through(post_id=post.id, hashtag_id=tag_objects[name].id))
        through.objects.bulk_create(links, ignore_conflicts=True, batch_size=1000)
        return len(tag_objects)

    def _create_follows(self, users, target, base_time):
        rows, seen = [], set()
        cursor = 0
        while len(rows) < target and cursor < target * 20:
            follower = (cursor * 17 + 3) % len(users)
            following = (cursor * 29 + 11 + cursor // 13) % len(users)
            cursor += 1
            if follower == following or (follower, following) in seen:
                continue
            seen.add((follower, following))
            rows.append(Follow(follower=users[follower], following=users[following],
                               created_at=base_time + timedelta(minutes=cursor * 19)))
        return len(Follow.objects.bulk_create(rows, batch_size=1000))

    def _create_likes(self, users, posts, target, base_time):
        rows, seen = [], set()
        cursor = 0
        while len(rows) < target and cursor < target * 30:
            user_index = (cursor * 31 + 7) % len(users)
            post_index = (cursor * 47 + cursor // 19) % len(posts)
            cursor += 1
            key = (user_index, post_index)
            if users[user_index].id == posts[post_index].author_id or key in seen:
                continue
            seen.add(key)
            rows.append(Like(user=users[user_index], post=posts[post_index],
                             created_at=base_time + timedelta(minutes=cursor * 3)))
        return len(Like.objects.bulk_create(rows, batch_size=2000))

    def _create_comments(self, users, posts, target, base_time):
        rows = []
        for index in range(target):
            post = posts[(index * 23 + index // 7) % len(posts)]
            author = users[(index * 31 + 9) % len(users)]
            topic = TOPICS[post.id % len(TOPICS)][0]
            content = f"{COMMENT_STARTERS[index % len(COMMENT_STARTERS)]} {topic.title()} is a good fit for this."
            rows.append(Comment(
                author=author, post=post, content=content[:500],
                created_at=base_time + timedelta(minutes=index * 11 + 4),
            ))
        return len(Comment.objects.bulk_create(rows, batch_size=2000))

    def _create_saves(self, users, posts, target, base_time):
        rows, seen = [], set()
        cursor = 0
        while len(rows) < target and cursor < target * 30:
            user_index = (cursor * 19 + 4) % len(users)
            post_index = (cursor * 43 + 2) % len(posts)
            cursor += 1
            key = (user_index, post_index)
            if key in seen:
                continue
            seen.add(key)
            rows.append(SavedPost(user=users[user_index], post=posts[post_index],
                                  created_at=base_time + timedelta(minutes=cursor * 23)))
        return len(SavedPost.objects.bulk_create(rows, batch_size=1000))

    def _create_notifications(self, follows_count, likes_count, comments_count):
        # Notification rows are made from persisted activity in a second pass below.
        rows = []
        for index, follow in enumerate(Follow.objects.order_by("id")):
            if index % 3 == 0:
                rows.append(Notification(
                    recipient=follow.following, actor=follow.follower,
                    notification_type="follow",
                    created_at=follow.created_at,
                ))
        for index, like in enumerate(Like.objects.select_related("post").order_by("id")):
            if index % 4 == 0 and like.post.author_id != like.user_id:
                rows.append(Notification(
                    recipient=like.post.author, actor=like.user,
                    notification_type="like", post=like.post,
                    created_at=like.created_at,
                ))
        for index, comment in enumerate(Comment.objects.select_related("post").order_by("id")):
            if index % 2 == 0 and comment.post.author_id != comment.author_id:
                rows.append(Notification(
                    recipient=comment.post.author, actor=comment.author,
                    notification_type="comment", post=comment.post, comment=comment,
                    created_at=comment.created_at,
                ))
        return len(Notification.objects.bulk_create(rows, batch_size=2000))