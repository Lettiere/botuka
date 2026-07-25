import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.organizations.models import Empresa


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class BaseAtiva(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    excluido_em = models.DateTimeField(null=True, blank=True)
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}


class Vaga(BaseAtiva):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        PUBLICADA = 'PUBLICADA', 'Publicada'
        PAUSADA = 'PAUSADA', 'Pausada'
        ENCERRADA = 'ENCERRADA', 'Encerrada'
        EXPIRADA = 'EXPIRADA', 'Expirada'
        REJEITADA = 'REJEITADA', 'Rejeitada'

    class VisibilidadeLocalizacao(models.TextChoices):
        PUBLICA = 'PUBLICA', 'Cidade e estado'
        APROXIMADA = 'APROXIMADA', 'Cidade, estado e bairro/região'
        PRIVADA = 'PRIVADA', 'Localização privada'

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='vagas', null=True, blank=True,
    )
    perfil_pessoa_fisica = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='vagas_como_pessoa_fisica',
    )
    usuario_criador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='vagas_criadas',
    )
    usuario_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vagas_responsavel')
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    descricao = models.TextField()
    requisitos = models.TextField(blank=True)
    responsabilidades = models.TextField(blank=True)
    beneficios = models.TextField(blank=True)
    tipo_contrato = models.CharField(max_length=40)
    modalidade = models.CharField(max_length=30)
    jornada = models.CharField(max_length=60, blank=True)
    quantidade = models.PositiveIntegerField(default=1)
    salario_minimo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salario_maximo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cidade = models.CharField(max_length=120)
    estado = models.CharField(max_length=2)
    bairro = models.CharField(max_length=120, blank=True)
    endereco_privado = models.CharField(max_length=255, blank=True)
    visibilidade_localizacao = models.CharField(
        max_length=12, choices=VisibilidadeLocalizacao.choices,
        default=VisibilidadeLocalizacao.PUBLICA,
    )
    ocultar_salario = models.BooleanField(default=False)
    destaque = models.BooleanField(default=False)
    aceita_candidatura_simplificada = models.BooleanField(default=False)
    categoria = models.CharField(max_length=120, blank=True)
    area_atuacao = models.CharField(max_length=120, blank=True)
    aceita_pcd = models.BooleanField(default=False)
    experiencia = models.CharField(max_length=120, blank=True)
    escolaridade = models.CharField(max_length=120, blank=True)
    inicio = models.DateField(null=True, blank=True)
    encerramento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    motivo_rejeicao = models.TextField(blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recruitment_vaga_tb'
        ordering = ['-criado_em']
        indexes = [models.Index(fields=['empresa', 'status', 'ativo'], name='recruit_vaga_emp_status_idx'), models.Index(fields=['slug'], name='recruit_vaga_slug_idx')]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(empresa__isnull=False) & Q(perfil_pessoa_fisica__isnull=True))
                    | (Q(empresa__isnull=True) & Q(perfil_pessoa_fisica__isnull=False))
                ),
                name='recruit_vaga_responsavel_xor_ck',
            ),
        ]

    def clean(self):
        errors = {}
        if self.salario_minimo is not None and self.salario_maximo is not None and self.salario_maximo < self.salario_minimo:
            errors['salario_maximo'] = 'O salário máximo deve ser maior ou igual ao mínimo.'
        if self.inicio and self.encerramento and self.encerramento < self.inicio:
            errors['encerramento'] = 'O encerramento deve ser posterior ou igual ao início.'
        if bool(self.empresa_id) == bool(self.perfil_pessoa_fisica_id):
            errors['empresa'] = 'Informe somente uma empresa ou um contratante pessoa física.'
        if self.empresa_id and self.status == self.Status.PUBLICADA:
            from apps.integrations.cnpj.services import cnpj_valido
            if (
                not self.empresa.ativo
                or self.empresa.status != Empresa.Status.ATIVA
                or not cnpj_valido(self.empresa.cpf_cnpj)
            ):
                errors['empresa'] = 'A empresa deve estar ativa e possuir CNPJ válido.'
        if self.perfil_pessoa_fisica_id and not self.perfil_pessoa_fisica.perfil_contratante_completo:
            errors['perfil_pessoa_fisica'] = 'O perfil do contratante deve estar completo e validado.'
        if self.status == self.Status.PUBLICADA:
            required = ('titulo', 'descricao', 'tipo_contrato', 'modalidade', 'cidade', 'estado')
            missing = [field for field in required if not getattr(self, field)]
            if missing:
                errors['status'] = 'Complete os campos obrigatórios antes de publicar.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        from apps.core.utils import gerar_slug_unico
        if not self.usuario_criador_id:
            self.usuario_criador_id = self.usuario_responsavel_id
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.titulo)
        if self.status == self.Status.PUBLICADA and not self.publicado_em:
            self.publicado_em = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo

    @property
    def responsavel_publico(self):
        if self.empresa_id:
            return self.empresa.nome_fantasia or self.empresa.razao_social
        perfil = self.perfil_pessoa_fisica
        return perfil.nome_exibicao or 'Contratante verificado'

    @property
    def contratante_verificado(self):
        return bool(self.empresa_id or (
            self.perfil_pessoa_fisica_id and self.perfil_pessoa_fisica.cpf_validado_em
        ))


class Curriculo(BaseAtiva):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        EM_PREENCHIMENTO = 'EM_PREENCHIMENTO', 'Em preenchimento'
        CONCLUIDO = 'CONCLUIDO', 'Concluído'

    class Visibilidade(models.TextChoices):
        PRIVADO = 'PRIVADO', 'Privado'
        CANDIDATURAS = 'CANDIDATURAS', 'Visível apenas em candidaturas'
        PUBLICO = 'PUBLICO', 'Público'

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='curriculo')
    titulo_profissional = models.CharField(max_length=180, blank=True)
    area_profissional = models.CharField(max_length=120, blank=True)
    objetivo_profissional = models.TextField(blank=True)
    resumo = models.TextField(blank=True)
    nivel_profissional = models.CharField(max_length=30, blank=True)
    disponibilidade = models.CharField(max_length=40, blank=True)
    tipo_contratacao_desejada = models.CharField(max_length=40, blank=True)
    modalidade_preferida = models.CharField(max_length=30, blank=True)
    pretensao_salarial = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    disponivel_viagens = models.BooleanField(default=False)
    disponivel_mudanca = models.BooleanField(default=False)
    telefone_publico = models.CharField(max_length=30, blank=True)
    email_publico = models.EmailField(blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    linkedin = models.URLField(blank=True)
    portfolio = models.URLField(blank=True)
    site_profissional = models.URLField(blank=True)
    github = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    visibilidade = models.CharField(max_length=20, choices=Visibilidade.choices, default=Visibilidade.PRIVADO)
    etapa_atual = models.PositiveSmallIntegerField(default=1)
    concluido_em = models.DateTimeField(null=True, blank=True)
    publico = models.BooleanField(default=False)

    class Meta:
        db_table = 'recruitment_curriculo_tb'
        indexes = [models.Index(fields=['visibilidade', 'status', 'ativo'], name='recruit_curr_vis_status_idx')]
        constraints = [
            models.CheckConstraint(condition=Q(etapa_atual__gte=1, etapa_atual__lte=10), name='recruit_curriculo_etapa_ck'),
            models.CheckConstraint(condition=Q(pretensao_salarial__isnull=True) | Q(pretensao_salarial__gte=0), name='recruit_curriculo_salario_ck'),
        ]

    def __str__(self):
        return self.titulo_profissional or self.usuario.get_username()


class ItemCurriculo(BaseAtiva):
    curriculo = models.ForeignKey(Curriculo, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=180)
    instituicao = models.CharField(max_length=180, blank=True)
    descricao = models.TextField(blank=True)
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        if self.inicio and self.fim and self.fim < self.inicio:
            raise ValidationError({'fim': 'A data final deve ser posterior ou igual à inicial.'})


class Experiencia(ItemCurriculo):
    cargo = models.CharField(max_length=180)
    atual = models.BooleanField(default=False)
    tipo_contratacao = models.CharField(max_length=40, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    resultados_responsabilidades = models.TextField(blank=True)
    tecnologias_habilidades = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.atual and self.fim:
            raise ValidationError({'fim': 'Uma experiência atual não pode ter data final.'})

    class Meta:
        db_table = 'recruitment_experiencia_tb'
        ordering = ['-inicio']
        constraints = [
            models.CheckConstraint(condition=Q(fim__isnull=True) | Q(inicio__isnull=True) | Q(fim__gte=models.F('inicio')), name='recruit_exp_datas_ck'),
            models.CheckConstraint(condition=Q(atual=False) | Q(fim__isnull=True), name='recruit_exp_atual_fim_ck'),
        ]


class Formacao(ItemCurriculo):
    nivel = models.CharField(max_length=80, blank=True)
    concluido = models.BooleanField(default=False)
    area = models.CharField(max_length=120, blank=True)
    situacao = models.CharField(max_length=30, blank=True)
    class Meta:
        db_table = 'recruitment_formacao_tb'
        ordering = ['-inicio']
        constraints = [models.CheckConstraint(condition=Q(fim__isnull=True) | Q(inicio__isnull=True) | Q(fim__gte=models.F('inicio')), name='recruit_form_datas_ck')]


class Curso(ItemCurriculo):
    class Tipo(models.TextChoices):
        CURSO = 'CURSO', 'Curso'
        CERTIFICACAO = 'CERTIFICACAO', 'Certificação'

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CURSO)
    carga_horaria = models.PositiveIntegerField(null=True, blank=True)
    codigo_credencial = models.CharField(max_length=120, blank=True)
    url_credencial = models.URLField(blank=True)
    validade = models.DateField(null=True, blank=True)
    class Meta:
        db_table = 'recruitment_curso_tb'
        ordering = ['-inicio']
        constraints = [models.CheckConstraint(condition=Q(fim__isnull=True) | Q(inicio__isnull=True) | Q(fim__gte=models.F('inicio')), name='recruit_curso_datas_ck')]


class Habilidade(BaseAtiva):
    curriculo = models.ForeignKey(Curriculo, on_delete=models.CASCADE, related_name='habilidades')
    nome = models.CharField(max_length=120)
    nivel = models.CharField(max_length=40, blank=True)
    categoria = models.CharField(max_length=80, blank=True)
    anos_experiencia = models.PositiveSmallIntegerField(null=True, blank=True)
    destaque = models.BooleanField(default=False)
    class Meta:
        db_table = 'recruitment_habilidade_tb'
        constraints = [
            models.UniqueConstraint(fields=['curriculo', 'nome'], condition=Q(ativo=True, excluido_em__isnull=True), name='recruit_habilidade_ativa_uk'),
            models.UniqueConstraint(Lower('nome'), 'curriculo', condition=Q(ativo=True, excluido_em__isnull=True), name='recruit_habilidade_nome_ci_uk'),
        ]


class Idioma(BaseAtiva):
    curriculo = models.ForeignKey(Curriculo, on_delete=models.CASCADE, related_name='idiomas')
    nome = models.CharField(max_length=80)
    nivel = models.CharField(max_length=40)
    leitura = models.CharField(max_length=20, blank=True)
    escrita = models.CharField(max_length=20, blank=True)
    conversacao = models.CharField(max_length=20, blank=True)
    class Meta:
        db_table = 'recruitment_idioma_tb'
        constraints = [
            models.UniqueConstraint(fields=['curriculo', 'nome'], condition=Q(ativo=True, excluido_em__isnull=True), name='recruit_idioma_ativo_uk'),
            models.UniqueConstraint(Lower('nome'), 'curriculo', condition=Q(ativo=True, excluido_em__isnull=True), name='recruit_idioma_nome_ci_uk'),
        ]


class CurriculoPrivacidade(BaseAtiva):
    curriculo = models.OneToOneField(Curriculo, on_delete=models.CASCADE, related_name='privacidade')
    mostrar_telefone = models.BooleanField(default=False)
    mostrar_email = models.BooleanField(default=False)
    mostrar_cidade = models.BooleanField(default=True)
    mostrar_estado = models.BooleanField(default=True)
    mostrar_linkedin = models.BooleanField(default=True)
    mostrar_portfolio = models.BooleanField(default=True)
    mostrar_pretensao_salarial = models.BooleanField(default=False)

    class Meta:
        db_table = 'recruitment_curriculo_privacidade_tb'


class Projeto(BaseAtiva):
    curriculo = models.ForeignKey(Curriculo, on_delete=models.CASCADE, related_name='projetos')
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=40, blank=True)
    url = models.URLField(blank=True)
    imagem = models.ImageField(upload_to='curriculos/projetos/%Y/%m/', blank=True)
    tecnologias = models.TextField(blank=True)
    data = models.DateField(null=True, blank=True)
    destaque = models.BooleanField(default=False)

    class Meta:
        db_table = 'recruitment_projeto_tb'
        ordering = ['-destaque', '-data', '-criado_em']
        indexes = [models.Index(fields=['curriculo', 'ativo'], name='recruit_proj_curr_ativo_idx')]


class CurriculoInformacaoAdicional(BaseAtiva):
    curriculo = models.OneToOneField(Curriculo, on_delete=models.CASCADE, related_name='informacoes_adicionais')
    possui_cnh = models.BooleanField(default=False)
    categorias_cnh = models.CharField(max_length=20, blank=True)
    veiculo_proprio = models.BooleanField(default=False)
    disponibilidade_horario = models.TextField(blank=True)
    trabalho_voluntario = models.TextField(blank=True)
    premiacoes = models.TextField(blank=True)
    interesses_profissionais = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        db_table = 'recruitment_curriculo_info_adicional_tb'

    def clean(self):
        if self.categorias_cnh and not self.possui_cnh:
            raise ValidationError({
                'categorias_cnh': 'Marque que possui CNH para informar as categorias.',
            })


class Candidatura(BaseAtiva):
    class Status(models.TextChoices):
        ENVIADA = 'ENVIADA', 'Enviada'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADA = 'APROVADA', 'Aprovada'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        RETIRADA = 'RETIRADA', 'Retirada'

    vaga = models.ForeignKey(Vaga, on_delete=models.PROTECT, related_name='candidaturas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='candidaturas')
    curriculo = models.ForeignKey(Curriculo, on_delete=models.PROTECT, related_name='candidaturas')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENVIADA)
    mensagem = models.TextField(blank=True)
    curriculo_snapshot = models.JSONField(null=True, blank=True)
    snapshot_versao = models.PositiveSmallIntegerField(default=1)
    consentimento_compartilhamento_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recruitment_candidatura_tb'
        constraints = [models.UniqueConstraint(fields=['vaga', 'usuario'], condition=Q(ativo=True, excluido_em__isnull=True), name='recruit_candidatura_ativa_uk')]
        indexes = [models.Index(fields=['vaga', 'status'], name='recruit_cand_vaga_status_idx')]

    def clean(self):
        errors = {}
        if not self.pk and self.vaga_id and self.vaga.status != Vaga.Status.PUBLICADA:
            errors['vaga'] = 'Somente vagas publicadas aceitam candidatura.'
        if self.curriculo_id and self.usuario_id and self.curriculo.usuario_id != self.usuario_id:
            errors['curriculo'] = 'O currículo deve pertencer ao candidato.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).all_objects.filter(pk=self.pk).values(
                'curriculo_snapshot', 'snapshot_versao',
                'consentimento_compartilhamento_em',
            ).first()
            if original:
                self.curriculo_snapshot = original['curriculo_snapshot']
                self.snapshot_versao = original['snapshot_versao']
                self.consentimento_compartilhamento_em = original['consentimento_compartilhamento_em']
        elif self.curriculo_id and not self.curriculo_snapshot:
            from apps.recruitment.services.dtos import curriculo_para_candidatura
            self.curriculo_snapshot = curriculo_para_candidatura(self.curriculo).serializar()
            self.consentimento_compartilhamento_em = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)


class VagaAuditoria(models.Model):
    vaga = models.ForeignKey(Vaga, on_delete=models.PROTECT, related_name='auditoria')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    acao = models.CharField(max_length=40)
    contexto = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_vaga_auditoria_tb'
        ordering = ['-criado_em']


class CandidaturaHistorico(models.Model):
    candidatura = models.ForeignKey(Candidatura, on_delete=models.CASCADE, related_name='historico')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status_anterior = models.CharField(max_length=20, blank=True)
    status_novo = models.CharField(max_length=20)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_candidatura_historico_tb'
        ordering = ['-criado_em']
