from dataclasses import dataclass, field


@dataclass
class CNPJData:
    cnpj: str
    razao_social: str = ''
    nome_fantasia: str = ''
    situacao_cadastral: str = ''
    data_abertura: str = ''
    natureza_juridica: str = ''
    porte: str = ''
    telefone: str = ''
    email: str = ''
    logradouro: str = ''
    numero: str = ''
    complemento: str = ''
    bairro: str = ''
    municipio: str = ''
    uf: str = ''
    cep: str = ''
    cnaes: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()
