from django.db import models
from django.conf import settings


class EditorialWorkflowStatus(models.TextChoices):
    """Vocabulário comum para adoção gradual pelos módulos editoriais."""

    RASCUNHO = "RASCUNHO", "Rascunho"
    EM_REVISAO = "EM_REVISAO", "Em revisão"
    EM_AJUSTE = "EM_AJUSTE", "Em ajuste"
    APROVADO = "APROVADO", "Aprovado"
    AGENDADO = "AGENDADO", "Agendado"
    PUBLICADO = "PUBLICADO", "Publicado"
    ARQUIVADO = "ARQUIVADO", "Arquivado"
    REJEITADO = "REJEITADO", "Rejeitado"


class EditorialAttributionMixin(models.Model):
    """Contrato abstrato de autoria/publicação para adoção pelos módulos futuros."""

    autor_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    organizacao_publicadora = models.ForeignKey(
        'organizations.Empresa', on_delete=models.PROTECT, related_name='+',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    status_editorial = models.CharField(
        max_length=20, choices=EditorialWorkflowStatus.choices,
        default=EditorialWorkflowStatus.RASCUNHO,
    )
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
