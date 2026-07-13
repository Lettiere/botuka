"""Modelos de autenticação e contas de usuário."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, Group, Permission, UserManager
from django.db.models import QuerySet
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


class UsuarioManager(UserManager):
    """Manager do usuário customizado."""

    def create_user(
        self,
        username: str,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: object,
    ) -> 'Usuario':
        extra_fields.setdefault('is_active', True)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(
        self,
        username: str,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: object,
    ) -> 'Usuario':
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(UUIDModel, TimeStampedModel, AbstractUser):
    """Usuário customizado da plataforma BOTUKA."""

    id = models.BigAutoField(primary_key=True, db_column='platform_usuario_id')
    perfil = models.ForeignKey(
        'core.Perfil',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='platform_usuario_perfil_fk',
        related_name='usuarios',
        verbose_name='perfil',
    )
    perfis_adicionais = models.ManyToManyField(
        'core.Perfil',
        blank=True,
        through='UsuarioPerfil',
        related_name='usuarios_adicionais',
        verbose_name='perfis adicionais',
    )
    groups = models.ManyToManyField(
        Group,
        blank=True,
        through='UsuarioGrupo',
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='user_set',
        related_query_name='user',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        through='UsuarioPermissao',
        help_text='Specific permissions for this user.',
        related_name='user_set',
        related_query_name='user',
        verbose_name='user permissions',
    )
    telefone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='telefone',
    )
    celular = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='celular',
    )
    foto = models.ImageField(
        upload_to='usuarios/fotos/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='foto',
    )
    ultimo_acesso = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='último acesso',
    )
    nome_exibicao = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='nome de exibição',
    )
    cpf = models.CharField(
        max_length=11,
        blank=True,
        db_index=True,
        verbose_name='CPF',
    )
    data_nascimento = models.DateField(
        blank=True,
        null=True,
        verbose_name='data de nascimento',
    )
    biografia = models.TextField(
        blank=True,
        verbose_name='biografia curta',
    )
    estado = models.ForeignKey(
        'locations.Estado',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='platform_usuario_estado_fk',
        related_name='usuarios',
        verbose_name='estado',
    )
    cidade = models.ForeignKey(
        'locations.Cidade',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='platform_usuario_cidade_fk',
        related_name='usuarios',
        verbose_name='cidade',
    )

    objects = UsuarioManager()

    class Meta:
        ordering = ['first_name', 'last_name', 'username']
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
        db_table = '"platform"."platform_usuario_tb"'
        indexes = [
            models.Index(fields=['uuid'], name='platform_usuario_uuid_idx'),
            models.Index(fields=['email'], name='platform_usuario_email_idx'),
            models.Index(fields=['is_active'], name='platform_usuario_active_idx'),
            models.Index(fields=['perfil'], name='platform_usuario_perfil_idx'),
            models.Index(fields=['cpf'], name='platform_usuario_cpf_idx'),
            models.Index(fields=['cidade'], name='platform_usuario_cidade_idx'),
        ]

    def __str__(self) -> str:
        return self.nome_exibicao or self.get_full_name() or self.username

    @property
    def cpf_mascarado(self) -> str:
        """Retorna CPF mascarado para exibição segura."""

        if not self.cpf or len(self.cpf) != 11:
            return ''

        return f'{self.cpf[:3]}.***.***-{self.cpf[-2:]}'

    @property
    def percentual_perfil(self) -> int:
        """Calcula uma conclusão simples do perfil público."""

        campos = [
            self.first_name,
            self.last_name,
            self.email,
            self.telefone,
            self.celular,
            self.foto,
            self.nome_exibicao,
            self.cpf,
            self.data_nascimento,
            self.biografia,
            self.cidade_id,
            self.estado_id,
        ]
        preenchidos = len([campo for campo in campos if campo])
        return round((preenchidos / len(campos)) * 100)

    def registrar_acesso(self) -> None:
        """Atualiza o marcador de último acesso do domínio."""

        self.ultimo_acesso = timezone.now()
        self.save(update_fields=['ultimo_acesso', 'atualizado_em'])

    def tem_perfil(self, nome: str) -> bool:
        """Verifica se o usuário possui o perfil informado."""

        if self.is_superuser:
            return True

        if not self.perfil_id:
            return False

        return self.perfil.nome.upper() == nome.upper()

    def permissoes_do_perfil(self) -> QuerySet:
        """Retorna permissões ativas vinculadas ao perfil principal."""

        if not self.perfil_id:
            from apps.core.models import Permissao

            return Permissao.objects.none()

        return self.perfil.perfil_permissoes.filter(
            ativo=True,
            permissao__ativo=True,
        ).select_related('permissao')

    def tem_permissao(self, codigo: str | None = None) -> bool:
        """Verifica permissão de domínio pelo código."""

        if self.is_superuser or self.tem_perfil('MASTER'):
            return True

        if not codigo or not self.perfil_id:
            return False

        return self.perfil.perfil_permissoes.filter(
            ativo=True,
            permissao__ativo=True,
            permissao__codigo=codigo,
        ).exists()


class UsuarioGrupo(UUIDModel, TimeStampedModel):
    """Tabela controlada para vínculo entre usuários e grupos do Django."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_usuario_grupo_id',
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='platform_usuario_fk',
    )
    grupo = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column='platform_grupo_fk',
    )

    class Meta:
        db_table = '"platform"."platform_usuario_grupo_tb"'
        ordering = ['usuario__username', 'grupo__name']
        verbose_name = 'grupo do usuário'
        verbose_name_plural = 'grupos dos usuários'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'grupo'],
                name='platform_usuario_grupo_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['usuario', 'grupo'], name='platform_user_group_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.usuario} - {self.grupo}'


class UsuarioPermissao(UUIDModel, TimeStampedModel):
    """Tabela controlada para vínculo entre usuários e permissões do Django."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_usuario_permissao_id',
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='platform_usuario_fk',
    )
    permissao = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        db_column='platform_permissao_fk',
    )

    class Meta:
        db_table = '"platform"."platform_usuario_permissao_tb"'
        ordering = ['usuario__username', 'permissao__codename']
        verbose_name = 'permissão do usuário'
        verbose_name_plural = 'permissões dos usuários'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'permissao'],
                name='platform_usuario_permissao_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['usuario', 'permissao'],
                name='platform_user_perm_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.usuario} - {self.permissao}'


class UsuarioPerfil(UUIDModel, TimeStampedModel):
    """Perfis adicionais vinculados ao usuário sem substituir o principal."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_usuario_perfil_adicional_id',
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='platform_usuario_fk',
        related_name='usuario_perfis_adicionais',
    )
    perfil = models.ForeignKey(
        'core.Perfil',
        on_delete=models.CASCADE,
        db_column='platform_perfil_fk',
        related_name='usuario_perfis_adicionais',
    )

    class Meta:
        db_table = '"platform"."platform_usuario_perfil_adicional_tb"'
        ordering = ['usuario__username', 'perfil__nome']
        verbose_name = 'perfil adicional do usuário'
        verbose_name_plural = 'perfis adicionais dos usuários'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'perfil'],
                name='platform_usuario_perfil_adic_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['usuario', 'perfil'],
                name='platform_user_perfil_adic_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.usuario} - {self.perfil}'
