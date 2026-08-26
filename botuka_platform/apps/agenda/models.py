from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel
from apps.organizations.models import EmpresaUsuario
from apps.services.models import Servico


class AgendaProfissional(UUIDModel):
    """
    Identidade de um profissional habilitado para operar na Agenda.

    Contextos suportados:
    - membro da equipe de uma empresa (EmpresaUsuario);
    - profissional autônomo/pessoa física (Usuario).
    """

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_profissional_id',
    )

    empresa_usuario = models.OneToOneField(
        EmpresaUsuario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='agenda_profissional',
        db_column='agenda_profissional_fk_empresa_usuario',
    )

    usuario_autonomo = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='agenda_profissional_autonomo',
        db_column='agenda_profissional_fk_usuario_autonomo',
    )

    ativo = models.BooleanField(
        default=True,
        db_column='agenda_profissional_ativo',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_profissional_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_profissional_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_profissional_tb"'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        empresa_usuario__isnull=False,
                        usuario_autonomo__isnull=True,
                    )
                    |
                    models.Q(
                        empresa_usuario__isnull=True,
                        usuario_autonomo__isnull=False,
                    )
                ),
                name='agenda_profissional_contexto_ck',
            ),
        ]

    @property
    def usuario(self):
        if self.empresa_usuario_id:
            return self.empresa_usuario.usuario
        return self.usuario_autonomo

    @property
    def empresa(self):
        if self.empresa_usuario_id:
            return self.empresa_usuario.empresa
        return None

    @property
    def eh_empresarial(self):
        return bool(self.empresa_usuario_id)

    def clean(self):
        super().clean()

        possui_empresa = bool(self.empresa_usuario_id)
        possui_autonomo = bool(self.usuario_autonomo_id)

        if possui_empresa == possui_autonomo:
            raise ValidationError(
                'Informe um membro da equipe ou um profissional autônomo, nunca os dois.'
            )

        if self.empresa_usuario_id and not self.empresa_usuario.ativo:
            raise ValidationError({
                'empresa_usuario': 'O membro da equipe precisa estar ativo.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.usuario)


class AgendaProfissionalServico(UUIDModel):
    """
    Define quais serviços um profissional efetivamente executa na Agenda.
    """

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_profissional_servico_id',
    )

    profissional = models.ForeignKey(
        AgendaProfissional,
        on_delete=models.CASCADE,
        related_name='servicos_vinculados',
        db_column='agenda_profissional_servico_fk_profissional',
    )

    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name='profissionais_agenda',
        db_column='agenda_profissional_servico_fk_servico',
    )

    duracao_minutos = models.PositiveIntegerField(
        db_column='agenda_profissional_servico_duracao_minutos',
    )

    ativo = models.BooleanField(
        default=True,
        db_column='agenda_profissional_servico_ativo',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_profissional_servico_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_profissional_servico_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_profissional_servico_tb"'
        ordering = ['profissional_id', 'servico_id']
        constraints = [
            models.UniqueConstraint(
                fields=['profissional', 'servico'],
                name='agenda_profissional_servico_uk',
            ),
            models.CheckConstraint(
                condition=models.Q(duracao_minutos__gt=0),
                name='agenda_prof_serv_duracao_ck',
            ),
        ]

    def clean(self):
        super().clean()

        if not self.profissional_id or not self.servico_id:
            return

        profissional = self.profissional
        servico = self.servico

        if profissional.empresa_usuario_id:
            empresa = profissional.empresa_usuario.empresa

            if servico.prestador_tipo != Servico.PrestadorTipo.EMPRESA:
                raise ValidationError({
                    'servico': 'Profissional de empresa só pode executar serviço empresarial.'
                })

            if servico.empresa_id != empresa.id:
                raise ValidationError({
                    'servico': 'O serviço precisa pertencer à mesma empresa do profissional.'
                })

        else:
            usuario = profissional.usuario_autonomo

            if servico.prestador_tipo != Servico.PrestadorTipo.PESSOA_FISICA:
                raise ValidationError({
                    'servico': 'Profissional autônomo só pode executar serviço de pessoa física.'
                })

            if servico.usuario_responsavel_id != usuario.id:
                raise ValidationError({
                    'servico': 'O serviço precisa pertencer ao próprio profissional autônomo.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.profissional} — {self.servico}'


class AgendaDisponibilidade(UUIDModel):
    """Faixa recorrente semanal de disponibilidade do profissional."""

    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, 'Segunda-feira'
        TERCA = 1, 'Terça-feira'
        QUARTA = 2, 'Quarta-feira'
        QUINTA = 3, 'Quinta-feira'
        SEXTA = 4, 'Sexta-feira'
        SABADO = 5, 'Sábado'
        DOMINGO = 6, 'Domingo'

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_disponibilidade_id',
    )

    profissional = models.ForeignKey(
        AgendaProfissional,
        on_delete=models.CASCADE,
        related_name='disponibilidades',
        db_column='agenda_disponibilidade_fk_profissional',
    )

    dia_semana = models.PositiveSmallIntegerField(
        choices=DiaSemana.choices,
        db_column='agenda_disponibilidade_dia_semana',
    )

    hora_inicio = models.TimeField(
        db_column='agenda_disponibilidade_hora_inicio',
    )

    hora_fim = models.TimeField(
        db_column='agenda_disponibilidade_hora_fim',
    )

    ativo = models.BooleanField(
        default=True,
        db_column='agenda_disponibilidade_ativo',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_disponibilidade_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_disponibilidade_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_disponibilidade_tb"'
        ordering = [
            'profissional_id',
            'dia_semana',
            'hora_inicio',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'profissional',
                    'dia_semana',
                    'hora_inicio',
                    'hora_fim',
                ],
                name='agenda_disponibilidade_uk',
            ),
            models.CheckConstraint(
                condition=models.Q(
                    hora_fim__gt=models.F('hora_inicio')
                ),
                name='agenda_disponibilidade_horario_ck',
            ),
        ]

    def clean(self):
        super().clean()

        if self.hora_inicio and self.hora_fim:
            if self.hora_fim <= self.hora_inicio:
                raise ValidationError({
                    'hora_fim': 'O horário final deve ser posterior ao horário inicial.'
                })

        if not self.profissional_id:
            return

        if not self.profissional.ativo:
            raise ValidationError({
                'profissional': 'O profissional precisa estar ativo.'
            })

        if self.dia_semana is None or not self.hora_inicio or not self.hora_fim:
            return

        conflitos = AgendaDisponibilidade.objects.filter(
            profissional=self.profissional,
            dia_semana=self.dia_semana,
            ativo=True,
            hora_inicio__lt=self.hora_fim,
            hora_fim__gt=self.hora_inicio,
        )

        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)

        if conflitos.exists():
            raise ValidationError(
                'Já existe uma faixa de disponibilidade conflitante.'
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.profissional} — '
            f'{self.get_dia_semana_display()} '
            f'{self.hora_inicio:%H:%M}-{self.hora_fim:%H:%M}'
        )


class AgendaBloqueio(UUIDModel):
    """
    Bloqueio pontual da agenda do profissional.

    Exemplos:
    férias, folga, compromisso pessoal, feriado ou indisponibilidade.
    """

    class Tipo(models.TextChoices):
        FOLGA = 'FOLGA', 'Folga'
        FERIAS = 'FERIAS', 'Férias'
        FERIADO = 'FERIADO', 'Feriado'
        PESSOAL = 'PESSOAL', 'Compromisso pessoal'
        OUTRO = 'OUTRO', 'Outro'

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_bloqueio_id',
    )

    profissional = models.ForeignKey(
        AgendaProfissional,
        on_delete=models.CASCADE,
        related_name='bloqueios',
        db_column='agenda_bloqueio_fk_profissional',
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.OUTRO,
        db_column='agenda_bloqueio_tipo',
    )

    inicio = models.DateTimeField(
        db_column='agenda_bloqueio_inicio',
    )

    fim = models.DateTimeField(
        db_column='agenda_bloqueio_fim',
    )

    motivo = models.CharField(
        max_length=220,
        blank=True,
        db_column='agenda_bloqueio_motivo',
    )

    ativo = models.BooleanField(
        default=True,
        db_column='agenda_bloqueio_ativo',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_bloqueio_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_bloqueio_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_bloqueio_tb"'
        ordering = ['inicio']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fim__gt=models.F('inicio')),
                name='agenda_bloqueio_periodo_ck',
            ),
        ]

    def clean(self):
        super().clean()

        if self.inicio and self.fim and self.fim <= self.inicio:
            raise ValidationError({
                'fim': 'O fim do bloqueio deve ser posterior ao início.'
            })

        if self.profissional_id and not self.profissional.ativo:
            raise ValidationError({
                'profissional': 'O profissional precisa estar ativo.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.profissional} — {self.inicio} até {self.fim}'


class Agendamento(UUIDModel):
    """Reserva de horário de um cliente com um profissional."""

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        CONFIRMADO = 'CONFIRMADO', 'Confirmado'
        CONCLUIDO = 'CONCLUIDO', 'Concluído'
        CANCELADO = 'CANCELADO', 'Cancelado'
        FALTOU = 'FALTOU', 'Cliente não compareceu'

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_agendamento_id',
    )

    profissional_servico = models.ForeignKey(
        AgendaProfissionalServico,
        on_delete=models.PROTECT,
        related_name='agendamentos',
        db_column='agenda_agendamento_fk_profissional_servico',
    )

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='agendamentos_cliente',
        db_column='agenda_agendamento_fk_cliente',
    )

    inicio = models.DateTimeField(
        db_column='agenda_agendamento_inicio',
    )

    fim = models.DateTimeField(
        db_column='agenda_agendamento_fim',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_column='agenda_agendamento_status',
    )

    observacoes = models.TextField(
        blank=True,
        db_column='agenda_agendamento_observacoes',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_agendamento_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_agendamento_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_agendamento_tb"'
        ordering = ['inicio']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fim__gt=models.F('inicio')),
                name='agenda_agendamento_periodo_ck',
            ),
        ]

    @property
    def profissional(self):
        return self.profissional_servico.profissional

    @property
    def servico(self):
        return self.profissional_servico.servico

    def clean(self):
        super().clean()

        if not self.profissional_servico_id:
            return

        if not self.inicio or not self.fim:
            return

        if self.fim <= self.inicio:
            raise ValidationError({
                'fim': 'O fim do agendamento deve ser posterior ao início.'
            })

        vinculo = self.profissional_servico
        profissional = vinculo.profissional

        if not vinculo.ativo or not profissional.ativo:
            raise ValidationError(
                'O profissional ou serviço não está disponível para agendamento.'
            )

        duracao_real = int(
            (self.fim - self.inicio).total_seconds() / 60
        )

        if duracao_real != vinculo.duracao_minutos:
            raise ValidationError({
                'fim': (
                    f'O serviço exige duração de '
                    f'{vinculo.duracao_minutos} minutos.'
                )
            })

        inicio_local = timezone.localtime(self.inicio)
        fim_local = timezone.localtime(self.fim)

        disponibilidade = AgendaDisponibilidade.objects.filter(
            profissional=profissional,
            ativo=True,
            dia_semana=inicio_local.weekday(),
            hora_inicio__lte=inicio_local.time(),
            hora_fim__gte=fim_local.time(),
        ).exists()

        if not disponibilidade:
            raise ValidationError(
                'O horário está fora da disponibilidade do profissional.'
            )

        bloqueado = AgendaBloqueio.objects.filter(
            profissional=profissional,
            ativo=True,
            inicio__lt=self.fim,
            fim__gt=self.inicio,
        ).exists()

        if bloqueado:
            raise ValidationError(
                'O profissional possui um bloqueio nesse período.'
            )

        conflitos = Agendamento.objects.filter(
            profissional_servico__profissional=profissional,
            status__in=[
                self.Status.PENDENTE,
                self.Status.CONFIRMADO,
            ],
            inicio__lt=self.fim,
            fim__gt=self.inicio,
        )

        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)

        if conflitos.exists():
            raise ValidationError(
                'Já existe outro agendamento para este profissional nesse horário.'
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.cliente} — {self.servico} — '
            f'{self.inicio:%d/%m/%Y %H:%M}'
        )
