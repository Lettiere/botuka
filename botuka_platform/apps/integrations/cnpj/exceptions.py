class CNPJError(Exception):
    """Erro base da integração de CNPJ."""


class CNPJInvalidoError(CNPJError):
    """CNPJ inválido."""


class CNPJProviderError(CNPJError):
    """Erro retornado pelo provider configurado."""


class CNPJNotFoundError(CNPJProviderError):
    """O provider não encontrou o CNPJ consultado."""


class CNPJRateLimitError(CNPJProviderError):
    """O provider recusou temporariamente a consulta por limite de uso."""
