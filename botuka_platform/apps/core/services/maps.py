"""Abstração configurável de mapas sem credenciais no frontend."""
from dataclasses import dataclass
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.conf import settings


@dataclass(frozen=True)
class MapPoint:
    latitude: float
    longitude: float
    label: str = ''


class MapProvider:
    def public_url(self, point):
        raise NotImplementedError

    def frontend_config(self):
        raise NotImplementedError


class OpenStreetMapProvider(MapProvider):
    def public_url(self, point):
        return f'https://www.openstreetmap.org/?mlat={point.latitude}&mlon={point.longitude}#map=16/{point.latitude}/{point.longitude}'

    def frontend_config(self):
        return {
            'tiles_url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            'attribution': '© OpenStreetMap contributors',
        }


class MapService:
    providers = {'openstreetmap': OpenStreetMapProvider}

    def __init__(self, provider=None):
        self.provider = self.providers.get(provider or settings.MAP_PROVIDER, OpenStreetMapProvider)()

    def public_url(self, latitude, longitude, label=''):
        return self.provider.public_url(MapPoint(float(latitude), float(longitude), label))

    def frontend_config(self):
        return self.provider.frontend_config()


class OpenStreetMapGeocoder:
    endpoint = 'https://nominatim.openstreetmap.org/search'

    def geocode(self, address):
        query = urlencode({'q': address, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'br'})
        request = Request(
            f'{self.endpoint}?{query}',
            headers={'User-Agent': 'BOTUKA/1.0 (geocodificacao administrativa)'},
        )
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode('utf-8'))
        if not result:
            return None
        return MapPoint(float(result[0]['lat']), float(result[0]['lon']), result[0].get('display_name', ''))


class GeocodingService:
    providers = {'openstreetmap': OpenStreetMapGeocoder}

    def __init__(self, provider=None):
        self.provider = self.providers.get(provider or settings.MAP_PROVIDER, OpenStreetMapGeocoder)()

    def geocode(self, address):
        if not address or len(address.strip()) < 5:
            return None
        return self.provider.geocode(address.strip())
