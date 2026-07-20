from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EventoPublicoDTO:
    uuid: UUID
    titulo: str
    resumo: str
    categoria: str
    inicio: object
    fim: object
    local: str
    organizador: str
    oficial: bool
    gratuito: bool | None
    imagem_url: str
    url: str
    origem: str


@dataclass(frozen=True, slots=True)
class ConteudoCidadeDTO:
    uuid: UUID
    titulo: str
    resumo: str
    categoria: str
    local: str
    imagem_url: str
    url: str
    origem: str
    oficial: bool = False
