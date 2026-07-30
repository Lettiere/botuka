from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario
from apps.organizations.services.subscription_limits import obter_assinatura_vigente

from .models import LimiteProdutoAdicional, Produto


PLAN_LIMITS={'GRATUITO':4,'BRONZE':8,'PRATA':16,'OURO':30,'PREMIUM':50,'EMPRESARIAL':100,'CORPORATIVO':200,'PERSONALIZADO':200}


@dataclass(frozen=True)
class ResultadoLimiteProduto:
    permitido: bool; padrao: int; plano: int; adicional: int
    efetivo: int | None; utilizado: int; disponivel: int | None
    excedido: bool; concessao: object = None


def validar_contexto(user, titular_tipo, empresa=None):
    if titular_tipo==Produto.TitularTipo.PESSOA_FISICA:
        if empresa: raise ValidationError({'empresa_proprietaria':'Produto pessoal não aceita empresa.'})
        return user,None
    if titular_tipo!=Produto.TitularTipo.EMPRESA or not empresa:
        raise ValidationError({'empresa_proprietaria':'Informe a empresa proprietária.'})
    if not empresa.ativo or empresa.status != empresa.Status.ATIVA:
        raise ValidationError({'empresa_proprietaria':'A empresa precisa estar ativa.'})
    if not (usuario_e_master(user) or empresas_gerenciaveis_para_usuario(user).filter(pk=empresa.pk).exists()):
        raise PermissionDenied('Empresa fora do seu escopo.')
    return empresa.usuario_proprietario,empresa


def _grant(user=None,empresa=None):
    now=timezone.now()
    return LimiteProdutoAdicional.objects.filter(
        usuario=user,empresa=empresa,ativo=True,inicio__lte=now,
    ).filter(Q(fim__isnull=True)|Q(fim__gt=now)).order_by('-atualizado_em').first()


def calcular_limite(user, titular_tipo, empresa=None):
    owner,company=validar_contexto(user,titular_tipo,empresa)
    default=10 if company else 4
    subscription=obter_assinatura_vigente(owner)
    plan=PLAN_LIMITS.get(subscription.plano.codigo,default) if subscription else default
    plan=max(default,plan)
    grant=_grant(empresa=company) if company else _grant(user=owner)
    total_manual=grant.limite_total if grant else 0
    adicional_manual=grant.adicional if grant and not grant.limite_total else 0
    effective=None if grant and grant.ilimitado else max(plan,total_manual)+adicional_manual
    used=Produto.all_objects.filter(ativo=True,removido_em__isnull=True).exclude(status=Produto.Status.ARQUIVADO)
    used=used.filter(empresa_proprietaria=company) if company else used.filter(titular_tipo='PF',proprietario=owner)
    count=used.count(); available=None if effective is None else max(effective-count,0)
    return ResultadoLimiteProduto(effective is None or count<effective,default,plan,grant.adicional if grant else 0,effective,count,available,effective is not None and count>effective,grant)


def validar_nova_criacao(user,titular_tipo,empresa=None):
    result=calcular_limite(user,titular_tipo,empresa)
    if not result.permitido:
        raise PermissionDenied(f'Você atingiu o limite de {result.efetivo} produtos. Solicite uma liberação ou plano superior.')
    return result


def validar_documentos_publicacao(produto):
    from apps.painel.forms import cnpj_valido, cpf_valido
    if produto.titular_tipo==Produto.TitularTipo.PESSOA_FISICA:
        owner=produto.proprietario
        if not cpf_valido(owner.cpf): raise ValidationError('Cadastre e valide um CPF válido antes de publicar.')
        complete=all((owner.first_name,owner.last_name,owner.telefone or owner.celular,owner.cep,owner.endereco,owner.numero,owner.bairro,owner.cidade_id,owner.estado_id))
    else:
        company=produto.empresa_proprietaria
        if not cnpj_valido(company.cpf_cnpj): raise ValidationError('A empresa deve possuir CNPJ válido.')
        complete=all((company.razao_social,company.telefone or company.whatsapp or company.email,company.cep,company.endereco,company.numero,company.bairro,company.cidade_id,company.estado_id))
    if not complete: raise ValidationError('Complete o endereço e os dados de contato do titular antes de publicar.')
    return True
import re
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.utils.text import slugify


def normalizar_whatsapp(value):
    digits = re.sub(r'\D', '', value or '')
    if not digits:
        return ''
    if digits.startswith('55') and len(digits) in {12, 13}:
        normalized = digits
    elif len(digits) in {10, 11}:
        normalized = f'55{digits}'
    else:
        raise ValidationError('Informe um WhatsApp brasileiro válido com DDD.')
    return normalized


def whatsapp_produto(produto):
    candidates = [
        produto.whatsapp,
        getattr(produto.empresa_proprietaria, 'whatsapp', '') if produto.empresa_proprietaria_id else '',
        getattr(produto.responsavel, 'telefone', ''),
    ]
    for candidate in candidates:
        try:
            number = normalizar_whatsapp(candidate)
        except ValidationError:
            continue
        if number:
            message = f'Olá! Vi o produto “{produto.nome}” na plataforma BOTUKA e gostaria de mais informações.'
            return {'numero': number, 'url': f'https://wa.me/{number}?text={quote(message)}'}
    return {'numero': '', 'url': ''}


def gerar_codigo_interno(produto):
    """Gera código imutável usando a sequência transacional do PK."""
    if produto.codigo_interno:
        return produto.codigo_interno
    company = produto.empresa_proprietaria
    owner = company or produto.proprietario
    name = getattr(company, 'nome_fantasia', '') or produto.proprietario.get_full_name() or produto.proprietario.username
    document = getattr(company, 'cpf_cnpj', '') or getattr(produto.proprietario, 'cpf', '')
    short_name = (slugify(name).replace('-', '').upper()[:12] or 'VENDEDOR')
    suffix = re.sub(r'\D', '', document)[-4:] or f'{owner.pk:04d}'[-4:]
    return f'BOT-{short_name}-{suffix}-{produto.pk:06d}'
