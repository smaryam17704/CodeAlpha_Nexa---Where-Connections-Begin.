from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from posts.models import Post
from social.models import Follow
from .forms import InterestSelectionForm, ProfileEditForm, ProfileSetupForm, SignUpForm
from .models import Interest, Profile

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, 'Welcome to Nexa! Let\'s set up your profile.')
            return redirect('accounts:onboarding_profile')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def onboarding_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            profile.onboarding_step = max(profile.onboarding_step, 1)
            profile.save(update_fields=['onboarding_step'])
            return redirect('accounts:onboarding_interests')
    else:
        form = ProfileSetupForm(instance=profile, user=request.user)
    return render(request, 'accounts/onboarding_profile.html', {'form': form, 'step': 1})


@login_required
def onboarding_interests(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = InterestSelectionForm(request.POST)
        if form.is_valid():
            profile.interests.set(form.cleaned_data['interests'])
            profile.onboarding_step = max(profile.onboarding_step, 2)
            profile.save(update_fields=['onboarding_step'])
            return redirect('accounts:onboarding_people')
    else:
        form = InterestSelectionForm()
    return render(request, 'accounts/onboarding_interests.html', {
        'form': form, 'step': 2, 'interests': Interest.objects.all(),
    })


@login_required
def onboarding_people(request):
    profile = request.user.profile
    if request.method == 'POST':
        follow_ids = request.POST.getlist('follow')
        for uid in follow_ids:
            if str(uid) != str(request.user.id):
                target = User.objects.filter(id=uid).select_related('profile').first()
                if target:
                    Follow.request_or_create(request.user, target)
        profile.onboarding_step = max(profile.onboarding_step, 3)
        profile.save(update_fields=['onboarding_step'])
        return redirect('accounts:onboarding_complete')

    interest_ids = profile.interests.values_list('id', flat=True)
    suggestions = User.objects.exclude(id=request.user.id).exclude(
        id__in=Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    )
    if interest_ids:
        suggestions = suggestions.filter(profile__interests__in=interest_ids).distinct()
    suggestions = suggestions.select_related('profile')[:8]
    return render(request, 'accounts/onboarding_people.html', {
        'step': 3, 'suggestions': suggestions,
    })


@login_required
def onboarding_complete(request):
    profile = request.user.profile
    profile.onboarding_step = 4
    profile.onboarding_complete = True
    profile.save(update_fields=['onboarding_step', 'onboarding_complete'])
    return render(request, 'accounts/onboarding_complete.html', {'step': 4})


@login_required
def profile_view(request, username):
    profile_user = get_object_or_404(User.objects.select_related('profile'), username=username)
    can_view = profile_user.profile.can_be_viewed_by(request.user)

    is_following = False
    is_requested = False
    if request.user.is_authenticated and request.user != profile_user:
        follow_row = Follow.objects.filter(follower=request.user, following=profile_user).first()
        is_following = bool(follow_row and follow_row.is_accepted())
        is_requested = bool(follow_row and follow_row.is_pending())

    if not can_view:
        return render(request, 'accounts/profile.html', {
            'profile_user': profile_user,
            'profile': profile_user.profile,
            'page_obj': None,
            'is_following': is_following,
            'is_requested': is_requested,
            'is_own_profile': request.user == profile_user,
            'is_private_and_blocked': True,
        })

    posts_qs = Post.objects.filter(author=profile_user).order_by('-created_at')
    paginator = Paginator(posts_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/profile.html', {
        'profile_user': profile_user,
        'profile': profile_user.profile,
        'page_obj': page_obj,
        'is_following': is_following,
        'is_requested': is_requested,
        'is_own_profile': request.user == profile_user,
        'is_private_and_blocked': False,
    })


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:profile', username=request.user.username)
    else:
        form = ProfileEditForm(instance=profile, user=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def followers_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not profile_user.profile.can_be_viewed_by(request.user):
        return render(request, 'accounts/user_list.html', {
            'profile_user': profile_user, 'title': 'Followers', 'page_obj': None,
            'my_following_ids': set(), 'my_pending_ids': set(), 'is_private_and_blocked': True,
        })
    follows = Follow.objects.filter(following=profile_user, status='accepted').select_related('follower__profile')
    my_following_ids = set(Follow.objects.filter(follower=request.user, status='accepted').values_list('following_id', flat=True))
    my_pending_ids = set(Follow.objects.filter(follower=request.user, status='pending').values_list('following_id', flat=True))
    paginator = Paginator([f.follower for f in follows], 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/user_list.html', {
        'profile_user': profile_user,
        'title': 'Followers',
        'page_obj': page_obj,
        'my_following_ids': my_following_ids,
        'my_pending_ids': my_pending_ids,
        'is_private_and_blocked': False,
    })


@login_required
def following_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not profile_user.profile.can_be_viewed_by(request.user):
        return render(request, 'accounts/user_list.html', {
            'profile_user': profile_user, 'title': 'Following', 'page_obj': None,
            'my_following_ids': set(), 'my_pending_ids': set(), 'is_private_and_blocked': True,
        })
    follows = Follow.objects.filter(follower=profile_user, status='accepted').select_related('following__profile')
    my_following_ids = set(Follow.objects.filter(follower=request.user, status='accepted').values_list('following_id', flat=True))
    my_pending_ids = set(Follow.objects.filter(follower=request.user, status='pending').values_list('following_id', flat=True))
    paginator = Paginator([f.following for f in follows], 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/user_list.html', {
        'profile_user': profile_user,
        'title': 'Following',
        'page_obj': page_obj,
        'my_following_ids': my_following_ids,
        'my_pending_ids': my_pending_ids,
        'is_private_and_blocked': False,
    })
