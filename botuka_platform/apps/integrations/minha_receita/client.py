import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from .exceptions import MinhaReceitaProviderError


class MinhaReceitaClient:
    """Cliente da descoberta municipal; não realiza consultas individuais."""

    base_url = 'https://minhareceita.org/'

    def discover_batch(self, *, limit: int = 100, cursor: str | None = None) -> dict:
        params = {'uf': 'SP', 'municipio': '3507506', 'limit': limit}
        if cursor:
            params['cursor'] = cursor
        url = f'{getattr(settings, "MINHA_RECEITA_BASE_URL", self.base_url)}?{urllib.parse.urlencode(params)}'
        timeout = int(getattr(settings, 'MINHA_RECEITA_TIMEOUT', 15))

        request = urllib.request.Request(
            url,
            headers={'Accept': 'application/json', 'User-Agent': 'BOTUKA/1.0'},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MinhaReceitaProviderError('Falha ao consultar a Minha Receita.') from exc

        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise MinhaReceitaProviderError('Resposta inválida da Minha Receita.')
        return {'data': payload['data'], 'cursor': payload.get('cursor')}
