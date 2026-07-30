from django.db.models import Prefetch, Q
from django.utils import timezone

from .models import Produto, ProdutoImagem


def produtos_publicos():
    return Produto.objects.filter(
        status=Produto.Status.PUBLICADO,
        publico=True,
        publicado_em__isnull=False,
        publicado_em__lte=timezone.now(),
    ).filter(
        Q(empresa_proprietaria__isnull=True)
        | Q(
            empresa_proprietaria__ativo=True,
            empresa_proprietaria__status='ATIVA',
            empresa_proprietaria__perfil_publico=True,
        )
    ).select_related(
        'empresa_proprietaria', 'empresa_proprietaria__cidade',
        'categoria_taxonomia', 'familia', 'tipo_produto', 'segmento',
        'responsavel',
    ).prefetch_related(
        Prefetch(
            'imagens',
            queryset=ProdutoImagem.objects.filter(ativo=True, removido_em__isnull=True).order_by('-principal', 'ordem'),
        )
    )


def produtos_para_home(limit=8):
    return list(produtos_publicos().filter(destaque=True).order_by('-publicado_em', '-atualizado_em')[:limit])
