from django.urls import path
from . import views

app_name = 'posts'

urlpatterns = [
    path('', views.home_feed, name='feed'),
    path('create/', views.create_post, name='create'),
    path('<int:pk>/', views.post_detail, name='detail'),
    path('<int:pk>/edit/', views.post_edit, name='edit'),
    path('<int:pk>/delete/', views.post_delete, name='delete'),
    path('tag/<str:name>/', views.hashtag_detail, name='hashtag'),
]
