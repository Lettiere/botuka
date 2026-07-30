from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    BloqueioNegociacao,
    Conversa,
    LogVerificacaoVendedor,
    MensagemConversa,
    Produto,
)


@dataclass(frozen=True)
class VerificationResult:
    allowed: bool
    code: str
    message: str


class SellerVerificationService:
    """Ponto único para verificações atuais e integrações futuras, sem API externa."""

    def can_start_conversation(self, *, seller, product, buyer):
        result = VerificationResult(True, 'OK', 'Conversa autorizada.')
        if not buyer.is_authenticated or not buyer.is_active:
            result = VerificationResult(False, 'BUYER_INACTIVE', 'Entre em sua conta para conversar.')
        elif buyer.pk == seller.pk:
            result = VerificationResult(False, 'SELF_CONVERSATION', 'Não é possível conversar consigo mesmo.')
        elif not seller.is_active:
            result = VerificationResult(False, 'SELLER_INACTIVE', 'Vendedor indisponível.')
        elif product.status != Produto.Status.PUBLICADO or not product.publico or not product.ativo or product.removido_em:
            result = VerificationResult(False, 'PRODUCT_UNAVAILABLE', 'Produto indisponível.')
        elif BloqueioNegociacao.objects.filter(
            ativo=True, bloqueador__in=(buyer, seller), bloqueado__in=(buyer, seller),
        ).exists():
            result = VerificationResult(False, 'PARTICIPANT_BLOCKED', 'Conversa não autorizada.')
        LogVerificacaoVendedor.objects.create(
            vendedor=seller, produto=product, comprador=buyer,
            permitido=result.allowed, codigo=result.code,
        )
        return result


seller_verification_service = SellerVerificationService()


@transaction.atomic
def iniciar_conversa(*, product, buyer, initial_message=''):
    seller = product.proprietario
    result = seller_verification_service.can_start_conversation(
        seller=seller, product=product, buyer=buyer,
    )
    if not result.allowed:
        raise ValidationError(result.message, code=result.code)
    conversation, _ = Conversa.objects.get_or_create(
        produto=product, comprador=buyer, vendedor=seller,
        status=Conversa.Status.ATIVA,
        defaults={'empresa': product.empresa_proprietaria},
    )
    if initial_message:
        MensagemConversa.objects.create(
            conversa=conversation, remetente=buyer, conteudo=initial_message,
        )
    return conversation
