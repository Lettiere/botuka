from django.utils import timezone
from apps.news.models import Artigo


def obter_noticias():
    base = (
        Artigo.objects.filter(status="PUBLICADO", ativo=True, excluido_em__isnull=True, publicado_em__lte=timezone.now(), categoria__ativo=True, categoria__excluido_em__isnull=True)
        .select_related("categoria", "autor")
        .order_by("-destaque", "-publicado_em", "-criado_em")
    )
    destaque = list(base.filter(destaque=True)[:6])
    recentes = list(base[:6])
    return destaque, recentes
