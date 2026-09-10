from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from posts.models import Hashtag, Post, visible_posts_qs
from social.models import Comment, Follow, Like, SavedPost

User = get_user_model()


def landing(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    stats = {
        'user_count': User.objects.count(),
        'post_count': Post.objects.count(),
    }
    return render(request, 'core/landing.html', {'stats': stats})


def home_redirect(request):
    from posts.views import home_feed
    return home_feed(request)


@login_required
def explore(request):
    popular_posts_qs = visible_posts_qs(request.user).exclude(author=request.user).annotate(
        like_total=Count('likes', distinct=True), comment_total=Count('comments', distinct=True)
    ).order_by('-like_total', '-comment_total', '-created_at').select_related(
        'author', 'author__profile')
    paginator = Paginator(popular_posts_qs, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    trending_hashtags = Hashtag.objects.annotate(
        post_total=Count('posts')
    ).filter(post_total__gt=0).order_by('-post_total')[:10]

    following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    suggested_creators = User.objects.exclude(
        id=request.user.id
    ).exclude(id__in=following_ids).annotate(
        post_total=Count('posts')
    ).order_by('-post_total')[:8]

    return render(request, 'core/explore.html', {
        'page_obj': page_obj,
        'trending_hashtags': trending_hashtags,
        'suggested_creators': suggested_creators,
    })


@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    people_page = Paginator([], 1).get_page(1)
    posts_page = Paginator([], 1).get_page(1)
    hashtags_page = Paginator([], 1).get_page(1)
    if query:
        people_qs = User.objects.filter(
            Q(username__icontains=query) | Q(profile__display_name__icontains=query)
        ).select_related('profile').order_by('username')
        posts_qs = visible_posts_qs(request.user).filter(caption__icontains=query).select_related(
            'author', 'author__profile')
        hashtags_qs = Hashtag.objects.filter(name__icontains=Hashtag.normalize(query))

        people_page = Paginator(people_qs, 10).get_page(request.GET.get('people_page'))
        posts_page = Paginator(posts_qs, 12).get_page(request.GET.get('posts_page'))
        hashtags_page = Paginator(hashtags_qs, 15).get_page(request.GET.get('tags_page'))

    return render(request, 'core/search.html', {
        'query': query, 'people_page': people_page, 'posts_page': posts_page, 'hashtags_page': hashtags_page,
    })


@login_required
def activity(request):
    user = request.user
    events = []
    for p in Post.objects.filter(author=user).order_by('-created_at')[:15]:
        events.append({'type': 'post', 'timestamp': p.created_at, 'post': p})
    for c in Comment.objects.filter(author=user).select_related('post').order_by('-created_at')[:15]:
        events.append({'type': 'comment', 'timestamp': c.created_at, 'comment': c})
    for l in Like.objects.filter(user=user).select_related('post').order_by('-created_at')[:15]:
        events.append({'type': 'like', 'timestamp': l.created_at, 'post': l.post})
    for f in Follow.objects.filter(follower=user).select_related('following__profile').order_by('-created_at')[:15]:
        events.append({'type': 'follow', 'timestamp': f.created_at, 'target': f.following})
    for s in SavedPost.objects.filter(user=user).select_related('post').order_by('-created_at')[:15]:
        events.append({'type': 'save', 'timestamp': s.created_at, 'post': s.post})

    events.sort(key=lambda e: e['timestamp'], reverse=True)
    return render(request, 'core/activity.html', {'events': events[:40]})


@login_required
def settings_view(request):
    return render(request, 'core/settings.html')


@login_required
@require_POST
def update_theme(request):
    theme = request.POST.get('theme', 'system')
    if theme not in ('light', 'dark', 'system'):
        theme = 'system'
    profile = request.user.profile
    profile.theme_preference = theme
    profile.save(update_fields=['theme_preference'])
    response = JsonResponse({'success': True, 'theme': theme})
    response.set_cookie('nexa_theme', theme, max_age=60 * 60 * 24 * 365)
    return response


@login_required
@require_POST
def update_notification_preferences(request):
    profile = request.user.profile
    profile.notify_on_like = request.POST.get('notify_on_like') == 'true'
    profile.notify_on_comment = request.POST.get('notify_on_comment') == 'true'
    profile.notify_on_follow = request.POST.get('notify_on_follow') == 'true'
    profile.save(update_fields=['notify_on_like', 'notify_on_comment', 'notify_on_follow'])
    return JsonResponse({
        'success': True,
        'notify_on_like': profile.notify_on_like,
        'notify_on_comment': profile.notify_on_comment,
        'notify_on_follow': profile.notify_on_follow,
    })


@login_required
@require_POST
def update_privacy(request):
    visibility = request.POST.get('visibility', 'public')
    if visibility not in ('public', 'private'):
        return JsonResponse({'error': 'Invalid visibility value.'}, status=400)
    profile = request.user.profile
    profile.visibility = visibility
    profile.save(update_fields=['visibility'])
    return JsonResponse({'success': True, 'visibility': profile.visibility})
