from apps.core.services.weather import clima_atual


def weather(request):
    return {'clima_botucatu': clima_atual()}
