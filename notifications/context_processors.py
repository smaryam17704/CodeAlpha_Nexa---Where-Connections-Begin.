def unread_count_processor(request):
    if request.user.is_authenticated:
        count = request.user.notifications.filter(is_read=False).count()
        return {'unread_notification_count': count}
    return {'unread_notification_count': 0}
