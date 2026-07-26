from io import BytesIO

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageOps

from apps.accounts.permissions import usuario_tem_permissao

from .models import TurismoStatus


TRANSITIONS = {
    TurismoStatus.RASCUNHO: {TurismoStatus.EM_ANALISE},
    TurismoStatus.REJEITADO: {TurismoStatus.EM_ANALISE},
    TurismoStatus.EM_ANALISE: {TurismoStatus.PUBLICADO, TurismoStatus.REJEITADO},
    TurismoStatus.PUBLICADO: {TurismoStatus.PAUSADO, TurismoStatus.ARQUIVADO},
    TurismoStatus.PAUSADO: {TurismoStatus.PUBLICADO, TurismoStatus.ARQUIVADO},
}


PREFIXOS = {
    'localturistico': 'TURISMO_LOCAL',
    'guiaturistico': 'TURISMO_GUIA',
    'empresaturistica': 'TURISMO_EMPRESA',
    'turismovideo': 'TURISMO_VIDEO',
    'turismoplaylist': 'TURISMO_PLAYLIST',
    'roteiroturistico': 'TURISMO_ROTEIRO',
    'experienciaturistica': 'TURISMO_EXPERIENCIA',
}


def alterar_status(obj, user, novo_status):
    if novo_status not in TRANSITIONS.get(obj.status, set()):
        raise ValidationError('Transição de status inválida.')
    prefixo = PREFIXOS.get(obj._meta.model_name)
    if not prefixo:
        raise ValidationError('Tipo de conteúdo não suportado.')
    if novo_status == TurismoStatus.EM_ANALISE:
        permission = f'{prefixo}_ENVIAR_ANALISE'
    elif novo_status == TurismoStatus.PUBLICADO:
        permission = f'{prefixo}_PUBLICAR'
    elif novo_status == TurismoStatus.PAUSADO:
        permission = f'{prefixo}_PAUSAR'
    else:
        permission = f'{prefixo}_MODERAR'
    if not usuario_tem_permissao(user, permission):
        raise ValidationError('Usuário sem permissão para esta transição.')
    if obj._meta.model_name == 'localturistico' and novo_status == TurismoStatus.PUBLICADO:
        validar_publicacao_local(obj)
    obj.status = novo_status
    obj.usuario_atualizador = user
    if novo_status == TurismoStatus.PUBLICADO:
        obj.publicado_por = user
        obj.publicado_em = timezone.now()
    if novo_status in {TurismoStatus.PUBLICADO, TurismoStatus.REJEITADO}:
        obj.moderado_por = user
        obj.moderado_em = timezone.now()
    obj.save()
    if obj._meta.model_name == 'localturistico' and novo_status == TurismoStatus.PUBLICADO:
        for relation in ('fotos', 'videos', 'playlists', 'contatos', 'redes_sociais_itens'):
            getattr(obj, relation).filter(ativo=True).update(
                status=TurismoStatus.PUBLICADO,
                publicado_por=user,
                publicado_em=timezone.now(),
                moderado_por=user,
                moderado_em=timezone.now(),
                usuario_atualizador=user,
            )


def processar_imagem_principal(local):
    if not local.imagem_principal:
        return
    local.imagem_principal.open('rb')
    with Image.open(local.imagem_principal) as original:
        imagem = ImageOps.exif_transpose(original).convert('RGB')
        imagem.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        webp = BytesIO()
        imagem.save(webp, format='WEBP', quality=84, method=6)
        thumb = ImageOps.fit(imagem, (640, 360), method=Image.Resampling.LANCZOS)
        thumb_io = BytesIO()
        thumb.save(thumb_io, format='WEBP', quality=80, method=6)
    base = str(local.uuid)
    local.imagem_principal_webp.save(f'{base}.webp', ContentFile(webp.getvalue()), save=False)
    local.imagem_thumbnail.save(f'{base}.webp', ContentFile(thumb_io.getvalue()), save=False)
    local.save(update_fields=['imagem_principal_webp', 'imagem_thumbnail', 'atualizado_em'])


def validar_publicacao_local(local):
    erros = []
    if not local.nome or not local.descricao_curta or not local.descricao_completa:
        erros.append('Preencha a identificação e a descrição pública.')
    if not local.categoria_id:
        erros.append('Selecione o tipo de local.')
    if not local.cidade or not local.estado:
        erros.append('Informe cidade e estado.')
    if not local.imagem_principal:
        erros.append('A imagem principal é obrigatória para publicação.')
    if not local.imagem_texto_alternativo:
        erros.append('Informe o texto alternativo da imagem principal.')
    if erros:
        raise ValidationError(erros)
    return True
