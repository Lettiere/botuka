from django.utils import timezone
from apps.media.models import Episodio, Programa, Transmissao
from apps.media.selectors import transmissoes_publicas, videos_em_destaque, videos_publicos


def obter_ytv():
    programas = list(
        Programa.objects.filter(ativo=True, excluido_em__isnull=True, canal__ativo=True, canal__excluido_em__isnull=True)
        .select_related("canal", "apresentador", "produtor")
        .order_by("nome")[:6]
    )
    episodios = list(videos_em_destaque('HOME')[:4])
    if not episodios:
        episodios = list(
            videos_publicos().filter(publicar_na_home=True)
            .order_by("-destaque", "-publicado_em")[:4]
        )
    if not episodios:
        episodios = list(
            videos_publicos().order_by("-destaque", "-publicado_em")[:4]
        )
    if not episodios:
        episodios = list(
            Episodio.objects.filter(ativo=True, excluido_em__isnull=True, programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True)
            .filter(status="PUBLICADO", publicado_em__isnull=False, publicado_em__lte=timezone.now())
            .select_related("programa", "temporada")
            .order_by("-destaque", "-publicado_em", "data_programada")[:4]
        )
    ao_vivo = list(
        transmissoes_publicas()
        .filter(status=Transmissao.Status.AO_VIVO)
        .order_by("-inicio")[:4]
    )
    return programas, episodios, ao_vivo
