class MinhaReceitaError(Exception):
    """Erro controlado ao consultar a fonte de descoberta."""


class MinhaReceitaProviderError(MinhaReceitaError):
    """A fonte não respondeu com um lote utilizável."""
