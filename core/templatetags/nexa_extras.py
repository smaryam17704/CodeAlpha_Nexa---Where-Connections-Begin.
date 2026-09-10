import re
from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.safestring import mark_safe
from django.utils.html import escape

from posts.models import Hashtag
from social.models import Follow

register = template.Library()
User = get_user_model()

HASHTAG_RE = re.compile(r'(#\w+)')


@register.simple_tag
def suggested_users(user, limit=5):
    if not user.is_authenticated:
        return []
    following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    qs = User.objects.exclude(id=user.id).exclude(id__in=following_ids).select_related('profile')
    interest_ids = user.profile.interests.values_list('id', flat=True)
    if interest_ids:
        matched = qs.filter(profile__interests__in=interest_ids).distinct()[:limit]
        if matched:
            return matched
    return qs.order_by('-date_joined')[:limit]


@register.simple_tag
def trending_hashtags(limit=6):
    return Hashtag.objects.annotate(post_total=Count('posts')).filter(
        post_total__gt=0).order_by('-post_total')[:limit]


@register.filter
def linkify_hashtags(text):
    def replace(match):
        tag = match.group(1)
        name = tag[1:].lower()
        return f'<a href="/posts/tag/{name}/" class="hashtag">{escape(tag)}</a>'
    escaped = escape(text)
    linked = HASHTAG_RE.sub(replace, str(escaped))
    return mark_safe(linked)


@register.filter
def initial(value):
    return value[:1].upper() if value else '?'


@register.filter
def is_liked_by(post, user):
    return post.is_liked_by(user)


@register.filter
def is_saved_by(post, user):
    return post.is_saved_by(user)
