import logging

from django.core.cache import cache

from .adapters import culture, events, gastronomy, government, media, news, organizations, places, recruitment, services, sports, tourism

logger = logging.getLogger(__name__)
CACHE_TIMEOUT = 300


def _secao(chave, carregador, padrao):
    valor = cache.get(chave)
    if valor is not None:
        return valor
    try:
        valor = carregador()
        cache.set(chave, valor, CACHE_TIMEOUT)
        return valor
    except Exception:
        logger.exception("Falha isolada ao montar a seção %s da HOME", chave)
        return padrao


def montar_contexto_home(usuario=None):
    empresas = _secao("home:empresas", organizations.obter_empresas_destaque, [])
    servicos_destaque = _secao("home:servicos", services.obter_servicos_destaque, [])
    recrutamento = _secao(
        "home:vagas",
        recruitment.obter_vagas_recentes,
        [],
    )
    noticias = _secao("home:news", news.obter_noticias, ([], []))
    # Chave versionada evita manter a estrutura legada em cache após a migração
    # das consultas públicas para Video e Transmissao.
    ytv = _secao("home:yubotuka:v3", media.obter_ytv, ([], [], []))
    esportes = _secao("home:sports", sports.obter_esportes, ([], [], [], []))
    prefeitura = _secao("home:government", government.obter_prefeitura, ([], []))
    eventos = _secao("home:events", events.obter_eventos, ([], []))
    cultura = _secao("home:culture", culture.obter_cultura, ([], []))
    gastronomia = _secao("home:gastronomy", gastronomy.obter_gastronomia, [])
    parques = _secao("home:places", places.obter_parques, [])
    turismo_destaque = _secao("home:tourism", tourism.obter_turismo, [])
    turismo_secoes = _secao("home:tourism:sections", tourism.obter_secoes_turismo, {})

    contexto = {
        "empresas_destaque": empresas,
        "servicos_destaque": servicos_destaque,
        "vagas_recentes": recrutamento,
        "noticias_destaque": noticias[0],
        "noticias_recentes": noticias[1],
        "programas_ytv": ytv[0],
        "episodios_ytv": ytv[1],
        "transmissoes_ao_vivo": ytv[2],
        "modalidades_esportivas": esportes[0],
        "campeonatos_ativos": esportes[1],
        "jogos_proximos": esportes[2],
        "resultados_recentes": esportes[3],
        "acoes_prefeitura": prefeitura[0],
        "orgaos_publicos": prefeitura[1],
        "eventos_destaque": eventos[0],
        "eventos_proximos": eventos[1],
        "cultura_destaque": cultura[0],
        "cultura_recentes": cultura[1],
        "gastronomia_destaque": gastronomia,
        "parques_destaque": parques,
        "turismo_destaque": turismo_destaque,
        "turismo_secoes": turismo_secoes,
    }
    contexto["estatisticas_home"] = {
        "empresas": len(empresas),
        "servicos": len(servicos_destaque),
        "vagas": len(recrutamento),
        "noticias": len(noticias[1]),
        "episodios": len(ytv[1]),
        "campeonatos": len(esportes[1]),
        "acoes_publicas": len(prefeitura[0]),
        "turismo": len(turismo_destaque),
    }
    return contexto
