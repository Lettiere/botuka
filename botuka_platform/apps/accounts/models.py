"""Modelos de autenticação e contas de usuário."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission, UserManager
from django.db.models import QuerySet
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel
from apps.accounts.validators import normalizar_cpf, validar_cpf


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
        validators=[validar_cpf],
        verbose_name='CPF',
    )
    cpf_validado_em = models.DateTimeField(blank=True, null=True, verbose_name='CPF validado em')
    bairro = models.CharField(max_length=120, blank=True, verbose_name='bairro ou região')
    endereco = models.CharField(max_length=180, blank=True, verbose_name='endereço')
    numero = models.CharField(max_length=20, blank=True, verbose_name='número')
    complemento = models.CharField(max_length=120, blank=True, verbose_name='complemento')
    cep = models.CharField(max_length=8, blank=True, verbose_name='CEP')
    termos_contratante_aceitos_em = models.DateTimeField(
        blank=True, null=True, verbose_name='termos de contratante aceitos em',
    )
    class VisibilidadeLocalizacao(models.TextChoices):
        PUBLICA = 'PUBLICA', 'Cidade e estado'
        APROXIMADA = 'APROXIMADA', 'Cidade, estado e região'
        PRIVADA = 'PRIVADA', 'Privada'

    visibilidade_localizacao = models.CharField(
        max_length=12, choices=VisibilidadeLocalizacao.choices,
        default=VisibilidadeLocalizacao.PUBLICA,
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
        constraints = [
            models.UniqueConstraint(
                fields=['cpf'], condition=~models.Q(cpf=''),
                name='platform_usuario_cpf_uk',
            ),
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

    @property
    def perfil_contratante_completo(self) -> bool:
        return all((
            self.first_name, self.last_name, self.cpf, self.cpf_validado_em,
            self.telefone or self.celular, self.cidade_id, self.estado_id,
            self.bairro, self.termos_contratante_aceitos_em,
        ))

    def registrar_acesso(self) -> None:
        """Atualiza o marcador de último acesso do domínio."""

        self.ultimo_acesso = timezone.now()
        self.save(update_fields=['ultimo_acesso', 'atualizado_em'])

    def save(self, *args, **kwargs):
        self.cpf = normalizar_cpf(self.cpf)
        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).values(
                'cpf', 'cpf_validado_em',
            ).first()
            if (
                anterior is not None and anterior['cpf'] != self.cpf
                and self.cpf_validado_em == anterior['cpf_validado_em']
            ):
                self.cpf_validado_em = None
        super().save(*args, **kwargs)

    def tem_perfil(self, nome: str) -> bool:
        """Verifica se o usuário possui o perfil informado."""

        from apps.accounts.permissions import usuario_e_master

        if usuario_e_master(self):
            return True
        nome_normalizado = nome.upper()
        if (
            self.perfil_id
            and self.perfil.ativo
            and self.perfil.removido_em is None
            and self.perfil.nome.upper() == nome_normalizado
        ):
            return True
        return self.usuario_perfis_adicionais.filter(
            perfil__nome__iexact=nome_normalizado,
            perfil__ativo=True,
            perfil__removido_em__isnull=True,
        ).exists()

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

        from apps.accounts.permissions import usuario_e_master

        if usuario_e_master(self) or self.tem_perfil('ROOT'):
            return True

        if not codigo:
            return False
        if self.concessoes_permissao.filter(
            permissao__codigo=codigo,
            permissao__ativo=True,
            revogada_em__isnull=True,
        ).filter(
            models.Q(valida_ate__isnull=True) | models.Q(valida_ate__gt=timezone.now())
        ).exists():
            return True
        from apps.core.models import PerfilPermissao
        return PerfilPermissao.objects.filter(
            perfil__in=self.perfis_adicionais.all() if not self.perfil_id else self.perfis_adicionais.all() | type(self.perfil).objects.filter(pk=self.perfil_id),
            ativo=True,
            permissao__ativo=True,
            permissao__codigo=codigo,
        ).exists()


class AcessoModulo(UUIDModel, TimeStampedModel):
    """Acesso único de um usuário a um módulo, com perfil e escopo próprios."""

    class Escopo(models.TextChoices):
        PROPRIOS = 'PROPRIOS', 'Próprios'
        EQUIPE = 'EQUIPE', 'Equipe'
        ORGANIZACAO = 'ORGANIZACAO', 'Organização'
        TODOS = 'TODOS', 'Todos'

    class Status(models.TextChoices):
        ATIVO = 'ATIVO', 'Ativo'
        SUSPENSO = 'SUSPENSO', 'Suspenso'
        REVOGADO = 'REVOGADO', 'Revogado'

    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='acessos_modulos',
    )
    modulo = models.CharField(max_length=60, db_index=True)
    perfil = models.ForeignKey(
        'core.Perfil', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acessos_modulos',
    )
    escopo = models.CharField(
        max_length=16, choices=Escopo.choices, default=Escopo.PROPRIOS,
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ATIVO,
        db_index=True,
    )
    concedido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='acessos_modulos_concedidos',
    )
    valida_ate = models.DateTimeField(null=True, blank=True)
    justificativa = models.TextField()
    observacao = models.TextField(blank=True)
    revogado_em = models.DateTimeField(null=True, blank=True)
    revogado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='acessos_modulos_revogados',
    )

    class Meta:
        ordering = ['usuario', 'modulo']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'modulo'],
                condition=~models.Q(status='REVOGADO'),
                name='accounts_acesso_modulo_corrente_uk',
            ),
        ]

    @property
    def vigente(self):
        return (
            self.status == self.Status.ATIVO
            and (self.valida_ate is None or self.valida_ate > timezone.now())
        )

    @property
    def total_permissoes(self):
        return self.concessoes.filter(revogada_em__isnull=True).count()


class ConcessaoPermissao(UUIDModel, TimeStampedModel):
    """Concessão individual, temporal e auditável de permissão de domínio."""

    class Escopo(models.TextChoices):
        PROPRIOS = 'PROPRIOS', 'Apenas registros próprios'
        EQUIPE = 'EQUIPE', 'Registros da própria equipe'
        ORGANIZACAO = 'ORGANIZACAO', 'Registros da própria organização'
        TODOS = 'TODOS', 'Todos os registros do módulo'

    id = models.BigAutoField(primary_key=True)
    acesso = models.ForeignKey(
        AcessoModulo, on_delete=models.PROTECT, null=True, blank=True,
        related_name='concessoes',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='concessoes_permissao',
    )
    permissao = models.ForeignKey(
        'core.Permissao', on_delete=models.PROTECT,
        related_name='concessoes_usuarios',
    )
    concedida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='permissoes_concedidas',
    )
    valida_ate = models.DateTimeField(null=True, blank=True)
    revogada_em = models.DateTimeField(null=True, blank=True)
    revogada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='permissoes_revogadas',
    )
    justificativa = models.TextField()
    observacao = models.TextField(blank=True)
    escopo = models.CharField(
        max_length=16, choices=Escopo.choices, default=Escopo.PROPRIOS,
        db_index=True,
    )
    perfil_funcional = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['usuario', 'permissao__codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'permissao'],
                condition=models.Q(revogada_em__isnull=True),
                name='accounts_concessao_ativa_uk',
            ),
        ]


class AuditoriaPermissao(UUIDModel, TimeStampedModel):
    class Acao(models.TextChoices):
        CONCEDER = 'CONCEDER', 'Conceder'
        REVOGAR = 'REVOGAR', 'Revogar'
        ALTERAR = 'ALTERAR', 'Alterar'

    id = models.BigAutoField(primary_key=True)
    usuario_beneficiado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='auditorias_permissao_recebidas',
    )
    permissao = models.ForeignKey('core.Permissao', on_delete=models.PROTECT)
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='auditorias_permissao_executadas',
    )
    acao = models.CharField(max_length=12, choices=Acao.choices)
    ip = models.GenericIPAddressField(null=True, blank=True)
    justificativa = models.TextField()
    estado_anterior = models.JSONField(default=dict)
    estado_posterior = models.JSONField(default=dict)

    class Meta:
        ordering = ['-criado_em']


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
