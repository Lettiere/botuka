"""Administração de organizações."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master

from apps.organizations.models import (
    Capacidade,
    CNAE,
    CNPJConsulta,
    Endereco,
    Empresa,
    EmpresaLink,
    EmpresaCapacidade,
    EmpresaCNAE,
    EmpresaEndereco,
    EmpresaFuncao,
    EmpresaPropriedade,
    EmpresaSolicitacao,
    EmpresaUsuario,
    EmpresaUsuarioFuncao,
    EmpresaUsuarioPermissao,
    Organizacao,
    OrganizacaoUsuario,
    Unidade,
    UsuarioCapacidade,
    UsuarioLimitePersonalizado,
)

admin.site.register(EmpresaLink)


class MasterOnlyAdminMixin:
    """Protege cadastros que concedem autoridade global ou institucional."""

    def has_module_permission(self, request):
        return usuario_e_master(request.user)

    def has_view_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_add_permission(self, request):
        return usuario_e_master(request.user)

    def has_change_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_delete_permission(self, request, obj=None):
        return usuario_e_master(request.user)


@admin.register(UsuarioLimitePersonalizado)
class UsuarioLimitePersonalizadoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'usuario', 'ativo', 'limite_empresas', 'empresas_ilimitadas',
        'limite_servicos', 'servicos_ilimitados', 'inicio', 'fim',
        'concedido_por',
    )
    list_filter = ('ativo', 'empresas_ilimitadas', 'servicos_ilimitados', 'inicio', 'fim')
    search_fields = ('usuario__username', 'usuario__email', 'motivo')
    autocomplete_fields = ('usuario',)
    readonly_fields = ('uuid', 'concedido_por', 'criado_em', 'atualizado_em')

    def save_model(self, request, obj, form, change):
        obj.concedido_por = request.user
        super().save_model(request, obj, form, change)


class EmpresaCapacidadeInline(admin.StackedInline):
    """Capacidades comerciais e institucionais vinculadas à empresa."""

    model = EmpresaCapacidade
    extra = 0
    min_num = 0
    show_change_link = False
    autocomplete_fields = ("capacidade",)

    fields = (
        ("capacidade", "status", "ativo"),
        "motivo_rejeicao",
        ("aprovado_por", "aprovado_em"),
        ("criado_em", "atualizado_em"),
    )

    readonly_fields = (
        "aprovado_por",
        "aprovado_em",
        "criado_em",
        "atualizado_em",
    )

    verbose_name = "Capacidade da empresa"
    verbose_name_plural = "Capacidades e autorizações da empresa"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("capacidade", "aprovado_por")
            .order_by("capacidade__nome")
        )

    def get_extra(self, request, obj=None, **kwargs):
        return 0

    def has_view_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_add_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_change_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_delete_permission(self, request, obj=None):
        return usuario_e_master(request.user)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        "nome_fantasia",
        "tipo_cadastro",
        "cpf_cnpj",
        "cidade",
        "estado",
        "status",
        "usuario_proprietario",
        "ativo",
        "perfil_publico",
        "verificada",
        "pode_vender_produtos",
        "status_institucional",
        "oficial",
    )

    list_filter = (
        "status",
        "tipo_cadastro",
        "ativo",
        "verificada",
        "perfil_publico",
        "estado",
        "cidade",
        "tipo_organizacao",
        "status_institucional",
        "oficial",
    )

    search_fields = (
        "nome_fantasia",
        "razao_social",
        "cpf_cnpj",
        "email",
        "telefone",
        "whatsapp",
        "usuario_proprietario__username",
        "usuario_proprietario__email",
    )

    autocomplete_fields = (
        "usuario_proprietario",
        "categoria_empresa",
        "estado",
        "cidade",
        "autorizada_por",
    )

    readonly_fields = (
        "uuid",
        "pode_vender_produtos",
        "pode_publicar_servicos",
        "pode_receber_leads_status",
        "criado_em",
        "atualizado_em",
        "excluido_em",
        "qr_token",
        "qr_atualizado_em",
    )

    list_select_related = (
        "usuario_proprietario",
        "categoria_empresa",
        "cidade",
        "estado",
    )

    ordering = ("nome_fantasia",)
    prepopulated_fields = {"slug": ("nome_fantasia",)}
    save_on_top = True

    fieldsets = (
        (
            "Identificação da empresa",
            {
                "fields": (
                    "usuario_proprietario",
                    "tipo_cadastro",
                    "nome_fantasia",
                    "razao_social",
                    "slug",
                    "categoria_empresa",
                    "status",
                    "ativo",
                ),
            },
        ),
        (
            "Dados fiscais e cadastrais",
            {
                "fields": (
                    "cpf_cnpj",
                    "inscricao_estadual",
                    "inscricao_municipal",
                    "natureza_juridica",
                    "porte",
                    "data_abertura",
                    "situacao_cadastral",
                ),
            },
        ),
        (
            "Contato",
            {
                "fields": (
                    "telefone",
                    "whatsapp",
                    "email",
                    "site",
                ),
            },
        ),
        (
            "Endereço",
            {
                "fields": (
                    "cep",
                    "endereco",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "estado",
                    "latitude",
                    "longitude",
                ),
            },
        ),
        (
            "Apresentação pública",
            {
                "fields": (
                    "descricao_curta",
                    "descricao_completa",
                    "logo",
                    "imagem_capa",
                    "perfil_publico",
                    "verificada",
                ),
            },
        ),
        (
            "Atendimento e operação",
            {
                "fields": (
                    "atende_online",
                    "atende_local",
                    "horario_atendimento",
                    "aceita_leads",
                    "canal_preferencial_lead",
                    "distribuicao_lead",
                ),
            },
        ),
        (
            "Autorizações calculadas",
            {
                "fields": (
                    "pode_vender_produtos",
                    "pode_publicar_servicos",
                    "pode_receber_leads_status",
                ),
                "description": (
                    "Estes indicadores são calculados pelas capacidades "
                    "aprovadas exibidas no final da página."
                ),
            },
        ),
        (
            "Identidade institucional",
            {
                "fields": (
                    "tipo_organizacao",
                    "status_institucional",
                    "institucional",
                    "oficial",
                    "parceira_oficial",
                    "selo_oficial",
                    "verificada_institucionalmente",
                    "autorizada_por",
                    "autorizada_em",
                    "observacao_institucional",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "QR Code",
            {
                "fields": (
                    "qr_ativo",
                    "qr_token",
                    "qr_atualizado_em",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "uuid",
                    "criado_em",
                    "atualizado_em",
                    "excluido_em",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    institutional_fields = (
        "tipo_organizacao",
        "status_institucional",
        "institucional",
        "oficial",
        "parceira_oficial",
        "selo_oficial",
        "verificada_institucionalmente",
        "autorizada_por",
        "autorizada_em",
        "observacao_institucional",
    )

    @admin.display(
        boolean=True,
        description="Pode vender produtos",
    )
    def pode_vender_produtos(self, obj):
        if not obj:
            return False
        return obj.pode_publicar_produto

    @admin.display(
        boolean=True,
        description="Pode publicar serviços",
    )
    def pode_publicar_servicos(self, obj):
        if not obj:
            return False
        return obj.pode_publicar_servico

    @admin.display(
        boolean=True,
        description="Pode receber leads",
    )
    def pode_receber_leads_status(self, obj):
        if not obj:
            return False
        return obj.pode_receber_lead

    def get_inlines(self, request, obj=None):
        if usuario_e_master(request.user):
            return (EmpresaCapacidadeInline,)
        return ()

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))

        if not usuario_e_master(request.user):
            fields.extend(self.institutional_fields)

        return tuple(dict.fromkeys(fields))

    def save_model(self, request, obj, form, change):
        if (
            not usuario_e_master(request.user)
            and set(form.changed_data) & set(self.institutional_fields)
        ):
            raise PermissionDenied(
                "Somente MASTER altera identidade institucional."
            )

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for deleted in formset.deleted_objects:
            deleted.delete()

        for instance in instances:
            if isinstance(instance, EmpresaCapacidade):
                if instance.status == EmpresaCapacidade.Status.APROVADA:
                    if not instance.aprovado_por_id:
                        instance.aprovado_por = request.user

                    if not instance.aprovado_em:
                        instance.aprovado_em = timezone.now()

                    instance.motivo_rejeicao = ""

                elif instance.status == EmpresaCapacidade.Status.REJEITADA:
                    if not instance.aprovado_por_id:
                        instance.aprovado_por = request.user

                    if not instance.aprovado_em:
                        instance.aprovado_em = timezone.now()

                elif instance.status == EmpresaCapacidade.Status.PENDENTE:
                    instance.aprovado_por = None
                    instance.aprovado_em = None

            instance.save()

        formset.save_m2m()


@admin.register(EmpresaUsuario)
class EmpresaUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        'empresa',
        'usuario',
        'funcao',
        'proprietario',
        'administrador',
        'ativo',
    )
    list_filter = (
        'funcao',
        'proprietario',
        'administrador',
        'ativo',
        'pode_editar',
        'pode_publicar_servico',
        'pode_gerenciar_equipe',
    )
    search_fields = (
        'empresa__nome_fantasia',
        'empresa__cpf_cnpj',
        'usuario__username',
        'usuario__email',
    )
    autocomplete_fields = ('empresa', 'usuario')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')
    list_select_related = ('empresa', 'usuario')
    ordering = ('empresa__nome_fantasia', 'usuario__username')

    def save_model(self, request, obj, form, change):
        if (
            obj.funcao == EmpresaUsuario.Funcao.ADMINISTRADOR_INSTITUCIONAL
            or obj.escopo == EmpresaUsuario.Escopo.GLOBAL
        ) and not usuario_e_master(request.user):
            raise PermissionDenied('Somente MASTER atribui papel institucional ou escopo global.')
        super().save_model(request, obj, form, change)


@admin.register(Capacidade)
class CapacidadeAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'exige_aprovacao', 'ativo')
    list_filter = ('exige_aprovacao', 'ativo')
    search_fields = ('codigo', 'nome')


@admin.register(UsuarioCapacidade)
class UsuarioCapacidadeAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('usuario', 'capacidade', 'status', 'ativo')
    list_filter = ('status', 'ativo', 'capacidade')
    search_fields = ('usuario__username', 'usuario__email', 'capacidade__codigo')
    autocomplete_fields = ('usuario', 'capacidade', 'aprovado_por')


@admin.register(EmpresaCapacidade)
class EmpresaCapacidadeAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('empresa', 'capacidade', 'status', 'ativo')
    list_filter = ('status', 'ativo', 'capacidade')
    search_fields = ('empresa__nome_fantasia', 'capacidade__codigo')
    autocomplete_fields = ('empresa', 'capacidade', 'aprovado_por')


@admin.register(EmpresaEndereco)
class EmpresaEnderecoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'endereco', 'principal', 'publico', 'ativo')
    list_filter = ('principal', 'publico', 'ativo')
    search_fields = ('empresa__nome_fantasia', 'endereco__logradouro')
    autocomplete_fields = ('empresa', 'endereco')


@admin.register(EmpresaPropriedade)
class EmpresaPropriedadeAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'usuario', 'atual', 'origem', 'inicio_em', 'fim_em')
    list_filter = ('atual', 'origem')
    search_fields = ('empresa__nome_fantasia', 'usuario__username', 'usuario__email')
    autocomplete_fields = ('empresa', 'usuario', 'aprovado_por')


@admin.register(EmpresaFuncao)
class EmpresaFuncaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')


@admin.register(EmpresaUsuarioFuncao)
class EmpresaUsuarioFuncaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    pass


@admin.register(EmpresaUsuarioPermissao)
class EmpresaUsuarioPermissaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    pass


@admin.register(CNAE)
class CNAEAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao', 'ativo')
    list_filter = ('ativo', 'secao', 'divisao')
    search_fields = ('codigo', 'descricao')


@admin.register(EmpresaCNAE)
class EmpresaCNAEAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'cnae', 'principal', 'origem', 'ativo')
    list_filter = ('principal', 'origem', 'ativo')
    search_fields = ('empresa__nome_fantasia', 'cnae__codigo')
    autocomplete_fields = ('empresa', 'cnae')


@admin.register(CNPJConsulta)
class CNPJConsultaAdmin(admin.ModelAdmin):
    list_display = ('cnpj', 'provider', 'sucesso', 'codigo_resposta', 'consultado_em', 'expira_em')
    list_filter = ('provider', 'sucesso', 'consultado_em')
    search_fields = ('cnpj', 'erro_resumido')
    autocomplete_fields = ('solicitado_por',)
    readonly_fields = ('resposta_json',)


@admin.register(EmpresaSolicitacao)
class EmpresaSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('tipo_solicitacao', 'empresa', 'cnpj', 'usuario_solicitante', 'status', 'criado_em')
    list_filter = ('tipo_solicitacao', 'status', 'criado_em')
    search_fields = ('cnpj', 'empresa__nome_fantasia', 'usuario_solicitante__username')
    autocomplete_fields = ('empresa', 'usuario_solicitante', 'analisado_por')


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = (
        'nome_fantasia',
        'documento',
        'categoria',
        'proprietario',
        'ativo',
    )
    list_filter = ('ativo', 'categoria', 'criado_em', 'atualizado_em')
    search_fields = (
        'nome_fantasia',
        'razao_social',
        'documento',
        'email',
        'proprietario__username',
        'proprietario__email',
    )
    ordering = ('nome_fantasia',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome_fantasia',)}


@admin.register(OrganizacaoUsuario)
class OrganizacaoUsuarioAdmin(admin.ModelAdmin):
    list_display = ('organizacao', 'usuario', 'ativo', 'criado_em')
    list_filter = ('ativo', 'organizacao', 'criado_em')
    search_fields = (
        'organizacao__nome_fantasia',
        'usuario__username',
        'usuario__email',
    )
    ordering = ('organizacao__nome_fantasia', 'usuario__username')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'organizacao',
        'categoria',
        'responsavel',
        'principal',
        'ativo',
    )
    list_filter = ('ativo', 'principal', 'categoria', 'criado_em')
    search_fields = (
        'nome',
        'email',
        'telefone',
        'organizacao__nome_fantasia',
        'responsavel__username',
        'responsavel__email',
    )
    ordering = ('organizacao__nome_fantasia', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('unidade', 'cidade', 'bairro', 'logradouro', 'numero', 'ativo')
    list_filter = ('ativo', 'cidade__estado', 'cidade', 'bairro')
    search_fields = (
        'logradouro',
        'numero',
        'complemento',
        'cep',
        'unidade__nome',
        'unidade__organizacao__nome_fantasia',
        'cidade__nome',
        'bairro__nome',
    )
    ordering = ('cidade__nome', 'logradouro', 'numero')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
