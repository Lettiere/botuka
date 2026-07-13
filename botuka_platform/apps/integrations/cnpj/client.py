from django.conf import settings

from apps.integrations.cnpj.providers.configured import ConfiguredCNPJProvider
from apps.integrations.cnpj.providers.mock import MockCNPJProvider


def get_cnpj_provider():
    provider = getattr(settings, 'CNPJ_PROVIDER', 'mock').lower()
    if provider in {'configured', 'http', 'api'}:
        return ConfiguredCNPJProvider()
    return MockCNPJProvider()
