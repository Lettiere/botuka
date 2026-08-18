from django.conf import settings


def runtime_urls(request):
    return {
        'botuka_platform_base_url': settings.BOTUKA_PLATFORM_BASE_URL,
        'botuka_social_base_url': settings.BOTUKA_SOCIAL_BASE_URL,
        'botuka_runtime': settings.BOTUKA_RUNTIME,
        'botuka_platform_home_url': f'{settings.BOTUKA_PLATFORM_BASE_URL}/',
        'botuka_social_home_url': f'{settings.BOTUKA_SOCIAL_BASE_URL}/social/',
        'botuka_platform_login_url': f'{settings.BOTUKA_PLATFORM_BASE_URL}/conta/login/',
        'botuka_platform_logout_url': f'{settings.BOTUKA_PLATFORM_BASE_URL}/conta/logout/',
    }
