# Nexa — Connect Beyond.

Nexa is a full-stack social networking platform: a home feed, multimedia posts with captions and hashtags, likes, comments, follows, saved posts, notifications, search, explore/discovery, profiles, onboarding, and light/dark themes — all backed by a real relational database with no mock or hardcoded data.

---

## 1. Overview

Nexa lets people create accounts, build a profile, follow others, publish image, video, audio, or document posts with captions and hashtags, and interact through likes, comments, and saves. Every number you see in the UI (like counts, follower counts, comment counts, notification badges) is computed live from the database.

**Product pillars:** Connect · Create · Discover · Engage

## 2. Features

- **Authentication** — registration, login, logout, and a full email-based password reset flow (Django's built-in auth, console email backend for local dev).
- **Onboarding** — 4-step flow: profile setup (name, username, avatar, bio) → interest selection → suggested people → completion.
- **Home feed** — chronological posts from people you follow, with a discovery fallback for brand-new accounts so the feed is never a blank page. The fallback respects account privacy (see below).
- **Posts** — create with an image, video, audio file, or document (JPG/JPEG/PNG/WEBP/GIF, MP4/WEBM/MOV, MP3/WAV/M4A, PDF/DOCX/XLSX/TXT/CSV), plus a caption and auto-extracted `#hashtags`; edit your own caption and delete with a confirmation modal that traps keyboard focus.
- **Likes & comments** — one like per user per post (DB-enforced), inline comment threads with delete-your-own permission checks. Comments load 10 at a time with a real "Load more comments" control backed by server-side pagination — a post's comments are never all sent to the browser at once.
- **Follow system** — follow/unfollow, followers/following lists (paginated), self-follow and duplicate-follow prevented at the database level.
- **Profiles** — avatar, bio, stats, post grid; edit your own profile with username-uniqueness validation.
- **Private accounts** — a real, database-backed profile-visibility setting (Public/Private). When private, a stranger's profile page, followers/following lists, and individual posts are blocked server-side (not just hidden with CSS) unless they're an approved follower or the owner.
- **Saved posts** — a private, per-user saved collection.
- **Notifications** — generated for likes, comments, and follows, with unread badges and mark-all-read — but only when the recipient's own notification preferences allow that type. Paginated.
- **Notification preferences** — real, database-backed per-type toggles (likes / comments / follows) in Settings. Disabling a type suppresses only the notification, never the underlying action.
- **Search** — people, posts, and hashtags, each independently paginated, from real queries against the database. Post results respect account privacy.
- **Explore** — popular posts (ranked by real like/comment counts, paginated), suggested creators, trending hashtags. Excludes private accounts' posts for non-followers.
- **Hashtag pages** — every `#tag` is a real, clickable, paginated, browsable page.
- **Settings** — profile management, appearance (light/dark/system, persisted per-user), real notification-preference switches, a real private-account switch, logout.
- **Light & dark themes** — independently designed (not simply inverted), persisted to the user's profile and a cookie, applied before first paint to avoid a flash of the wrong theme.
- **Responsive layout** — three-column desktop shell, condensed tablet layout, single-column mobile layout with a bottom tab bar.
- **Toasts, modals, empty/error/loading states** — no `alert()` dialogs, no blank screens. The delete-confirmation modal has a real keyboard focus trap (Tab/Shift+Tab cycle inside it, focus returns to the triggering element on close).
- **XSS-safe comment rendering** — comments added or loaded via JavaScript are built with safe DOM APIs (`textContent`/`createElement`), never `innerHTML` string interpolation of user content. Server-rendered comments rely on Django's default auto-escaping. Covered by an automated test that submits a `<script>` payload and asserts it's never rendered unescaped.
- **Security** — CSRF protection, login-required views, server-side ownership checks on every edit/delete, server-side validation on every form, server-side privacy enforcement (not just hidden UI).
- **Automated tests** — a real Django test suite (104 tests) covering auth, ownership, likes/comments/follows/saves, notification-preference enforcement, privacy enforcement, pagination, search, explore, and CSRF.

## 3. Technology Stack

- **Frontend:** HTML5, CSS3 (custom design-token system, no framework), vanilla JavaScript (`fetch()` + JSON endpoints, no jQuery/React/Vue)
- **Backend:** Django 6 (Python), server-rendered templates + JSON endpoints for dynamic interaction
- **Database:** SQLite via Django ORM (default `db.sqlite3`, easy to swap for Postgres/MySQL later by changing `DATABASES` in `settings.py`)
- **Media:** Django's local file storage for avatars and post media, with content validation, configurable size limits, generated storage names, and type-specific feed/detail rendering

## 4. Project Architecture

Nexa is split into five Django apps, each with a single responsibility:

| App | Responsibility |
|---|---|
| `core` | Landing page, search, explore, activity, settings, theme endpoint, shared template tags |
| `accounts` | Auth, onboarding, `Profile`/`Interest` models, profile views |
| `posts` | `Post`/`Hashtag` models, feed, create/edit/delete, hashtag pages |
| `social` | `Follow`/`Like`/`Comment`/`SavedPost` models and their AJAX endpoints |
| `notifications` | `Notification` model, notification list, mark-read endpoint |

```
Nexa/
  manage.py
  requirements.txt
  .env.example
  README.md
  nexa_project/        # Django project settings, root urls
  core/                # landing, search, explore, activity, settings
  accounts/            # auth, onboarding, profile
  posts/               # posts, hashtags, feed
  social/              # likes, comments, follows, saves
  notifications/       # notifications
  templates/           # all HTML templates (base.html, app_base.html, per-app dirs)
  static/
    css/                # tokens.css, base.css, shell.css, components.css, landing.css
    js/                 # theme.js, toast.js, nexa.js
    img/nexa-logo.png   # official brand asset
  media/                # user-uploaded avatars & post images (created at runtime)
```

## 5. Requirements / Prerequisites

- Python 3.10+
- pip

## 6. Installation

```bash
# 1. Unzip and enter the project
cd Nexa

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## 7. Environment Configuration

```bash
cp .env.example .env
```

Then export the values in your shell (or use a tool like `django-environ`/`python-dotenv` if you prefer auto-loading — Nexa reads them as plain `os.environ` values):

```bash
export NEXA_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
export NEXA_DEBUG=True
```

If you skip this step, Nexa falls back to a working local development key, so setup still runs — just don't reuse that key in any real deployment.

## 8. Database Setup & Migrations

```bash
python manage.py migrate
```

## 9. Seed the Interest Categories

Onboarding step 2 (interest selection) reads from the `Interest` table. Seed it once:

```bash
python manage.py seed_interests
```

## 10. Showcase Community

This archive includes a populated synthetic community with local avatars, image/video/audio/document posts, follows, likes, comments, saves, hashtags, and notifications. It is demo/showcase data only — not real users — created through the Django ORM at approximately this scale:

- 250 users / 250 profiles
- 720 posts (600 image, 50 video, 35 audio, 35 document)
- 1,300 follows
- 35,000 likes
- 3,000 comments
- 400 saves
- 25 hashtags
- 10,676 notifications

It can be audited without changing the UI:

```bash
python manage.py seed_showcase --dry-run
python manage.py audit_showcase_media
```

The seed command is deterministic and does not overwrite existing data by default. Use `python manage.py seed_showcase --reset` only when you intentionally want to replace the showcase community. Showcase accounts use the password `ShowcasePass!2026` for local demonstration purposes.

## 11. Create a Superuser (for `/admin/`)

```bash
python manage.py createsuperuser
```

## 12. Static & Media Files

For local development, Django serves static and media files automatically when `DEBUG=True` (already wired up in `nexa_project/urls.py`). No extra step is required. For a production deployment you would additionally run:

```bash
python manage.py collectstatic
```

## 13. Running the Development Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/**.

## 14. How to Use Nexa

1. Open the landing page and click **Sign Up**.
2. Complete the 4-step onboarding (profile → interests → suggested people → done).
3. From **Create** in the sidebar, publish an image, video, audio, or document post with a caption and `#hashtags`.
4. Create a second account in another browser/incognito window, follow the first account, then like/comment/save its post — you'll see a real notification appear.
5. Try **Explore** and **Search** to see hashtag and discovery features backed by live data.
6. Open **Settings → Appearance** to switch between Light, Dark, and System themes — your choice is saved to your profile.
7. Open **Settings → Notifications** and turn off, say, Likes — have your second account like the first account's post again, and confirm no like notification is generated (the like itself still counts).
8. Open **Settings → Privacy** and switch your account to Private — log in as the second account and confirm its profile, followers list, and posts are now blocked until it follows you back.
9. On a post with several comments, confirm the **"Load more comments"** button appears once there are more than 10 and fetches the rest without reloading the page.

## 15. Project Structure Notes

- `templates/base.html` is the root template (theme bootstrap, toast region, global JS/CSS).
- `templates/app_base.html` extends it and adds the authenticated app shell (sidebar, mobile nav, right rail) via `{% block shell_content %}`.
- `static/js/nexa.js` handles all AJAX interactions (like, save, follow, comment, load-more-comments, delete-confirmation modal with a real focus trap) using `fetch()` and Django's CSRF cookie — no page reloads for these actions. User-generated content inserted by JS is built with `textContent`/`createElement`, never `innerHTML` string interpolation.
- `core/templatetags/nexa_extras.py` provides `{% suggested_users %}`, `{% trending_hashtags %}`, and the hashtag-linkifying filter used across templates.
- `accounts.Profile.can_be_viewed_by(user)` is the single source of truth for privacy enforcement, reused across profile view, followers/following, post detail, feed, explore, search, and hashtag pages.

## 16. Important Configuration

- `EMAIL_BACKEND` is set to Django's **console backend** in `settings.py` — password-reset emails print to the terminal running `runserver` instead of being sent over SMTP. Point `EMAIL_BACKEND`/`EMAIL_HOST*` at a real provider (e.g. SendGrid, SES, Postmark) before deploying.
- `ALLOWED_HOSTS = ['*']` is set for local development convenience — restrict this before deploying.
- Uploaded media is validated server-side for its selected type, extension, recognizable content, dangerous-file signatures, and configurable size limits in `posts/validation.py`. Defaults are 8MB for images, 100MB for videos, 50MB for audio, and 25MB for documents.

## 17. Testing

Nexa ships with a real, checked-in Django automated test suite — **104 tests** across all five apps
(76 original tests plus 28 dedicated privacy/security tests), covering:

- Registration (valid data, duplicate username, invalid data), login, logout, protected-page redirects
- Profile creation/editing, username uniqueness, and profile-privacy enforcement (private profiles
  blocked for strangers, visible to approved followers and the owner)
- Post create/edit/delete with ownership enforcement (owner vs. non-owner)
- Hashtag extraction and hashtag-page pagination
- Likes: like/unlike, the database uniqueness constraint (verified via a direct `IntegrityError`),
  and notification suppression when the recipient has disabled like notifications
- Comments: add/delete, ownership on delete, server-paginated "load more" (10 per page), and a
  dedicated XSS test that submits a `<script>` payload and asserts it's stored verbatim but never
  rendered unescaped in the page
- Follows: follow/unfollow, duplicate-follow and self-follow prevention, notification suppression
- Saved posts: save/unsave, and that one user's saved collection never appears for another user
- Notifications: generation for like/comment/follow, no self-notifications, read/unread behavior,
  mark-all-read, pagination
- Search (people/posts/hashtags, each paginated, privacy-aware) and Explore (real content, pagination)
- Multimedia creation and rendering for image, video, audio, and document posts, plus invalid-extension,
  executable, mismatched-type, and oversized-upload rejection
- Settings persistence: theme, notification preferences, and privacy setting all persist across
  requests (including a logout/login cycle)
- Security: CSRF is actually enforced (checked with `enforce_csrf_checks=True`, not assumed), and
  every major protected route redirects an unauthenticated request

Run it yourself:

```bash
python manage.py test
```

All 104 tests were run and passed at the time this project was packaged — `check`,
`makemigrations --check`, and `collectstatic` were also run clean, and both `.js` files were
syntax-checked with `node --check`.

**What this still doesn't cover:** the test suite runs entirely against Django's server-rendered
HTML (via the test client). It does not exercise JavaScript execution, click interactions, CSS
rendering, or responsive layout in an actual browser — that environment isn't available where this
project was built. The JS was written carefully and reviewed, and its syntax was verified, but "runs
correctly in a real browser" has not been independently confirmed the way the backend behavior has.
If that matters for your use case, run the app locally and click through it yourself before treating
it as fully browser-verified.

## 18. Troubleshooting

- **`ModuleNotFoundError: No module named 'django'`** — make sure your virtual environment is activated and `pip install -r requirements.txt` succeeded.
- **Images/avatars don't load** — confirm `DEBUG=True` while developing locally (media is only auto-served in debug mode), and that the `media/` folder is writable.
- **"That port is already in use"** — run `python manage.py runserver 8001` (or any free port).
- **Interest checkboxes are empty during onboarding** — run `python manage.py seed_interests`.
- **Styles look unstyled/broken** — hard-refresh (static files are versionless in dev); in production remember to run `collectstatic`.
- **Password reset email doesn't arrive** — by design in local dev; check the terminal running `runserver`, the reset link is printed there.

---

Nexa · Connect Beyond.
