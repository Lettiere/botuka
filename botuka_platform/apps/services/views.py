"""Páginas públicas e redirecionamentos curtos de serviços e empresas."""

import time

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, Exists, IntegerField, OuterRef, Prefetch, Q, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.crypto import salted_hmac

from apps.organizations.models import Empresa, EmpresaLead, EmpresaSolicitacao, EmpresaUsuario
from apps.organizations.permissions import usuario_pode_editar_empresa
from apps.services.forms import EmpresaLeadForm, EmpresaReivindicacaoForm
from apps.services.models import Servico, ServicoImagem, Setor
from apps.core.seo.page_builders import empresa_seo, listing_seo, servico_seo
from apps.core.services.contacts import formatar_telefone, normalizar_telefone, telefone_para_whatsapp
from apps.products.models import Produto
from apps.products.public_catalog import produtos_publicos as catalogo_produtos_publicos
from apps.recruitment.models import Vaga
from apps.social.selectors import contagem_seguidores_empresa
from apps.social.services import usuario_segue_empresa
from apps.agenda.public_services import servicos_agendaveis, vinculos_agendaveis
from apps.core.services.public_sharing import obter_dados_compartilhamento


def empresas_publicas(request):
    queryset = (
        Empresa.objects
        .filter(
            ativo=True,
            perfil_publico=True,
            status=Empresa.Status.ATIVA,
            excluido_em__isnull=True,
        )
        .select_related('categoria_empresa', 'cidade', 'estado')
        .annotate(
            tem_usuario=Exists(
                EmpresaUsuario.objects.filter(
                    empresa_id=OuterRef('pk'),
                    ativo=True,
                )
            ),
            tem_imagem=Case(
                When(
                    Q(logo__isnull=False) & ~Q(logo=''),
                    then=Value(1),
                ),
                When(
                    Q(imagem_capa__isnull=False) & ~Q(imagem_capa=''),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
    )
    q = request.GET.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(Q(nome_fantasia__icontains=q) | Q(razao_social__icontains=q) | Q(descricao_curta__icontains=q) | Q(categoria_empresa__nome__icontains=q) | Q(bairro__icontains=q))
    if request.GET.get('categoria'): queryset = queryset.filter(categoria_empresa__slug=request.GET['categoria'][:100])
    if request.GET.get('bairro'): queryset = queryset.filter(bairro__iexact=request.GET['bairro'][:100])
    if request.GET.get('verificada') == '1': queryset = queryset.filter(verificada=True)
    if request.GET.get('ordem') == 'az':
        queryset = queryset.order_by(
            '-tem_usuario',
            '-tem_imagem',
            'nome_fantasia',
            'razao_social',
        )
    else:
        queryset = queryset.order_by(
            '-tem_usuario',
            '-tem_imagem',
            '-atualizado_em',
        )
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    categorias = Empresa.objects.filter(ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA, categoria_empresa__isnull=False).values('categoria_empresa__slug', 'categoria_empresa__nome').distinct().order_by('categoria_empresa__nome')
    seo = listing_seo(request, 'Empresas em Botucatu | BOTUKA', 'Encontre empresas, negócios e organizações com perfil público em Botucatu.')
    return render(request, 'publico/empresas/lista.html', {'page_obj': page, 'empresas': page.object_list, 'categorias': categorias, 'total': page.paginator.count, 'seo': seo})


def servicos_publicos(request):
    queryset = Servico.objects.publicamente_visiveis().filter(Q(empresa__isnull=True) | Q(empresa__ativo=True, empresa__perfil_publico=True, empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True)).select_related('empresa', 'setor', 'profissao', 'tipo_servico').prefetch_related('atributos_adicionais', Prefetch('imagens', queryset=ServicoImagem.objects.filter(ativo=True, excluido_em__isnull=True).order_by('-principal', 'ordem')))
    q = request.GET.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(Q(titulo__icontains=q) | Q(descricao_curta__icontains=q) | Q(descricao_completa__icontains=q) | Q(setor__nome__icontains=q) | Q(profissao__nome__icontains=q) | Q(empresa__nome_fantasia__icontains=q) | Q(atributos_adicionais__valor__icontains=q) | Q(atributos_adicionais__nome_personalizado__icontains=q)).distinct()
    if request.GET.get('categoria'): queryset = queryset.filter(setor__slug=request.GET['categoria'][:100])
    if request.GET.get('prestador') in Servico.PrestadorTipo.values: queryset = queryset.filter(prestador_tipo=request.GET['prestador'])
    if request.GET.get('remoto') == '1': queryset = queryset.filter(atendimento_remoto=True)
    if request.GET.get('presencial') == '1': queryset = queryset.filter(atendimento_presencial=True)
    empresa_slug = request.GET.get('empresa', '').strip()[:100]
    if empresa_slug:
        queryset = queryset.filter(empresa__slug=empresa_slug)
    queryset = queryset.order_by('titulo' if request.GET.get('ordem') == 'az' else '-publicado_em')
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    seo = listing_seo(request, 'Serviços em Botucatu | BOTUKA', 'Encontre serviços, profissionais e empresas prestadoras em Botucatu.')
    return render(request, 'publico/servicos/lista.html', {'page_obj': page, 'servicos': page.object_list, 'categorias': Setor.objects.visiveis_para().filter(ativo=True), 'total': page.paginator.count, 'seo': seo})


def servico_publico(request, slug):
    servico = get_object_or_404(
        Servico.objects.publicamente_visiveis().select_related('empresa', 'usuario_responsavel', 'tipo_servico').prefetch_related('atributos_adicionais', 'links', Prefetch('imagens', queryset=ServicoImagem.objects.filter(ativo=True, excluido_em__isnull=True).order_by('-principal', 'ordem'))),
        slug=slug,
    )
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    links = servico.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    agenda_disponivel = bool(
        servico.empresa_id
        and vinculos_agendaveis(empresa=servico.empresa, servico=servico)
    )
    return render(request, 'publico/servicos/detalhe.html', {'servico': servico, 'share_object': servico, 'share_type': 'servico', 'links': links, 'videos': [link for link in links if link.url_embed][:6], 'seo': servico_seo(request, servico), 'agenda_disponivel': agenda_disponivel})


def empresa_publica(request, slug):
    # Mantém compatibilidade com a URL pública histórica da Golden Beer.
    if slug == 'aleicah-marketing-digital':
        return redirect(
            'publico:empresa',
            slug='golden-beer-tap-house',
            permanent=True,
        )

    empresa = get_object_or_404(
        Empresa.objects.prefetch_related('links'),
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
    )
    links = empresa.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    produtos_publicos = (
        catalogo_produtos_publicos().filter(
            empresa_proprietaria=empresa, ativo=True, removido_em__isnull=True,
        )
        if empresa.verificada and empresa.pode_publicar_produto
        else Produto.objects.none()
    )
    servicos_publicados = Servico.objects.publicamente_visiveis().filter(empresa=empresa)
    produtos = produtos_publicos[:6]
    servicos = servicos_publicados[:6]
    servicos_agenda = servicos_agendaveis(empresa)
    vagas = Vaga.objects.filter(
        empresa=empresa, ativo=True, excluido_em__isnull=True,
        status=Vaga.Status.PUBLICADA,
    )[:6]
    partes_endereco = [empresa.endereco, empresa.numero, empresa.complemento,
                       empresa.bairro, getattr(empresa.cidade, 'nome', ''),
                       getattr(empresa.estado, 'sigla', '')]
    endereco_publico = ', '.join(str(parte).strip() for parte in partes_endereco if parte)
    coordenadas = (f'{empresa.latitude},{empresa.longitude}'
                   if empresa.latitude is not None and empresa.longitude is not None else '')
    endereco_suficiente = bool(empresa.endereco and (empresa.cidade_id or empresa.bairro or empresa.cep))
    destino_mapa = coordenadas or (endereco_publico if endereco_suficiente else '')
    google_maps_url = (f"https://www.google.com/maps/search/?{urlencode({'api': '1', 'query': destino_mapa})}"
                       if destino_mapa else '')
    waze_params = {'navigate': 'yes'}
    if coordenadas:
        waze_params['ll'] = coordenadas
    elif endereco_publico:
        waze_params['q'] = endereco_publico
    waze_url = f"https://www.waze.com/ul?{urlencode(waze_params)}" if destino_mapa else ''
    telefone_normalizado = normalizar_telefone(empresa.telefone)

    telefone_local = telefone_normalizado or ''
    if telefone_local.startswith('55') and len(telefone_local) == 13:
        telefone_local = telefone_local[2:]

    telefone_parece_celular = (
        len(telefone_local) == 11
        and telefone_local[2:3] == '9'
    )

    numero_whatsapp = (
        empresa.whatsapp
        or (empresa.telefone if telefone_parece_celular else '')
    )

    whatsapp_url = telefone_para_whatsapp(
        numero_whatsapp,
        f'Olá! Encontrei {empresa.nome_exibicao} no BOTUKA.',
    )

    whatsapp_formatado = formatar_telefone(numero_whatsapp)

    mapa_embed_url = (
        f"https://www.google.com/maps?{urlencode({'q': destino_mapa, 'output': 'embed'})}"
        if destino_mapa
        else ''
    )

    pode_editar_empresa = usuario_pode_editar_empresa(
        request.user,
        empresa,
    )

    reivindicacao_aberta = False
    if request.user.is_authenticated:
        reivindicacao_aberta = EmpresaSolicitacao.objects.filter(
            empresa=empresa,
            usuario_solicitante=request.user,
            tipo_solicitacao=EmpresaSolicitacao.TipoSolicitacao.REIVINDICACAO,
            status__in=[
                EmpresaSolicitacao.Status.RASCUNHO,
                EmpresaSolicitacao.Status.PENDENTE,
                EmpresaSolicitacao.Status.EM_ANALISE,
                EmpresaSolicitacao.Status.CORRECAO_SOLICITADA,
            ],
        ).exists()

    pode_reivindicar = (
        empresa.usuario_proprietario_id is None
        and not pode_editar_empresa
    )

    reivindicacao_form = (
        EmpresaReivindicacaoForm()
        if request.user.is_authenticated
        and pode_reivindicar
        and not reivindicacao_aberta
        else None
    )

    origem_publica = ''
    if empresa.origem_cadastro == Empresa.OrigemCadastro.API:
        origem_publica = (
            'Perfil criado pelo BOTUKA a partir de dados cadastrais '
            'obtidos por integração com fonte pública.'
        )

    cnpj_formatado = ''
    cnpj = ''.join(ch for ch in (empresa.cpf_cnpj or '') if ch.isdigit())
    if len(cnpj) == 14:
        cnpj_formatado = (
            f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/'
            f'{cnpj[8:12]}-{cnpj[12:]}'
        )

    lead_prefill = {
        'nome': '',
        'telefone': '',
        'email': '',
    }

    if request.user.is_authenticated:
        nome_usuario = (
            request.user.get_full_name().strip()
            or request.user.nome_exibicao.strip()
            or request.user.username
        )

        lead_prefill = {
            'nome': nome_usuario,
            'telefone': request.user.celular or request.user.telefone or '',
            'email': request.user.email or '',
        }

    share = obter_dados_compartilhamento(empresa, request)
    return render(request, 'publico/empresas/detalhe.html', {
        'empresa': empresa,
        'links': links, 'videos': [link for link in links if link.url_embed][:6],
        'seo': empresa_seo(request, empresa), 'produtos': produtos[:6],
        'servicos': servicos, 'vagas': vagas,
        'tem_produtos': produtos_publicos.exists(),
        'tem_servicos': servicos_publicados.exists(),
        'produtos_url': f"{reverse('products:loja')}?{urlencode({'empresa': str(empresa.uuid)})}",
        'servicos_url': f"{reverse('publico:servicos')}?{urlencode({'empresa': empresa.slug})}",
        'agenda_disponivel': servicos_agenda.exists(),
        'endereco_publico': endereco_publico,
        'google_maps_url': google_maps_url, 'waze_url': waze_url,
        'telefone_formatado': formatar_telefone(empresa.telefone),
        'telefone_url': f'tel:+{telefone_normalizado}' if telefone_normalizado else '',
        'whatsapp_formatado': whatsapp_formatado,
        'whatsapp_url': whatsapp_url,
        'lead_prefill': lead_prefill,
        'mapa_embed_url': mapa_embed_url,
        'pode_editar_empresa': pode_editar_empresa,
        'pode_reivindicar': pode_reivindicar,
        'reivindicacao_aberta': reivindicacao_aberta,
        'reivindicacao_form': reivindicacao_form,
        'origem_publica': origem_publica,
        'cnpj_formatado': cnpj_formatado,
        'share': share,
        'qrcode_url': reverse('sharing:png', args=['empresa', empresa.uuid]),
        'followers_count': contagem_seguidores_empresa(empresa),
        'is_following_company': usuario_segue_empresa(request.user, empresa),
    })




@require_POST
def empresa_lead_criar(request, slug):
    empresa = get_object_or_404(
        Empresa,
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
        excluido_em__isnull=True,
    )

    if not empresa.aceita_leads:
        return JsonResponse(
            {
                "ok": False,
                "message": "Esta empresa não está recebendo contatos pelo BOTUKA no momento.",
            },
            status=403,
        )

    telefone_normalizado = normalizar_telefone(empresa.telefone)
    telefone_local = telefone_normalizado or ""

    if telefone_local.startswith("55") and len(telefone_local) == 13:
        telefone_local = telefone_local[2:]

    telefone_parece_celular = (
        len(telefone_local) == 11
        and telefone_local[2:3] == "9"
    )

    numero_whatsapp = (
        empresa.whatsapp
        or (empresa.telefone if telefone_parece_celular else "")
    )

    whatsapp_destino = normalizar_telefone(numero_whatsapp)

    if not telefone_para_whatsapp(numero_whatsapp):
        return JsonResponse(
            {
                "ok": False,
                "message": "Esta empresa não possui WhatsApp disponível.",
            },
            status=400,
        )

    # Proteção simples contra envio repetitivo.
    cooldown_key = f"empresa_lead_cooldown_{empresa.pk}"
    agora = time.time()
    ultimo_envio = request.session.get(cooldown_key)

    if ultimo_envio:
        try:
            if agora - float(ultimo_envio) < 10:
                return JsonResponse(
                    {
                        "ok": False,
                        "message": "Aguarde alguns segundos antes de enviar outro contato.",
                    },
                    status=429,
                )
        except (TypeError, ValueError):
            pass

    form = EmpresaLeadForm(request.POST)

    if not form.is_valid():
        return JsonResponse(
            {
                "ok": False,
                "message": "Confira os dados informados.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    dados = form.cleaned_data

    perfil_publico_url = (
        f"https://www.botuka.com.br"
        f"{reverse('publico:empresa', kwargs={'slug': empresa.slug})}"
    )

    mensagem_whatsapp = (
        "Olá! Encontrei seu perfil no BOTUKA:\n"
        f"{perfil_publico_url}\n\n"
        f"Assunto: {dados['assunto']}\n\n"
        f"{dados['mensagem']}\n\n"
        "Meus dados:\n"
        f"Nome: {dados['nome']}\n"
        f"Telefone: {dados['telefone']}\n"
        f"E-mail: {dados['email']}\n\n"
        "Contato gerado pelo BOTUKA."
    )

    whatsapp_url = telefone_para_whatsapp(
        numero_whatsapp,
        mensagem_whatsapp,
    )

    ip = request.META.get("REMOTE_ADDR", "")
    ip_hash = (
        salted_hmac("empresa_lead_ip", ip).hexdigest()
        if ip
        else ""
    )

    lead = EmpresaLead.objects.create(
        empresa=empresa,
        usuario=request.user if request.user.is_authenticated else None,
        nome=dados["nome"],
        email=dados["email"],
        telefone=dados["telefone"],
        assunto=dados["assunto"],
        mensagem=dados["mensagem"],
        canal=EmpresaLead.Canal.WHATSAPP,
        origem=EmpresaLead.Origem.EMPRESA,
        pagina_origem=request.path[:300],
        url_origem=perfil_publico_url[:500],
        referrer=request.META.get("HTTP_REFERER", "")[:500],
        utm_source=request.POST.get("utm_source", "")[:120],
        utm_medium=request.POST.get("utm_medium", "")[:120],
        utm_campaign=request.POST.get("utm_campaign", "")[:180],
        utm_content=request.POST.get("utm_content", "")[:180],
        utm_term=request.POST.get("utm_term", "")[:180],
        session_id=request.session.session_key or "",
        ip_hash=ip_hash,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        whatsapp_destino=whatsapp_destino[:20],
        mensagem_whatsapp=mensagem_whatsapp,
    )

    request.session[cooldown_key] = agora

    return JsonResponse(
        {
            "ok": True,
            "lead_id": str(lead.uuid),
            "whatsapp_url": whatsapp_url,
        },
        status=201,
    )


@login_required
@require_POST
def empresa_reivindicar(request, slug):
    empresa = get_object_or_404(
        Empresa,
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
    )

    if usuario_pode_editar_empresa(request.user, empresa):
        messages.info(
            request,
            'Você já possui permissão para administrar esta empresa.',
        )
        return redirect('publico:empresa', slug=empresa.slug)

    if empresa.usuario_proprietario_id is not None:
        messages.warning(
            request,
            'Esta empresa já possui um responsável cadastrado.',
        )
        return redirect('publico:empresa', slug=empresa.slug)

    existente = EmpresaSolicitacao.objects.filter(
        empresa=empresa,
        usuario_solicitante=request.user,
        tipo_solicitacao=EmpresaSolicitacao.TipoSolicitacao.REIVINDICACAO,
        status__in=[
            EmpresaSolicitacao.Status.RASCUNHO,
            EmpresaSolicitacao.Status.PENDENTE,
            EmpresaSolicitacao.Status.EM_ANALISE,
            EmpresaSolicitacao.Status.CORRECAO_SOLICITADA,
        ],
    ).first()

    if existente:
        messages.info(
            request,
            'Você já possui uma solicitação de reivindicação em andamento.',
        )
        return redirect('publico:empresa', slug=empresa.slug)

    form = EmpresaReivindicacaoForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            'Confira os dados informados para reivindicar esta empresa.',
        )
        return redirect('publico:empresa', slug=empresa.slug)

    solicitacao = form.save(commit=False)
    solicitacao.empresa = empresa
    solicitacao.cnpj = empresa.cpf_cnpj or ''
    solicitacao.usuario_solicitante = request.user
    solicitacao.tipo_solicitacao = (
        EmpresaSolicitacao.TipoSolicitacao.REIVINDICACAO
    )
    solicitacao.status = EmpresaSolicitacao.Status.PENDENTE
    solicitacao.save()

    messages.success(
        request,
        'Solicitação enviada. O BOTUKA analisará a reivindicação da empresa.',
    )

    return redirect('publico:empresa', slug=empresa.slug)

def qrcode_servico_redirect(request, token):
    servico = get_object_or_404(
        Servico.objects.publicamente_visiveis(), qr_token=token, qr_ativo=True,
    )
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    return redirect('publico:servico', slug=servico.slug, permanent=False)


def qrcode_empresa_redirect(request, token):
    empresa = get_object_or_404(Empresa, qr_token=token, qr_ativo=True, ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA)
    return redirect('publico:empresa', slug=empresa.slug, permanent=False)
