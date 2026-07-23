"""Provisionamento seguro do perfil e de usuários MASTER."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.core.models import Perfil, PerfilPermissao, Permissao


@transaction.atomic
def garantir_usuario_master(*, email: str, senha: str, username: str | None = None):
    """Cria ou atualiza um MASTER sem duplicar o usuário."""

    email = email.strip().lower()
    username = (username or email).strip()
    perfil, _ = Perfil.all_objects.update_or_create(
        nome='MASTER',
        defaults={
            'descricao': 'Acesso global à plataforma BOTUKA.',
            'ativo': True,
            'removido_em': None,
        },
    )
    permissoes = Permissao.objects.filter(ativo=True, removido_em__isnull=True)
    for permissao in permissoes:
        PerfilPermissao.all_objects.update_or_create(
            perfil=perfil,
            permissao=permissao,
            defaults={'ativo': True, 'removido_em': None},
        )

    Usuario = get_user_model()
    usuario = Usuario.objects.filter(Q(email__iexact=email) | Q(username__iexact=username)).first()
    criado = usuario is None
    if criado:
        usuario = Usuario(username=username, email=email)
    elif usuario.username.lower() != username.lower():
        if not Usuario.objects.exclude(pk=usuario.pk).filter(username__iexact=username).exists():
            usuario.username = username

    usuario.email = email
    usuario.perfil = perfil
    usuario.is_active = True
    usuario.is_staff = True
    usuario.is_superuser = True
    usuario.set_password(senha)
    usuario.save()
    return usuario, criado
