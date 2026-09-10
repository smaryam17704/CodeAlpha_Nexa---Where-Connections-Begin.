from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
from .forms import StyledAuthenticationForm, StyledPasswordResetForm, StyledSetPasswordForm

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html', authentication_form=StyledAuthenticationForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.txt',
        subject_template_name='accounts/password_reset_subject.txt',
        form_class=StyledPasswordResetForm,
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        form_class=StyledSetPasswordForm,
        success_url=reverse_lazy('accounts:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),

    path('onboarding/profile/', views.onboarding_profile, name='onboarding_profile'),
    path('onboarding/interests/', views.onboarding_interests, name='onboarding_interests'),
    path('onboarding/people/', views.onboarding_people, name='onboarding_people'),
    path('onboarding/complete/', views.onboarding_complete, name='onboarding_complete'),

    path('u/<str:username>/', views.profile_view, name='profile'),
    path('u/<str:username>/followers/', views.followers_list, name='followers'),
    path('u/<str:username>/following/', views.following_list, name='following'),
    path('settings/profile/', views.profile_edit, name='profile_edit'),
]
