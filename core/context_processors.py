def theme_processor(request):
    theme = 'system'
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        theme = request.user.profile.theme_preference
    else:
        theme = request.COOKIES.get('nexa_theme', 'system')
    return {'active_theme': theme}
