from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel
from apps.organizations.models import Empresa, EmpresaUsuario
from apps.services.models import Servico


class AgendaEmpresa(UUIDModel):
    """Estado operacional explícito da Agenda de uma empresa."""

    class Status(models.TextChoices):
        PENDENTE_CONFIGURACAO = 'PENDENTE_CONFIGURACAO', 'Pendente de configuração'
        FECHADA = 'FECHADA', 'Fechada'
        ABERTA = 'ABERTA', 'Aberta'

    id = models.BigAutoField(primary_key=True, db_column='agenda_empresa_id')
    empresa = models.OneToOneField(
        Empresa, on_delete=models.CASCADE, related_name='agenda_configuracao',
        db_column='agenda_empresa_fk_empresa',
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDENTE_CONFIGURACAO,
        db_column='agenda_empresa_status',
    )
    antecedencia_minima_minutos = models.PositiveIntegerField(
        default=0, db_column='agenda_empresa_antecedencia_minima_minutos',
    )
    horizonte_maximo_dias = models.PositiveIntegerField(
        default=90, db_column='agenda_empresa_horizonte_maximo_dias',
    )
    intervalo_grade_minutos = models.PositiveIntegerField(
        default=0, db_column='agenda_empresa_intervalo_grade_minutos',
    )
    cancelamento_antecedencia_minutos = models.PositiveIntegerField(
        default=0, db_column='agenda_empresa_cancelamento_antecedencia_minutos',
    )
    aberto_em = models.DateTimeField(null=True, blank=True, db_column='agenda_empresa_aberto_em')
    fechado_em = models.DateTimeField(null=True, blank=True, db_column='agenda_empresa_fechado_em')
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='agendas_empresa_atualizadas', db_column='agenda_empresa_fk_atualizado_por',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='agenda_empresa_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='agenda_empresa_atualizado_em')

    class Meta:
        db_table = '"agenda"."agenda_empresa_tb"'
        ordering = ['empresa_id']

    def clean(self):
        super().clean()
        if self.intervalo_grade_minutos > 1440:
            raise ValidationError({'intervalo_grade_minutos': 'O intervalo não pode ultrapassar 24 horas.'})
        if self.horizonte_maximo_dias < 1:
            raise ValidationError({'horizonte_maximo_dias': 'O horizonte deve ser de pelo menos um dia.'})

    def __str__(self):
        return f'{self.empresa} — {self.get_status_display()}'


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

    buffer_antes_minutos = models.PositiveIntegerField(
        default=0,
        db_column='agenda_profissional_servico_buffer_antes_minutos',
    )

    buffer_depois_minutos = models.PositiveIntegerField(
        default=0,
        db_column='agenda_profissional_servico_buffer_depois_minutos',
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
        for campo in ('buffer_antes_minutos', 'buffer_depois_minutos'):
            valor = getattr(self, campo, 0)
            if valor is not None and valor > 1440:
                raise ValidationError({campo: 'O buffer não pode exceder 24 horas.'})

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


class AgendaFuncionamentoEmpresa(UUIDModel):
    """Faixa semanal que limita a operação da Agenda de uma empresa."""

    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, 'Segunda-feira'
        TERCA = 1, 'Terça-feira'
        QUARTA = 2, 'Quarta-feira'
        QUINTA = 3, 'Quinta-feira'
        SEXTA = 4, 'Sexta-feira'
        SABADO = 5, 'Sábado'
        DOMINGO = 6, 'Domingo'

    id = models.BigAutoField(primary_key=True, db_column='agenda_funcionamento_empresa_id')
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name='funcionamentos_agenda',
        db_column='agenda_funcionamento_empresa_fk_empresa',
    )
    dia_semana = models.PositiveSmallIntegerField(
        choices=DiaSemana.choices, db_column='agenda_funcionamento_empresa_dia_semana',
    )
    hora_inicio = models.TimeField(db_column='agenda_funcionamento_empresa_hora_inicio')
    hora_fim = models.TimeField(db_column='agenda_funcionamento_empresa_hora_fim')
    ativo = models.BooleanField(default=True, db_column='agenda_funcionamento_empresa_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='agenda_funcionamento_empresa_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='agenda_funcionamento_empresa_atualizado_em')

    class Meta:
        db_table = '"agenda"."agenda_funcionamento_empresa_tb"'
        ordering = ['empresa_id', 'dia_semana', 'hora_inicio']
        verbose_name = 'funcionamento da empresa na Agenda'
        verbose_name_plural = 'funcionamentos das empresas na Agenda'
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'dia_semana', 'hora_inicio', 'hora_fim'],
                name='agenda_func_empresa_periodo_uk',
            ),
            models.CheckConstraint(
                condition=models.Q(dia_semana__gte=0, dia_semana__lte=6),
                name='agenda_func_empresa_dia_ck',
            ),
            models.CheckConstraint(
                condition=models.Q(hora_fim__gt=models.F('hora_inicio')),
                name='agenda_func_empresa_horario_ck',
            ),
        ]
        indexes = [
            models.Index(
                fields=['empresa', 'dia_semana', 'ativo'],
                name='agenda_func_empresa_dia_idx',
            ),
        ]

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
            raise ValidationError({'hora_fim': 'O horário final deve ser posterior ao inicial.'})
        if self.empresa_id is None or self.dia_semana is None or not self.hora_inicio or not self.hora_fim:
            return
        conflitos = AgendaFuncionamentoEmpresa.objects.filter(
            empresa=self.empresa, dia_semana=self.dia_semana, ativo=True,
            hora_inicio__lt=self.hora_fim, hora_fim__gt=self.hora_inicio,
        )
        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)
        if conflitos.exists():
            raise ValidationError('Já existe um período de funcionamento conflitante.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.empresa} — {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fim:%H:%M}'


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


class AgendaDisponibilidadeData(UUIDModel):
    """
    Faixa de disponibilidade específica para uma data do calendário.

    Quando existir disponibilidade específica para uma data,
    ela poderá sobrescrever a disponibilidade semanal recorrente.
    """

    id = models.BigAutoField(
        primary_key=True,
        db_column='agenda_disponibilidade_data_id',
    )

    profissional = models.ForeignKey(
        AgendaProfissional,
        on_delete=models.CASCADE,
        related_name='disponibilidades_data',
        db_column='agenda_disponibilidade_data_fk_profissional',
    )

    data = models.DateField(
        db_column='agenda_disponibilidade_data_data',
    )

    hora_inicio = models.TimeField(
        db_column='agenda_disponibilidade_data_hora_inicio',
    )

    hora_fim = models.TimeField(
        db_column='agenda_disponibilidade_data_hora_fim',
    )

    ativo = models.BooleanField(
        default=True,
        db_column='agenda_disponibilidade_data_ativo',
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='agenda_disponibilidade_data_criado_em',
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='agenda_disponibilidade_data_atualizado_em',
    )

    class Meta:
        db_table = '"agenda"."agenda_disponibilidade_data_tb"'
        ordering = [
            'profissional_id',
            'data',
            'hora_inicio',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'profissional',
                    'data',
                    'hora_inicio',
                    'hora_fim',
                ],
                name='agenda_disponibilidade_data_uk',
            ),
            models.CheckConstraint(
                condition=models.Q(
                    hora_fim__gt=models.F('hora_inicio')
                ),
                name='agenda_disponibilidade_data_horario_ck',
            ),
        ]
        indexes = [
            models.Index(
                fields=['profissional', 'data', 'ativo'],
                name='agenda_disp_data_prof_idx',
            ),
        ]

    def clean(self):
        super().clean()

        if self.hora_inicio and self.hora_fim:
            if self.hora_fim <= self.hora_inicio:
                raise ValidationError({
                    'hora_fim':
                    'O horário final deve ser posterior ao horário inicial.'
                })

        if not self.profissional_id:
            return

        if not self.profissional.ativo:
            raise ValidationError({
                'profissional': 'O profissional precisa estar ativo.'
            })

        if not self.data or not self.hora_inicio or not self.hora_fim:
            return

        conflitos = AgendaDisponibilidadeData.objects.filter(
            profissional=self.profissional,
            data=self.data,
            ativo=True,
            hora_inicio__lt=self.hora_fim,
            hora_fim__gt=self.hora_inicio,
        )

        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)

        if conflitos.exists():
            raise ValidationError(
                'Já existe uma disponibilidade conflitante nesta data.'
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.profissional} — '
            f'{self.data:%d/%m/%Y} '
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
        ocupacao_inicio = inicio_local - timedelta(
            minutes=vinculo.buffer_antes_minutos
        )
        ocupacao_fim = fim_local + timedelta(
            minutes=vinculo.buffer_depois_minutos
        )

        mesma_data = (
            ocupacao_inicio.date() == ocupacao_fim.date()
        )

        disponibilidades_data = AgendaDisponibilidadeData.objects.filter(
            profissional=profissional,
            data=ocupacao_inicio.date(),
            ativo=True,
        )

        if disponibilidades_data.exists():
            disponibilidade = (
                mesma_data
                and disponibilidades_data.filter(
                    hora_inicio__lte=ocupacao_inicio.time(),
                    hora_fim__gte=ocupacao_fim.time(),
                ).exists()
            )
        else:
            disponibilidade = (
                mesma_data
                and AgendaDisponibilidade.objects.filter(
                    profissional=profissional,
                    ativo=True,
                    dia_semana=ocupacao_inicio.weekday(),
                    hora_inicio__lte=ocupacao_inicio.time(),
                    hora_fim__gte=ocupacao_fim.time(),
                ).exists()
            )

        if not disponibilidade:
            raise ValidationError(
                'O horário está fora da disponibilidade do profissional.'
            )

        empresa = profissional.empresa
        if empresa and AgendaFuncionamentoEmpresa.objects.filter(empresa=empresa).exists():
            funcionamento = (
                ocupacao_inicio.date() == ocupacao_fim.date()
                and AgendaFuncionamentoEmpresa.objects.filter(
                empresa=empresa, ativo=True,
                dia_semana=ocupacao_inicio.weekday(),
                hora_inicio__lte=ocupacao_inicio.time(),
                hora_fim__gte=ocupacao_fim.time(),
                ).exists()
            )
            if not funcionamento:
                raise ValidationError('O horário está fora do funcionamento da empresa.')

        bloqueado = AgendaBloqueio.objects.filter(
            profissional=profissional,
            ativo=True,
            inicio__lt=ocupacao_fim,
            fim__gt=ocupacao_inicio,
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
        ).select_related('profissional_servico')

        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)

        if any(
            outro.inicio - timedelta(
                minutes=outro.profissional_servico.buffer_antes_minutos
            ) < ocupacao_fim
            and outro.fim + timedelta(
                minutes=outro.profissional_servico.buffer_depois_minutos
            ) > ocupacao_inicio
            for outro in conflitos
        ):
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


class AgendamentoHistorico(UUIDModel):
    class Acao(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        STATUS = 'STATUS', 'Status alterado'
        REAGENDADO = 'REAGENDADO', 'Reagendado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    id = models.BigAutoField(primary_key=True, db_column='agenda_historico_id')
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name='historico',
        db_column='agenda_historico_fk_agendamento',
    )
    acao = models.CharField(max_length=20, choices=Acao.choices, db_column='agenda_historico_acao')
    status_anterior = models.CharField(max_length=20, blank=True, db_column='agenda_historico_status_anterior')
    status_novo = models.CharField(max_length=20, blank=True, db_column='agenda_historico_status_novo')
    inicio_anterior = models.DateTimeField(null=True, blank=True, db_column='agenda_historico_inicio_anterior')
    inicio_novo = models.DateTimeField(null=True, blank=True, db_column='agenda_historico_inicio_novo')
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='historicos_agendamento_realizados', db_column='agenda_historico_fk_realizado_por',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='agenda_historico_criado_em')

    class Meta:
        db_table = '"agenda"."agenda_agendamento_historico_tb"'
        ordering = ['-criado_em', '-id']
        indexes = [models.Index(fields=['agendamento', 'criado_em'], name='agenda_hist_agend_data_idx')]
