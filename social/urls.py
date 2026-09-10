from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    path('post/<int:pk>/like/', views.toggle_like, name='toggle_like'),
    path('post/<int:pk>/save/', views.toggle_save, name='toggle_save'),
    path('post/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('post/<int:pk>/comments/', views.load_comments, name='load_comments'),
    path('comment/<int:pk>/delete/', views.delete_comment, name='delete_comment'),
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('follow-requests/<int:pk>/accept/', views.accept_follow_request, name='accept_follow_request'),
    path('follow-requests/<int:pk>/reject/', views.reject_follow_request, name='reject_follow_request'),
    path('saved/', views.saved_posts_list, name='saved_posts'),
]
