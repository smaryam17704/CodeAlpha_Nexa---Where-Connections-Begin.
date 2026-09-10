from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from social.models import Follow
from .forms import PostCreateForm, PostEditForm
from .models import Hashtag, Post, visible_posts_qs


@login_required
def home_feed(request):
    following_ids = Follow.objects.filter(follower=request.user, status='accepted').values_list('following_id', flat=True)
    feed_qs = Post.objects.filter(
        Q(author_id__in=following_ids) | Q(author=request.user)
    ).select_related('author', 'author__profile').prefetch_related('hashtags').distinct()

    has_following_content = feed_qs.exists()
    if not has_following_content:
        # Discovery fallback so a brand new account isn't looking at a totally blank page.
        # Respects privacy: private accounts are excluded unless already followed.
        feed_qs = visible_posts_qs(request.user).exclude(author=request.user).select_related(
            'author', 'author__profile').prefetch_related('hashtags')

    paginator = Paginator(feed_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'posts/feed.html', {
        'page_obj': page_obj,
        'is_discovery_fallback': not has_following_content,
    })


@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            post.extract_and_set_hashtags()
            messages.success(request, 'Your post has been published.')
            return redirect('posts:detail', pk=post.pk)
    else:
        form = PostCreateForm()
    return render(request, 'posts/create.html', {'form': form})


from django.core.exceptions import PermissionDenied


from django.core.paginator import Paginator


@login_required
def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('author', 'author__profile'), pk=pk)
    if not post.author.profile.can_be_viewed_by(request.user):
        raise PermissionDenied("This account is private.")
    comments_qs = post.comments.select_related('author', 'author__profile')
    paginator = Paginator(comments_qs, 10)
    comments_page = paginator.get_page(1)
    return render(request, 'posts/detail.html', {
        'post': post,
        'comments': comments_page,
        'has_more_comments': comments_page.has_next(),
    })


@login_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        messages.error(request, 'You can only edit your own posts.')
        return redirect('posts:detail', pk=pk)
    if request.method == 'POST':
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            post.extract_and_set_hashtags()
            messages.success(request, 'Post updated.')
            return redirect('posts:detail', pk=pk)
    else:
        form = PostEditForm(instance=post)
    return render(request, 'posts/edit.html', {'form': form, 'post': post})


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        return JsonResponse({'error': 'You can only delete your own posts.'}, status=403)
    post.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    messages.success(request, 'Post deleted.')
    return redirect('accounts:profile', username=request.user.username)


@login_required
def hashtag_detail(request, name):
    hashtag = get_object_or_404(Hashtag, name=Hashtag.normalize(name))
    posts_qs = visible_posts_qs(request.user).filter(hashtags=hashtag).select_related(
        'author', 'author__profile').order_by('-created_at')
    paginator = Paginator(posts_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'posts/hashtag.html', {'hashtag': hashtag, 'page_obj': page_obj})
