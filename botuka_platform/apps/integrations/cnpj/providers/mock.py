from apps.integrations.cnpj.providers.base import BaseCNPJProvider
from apps.integrations.cnpj.schemas import CNPJData


class MockCNPJProvider(BaseCNPJProvider):
    name = 'mock'

    def consultar(self, cnpj: str) -> CNPJData:
        return CNPJData(
            cnpj=cnpj,
            razao_social='Empresa de Demonstração BOTUKA',
            nome_fantasia='Demonstração BOTUKA',
            situacao_cadastral='ATIVA',
            municipio='Botucatu',
            uf='SP',
            raw={'mock': True},
        )
