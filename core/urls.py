from django.urls import path
from posts.views import home_feed
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('home/', home_feed, name='home'),
    path('explore/', views.explore, name='explore'),
    path('search/', views.search, name='search'),
    path('activity/', views.activity, name='activity'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/theme/', views.update_theme, name='update_theme'),
    path('settings/notifications/', views.update_notification_preferences, name='update_notification_preferences'),
    path('settings/privacy/', views.update_privacy, name='update_privacy'),
]
