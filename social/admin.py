from django.contrib import admin
from .models import Comment, Follow, Like, SavedPost

admin.site.register(Comment)
admin.site.register(Follow)
admin.site.register(Like)
admin.site.register(SavedPost)
