from django.utils import timezone
from apps.media.models import Episodio, Programa, Transmissao


def obter_ytv():
    programas = list(
        Programa.objects.filter(ativo=True, excluido_em__isnull=True, canal__ativo=True, canal__excluido_em__isnull=True)
        .select_related("canal", "apresentador", "produtor")
        .order_by("nome")[:6]
    )
    episodios = list(
        Episodio.objects.filter(ativo=True, excluido_em__isnull=True, programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True)
        .filter(status="PUBLICADO", publicado_em__isnull=False, publicado_em__lte=timezone.now())
        .select_related("programa", "temporada")
        .order_by("-destaque", "-publicado_em", "data_programada")[:4]
    )
    ao_vivo = list(
        Transmissao.objects.filter(ativo=True, excluido_em__isnull=True, status="AO_VIVO", episodio__status="AO_VIVO", episodio__ativo=True, episodio__programa__ativo=True, episodio__programa__canal__ativo=True)
        .select_related("episodio", "episodio__programa", "disputa", "acao_publica")
        .order_by("-inicio")[:4]
    )
    return programas, episodios, ao_vivo
