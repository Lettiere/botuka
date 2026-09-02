"""Views da área interna do usuário."""

from __future__ import annotations

from functools import wraps
import re
from datetime import timedelta
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from apps.core.services.images import optimize_uploaded_image

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.core.services.public_sharing import gerar_qrcode_png, obter_url_publica
from apps.painel.forms import (
    ApresentacaoUsuarioForm,
    ContatoUsuarioForm,
    DadosPessoaisForm,
    DocumentoUsuarioForm,
    EmpresaCNPJConsultaForm,
    EmpresaCapacidadeForm,
    EmpresaDocumentoForm,
    EmpresaEnderecoForm,
    EmpresaForm,
    EmpresaEtapaForm,
    EmpresaInstitucionalForm,
    EmpresaLinkForm,
    EmpresaSolicitacaoAnaliseForm,
    EmpresaUsuarioForm,
    FotoPerfilForm,
    UsuarioLimitePersonalizadoForm,
    ServicoAreaForm,
    ServicoCaracteristicaForm,
    ServicoForm,
    ServicoRapidoForm,
    ServicoImagemForm,
    ServicoLinkForm,
)
from apps.core.models import Auditoria
from apps.core.attribute_forms import atributo_formset
from apps.integrations.cnpj.exceptions import CNPJError
from apps.integrations.cnpj.services import consultar_cnpj
from apps.agenda.models import (
    AgendaProfissional,
    AgendaProfissionalServico,
    AgendaDisponibilidade,
    AgendaBloqueio,
    Agendamento,
)
from apps.agenda.public_services import resumo_operacional_empresa
from apps.taxonomy.models import Subcategoria
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade, EmpresaEndereco, EmpresaLink, EmpresaSolicitacao, EmpresaUsuario, UsuarioLimitePersonalizado
from apps.organizations.plans import (
    LimiteUsuarioService, obter_assinatura_vigente,
    total_empresas_ativas, total_servicos_utilizados,
)
from apps.organizations.services.commercial_limits import (
    salvar_limite_personalizado, suspender_limite_personalizado,
)
from apps.organizations.services.institutional import (
    atualizar_identidade_institucional, conceder_capacidade, revogar_capacidade,
)
from apps.organizations.services.company_dashboard import construir_painel_empresa
from apps.organizations.permissions import (
    empresas_disponiveis_para_usuario,
    usuario_pode_editar_empresa,
    usuario_pode_gerenciar_empresa,
    usuario_pode_gerenciar_equipe,
    usuario_pode_visualizar_empresa,
)
from apps.organizations.plans import (
    LimitePlanoExcedido,
    bloquear_e_validar_criacao_empresa,
    bloquear_e_validar_criacao_servico,
    validar_contexto_servico,
)
from apps.services.models import AreaProfissional, Profissao, ProfissaoTipoServico, Servico, ServicoArea, ServicoCaracteristica, ServicoImagem, ServicoLink, Setor, TipoServico
from apps.services.permissions import (
    servicos_disponiveis_para_usuario,
    usuario_pode_editar_servico,
    usuario_pode_publicar_servico,
    usuario_pode_visualizar_servico,
)
from apps.products.models import Conversa, Produto
from apps.products.services import calcular_limite


def painel_permission_required(codigo: str):
    """Decorator para validar permissões de domínio no painel."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            tem_permissao = getattr(request.user, 'tem_permissao', None)
            if callable(tem_permissao) and tem_permissao(codigo):
                return view_func(request, *args, **kwargs)

            raise PermissionDenied

        return wrapper

    return decorator


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    from apps.painel.services import montar_dashboard_conta
    from apps.painel.navigation import painel_navigation

    navigation = painel_navigation(request)
    return render(request, 'painel/dashboard.html', {
        "dashboard": montar_dashboard_conta(
            request.user,
            navigation["painel_module_groups"],
            request._painel_permission_checker,
        ),
        "usuario_master": usuario_e_master(request.user),
    })


@login_required
def perfil(request: HttpRequest) -> HttpResponse:
    forms = {
        'dados': DadosPessoaisForm(instance=request.user),
        'contato': ContatoUsuarioForm(instance=request.user),
        'foto': FotoPerfilForm(instance=request.user),
        'documento': DocumentoUsuarioForm(instance=request.user),
        'apresentacao': ApresentacaoUsuarioForm(instance=request.user),
    }

    if request.method == 'POST':
        secao = request.POST.get('secao', 'dados')
        form_classes = {
            'dados': DadosPessoaisForm,
            'contato': ContatoUsuarioForm,
            'foto': FotoPerfilForm,
            'documento': DocumentoUsuarioForm,
            'apresentacao': ApresentacaoUsuarioForm,
        }
        form_class = form_classes.get(secao, DadosPessoaisForm)
        form = form_class(request.POST, request.FILES, instance=request.user)
        forms[secao] = form

        if form.is_valid():
            form.save()
            if secao in {'dados', 'foto', 'apresentacao'}:
                from apps.social.services import sincronizar_perfil_publico
                sincronizar_perfil_publico(request.user, origem='platform')
            messages.success(request, 'Perfil atualizado com sucesso.')

    empresas = request.user.organizacoes.all()
    empresas_proprietario = request.user.organizacoes_proprietario.all()
    total_empresas = empresas.count() + empresas_proprietario.count()
    return render(
        request,
        'painel/perfil.html',
        {
            'forms': forms,
            'empresas': empresas,
            'empresas_proprietario': empresas_proprietario,
            'total_empresas': total_empresas,
        },
    )


def render_pagina(request: HttpRequest, template_name: str, titulo: str) -> HttpResponse:
    return render(request, template_name, {'titulo': titulo})


def _empresa_autorizada(request: HttpRequest, uuid) -> Empresa:
    return get_object_or_404(empresas_disponiveis_para_usuario(request.user), uuid=uuid)


def _aplicar_filtros_empresas(request: HttpRequest, queryset):
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    cidade = request.GET.get('cidade', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    somente_ativas = request.GET.get('somente_ativas')

    if busca:
        busca_digitos = ''.join(char for char in busca if char.isdigit())
        filtro_busca = (
            Q(nome_fantasia__icontains=busca)
            | Q(razao_social__icontains=busca)
            | Q(cpf_cnpj__icontains=busca_digitos or busca)
        )
        queryset = queryset.filter(filtro_busca)

    if status:
        queryset = queryset.filter(status=status)

    if cidade:
        queryset = queryset.filter(cidade__nome__icontains=cidade)

    if tipo:
        queryset = queryset.filter(tipo_cadastro=tipo)

    if somente_ativas:
        queryset = queryset.filter(ativo=True, status=Empresa.Status.ATIVA)

    return queryset


@login_required
def empresas_lista(request: HttpRequest) -> HttpResponse:
    from apps.organizations.plans import usuario_pode_criar_empresa
    limite_empresas = usuario_pode_criar_empresa(request.user)
    empresas_base = empresas_disponiveis_para_usuario(request.user)
    empresas_filtradas = _aplicar_filtros_empresas(request, empresas_base).annotate(
        total_usuarios=Count(
            'usuarios_vinculados',
            filter=Q(usuarios_vinculados__ativo=True),
            distinct=True,
        )
    )
    paginator = Paginator(empresas_filtradas, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)

    return render(
        request,
        'painel/empresas/lista.html',
        {
            'titulo': 'Minhas empresas',
            'empresas': page_obj.object_list,
            'page_obj': page_obj,
            'querystring': querystring.urlencode(),
            'total_empresas': empresas_base.count(),
            'total_filtrado': paginator.count,
            'total_ativas': empresas_base.filter(status=Empresa.Status.ATIVA).count(),
            'total_pendentes': empresas_base.filter(status=Empresa.Status.PENDENTE).count(),
            'pode_criar_empresa': limite_empresas.permitido,
            'limite_empresas': limite_empresas.limite,
        },
    )


@login_required
def empresa_criar(request: HttpRequest) -> HttpResponse:
    from apps.organizations.plans import usuario_pode_criar_empresa
    limite = usuario_pode_criar_empresa(request.user)
    if not limite.permitido:
        messages.error(request, f'Seu plano permite no máximo {limite.limite} empresa ativa. Faça upgrade para cadastrar outra empresa.')
        return redirect('painel:empresas_lista')
    return _empresa_wizard(request, etapa=1)


@login_required
def empresa_configurar(request: HttpRequest, uuid, etapa: int) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_editar_empresa(request.user, empresa):
        raise PermissionDenied
    if empresa.status != Empresa.Status.RASCUNHO:
        messages.info(request, 'O cadastro já foi concluído; use a edição da empresa para corrigir os dados.')
        return redirect('painel:empresa_editar', uuid=empresa.uuid)
    return _empresa_wizard(request, etapa=etapa, empresa=empresa)


def _empresa_wizard(request, *, etapa, empresa=None):
    etapa = max(1, min(7, int(etapa)))
    nova = empresa is None
    if nova and etapa != 1:
        return redirect('painel:empresa_criar')
    form = EmpresaEtapaForm(
        request.POST or None, request.FILES or None, instance=empresa,
        usuario=request.user, pode_alterar_status=False, etapa=etapa,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                if nova:
                    bloquear_e_validar_criacao_empresa(request.user)
                empresa = form.save(commit=False)
                empresa.usuario_proprietario = request.user
                empresa.status = Empresa.Status.RASCUNHO
                empresa.cadastro_etapa = max(empresa.cadastro_etapa or 1, min(etapa + 1, 7))
                empresa.save()
                if nova:
                    EmpresaUsuario.objects.create(
                        empresa=empresa, usuario=request.user,
                        funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
                        proprietario=True, administrador=True, pode_editar=True,
                        pode_publicar_servico=True, pode_gerenciar_equipe=True,
                    )
                acao = request.POST.get('acao', 'continuar')
                if etapa == 7 and acao == 'continuar':
                    empresa.status = Empresa.Status.PENDENTE
                    empresa.cadastro_etapa = 7
                    empresa.save(update_fields=['status', 'cadastro_etapa', 'atualizado_em'])
        except LimitePlanoExcedido as exc:
            form.add_error(None, str(exc))
        except ValidationError as exc:
            _adicionar_erros_da_etapa(form, exc)
        else:
            if acao == 'sair' or etapa == 7:
                messages.success(request, 'Progresso da empresa salvo.')
                return redirect('painel:empresa_detalhe', uuid=empresa.uuid)
            return redirect(
                'painel:empresa_configurar', uuid=empresa.uuid, etapa=etapa + 1
            )

    etapas = ('Identificação', 'Atuação', 'Apresentação', 'Contatos',
              'Localização', 'Operação', 'Revisão')
    return render(request, 'painel/empresas/wizard.html', {
        'titulo': 'Configurar empresa', 'form': form, 'empresa': empresa,
        'etapa': etapa, 'etapas': tuple(enumerate(etapas, 1)),
        'progresso': round(etapa / 7 * 100),
    })


def _adicionar_erros_da_etapa(form, exc: ValidationError) -> None:
    """Anexa erros somente a campos presentes; os demais viram erro da etapa."""
    if hasattr(exc, 'error_dict'):
        for campo, erros in exc.error_dict.items():
            destino = campo if campo in form.fields else None
            for erro in erros:
                form.add_error(destino, erro.message)
        return
    for erro in exc.error_list:
        form.add_error(None, erro.message)


@login_required
def empresa_detalhe(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_visualizar_empresa(request.user, empresa):
        raise PermissionDenied

    permissoes = {
        'pode_editar': usuario_pode_editar_empresa(request.user, empresa),
        'pode_gerenciar': usuario_pode_gerenciar_empresa(request.user, empresa),
        'pode_gerenciar_equipe': usuario_pode_gerenciar_equipe(request.user, empresa),
        'pode_criar_produto': usuario_tem_permissao(request.user, 'products.criar_empresa'),
    }
    painel_empresa = construir_painel_empresa(
        empresa=empresa, usuario=request.user, permissoes=permissoes,
    )

    return render(
        request,
        'painel/empresas/detalhe.html',
        {
            'empresa': empresa,
            **permissoes,
            'pode_institucional': (
                usuario_e_master(request.user)
                or usuario_tem_permissao(request.user, 'institucional.gerenciar')
            ),
            'painel_empresa': painel_empresa,
        },
    )


@login_required
def administracao_plataforma(request: HttpRequest) -> HttpResponse:
    if not usuario_e_master(request.user):
        raise PermissionDenied
    Usuario = get_user_model()
    agora = timezone.now()
    beneficios_vigentes = UsuarioLimitePersonalizado.objects.filter(
        ativo=True, inicio__lte=agora,
    ).filter(Q(fim__isnull=True) | Q(fim__gt=agora))
    beneficios = list(beneficios_vigentes.select_related('usuario'))
    empresas_extras = 0
    servicos_extras = 0
    for beneficio in beneficios:
        base = LimiteUsuarioService.obter_limites_do_plano(beneficio.usuario)
        if not beneficio.empresas_ilimitadas and beneficio.limite_empresas is not None:
            empresas_extras += max(beneficio.limite_empresas - (base.limite_empresas or 0), 0)
        if not beneficio.servicos_ilimitados and beneficio.limite_servicos is not None:
            servicos_extras += max(beneficio.limite_servicos - (base.limite_servicos or 0), 0)
    return render(request, 'painel/administracao/index.html', {
        'total_usuarios': Usuario.objects.count(),
        'total_organizacoes': Empresa.objects.count(),
        'total_capacidades': Capacidade.objects.filter(ativo=True).count(),
        'auditorias': Auditoria.objects.select_related('usuario')[:20],
        'organizacoes': Empresa.objects.order_by('-atualizado_em')[:12],
        'limites_personalizados': beneficios_vigentes.count(),
        'empresas_extras': empresas_extras,
        'servicos_extras': servicos_extras,
        'limites_expirando': UsuarioLimitePersonalizado.objects.filter(
            ativo=True, fim__gt=agora,
            fim__lte=agora + timedelta(days=30),
        ).count(),
        'limites_vencidos': UsuarioLimitePersonalizado.objects.filter(
            fim__lte=agora,
        ).count(),
    })


@login_required
def limites_comerciais_lista(request: HttpRequest) -> HttpResponse:
    if not usuario_e_master(request.user):
        raise PermissionDenied
    Usuario = get_user_model()
    usuarios = Usuario.objects.select_related(
        'perfil', 'limite_comercial_personalizado',
    ).order_by('first_name', 'username')
    termo = request.GET.get('q', '').strip()
    if termo:
        usuarios = usuarios.filter(
            Q(first_name__icontains=termo) | Q(last_name__icontains=termo)
            | Q(username__icontains=termo) | Q(email__icontains=termo)
        )
    pagina = Paginator(usuarios, 30).get_page(request.GET.get('page'))
    linhas = []
    for usuario in pagina.object_list:
        assinatura = obter_assinatura_vigente(usuario)
        limites = LimiteUsuarioService.obter_limites(usuario)
        linhas.append({
            'usuario': usuario,
            'plano': assinatura.plano.nome if assinatura else 'Gratuito',
            'empresas': total_empresas_ativas(usuario),
            'servicos': total_servicos_utilizados(usuario),
            'limites': limites,
        })
    return render(request, 'painel/administracao/limites/lista.html', {
        'pagina': pagina, 'linhas': linhas, 'termo': termo,
    })


@login_required
def limite_comercial_editar(request: HttpRequest, uuid) -> HttpResponse:
    if not usuario_e_master(request.user):
        raise PermissionDenied
    Usuario = get_user_model()
    usuario = get_object_or_404(Usuario, uuid=uuid)
    limite = UsuarioLimitePersonalizado.objects.filter(usuario=usuario).first()
    instancia = limite or UsuarioLimitePersonalizado(
        usuario=usuario, concedido_por=request.user,
    )
    form = UsuarioLimitePersonalizadoForm(request.POST or None, instance=instancia)
    if request.method == 'POST':
        if request.POST.get('operacao') == 'suspender' and limite:
            suspender_limite_personalizado(
                executor=request.user, usuario=usuario,
                motivo=request.POST.get('motivo_suspensao', ''),
                request=request,
            )
            messages.success(request, 'Limite personalizado suspenso.')
            return redirect('painel:limites_comerciais_lista')
        if form.is_valid():
            salvar_limite_personalizado(
                executor=request.user, usuario=usuario,
                dados=form.cleaned_data, request=request,
            )
            messages.success(request, 'Limites comerciais atualizados.')
            return redirect('painel:limites_comerciais_lista')
    assinatura = obter_assinatura_vigente(usuario)
    efetivos = LimiteUsuarioService.obter_limites(usuario)
    return render(request, 'painel/administracao/limites/editar.html', {
        'usuario_limite': usuario, 'limite': limite, 'form': form,
        'plano': assinatura.plano if assinatura else None,
        'efetivos': efetivos,
        'empresas_utilizadas': total_empresas_ativas(usuario),
        'servicos_utilizados': total_servicos_utilizados(usuario),
    })


@login_required
def empresa_institucional(request: HttpRequest, uuid) -> HttpResponse:
    empresa = get_object_or_404(Empresa, uuid=uuid)
    autorizado = (
        usuario_e_master(request.user)
        or usuario_tem_permissao(request.user, 'institucional.gerenciar')
        or usuario_tem_permissao(request.user, 'capacidades.gerenciar')
    )
    if not autorizado:
        raise PermissionDenied

    form = EmpresaInstitucionalForm(request.POST or None, instance=empresa)
    if request.method == 'POST':
        operacao = request.POST.get('operacao', 'identidade')
        if operacao == 'identidade' and form.is_valid():
            atualizar_identidade_institucional(
                executor=request.user, empresa=empresa,
                dados=form.cleaned_data, request=request,
            )
            messages.success(request, 'Identidade institucional atualizada.')
            return redirect('painel:empresa_institucional', uuid=empresa.uuid)
        codigo = request.POST.get('capacidade', '').strip().upper()
        if operacao == 'conceder' and codigo:
            conceder_capacidade(
                executor=request.user, empresa=empresa, codigo=codigo, request=request,
            )
            messages.success(request, 'Capacidade concedida.')
            return redirect('painel:empresa_institucional', uuid=empresa.uuid)
        if operacao == 'revogar' and codigo:
            revogar_capacidade(
                executor=request.user, empresa=empresa, codigo=codigo,
                motivo=request.POST.get('motivo', ''), request=request,
            )
            messages.success(request, 'Capacidade revogada.')
            return redirect('painel:empresa_institucional', uuid=empresa.uuid)

    return render(request, 'painel/empresas/institucional.html', {
        'empresa': empresa,
        'form': form,
        'capacidades': Capacidade.objects.filter(ativo=True).order_by('nome'),
        'capacidades_concedidas': EmpresaCapacidade.objects.filter(
            empresa=empresa, ativo=True,
        ).select_related('capacidade'),
        'historico': Auditoria.objects.filter(
            organizacao_uuid=empresa.uuid,
        ).select_related('usuario')[:30],
    })


@login_required
def empresa_editar(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_editar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        form = EmpresaForm(
            request.POST,
            request.FILES,
            instance=empresa,
            usuario=request.user,
            pode_alterar_status=usuario_pode_gerenciar_empresa(request.user, empresa),
        )

        if form.is_valid():
            form.save()
            messages.success(request, 'Empresa atualizada com sucesso.')
            return redirect('painel:empresa_detalhe', uuid=empresa.uuid)
    else:
        form = EmpresaForm(
            instance=empresa,
            usuario=request.user,
            pode_alterar_status=usuario_pode_gerenciar_empresa(request.user, empresa),
        )

    return render(
        request,
        'painel/empresas/form.html',
        {
            'titulo': 'Editar empresa',
            'form': form,
            'empresa': empresa,
        },
    )


@login_required
def empresa_equipe(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_gerenciar_equipe(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        acao = request.POST.get('acao', 'adicionar')

        if acao in {'ativar', 'desativar'}:
            vinculo = get_object_or_404(
                EmpresaUsuario,
                empresa=empresa,
                pk=request.POST.get('vinculo_id'),
            )

            if vinculo.proprietario:
                messages.error(
                    request,
                    'O proprietário não pode ser desativado por este fluxo.',
                )
            else:
                vinculo.ativo = acao == 'ativar'
                vinculo.save(
                    update_fields=[
                        'ativo',
                        'atualizado_em',
                    ]
                )

                if not vinculo.ativo:
                    AgendaProfissional.objects.filter(
                        empresa_usuario=vinculo,
                        ativo=True,
                    ).update(
                        ativo=False,
                        atualizado_em=timezone.now(),
                    )

                messages.success(
                    request,
                    'Vínculo atualizado com sucesso.',
                )

            return redirect(
                'painel:empresa_equipe',
                uuid=empresa.uuid,
            )

        if acao in {
            'agenda_profissional_ativar',
            'agenda_profissional_desativar',
        }:
            vinculo = get_object_or_404(
                EmpresaUsuario.objects.select_related(
                    'empresa',
                    'usuario',
                ),
                empresa=empresa,
                pk=request.POST.get('vinculo_id'),
            )

            if not vinculo.ativo:
                messages.error(
                    request,
                    'Ative o membro da equipe antes de habilitá-lo na Agenda.',
                )
                return redirect(
                    'painel:empresa_equipe',
                    uuid=empresa.uuid,
                )

            if not empresa.pode_publicar_servico:
                messages.error(
                    request,
                    'A empresa precisa estar autorizada a prestar serviços antes de configurar profissionais da Agenda.',
                )
                return redirect(
                    'painel:empresa_equipe',
                    uuid=empresa.uuid,
                )

            if acao == 'agenda_profissional_ativar':
                profissional, criado = (
                    AgendaProfissional.objects.get_or_create(
                        empresa_usuario=vinculo,
                        defaults={
                            'ativo': True,
                        },
                    )
                )

                if not criado and not profissional.ativo:
                    profissional.ativo = True
                    profissional.save(
                        update_fields=[
                            'ativo',
                            'atualizado_em',
                        ]
                    )

                messages.success(
                    request,
                    'Profissional habilitado na Agenda.',
                )

            else:
                profissional = (
                    AgendaProfissional.objects
                    .filter(
                        empresa_usuario=vinculo,
                    )
                    .first()
                )

                if profissional is None:
                    messages.info(
                        request,
                        'Este membro ainda não é profissional da Agenda.',
                    )
                elif profissional.ativo:
                    profissional.ativo = False
                    profissional.save(
                        update_fields=[
                            'ativo',
                            'atualizado_em',
                        ]
                    )

                    messages.success(
                        request,
                        'Profissional desabilitado da Agenda sem apagar o histórico.',
                    )
                else:
                    messages.info(
                        request,
                        'O profissional já está desabilitado na Agenda.',
                    )

            return redirect(
                'painel:empresa_equipe',
                uuid=empresa.uuid,
            )

        form = EmpresaUsuarioForm(request.POST, empresa=empresa, ator=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuário vinculado à empresa com sucesso.')
            return redirect('painel:empresa_equipe', uuid=empresa.uuid)
    else:
        form = EmpresaUsuarioForm(empresa=empresa, ator=request.user)

    vinculos = empresa.usuarios_vinculados.select_related(
        'usuario',
        'agenda_profissional',
    ).order_by(
        '-proprietario',
        '-administrador',
        'usuario__first_name',
        'usuario__username',
    )

    return render(
        request,
        'painel/empresas/equipe.html',
        {
            'empresa': empresa,
            'form': form,
            'vinculos': vinculos,
        },
    )


@login_required
def empresa_alterar_status(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_gerenciar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method != 'POST':
        return redirect('painel:empresa_detalhe', uuid=empresa.uuid)

    novo_status = request.POST.get('status')
    if novo_status not in Empresa.Status.values:
        messages.error(request, 'Status inválido.')
        return redirect('painel:empresa_detalhe', uuid=empresa.uuid)

    empresa.status = novo_status
    empresa.ativo = novo_status not in {Empresa.Status.SUSPENSA, Empresa.Status.BLOQUEADA}
    empresa.save(update_fields=['status', 'ativo', 'atualizado_em'])
    messages.success(request, 'Status da empresa atualizado.')
    return redirect('painel:empresa_detalhe', uuid=empresa.uuid)


@login_required
def empresa_excluir(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_gerenciar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        empresa.delete()
        messages.success(request, 'Empresa removida com sucesso.')
        return redirect('painel:empresas_lista')

    return render(
        request,
        'painel/empresas/confirmar_exclusao.html',
        {'empresa': empresa},
    )


@login_required
def empresa_adicionar(request: HttpRequest) -> HttpResponse:
    return empresa_criar(request)


@login_required
def empresa_ajax_consultar_cnpj(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido.'}, status=405)

    form = EmpresaCNPJConsultaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'erros': form.errors}, status=400)

    try:
        dados = consultar_cnpj(form.cleaned_data['cnpj'], usuario=request.user)
    except CNPJError as exc:
        return JsonResponse({'ok': False, 'erro': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'ok': False, 'erro': 'Não foi possível consultar o CNPJ agora.'}, status=502)

    return JsonResponse({'ok': True, 'dados': dados})


@login_required
def empresa_capacidades(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_gerenciar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        form = EmpresaCapacidadeForm(request.POST, empresa=empresa)
        if form.is_valid():
            capacidade = form.save(commit=False)
            capacidade.empresa = empresa
            capacidade.solicitado_por = request.user
            capacidade.save()
            messages.success(request, 'Capacidade solicitada com sucesso.')
            return redirect('painel:empresa_capacidades', uuid=empresa.uuid)
    else:
        form = EmpresaCapacidadeForm(empresa=empresa)

    capacidades = empresa.capacidades_empresa.select_related('capacidade').order_by('-criado_em')
    return render(request, 'painel/empresas/capacidades.html', {'empresa': empresa, 'form': form, 'capacidades': capacidades})


@login_required
def empresa_enderecos(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_editar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        form = EmpresaEnderecoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                endereco = form.save()
                if endereco.principal:
                    EmpresaEndereco.objects.filter(empresa=empresa, principal=True).update(principal=False)
                EmpresaEndereco.objects.create(
                    empresa=empresa,
                    endereco=endereco,
                    principal=endereco.principal,
                    publico=True,
                )
            messages.success(request, 'Endereço vinculado com sucesso.')
            return redirect('painel:empresa_enderecos', uuid=empresa.uuid)
    else:
        form = EmpresaEnderecoForm()

    enderecos = empresa.enderecos_empresa.select_related('endereco').order_by('-principal', '-criado_em')
    return render(request, 'painel/empresas/enderecos.html', {'empresa': empresa, 'form': form, 'enderecos': enderecos})


@login_required
def empresa_documentos(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_gerenciar_empresa(request.user, empresa):
        raise PermissionDenied

    if request.method == 'POST':
        form = EmpresaDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.usuario = request.user
            documento.status_validacao = documento.StatusValidacao.PENDENTE
            documento.save()
            messages.success(request, 'Documento enviado para análise.')
            return redirect('painel:empresa_documentos', uuid=empresa.uuid)
    else:
        form = EmpresaDocumentoForm()

    documentos = request.user.documentos_pessoais.select_related('tipo_documento').order_by('-criado_em')
    return render(request, 'painel/empresas/documentos.html', {'empresa': empresa, 'form': form, 'documentos': documentos})


@login_required
def empresa_solicitacoes(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    solicitacoes = empresa.solicitacoes.select_related('usuario_solicitante', 'analisado_por').order_by('-criado_em')
    return render(request, 'painel/empresas/solicitacoes.html', {'empresa': empresa, 'solicitacoes': solicitacoes})


@login_required
def empresa_solicitacoes_lista(request: HttpRequest) -> HttpResponse:
    if not usuario_tem_permissao(request.user, 'empresas.gerenciar'):
        raise PermissionDenied

    solicitacoes = EmpresaSolicitacao.objects.select_related('empresa', 'usuario_solicitante').order_by('-criado_em')
    return render(request, 'painel/empresas/solicitacoes_lista.html', {'solicitacoes': solicitacoes})


@login_required
def empresa_solicitacao_analisar(request: HttpRequest, pk: int) -> HttpResponse:
    if not usuario_tem_permissao(request.user, 'empresas.gerenciar'):
        raise PermissionDenied

    solicitacao = get_object_or_404(EmpresaSolicitacao, pk=pk)
    if request.method == 'POST':
        form = EmpresaSolicitacaoAnaliseForm(request.POST, instance=solicitacao)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.analisado_por = request.user
            solicitacao.analisado_em = timezone.now()
            solicitacao.save()
            messages.success(request, 'Solicitação analisada com sucesso.')
            return redirect('painel:empresa_solicitacoes_lista')
    else:
        form = EmpresaSolicitacaoAnaliseForm(instance=solicitacao)

    return render(request, 'painel/empresas/solicitacao_analisar.html', {'solicitacao': solicitacao, 'form': form})


@painel_permission_required('publicacoes.visualizar')
def publicacoes_lista(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/publicacoes/lista.html', 'Publicações')


def _servico_autorizado(request: HttpRequest, uuid) -> Servico:
    servico = get_object_or_404(servicos_disponiveis_para_usuario(request.user), uuid=uuid)
    if not usuario_pode_visualizar_servico(request.user, servico):
        raise PermissionDenied
    return servico


def _aplicar_filtros_servicos(request: HttpRequest, queryset):
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    empresa = request.GET.get('empresa', '').strip()
    setor = request.GET.get('setor', '').strip()

    if busca:
        queryset = queryset.filter(
            Q(titulo__icontains=busca)
            | Q(descricao_curta__icontains=busca)
            | Q(empresa__nome_fantasia__icontains=busca)
        )
    if status:
        queryset = queryset.filter(status=status)
    if empresa.isdigit():
        queryset = queryset.filter(empresa_id=empresa)
    if setor.isdigit():
        queryset = queryset.filter(setor_id=setor)
    return queryset


@login_required
def servicos_lista(request: HttpRequest) -> HttpResponse:
    servicos_base = servicos_disponiveis_para_usuario(request.user)
    servicos_filtrados = _aplicar_filtros_servicos(request, servicos_base)
    paginator = Paginator(servicos_filtrados, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)

    return render(
        request,
        'painel/servicos/lista.html',
        {
            'titulo': 'Serviços',
            'servicos': page_obj.object_list,
            'page_obj': page_obj,
            'querystring': querystring.urlencode(),
            'status_choices': Servico.Status.choices,
            'empresas_filtro': Empresa.objects.filter(servicos__in=servicos_base).distinct().order_by('nome_fantasia'),
            'setores_filtro': Setor.objects.filter(servicos__in=servicos_base).distinct().order_by('nome'),
            'total_servicos': servicos_base.count(),
            'total_publicados': servicos_base.filter(status=Servico.Status.PUBLICADO).count(),
            'total_pendentes': servicos_base.filter(status__in=[Servico.Status.PENDENTE, Servico.Status.EM_ANALISE]).count(),
            'total_rascunhos': servicos_base.filter(status=Servico.Status.RASCUNHO).count(),
        },
    )


@login_required
def servico_criar(request: HttpRequest) -> HttpResponse:
    empresa_contexto = None
    empresa_id = request.GET.get('empresa', '').strip()

    if empresa_id:
        if not empresa_id.isdigit():
            raise PermissionDenied
        empresa_contexto = get_object_or_404(
            empresas_disponiveis_para_usuario(request.user), pk=empresa_id,
        )
        if not usuario_pode_gerenciar_empresa(request.user, empresa_contexto):
            raise PermissionDenied
        if not empresa_contexto.pode_criar_rascunho_servico:
            messages.warning(
                request,
                'A atuação desta empresa não permite cadastrar serviços.',
            )
            return redirect('painel:empresa_detalhe', uuid=empresa_contexto.uuid)
        empresa_post = request.POST.get('empresa', '').strip()
        if (
            request.method == 'POST'
            and empresa_post
            and empresa_post != str(empresa_contexto.pk)
        ):
            raise PermissionDenied

    form = ServicoRapidoForm(
        request.POST or None,
        usuario=request.user,
        empresa_contexto=empresa_contexto,
    )
    if request.method == 'POST':
        acao = request.POST.get('acao', 'rascunho')
        if acao not in {'rascunho', 'continuar'}:
            form.add_error(None, 'Ação inválida para o cadastro inicial.')
        arquivos, erros_upload = _validar_uploads_servico(request)
        for erro in erros_upload:
            form.add_error(None, erro)
        if form.is_valid() and acao in {'rascunho', 'continuar'} and not erros_upload:
            servico = form.save(commit=False)
            servico.status = Servico.Status.RASCUNHO
            try:
                with transaction.atomic():
                    bloquear_e_validar_criacao_servico(
                        request.user, servico.prestador_tipo, servico.empresa,
                    )
                    servico.save()
                    _salvar_imagens_servico(request, servico)
                if acao == 'continuar':
                    messages.success(
                        request,
                        'Rascunho criado. Continue a configuração completa do serviço.',
                    )
                    return redirect('painel:servico_editar', uuid=servico.uuid)
                messages.success(request, 'Serviço salvo como rascunho.')
                return redirect('painel:servico_detalhe', uuid=servico.uuid)
            except (ValidationError, LimitePlanoExcedido) as exc:
                form.add_error(None, exc)
        messages.error(request, 'Revise os campos destacados.')

    return render(request, 'painel/servicos/novo.html', {
        'titulo': 'Cadastrar serviço',
        'form': form,
        'profissional_responsavel': request.user,
        'empresa_contexto': empresa_contexto,
    })
def _formularios_links_post(request):
    indices = sorted({int(match.group(1)) for chave in request.POST for match in [re.match(r'links-(\d+)-url$', chave)] if match})
    return [ServicoLinkForm(request.POST, prefix=f'links-{indice}') for indice in indices if request.POST.get(f'links-{indice}-url', '').strip()]


def _validar_uploads_servico(request):
    arquivos = ([request.FILES['imagem_capa']] if request.FILES.get('imagem_capa') else []) + request.FILES.getlist('galeria')
    erros = []
    if len(arquivos) > 8:
        erros.append('Envie no máximo 8 imagens, incluindo a capa.')
    permitidos = {'image/jpeg': {'.jpg', '.jpeg'}, 'image/png': {'.png'}, 'image/webp': {'.webp'}}
    for arquivo in arquivos:
        extensao = '.' + arquivo.name.rsplit('.', 1)[-1].lower() if '.' in arquivo.name else ''
        if arquivo.size > 5 * 1024 * 1024 or arquivo.content_type not in permitidos or extensao not in permitidos.get(arquivo.content_type, set()):
            erros.append(f'Imagem inválida: {arquivo.name}. Use JPG, PNG ou WebP de até 5 MB.')
            continue
        try:
            imagem = Image.open(arquivo)
            imagem.verify()
            arquivo.seek(0)
        except (UnidentifiedImageError, OSError):
            erros.append(f'O arquivo {arquivo.name} não é uma imagem válida.')
    return arquivos, erros


def _salvar_imagens_servico(request, servico):
    """Atualiza metadados, exclusões lógicas e novos uploads do serviço."""
    imagens = list(ServicoImagem.objects.filter(servico=servico, ativo=True))
    remover = set(request.POST.getlist('remover_imagem'))
    principal_uuid = request.POST.get('imagem_principal', '').strip()
    for imagem in imagens:
        chave = str(imagem.uuid)
        if chave in remover:
            imagem.delete()
            continue
        imagem.legenda = request.POST.get(f'imagem-{chave}-legenda', imagem.legenda).strip()[:160]
        imagem.credito = request.POST.get(f'imagem-{chave}-credito', imagem.credito).strip()[:160]
        imagem.texto_alternativo = request.POST.get(
            f'imagem-{chave}-texto_alternativo', imagem.texto_alternativo,
        ).strip()[:220]
        ordem = str(request.POST.get(f'imagem-{chave}-ordem', imagem.ordem))
        imagem.ordem = int(ordem) if ordem.isdigit() else imagem.ordem
        imagem.save(update_fields=['legenda', 'credito', 'texto_alternativo', 'ordem', 'atualizado_em'])

    capa = request.FILES.get('imagem_capa')
    galeria = request.FILES.getlist('galeria')
    capa = optimize_uploaded_image(capa, policy='content') if capa else None
    galeria = [optimize_uploaded_image(arquivo, policy='content') for arquivo in galeria]
    if capa:
        ServicoImagem.objects.filter(servico=servico, ativo=True, principal=True).update(principal=False)
        ServicoImagem.objects.create(
            servico=servico, imagem=capa, principal=True, ordem=0,
            legenda=request.POST.get('imagem_capa_legenda', '').strip()[:160],
            credito=request.POST.get('imagem_capa_credito', '').strip()[:160],
            texto_alternativo=request.POST.get('imagem_capa_alt', '').strip()[:220],
        )
    for ordem, arquivo in enumerate(galeria, start=1):
        ServicoImagem.objects.create(servico=servico, imagem=arquivo, principal=False, ordem=ordem)

    try:
        principal_valido = str(UUID(principal_uuid)) if principal_uuid else ''
    except (ValueError, AttributeError):
        principal_valido = ''
    if principal_valido and not capa:
        ServicoImagem.objects.filter(servico=servico, ativo=True, principal=True).update(principal=False)
        ServicoImagem.objects.filter(servico=servico, ativo=True, uuid=principal_valido).update(principal=True)
    if not ServicoImagem.objects.filter(servico=servico, ativo=True, principal=True).exists():
        primeira = ServicoImagem.objects.filter(servico=servico, ativo=True).order_by('ordem', 'id').first()
        if primeira:
            primeira.principal = True
            primeira.save(update_fields=['principal', 'atualizado_em'])


@login_required
def servico_detalhe(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    return render(
        request,
        'painel/servicos/detalhe.html',
        {
            'servico': servico,
            'pode_editar': usuario_pode_editar_servico(request.user, servico),
            'imagens': servico.imagens.filter(ativo=True).order_by('-principal', 'ordem'),
            'areas': servico.areas.filter(ativo=True),
            'caracteristicas': servico.caracteristicas.filter(ativo=True).order_by('ordem'),
        },
    )


@login_required
def servico_editar(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied

    if request.method == 'POST':
        form = ServicoForm(request.POST, request.FILES, instance=servico, usuario=request.user)
        atributos = atributo_formset('servico', instance=servico, data=request.POST)
        arquivos, erros_upload = _validar_uploads_servico(request)
        valido = form.is_valid() and atributos.is_valid() and not erros_upload
        acao = request.POST.get('acao', 'salvar')
        # Validar vínculo de empresa
        if valido:
            servico_obj = form.save(commit=False)
            # PF não pode ter empresa
            try:
                validar_contexto_servico(
                    request.user, servico_obj.prestador_tipo, servico_obj.empresa,
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error('empresa', str(exc))
                valido = False
        # Só exige permissão de publicar caso seja publicação
        if acao == 'publicar':
            if not usuario_pode_publicar_servico(request.user, servico):
                raise PermissionDenied
        if valido:
            with transaction.atomic():
                servico_obj.save()
                atributos.save()
                _salvar_imagens_servico(request, servico_obj)
            messages.success(request, 'Serviço atualizado com sucesso.')
            return redirect('painel:servico_detalhe', uuid=servico_obj.uuid)
        for erro in erros_upload:
            form.add_error(None, erro)
    else:
        form = ServicoForm(instance=servico, usuario=request.user)
        atributos = atributo_formset('servico', instance=servico)

    return render(request, 'painel/servicos/form.html', {
        'titulo': 'Editar serviço',
        'form': form,
        'servico': servico,
        'imagens': servico.imagens.filter(ativo=True).order_by('-principal', 'ordem'),
        'profissional_responsavel': request.user,
        'atributos': atributos,
        'atributo_contexto': 'servico',
    })


@login_required
def servico_excluir(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        servico.delete()
        messages.success(request, 'Serviço removido com sucesso.')
        return redirect('painel:servicos_lista')
    return render(request, 'painel/servicos/confirmar_exclusao.html', {'servico': servico})


@login_required
def servico_alterar_status(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if request.method != 'POST':
        return redirect('painel:servico_detalhe', uuid=servico.uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied

    novo_status = request.POST.get('status')
    if novo_status not in Servico.Status.values:
        messages.error(request, 'Status inválido.')
    elif (
        novo_status == Servico.Status.PUBLICADO
        and (
            not usuario_pode_publicar_servico(request.user, servico)
            or (
                servico.empresa_id
                and not servico.empresa.pode_publicar_servico
            )
        )
    ):
        raise PermissionDenied
    else:
        status_anterior = servico.status
        publicado_em_anterior = servico.publicado_em
        servico.status = novo_status
        try:
            servico.save(update_fields=['status', 'publicado_em', 'atualizado_em'])
        except ValidationError as exc:
            # Erros de validação pertencem ao fluxo esperado da interface; erros
            # inesperados de banco ou programação continuam propagando.
            servico.status = status_anterior
            servico.publicado_em = publicado_em_anterior
            detalhes = ' '.join(exc.messages)
            if novo_status == Servico.Status.PUBLICADO:
                mensagem = 'Não foi possível publicar o serviço.'
            else:
                mensagem = 'Não foi possível atualizar o status do serviço.'
            messages.error(request, f'{mensagem} {detalhes}'.strip())
        else:
            messages.success(request, 'Status do serviço atualizado.')
    return redirect('painel:servico_detalhe', uuid=servico.uuid)


@login_required
def servico_imagens(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        remover = request.POST.get('remover')
        if remover:
            imagem = get_object_or_404(ServicoImagem, servico=servico, uuid=remover, ativo=True)
            imagem.delete()
            messages.success(request, 'Imagem removida do serviço.')
            return redirect('painel:servico_imagens', uuid=servico.uuid)
        form = ServicoImagemForm(request.POST, request.FILES)
        if form.is_valid():
            imagem = form.save(commit=False)
            imagem.servico = servico
            if imagem.principal:
                ServicoImagem.objects.filter(servico=servico, ativo=True, principal=True).update(principal=False)
            imagem.save()
            messages.success(request, 'Imagem adicionada com sucesso.')
            return redirect('painel:servico_imagens', uuid=servico.uuid)
    else:
        form = ServicoImagemForm()
    imagens = ServicoImagem.objects.filter(servico=servico, ativo=True).order_by('-principal', 'ordem')
    return render(request, 'painel/servicos/imagens.html', {'servico': servico, 'form': form, 'imagens': imagens})


@login_required
def servico_areas(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        form = ServicoAreaForm(request.POST)
        if form.is_valid():
            area = form.save(commit=False)
            area.servico = servico
            area.save()
            messages.success(request, 'Área de atendimento adicionada com sucesso.')
            return redirect('painel:servico_areas', uuid=servico.uuid)
    else:
        form = ServicoAreaForm()
    areas = ServicoArea.objects.filter(servico=servico, ativo=True)
    return render(request, 'painel/servicos/areas.html', {'servico': servico, 'form': form, 'areas': areas})


@login_required
def servico_caracteristicas(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        form = ServicoCaracteristicaForm(request.POST)
        if form.is_valid():
            caracteristica = form.save(commit=False)
            caracteristica.servico = servico
            caracteristica.save()
            messages.success(request, 'Característica adicionada com sucesso.')
            return redirect('painel:servico_caracteristicas', uuid=servico.uuid)
    else:
        form = ServicoCaracteristicaForm()
    caracteristicas = ServicoCaracteristica.objects.filter(servico=servico, ativo=True).order_by('ordem')
    return render(request, 'painel/servicos/caracteristicas.html', {'servico': servico, 'form': form, 'caracteristicas': caracteristicas})


def _resposta_qrcode(objeto, request, nome: str) -> HttpResponse:
    resposta = HttpResponse(gerar_qrcode_png(objeto, request), content_type='image/png')
    resposta['Content-Disposition'] = f'inline; filename="{nome}.png"'
    resposta['Cache-Control'] = 'private, no-store'
    return resposta


@login_required
def servico_links(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        excluir = request.POST.get('excluir')
        if excluir:
            get_object_or_404(ServicoLink, uuid=excluir, servico=servico).delete()
            messages.success(request, 'Link removido com sucesso.')
            return redirect('painel:servico_links', uuid=servico.uuid)
        form = ServicoLinkForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                link = form.save(commit=False)
                link.servico = servico
                link.save()
            messages.success(request, 'Link adicionado com sucesso.')
            return redirect('painel:servico_links', uuid=servico.uuid)
    else:
        form = ServicoLinkForm()
    return render(request, 'painel/links/gerenciar.html', {'objeto': servico, 'tipo_objeto': 'serviço', 'form': form, 'links': servico.links.filter(excluido_em__isnull=True), 'voltar_url': reverse('painel:servico_detalhe', kwargs={'uuid': servico.uuid})})


@login_required
def empresa_links(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)
    if not usuario_pode_editar_empresa(request.user, empresa):
        raise PermissionDenied
    if request.method == 'POST':
        excluir = request.POST.get('excluir')
        if excluir:
            get_object_or_404(EmpresaLink, uuid=excluir, empresa=empresa).delete()
            messages.success(request, 'Link removido com sucesso.')
            return redirect('painel:empresa_links', uuid=empresa.uuid)
        form = EmpresaLinkForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                link = form.save(commit=False)
                link.empresa = empresa
                link.save()
            messages.success(request, 'Link adicionado com sucesso.')
            return redirect('painel:empresa_links', uuid=empresa.uuid)
    else:
        form = EmpresaLinkForm()
    return render(request, 'painel/links/gerenciar.html', {'objeto': empresa, 'tipo_objeto': 'empresa', 'form': form, 'links': empresa.links.filter(excluido_em__isnull=True), 'voltar_url': reverse('painel:empresa_detalhe', kwargs={'uuid': empresa.uuid})})


def _auditar_qr(request, entidade, objeto, token_anterior):
    Auditoria.objects.create(usuario=request.user, acao='REGENERAR_QR_TOKEN', entidade=entidade, registro_id=str(objeto.uuid), dados_antes_json={'qr_token': str(token_anterior)}, dados_depois_json={'qr_token': str(objeto.qr_token)}, ip=request.META.get('REMOTE_ADDR'), user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000])


@login_required
def servico_qrcode(request: HttpRequest, uuid) -> HttpResponse:
    servico = get_object_or_404(servicos_disponiveis_para_usuario(request.user), uuid=uuid)
    if not usuario_pode_editar_servico(request.user, servico):
        raise PermissionDenied
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'regenerar':
            anterior = servico.qr_token
            with transaction.atomic():
                servico.regenerar_qr_token()
                _auditar_qr(request, 'services.Servico', servico, anterior)
            messages.success(request, 'Token do QR Code regenerado. O link anterior foi invalidado.')
        elif acao == 'alternar':
            servico.qr_ativo = not servico.qr_ativo
            servico.qr_atualizado_em = timezone.now()
            servico.save(update_fields=['qr_ativo', 'qr_atualizado_em', 'atualizado_em'])
        return redirect('painel:servico_qrcode', uuid=servico.uuid)
    url = obter_url_publica(servico, request)
    if request.GET.get('formato') == 'png':
        return _resposta_qrcode(servico, request, f'botuka-servico-{servico.uuid}')
    return render(request, 'painel/qrcode.html', {'objeto': servico, 'tipo_objeto': 'serviço', 'url_curta': url, 'imagem_url': f'{request.path}?formato=png', 'voltar_url': reverse('painel:servico_detalhe', kwargs={'uuid': servico.uuid})})


@login_required
def empresa_qrcode(request: HttpRequest, uuid) -> HttpResponse:
    empresa = get_object_or_404(empresas_disponiveis_para_usuario(request.user), uuid=uuid)
    if not usuario_pode_editar_empresa(request.user, empresa):
        raise PermissionDenied
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'regenerar':
            anterior = empresa.qr_token
            with transaction.atomic():
                empresa.regenerar_qr_token()
                _auditar_qr(request, 'organizations.Empresa', empresa, anterior)
            messages.success(request, 'Token do QR Code regenerado. O link anterior foi invalidado.')
        elif acao == 'alternar':
            empresa.qr_ativo = not empresa.qr_ativo
            empresa.qr_atualizado_em = timezone.now()
            empresa.save(update_fields=['qr_ativo', 'qr_atualizado_em', 'atualizado_em'])
        return redirect('painel:empresa_qrcode', uuid=empresa.uuid)
    url = obter_url_publica(empresa, request)
    if request.GET.get('formato') == 'png':
        return _resposta_qrcode(empresa, request, f'botuka-empresa-{empresa.uuid}')
    return render(request, 'painel/qrcode.html', {'objeto': empresa, 'tipo_objeto': 'empresa', 'url_curta': url, 'imagem_url': f'{request.path}?formato=png', 'voltar_url': reverse('painel:empresa_detalhe', kwargs={'uuid': empresa.uuid})})


@login_required
def servico_preview(request: HttpRequest, uuid) -> HttpResponse:
    servico = _servico_autorizado(request, uuid)
    return render(request, 'painel/servicos/preview.html', {'servico': servico})


@login_required
def servicos_ajax_setores(request: HttpRequest) -> JsonResponse:
    termo = request.GET.get('q', '').strip()[:100]
    setores = Setor.objects.visiveis_para(request.user).filter(ativo=True)
    if termo:
        setores = setores.filter(nome__icontains=termo)
    return JsonResponse({'results': [
        {'id': setor.id, 'text': setor.nome}
        for setor in setores.order_by('nome')[:100]
    ]})


@login_required
def servicos_ajax_areas(request: HttpRequest) -> JsonResponse:
    setor_id = request.GET.get('setor_id')
    if not setor_id or not setor_id.isdigit():
        return JsonResponse({'results': []})

    if not Setor.objects.visiveis_para(request.user).filter(pk=setor_id, ativo=True).exists():
        return JsonResponse({'results': []})
    termo = request.GET.get('q', '').strip()[:100]
    areas = AreaProfissional.objects.visiveis_para(request.user).filter(ativo=True, setor_id=setor_id)
    if termo:
        areas = areas.filter(nome__icontains=termo)

    return JsonResponse(
        {
            'results': [
                {'id': area.id, 'text': area.nome}
                for area in areas.order_by('nome')[:100]
            ]
        }
    )


@login_required
def servicos_ajax_profissoes(request: HttpRequest) -> JsonResponse:
    area_id = request.GET.get('area_profissional_id')
    if not area_id or not area_id.isdigit():
        return JsonResponse({'results': []})
    area = AreaProfissional.objects.visiveis_para(request.user).filter(pk=area_id, ativo=True).first()
    if not area:
        return JsonResponse({'results': []})
    termo = request.GET.get('q', '').strip()[:100]
    profissoes = Profissao.objects.visiveis_para(request.user).filter(
        ativo=True, area=area, setor=area.setor,
    )
    if termo:
        profissoes = profissoes.filter(nome__icontains=termo)

    return JsonResponse(
        {
            'results': [
                {'id': profissao.id, 'text': profissao.nome}
                for profissao in profissoes.order_by('nome')[:200]
            ]
        }
    )


@login_required
def servicos_ajax_tipos(request: HttpRequest) -> JsonResponse:
    profissao_id = request.GET.get('profissao_id')
    if not profissao_id or not profissao_id.isdigit():
        return JsonResponse({'results': []})
    termo = request.GET.get('q', '').strip()[:100]
    tipos = TipoServico.objects.visiveis_para(request.user).filter(
        ativo=True,
        vinculos_profissoes__profissao_id=profissao_id,
        vinculos_profissoes__profissao__ativo=True,
        vinculos_profissoes__ativo=True,
        vinculos_profissoes__in=ProfissaoTipoServico.objects.visiveis_para(request.user),
    )
    if termo:
        tipos = tipos.filter(nome__icontains=termo)
    return JsonResponse({'results': [
        {'id': tipo.id, 'text': tipo.nome}
        for tipo in tipos.distinct().order_by('nome')[:100]
    ]})


@painel_permission_required('produtos.visualizar')
def produtos_lista(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/produtos/lista.html', 'Produtos')


@painel_permission_required('vagas.visualizar')
def vagas_lista(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/vagas/lista.html', 'Vagas')


@painel_permission_required('curriculo.visualizar')
def curriculo(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/curriculo/index.html', 'Currículo')


@painel_permission_required('eventos.visualizar')
def eventos_lista(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/eventos/lista.html', 'Eventos')


@painel_permission_required('rede_social.acessar')
def rede_social(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/rede_social/index.html', 'Rede social')


@painel_permission_required('mensagens.acessar')
def mensagens(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/mensagens/index.html', 'Mensagens')


@painel_permission_required('configuracoes.editar')
def configuracoes(request: HttpRequest) -> HttpResponse:
    return render_pagina(request, 'painel/configuracoes/index.html', 'Configurações')



@login_required
def empresa_agenda(request: HttpRequest, uuid) -> HttpResponse:
    empresa = _empresa_autorizada(request, uuid)

    if not usuario_pode_gerenciar_empresa(request.user, empresa):
        raise PermissionDenied

    if not empresa.pode_aceitar_agendamentos:
        messages.warning(
            request,
            'Esta empresa não possui a capacidade de Agenda habilitada.'
        )
        return redirect('painel:empresa_detalhe', uuid=empresa.uuid)

    profissionais = (
        AgendaProfissional.objects
        .filter(
            empresa_usuario__empresa=empresa,
            ativo=True,
        )
        .select_related(
            'empresa_usuario',
            'empresa_usuario__usuario',
        )
        .order_by(
            'empresa_usuario__usuario__nome_exibicao',
            'empresa_usuario__usuario__first_name',
        )
    )

    servicos = (
        AgendaProfissionalServico.objects
        .filter(
            profissional__empresa_usuario__empresa=empresa,
            ativo=True,
        )
        .select_related(
            'profissional',
            'profissional__empresa_usuario',
            'profissional__empresa_usuario__usuario',
            'servico',
        )
    )

    disponibilidades = (
        AgendaDisponibilidade.objects
        .filter(
            profissional__empresa_usuario__empresa=empresa,
            ativo=True,
        )
        .select_related(
            'profissional',
            'profissional__empresa_usuario',
            'profissional__empresa_usuario__usuario',
        )
    )

    bloqueios = (
        AgendaBloqueio.objects
        .filter(
            profissional__empresa_usuario__empresa=empresa,
            ativo=True,
        )
        .select_related(
            'profissional',
            'profissional__empresa_usuario',
            'profissional__empresa_usuario__usuario',
        )
        .order_by('inicio')
    )

    agendamentos = (
        Agendamento.objects
        .filter(
            profissional_servico__profissional__empresa_usuario__empresa=empresa,
        )
        .select_related(
            'cliente',
            'profissional_servico',
            'profissional_servico__servico',
            'profissional_servico__profissional',
            'profissional_servico__profissional__empresa_usuario',
            'profissional_servico__profissional__empresa_usuario__usuario',
        )
        .order_by('inicio')[:50]
    )

    contexto = {
        'empresa': empresa,
        'profissionais': profissionais,
        'servicos_agenda': servicos,
        'disponibilidades': disponibilidades,
        'bloqueios': bloqueios,
        'agendamentos': agendamentos,
    }

    return render(
        request,
        'painel/agenda/dashboard.html',
        contexto,
    )

@login_required
def empresa_subcategorias_json(
    request: HttpRequest,
) -> JsonResponse:
    categoria_id = request.GET.get('categoria')

    if not categoria_id:
        return JsonResponse(
            {
                'subcategorias': [],
            }
        )

    try:
        categoria_id = int(categoria_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {
                'subcategorias': [],
            },
            status=400,
        )

    qs = (
        Subcategoria.objects
        .filter(
            categoria_id=categoria_id,
            ativo=True,
            removido_em__isnull=True,
        )
        .order_by(
            'ordem',
            'nome',
        )
    )

    return JsonResponse(
        {
            'subcategorias': [
                {
                    'id': item.pk,
                    'nome': item.nome,
                }
                for item in qs
            ]
        }
    )
