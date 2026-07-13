class CNPJError(Exception):
    """Erro base da integração de CNPJ."""


class CNPJInvalidoError(CNPJError):
    """CNPJ inválido."""


class CNPJProviderError(CNPJError):
    """Erro retornado pelo provider configurado."""
