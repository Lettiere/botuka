from dataclasses import asdict, dataclass
from decimal import Decimal

from apps.recruitment.models import Curriculo


@dataclass(frozen=True)
class CurriculoDTO:
    uuid: str
    titulo_profissional: str
    area_profissional: str
    objetivo_profissional: str
    resumo: str
    nivel_profissional: str
    cidade: str
    estado: str
    telefone: str
    email: str
    linkedin: str
    portfolio: str
    site_profissional: str
    github: str
    pretensao_salarial: str | None
    experiencias: tuple
    formacoes: tuple
    cursos: tuple
    habilidades: tuple
    idiomas: tuple
    projetos: tuple

    def serializar(self):
        return asdict(self)


def _privacidade(curriculo):
    try: return curriculo.privacidade
    except Curriculo.privacidade.RelatedObjectDoesNotExist: return None


def _montar(curriculo, respeitar_privacidade=True):
    p = _privacidade(curriculo)
    permite = lambda campo, padrao=False: not respeitar_privacidade or bool(p and getattr(p, campo, padrao))
    salario = curriculo.pretensao_salarial if permite('mostrar_pretensao_salarial') else None
    return CurriculoDTO(
        str(curriculo.uuid), curriculo.titulo_profissional, curriculo.area_profissional,
        curriculo.objetivo_profissional, curriculo.resumo, curriculo.nivel_profissional,
        curriculo.cidade if permite('mostrar_cidade') else '',
        curriculo.estado if permite('mostrar_estado') else '',
        curriculo.telefone_publico if permite('mostrar_telefone') else '',
        curriculo.email_publico if permite('mostrar_email') else '',
        curriculo.linkedin if permite('mostrar_linkedin') else '',
        curriculo.portfolio if permite('mostrar_portfolio') else '',
        curriculo.site_profissional, curriculo.github,
        str(salario) if isinstance(salario, Decimal) else None,
        tuple({
            'uuid': str(x.uuid), 'empresa': x.titulo, 'cargo': x.cargo,
            'descricao': x.descricao,
            'inicio': x.inicio.isoformat() if x.inicio else None,
            'fim': x.fim.isoformat() if x.fim else None,
            'atual': x.atual,
        } for x in curriculo.experiencia_set.filter(ativo=True, excluido_em__isnull=True)),
        tuple({
            'uuid': str(x.uuid), 'curso': x.titulo, 'instituicao': x.instituicao,
            'nivel': x.nivel,
            'inicio': x.inicio.isoformat() if x.inicio else None,
            'fim': x.fim.isoformat() if x.fim else None,
        } for x in curriculo.formacao_set.filter(ativo=True, excluido_em__isnull=True)),
        tuple({
            'uuid': str(x.uuid), 'nome': x.titulo, 'instituicao': x.instituicao,
            'tipo': x.tipo, 'carga_horaria': x.carga_horaria,
        } for x in curriculo.curso_set.filter(ativo=True, excluido_em__isnull=True)),
        tuple({
            'nome': x.nome, 'nivel': x.nivel, 'categoria': x.categoria,
        } for x in curriculo.habilidades.filter(ativo=True, excluido_em__isnull=True)),
        tuple({
            'nome': x.nome, 'nivel': x.nivel,
        } for x in curriculo.idiomas.filter(ativo=True, excluido_em__isnull=True)),
        tuple({
            'uuid': str(x.uuid), 'titulo': x.titulo, 'descricao': x.descricao,
            'url': x.url, 'tecnologias': x.tecnologias,
        } for x in curriculo.projetos.filter(ativo=True, excluido_em__isnull=True)),
    )


def curriculo_para_painel(curriculo): return _montar(curriculo, respeitar_privacidade=False)
def curriculo_para_candidatura(curriculo): return _montar(curriculo, respeitar_privacidade=True)


def curriculo_publico(curriculo):
    if not (curriculo.ativo and curriculo.excluido_em is None and
            curriculo.status == Curriculo.Status.CONCLUIDO and
            curriculo.visibilidade == Curriculo.Visibilidade.PUBLICO):
        return None
    return _montar(curriculo, respeitar_privacidade=True)
