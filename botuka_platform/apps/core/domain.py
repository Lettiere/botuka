import uuid
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags

from apps.core.models import Auditoria
from apps.accounts.permissions import usuario_tem_permissao


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class SoftDeleteMixin(models.Model):
    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}


class EditorialStatus(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    EM_REVISAO = 'EM_REVISAO', 'Em revisão'
    APROVADO = 'APROVADO', 'Aprovado'
    PUBLICADO = 'PUBLICADO', 'Publicado'
    PAUSADO = 'PAUSADO', 'Pausado'
    REJEITADO = 'REJEITADO', 'Rejeitado'


def texto_sem_html(valor):
    valor = valor or ''
    if strip_tags(valor) != valor:
        raise ValidationError('HTML não é permitido.')
    return valor


def _cabecalho(arquivo, tamanho=16):
    file_object = getattr(arquivo, "file", arquivo)
    if not hasattr(file_object, "read"):
        return b""
    position = file_object.tell() if hasattr(file_object, "tell") else None
    header = file_object.read(tamanho)
    if position is not None and hasattr(file_object, "seek"):
        file_object.seek(position)
    return header


def validar_imagem_publica(arquivo):
    if not arquivo:
        return
    if getattr(arquivo, "size", 0) > 5 * 1024 * 1024:
        raise ValidationError("A imagem deve ter no máximo 5 MB.")
    extension = Path(arquivo.name).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError("Envie uma imagem JPG, PNG ou WEBP.")
    content_type = getattr(arquivo, "content_type", "")
    if content_type and content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValidationError("O tipo MIME da imagem não é permitido.")
    header = _cabecalho(arquivo)
    signatures = (
        header.startswith(b"\xff\xd8\xff"),
        header.startswith(b"\x89PNG\r\n\x1a\n"),
        header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    )
    if header and not any(signatures):
        raise ValidationError("A assinatura do arquivo não corresponde a uma imagem permitida.")


def validar_documento_publico(arquivo):
    if not arquivo:
        return
    if getattr(arquivo, "size", 0) > 10 * 1024 * 1024:
        raise ValidationError("O documento deve ter no máximo 10 MB.")
    extension = Path(arquivo.name).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".odt"}
    if extension not in allowed:
        raise ValidationError("Envie PDF, DOC, DOCX ou ODT.")
    content_type = getattr(arquivo, "content_type", "")
    allowed_mimes = {
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.oasis.opendocument.text", "application/zip",
    }
    if content_type and content_type not in allowed_mimes:
        raise ValidationError("O tipo MIME do documento não é permitido.")
    header = _cabecalho(arquivo)
    valid = header.startswith(b"%PDF-") if extension == ".pdf" else header.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0"))
    if header and not valid:
        raise ValidationError("A assinatura do arquivo não corresponde ao formato informado.")


def auditar(request, acao, objeto, antes=None, depois=None, motivo=''):
    Auditoria.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        acao=acao,
        entidade=objeto._meta.label,
        registro_id=str(getattr(objeto, 'uuid', objeto.pk)),
        dados_antes_json=antes or {}, dados_depois_json=depois or {}, motivo=motivo,
        ip=request.META.get('REMOTE_ADDR'), user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
    )


def exige_permissao(usuario, codigo):
    if not usuario_tem_permissao(usuario, codigo):
        raise PermissionDenied


def uuid_field(prefix):
    return models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, db_column=f'{prefix}_uuid')
