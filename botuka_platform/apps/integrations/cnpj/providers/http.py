import json
import urllib.error
import urllib.request

from apps.integrations.cnpj.exceptions import (
    CNPJNotFoundError,
    CNPJProviderError,
    CNPJRateLimitError,
)


def obter_json(url: str, *, timeout: int) -> dict:
    request = urllib.request.Request(
        url, headers={'Accept': 'application/json', 'User-Agent': 'BOTUKA/1.0'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CNPJNotFoundError('CNPJ não encontrado pelo provider.') from exc
        if exc.code == 429:
            raise CNPJRateLimitError('Limite de consultas do provider atingido.') from exc
        raise CNPJProviderError(f'Provider de CNPJ respondeu HTTP {exc.code}.') from exc
    except (
        urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError,
    ) as exc:
        raise CNPJProviderError('Falha ao consultar provider de CNPJ.') from exc
    if not isinstance(payload, dict):
        raise CNPJProviderError('Provider de CNPJ retornou JSON inválido.')
    return payload
