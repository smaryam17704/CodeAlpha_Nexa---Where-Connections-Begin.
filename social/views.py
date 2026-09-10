from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from notifications.models import Notification
from posts.models import Post
from .models import Comment, Follow, Like, SavedPost

User = get_user_model()


@login_required
@require_POST
def toggle_like(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not post.author.profile.can_be_viewed_by(request.user):
        return JsonResponse({'error': 'This post is private.'}, status=403)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if post.author != request.user and post.author.profile.notify_on_like:
            Notification.objects.create(recipient=post.author, actor=request.user,
                                         notification_type='like', post=post)
    return JsonResponse({'liked': liked, 'like_count': post.like_count()})


@login_required
@require_POST
def toggle_save(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not post.author.profile.can_be_viewed_by(request.user):
        return JsonResponse({'error': 'This post is private.'}, status=403)
    saved_obj, created = SavedPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        saved_obj.delete()
        saved = False
    else:
        saved = True
    return JsonResponse({'saved': saved})


@login_required
def load_comments(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not post.author.profile.can_be_viewed_by(request.user):
        return JsonResponse({'error': 'This post is private.'}, status=403)
    comments_qs = post.comments.select_related('author', 'author__profile')
    paginator = Paginator(comments_qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    data = [{
        'id': c.id,
        'author_username': c.author.username,
        'author_display': c.author.profile.get_display_name(),
        'avatar_url': c.author.profile.avatar.url if c.author.profile.avatar else '',
        'content': c.content,
        'can_delete': c.author_id == request.user.id,
    } for c in page_obj]
    return JsonResponse({
        'comments': data,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
    })


@login_required
@require_POST
def add_comment(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not post.author.profile.can_be_viewed_by(request.user):
        return JsonResponse({'error': 'This post is private.'}, status=403)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)
    if len(content) > 500:
        return JsonResponse({'error': 'Comment is too long.'}, status=400)
    comment = Comment.objects.create(author=request.user, post=post, content=content)
    if post.author != request.user and post.author.profile.notify_on_comment:
        Notification.objects.create(recipient=post.author, actor=request.user,
                                     notification_type='comment', post=post, comment=comment)
    return JsonResponse({
        'id': comment.id,
        'author': comment.author.username,
        'author_display': comment.author.profile.get_display_name(),
        'avatar_url': comment.author.profile.avatar.url if comment.author.profile.avatar else '',
        'content': comment.content,
        'comment_count': post.comment_count(),
        'can_delete': True,
    })


@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author != request.user:
        return JsonResponse({'error': 'You can only delete your own comments.'}, status=403)
    post = comment.post
    comment.delete()
    return JsonResponse({'success': True, 'comment_count': post.comment_count()})


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    existing = Follow.objects.filter(follower=request.user, following=target).first()
    if existing:
        # Toggling again on an accepted follow unfollows; toggling again on a
        # pending request cancels that request. Either way, remove the row.
        existing.delete()
        return JsonResponse({
            'following': False,
            'status': 'none',
            'follower_count': target.profile.follower_count,
        })

    follow, _ = Follow.request_or_create(request.user, target)
    if follow.is_accepted():
        if target.profile.notify_on_follow:
            Notification.objects.create(recipient=target, actor=request.user, notification_type='follow')
        return JsonResponse({
            'following': True,
            'status': 'accepted',
            'follower_count': target.profile.follower_count,
        })
    else:
        if target.profile.notify_on_follow:
            Notification.objects.create(recipient=target, actor=request.user,
                                         notification_type='follow_request', follow=follow)
        return JsonResponse({
            'following': False,
            'status': 'pending',
            'follower_count': target.profile.follower_count,
        })


@login_required
@require_POST
def accept_follow_request(request, pk):
    follow = get_object_or_404(Follow, pk=pk, following=request.user, status=Follow.STATUS_PENDING)
    follow.status = Follow.STATUS_ACCEPTED
    follow.save(update_fields=['status'])
    if follow.follower.profile.notify_on_follow:
        Notification.objects.create(recipient=follow.follower, actor=request.user,
                                     notification_type='follow_accept')
    return JsonResponse({'status': 'accepted', 'follower_count': request.user.profile.follower_count})


@login_required
@require_POST
def reject_follow_request(request, pk):
    follow = get_object_or_404(Follow, pk=pk, following=request.user, status=Follow.STATUS_PENDING)
    follow.delete()
    return JsonResponse({'status': 'rejected'})


@login_required
def saved_posts_list(request):
    saved = SavedPost.objects.filter(user=request.user).select_related(
        'post__author', 'post__author__profile').order_by('-created_at')
    paginator = Paginator(saved, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'social/saved_posts.html', {'page_obj': page_obj})
