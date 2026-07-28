from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import usuario_tem_permissao
from apps.core.domain import auditar

from .models import Artigo, EditorialStatus, HistoricoEditorial


TRANSICOES = {
    EditorialStatus.RASCUNHO: {EditorialStatus.ENVIADO_REVISAO, EditorialStatus.ARQUIVADO},
    EditorialStatus.ENVIADO_REVISAO: {EditorialStatus.EM_REVISAO, EditorialStatus.RASCUNHO},
    EditorialStatus.EM_REVISAO: {
        EditorialStatus.CORRECAO_SOLICITADA, EditorialStatus.APROVADO,
        EditorialStatus.REJEITADO,
    },
    EditorialStatus.CORRECAO_SOLICITADA: {EditorialStatus.ENVIADO_REVISAO, EditorialStatus.ARQUIVADO},
    EditorialStatus.APROVADO: {
        EditorialStatus.AGENDADO, EditorialStatus.PUBLICADO,
        EditorialStatus.CORRECAO_SOLICITADA, EditorialStatus.ARQUIVADO,
    },
    EditorialStatus.AGENDADO: {
        EditorialStatus.PUBLICADO, EditorialStatus.APROVADO,
        EditorialStatus.DESPUBLICADO,
    },
    EditorialStatus.PUBLICADO: {EditorialStatus.DESPUBLICADO, EditorialStatus.ARQUIVADO},
    EditorialStatus.REJEITADO: {EditorialStatus.RASCUNHO, EditorialStatus.ARQUIVADO},
    EditorialStatus.DESPUBLICADO: {
        EditorialStatus.PUBLICADO, EditorialStatus.AGENDADO, EditorialStatus.ARQUIVADO,
    },
    EditorialStatus.ARQUIVADO: {EditorialStatus.RASCUNHO},
}

PERMISSAO_TRANSICAO = {
    EditorialStatus.ENVIADO_REVISAO: "news.enviar_revisao",
    EditorialStatus.EM_REVISAO: "news.revisar",
    EditorialStatus.CORRECAO_SOLICITADA: "news.solicitar_correcao",
    EditorialStatus.APROVADO: "news.aprovar",
    EditorialStatus.AGENDADO: "news.agendar",
    EditorialStatus.PUBLICADO: "news.publicar",
    EditorialStatus.DESPUBLICADO: "news.despublicar",
    EditorialStatus.ARQUIVADO: "news.arquivar",
    EditorialStatus.REJEITADO: "news.revisar",
}


def pode_editar_artigo(usuario, artigo):
    if usuario_tem_permissao(usuario, "news.editar_qualquer") or usuario_tem_permissao(usuario, "news.gerenciar"):
        return True
    return (
        usuario_tem_permissao(usuario, "news.editar_propria")
        and (artigo.autor_id == usuario.pk or artigo.autor_editorial_id and artigo.autor_editorial.usuario_id == usuario.pk)
    )


def validar_transicao(usuario, anterior, novo):
    if anterior == novo:
        return
    if novo not in TRANSICOES.get(anterior, set()):
        raise ValidationError({"status": f"Transição de {anterior} para {novo} não permitida."})
    permissao = PERMISSAO_TRANSICAO.get(novo)
    if permissao and not (
        usuario_tem_permissao(usuario, permissao)
        or usuario_tem_permissao(usuario, "news.gerenciar")
    ):
        raise PermissionDenied(f"Permissão necessária: {permissao}")


@transaction.atomic
def alterar_status(*, artigo, novo_status, usuario, request=None, observacao="", agendado_para=None):
    anterior = artigo.status
    validar_transicao(usuario, anterior, novo_status)
    if novo_status == EditorialStatus.AGENDADO:
        artigo.agendado_para = agendado_para or artigo.agendado_para
        if not artigo.agendado_para or artigo.agendado_para <= timezone.now():
            raise ValidationError({"agendado_para": "O agendamento deve estar no futuro."})
    if novo_status == EditorialStatus.PUBLICADO:
        artigo.publicado_em = timezone.now()
        artigo.publicador = usuario
    if novo_status in {
        EditorialStatus.EM_REVISAO, EditorialStatus.CORRECAO_SOLICITADA,
        EditorialStatus.APROVADO, EditorialStatus.REJEITADO,
    }:
        artigo.revisado_por = usuario
        artigo.revisado_em = timezone.now()
    artigo.status = novo_status
    artigo.full_clean()
    artigo.save()
    HistoricoEditorial.objects.create(
        artigo=artigo, usuario=usuario, status_anterior=anterior,
        status_novo=novo_status, acao="ALTERAR_STATUS", observacao=observacao,
    )
    if request:
        auditar(
            request, "ALTERAR_STATUS", artigo,
            antes={"status": anterior}, depois={"status": novo_status},
            motivo=observacao,
        )
    return artigo


def publicar_agendados(agora=None):
    agora = agora or timezone.now()
    publicados = 0
    queryset = Artigo.objects.filter(
        status=EditorialStatus.AGENDADO,
        agendado_para__isnull=False,
        agendado_para__lte=agora,
    ).select_related("publicador")
    for artigo in queryset:
        artigo.status = EditorialStatus.PUBLICADO
        artigo.publicado_em = artigo.agendado_para
        artigo.full_clean()
        artigo.save()
        HistoricoEditorial.objects.create(
            artigo=artigo, usuario=artigo.publicador,
            status_anterior=EditorialStatus.AGENDADO,
            status_novo=EditorialStatus.PUBLICADO,
            acao="PUBLICACAO_AGENDADA",
        )
        publicados += 1
    return publicados
