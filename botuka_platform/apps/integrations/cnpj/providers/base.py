from abc import ABC, abstractmethod

from apps.integrations.cnpj.schemas import CNPJData


class BaseCNPJProvider(ABC):
    name = 'base'

    @abstractmethod
    def consultar(self, cnpj: str) -> CNPJData:
        raise NotImplementedError
