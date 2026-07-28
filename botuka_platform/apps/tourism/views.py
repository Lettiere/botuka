from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import usuario_tem_permissao
from apps.core.services.maps import GeocodingService, MapService

from .forms import (
    ContatoTurismoForm, EmpresaTuristicaForm, ExperienciaTuristicaForm,
    GaleriaUploadForm,
    GuiaTuristicoForm, LocalCategoriaForm, LocalContatosForm,
    LocalIdentificacaoForm, LocalImagemPrincipalForm, LocalInformacoesForm,
    LocalLocalizacaoForm, LocalPlaylistForm, LocalRelacoesForm,
    LocalTuristicoForm, LocalVideoForm, RedeSocialTurismoForm,
    RoteiroTuristicoForm, TurismoFotoForm, TurismoPlaylistForm,
    TurismoPlaylistVideoForm, TurismoVideoForm,
)
from .models import (
    ContatoTurismo, EmpresaTuristica, ExperienciaTuristica, GuiaTuristico,
    LocalTuristico, RedeSocialTurismo, RoteiroTuristico, TurismoFoto,
    TurismoPlaylist, TurismoPlaylistVideo, TurismoStatus, TurismoVideo,
)
from .permissions import objetos_editaveis, pode_editar, require
from .services import alterar_status, processar_imagem_principal, validar_publicacao_local


LOCAL_STEPS = (
    (1, 'Identificação', 'Nome, descrições e situação atual do local.'),
    (2, 'Categoria', 'Classifique o tipo de atrativo turístico.'),
    (3, 'Localização', 'Informe o endereço e defina a precisão pública.'),
    (4, 'Informações práticas', 'Oriente visitantes sobre funcionamento e estrutura.'),
    (5, 'Imagem principal', 'Defina a capa usada na página pública e na HOME.'),
    (6, 'Galeria de imagens', 'Organize imagens complementares e seus créditos.'),
    (7, 'Vídeos e playlists', 'Relacione conteúdo audiovisual seguro do YouTube.'),
    (8, 'Contatos e redes sociais', 'Cadastre somente canais autorizados para divulgação.'),
    (9, 'Relações e responsáveis', 'Vincule guias, empresa e responsável administrativo.'),
    (10, 'Revisão e publicação', 'Revise o cadastro antes de enviar para análise.'),
)

LOCAL_STEP_FORMS = {
    1: LocalIdentificacaoForm,
    2: LocalCategoriaForm,
    3: LocalLocalizacaoForm,
    4: LocalInformacoesForm,
    5: LocalImagemPrincipalForm,
    8: LocalContatosForm,
    9: LocalRelacoesForm,
}


ENTITY = {
    'locais': {
        'model': LocalTuristico, 'form': LocalTuristicoForm, 'label': 'Local turístico',
        'plural': 'Locais turísticos', 'prefix': 'TURISMO_LOCAL',
        'own': 'TURISMO_LOCAL_EDITAR_PROPRIOS', 'all': 'TURISMO_LOCAL_EDITAR_TODOS',
        'title': 'nome', 'search': 'nome', 'new_name': 'painel:turismo_local_novo',
    },
    'guias': {
        'model': GuiaTuristico, 'form': GuiaTuristicoForm, 'label': 'Guia turístico',
        'plural': 'Guias turísticos', 'prefix': 'TURISMO_GUIA',
        'own': 'TURISMO_GUIA_EDITAR_PROPRIO', 'all': 'TURISMO_GUIA_EDITAR_TODOS',
        'title': 'nome_profissional', 'search': 'nome_profissional', 'new_name': 'painel:turismo_guia_novo',
    },
    'empresas': {
        'model': EmpresaTuristica, 'form': EmpresaTuristicaForm, 'label': 'Empresa turística',
        'plural': 'Empresas turísticas', 'prefix': 'TURISMO_EMPRESA',
        'own': 'TURISMO_EMPRESA_EDITAR_PROPRIAS', 'all': 'TURISMO_EMPRESA_EDITAR_TODAS',
        'title': 'empresa', 'search': 'empresa__nome_fantasia', 'new_name': 'painel:turismo_empresa_nova',
    },
    'videos': {
        'model': TurismoVideo, 'form': TurismoVideoForm, 'label': 'Vídeo',
        'plural': 'Vídeos', 'prefix': 'TURISMO_VIDEO',
        'own': 'TURISMO_VIDEO_EDITAR_PROPRIOS', 'all': 'TURISMO_VIDEO_MODERAR',
        'title': 'titulo', 'search': 'titulo', 'new_name': 'painel:turismo_video_novo',
    },
    'playlists': {
        'model': TurismoPlaylist, 'form': TurismoPlaylistForm, 'label': 'Playlist',
        'plural': 'Playlists', 'prefix': 'TURISMO_PLAYLIST',
        'own': 'TURISMO_PLAYLIST_EDITAR_PROPRIAS', 'all': 'TURISMO_PLAYLIST_MODERAR',
        'title': 'titulo', 'search': 'titulo', 'new_name': 'painel:turismo_playlist_nova',
    },
    'roteiros': {
        'model': RoteiroTuristico, 'form': RoteiroTuristicoForm, 'label': 'Roteiro',
        'plural': 'Roteiros', 'prefix': 'TURISMO_ROTEIRO',
        'own': 'TURISMO_ROTEIRO_EDITAR_PROPRIOS', 'all': 'TURISMO_ROTEIRO_PUBLICAR',
        'title': 'titulo', 'search': 'titulo', 'new_name': 'painel:turismo_roteiro_novo',
    },
    'experiencias': {
        'model': ExperienciaTuristica, 'form': ExperienciaTuristicaForm, 'label': 'Experiência',
        'plural': 'Experiências', 'prefix': 'TURISMO_EXPERIENCIA',
        'own': 'TURISMO_EXPERIENCIA_EDITAR_PROPRIAS', 'all': 'TURISMO_EXPERIENCIA_PUBLICAR',
        'title': 'titulo', 'search': 'titulo', 'new_name': 'painel:turismo_experiencia_nova',
    },
}


def _allowed(user, code):
    return usuario_tem_permissao(user, code)


def _queryset(user, config):
    if config['model'] is LocalTuristico and _allowed(user, 'TURISMO_LOCAL_MODERAR'):
        return config['model'].all_objects.filter(ativo=True)
    return objetos_editaveis(
        user, config['model'].all_objects.filter(ativo=True),
        config['own'], config['all'],
    )


def _form(config, *args, user=None, **kwargs):
    return config['form'](*args, usuario=user, **kwargs)


@login_required
def dashboard(request):
    if not any(_allowed(request.user, f"{item['prefix']}_VISUALIZAR_PAINEL") or
               _allowed(request.user, f"{item['prefix']}_CADASTRAR") or
               _allowed(request.user, item['own']) or _allowed(request.user, item['all'])
               for item in ENTITY.values()):
        raise PermissionDenied

    counters, recentes, pendentes = [], [], []
    for slug, config in ENTITY.items():
        qs = _queryset(request.user, config)
        status_counts = dict(qs.values_list('status').annotate(total=Count('pk')))
        total = qs.count()
        counters.append({
            'slug': slug, 'label': config['plural'], 'icon': {
                'locais': 'geo-alt', 'guias': 'person-badge', 'empresas': 'buildings',
                'videos': 'play-btn', 'playlists': 'collection-play',
                'roteiros': 'signpost-split', 'experiencias': 'stars',
            }[slug],
            'total': total, 'publicados': status_counts.get(TurismoStatus.PUBLICADO, 0),
            'analise': status_counts.get(TurismoStatus.EM_ANALISE, 0),
            'rascunhos': status_counts.get(TurismoStatus.RASCUNHO, 0),
        })
        for obj in qs.order_by('-atualizado_em')[:4]:
            recentes.append((obj.atualizado_em, slug, config, obj))
        if _allowed(request.user, f"{config['prefix']}_MODERAR") or _allowed(request.user, f"{config['prefix']}_PUBLICAR"):
            for obj in config['model'].objects.filter(status=TurismoStatus.EM_ANALISE).order_by('atualizado_em')[:8]:
                pendentes.append((obj.atualizado_em, slug, config, obj))

    actions = []
    for slug, config in ENTITY.items():
        if _allowed(request.user, f"{config['prefix']}_CADASTRAR"):
            actions.append({
                'slug': slug, 'label': f"Novo {config['label'].lower()}",
                'description': {
                    'locais': 'Cadastre pontos de interesse, parques, museus, trilhas e mirantes.',
                    'guias': 'Cadastre um guia pessoa física ou vinculado a uma empresa.',
                    'empresas': 'Classifique uma empresa existente para atuação no Turismo.',
                    'videos': 'Associe um vídeo seguro do YouTube a um conteúdo turístico.',
                    'playlists': 'Organize vídeos em uma sequência temática.',
                    'roteiros': 'Monte um percurso com locais e guias.',
                    'experiencias': 'Cadastre passeios, atividades e visitas guiadas.',
                }[slug],
                'url_name': config['new_name'],
                'icon': next(item['icon'] for item in counters if item['slug'] == slug),
            })
    return render(request, 'painel/turismo/dashboard.html', {
        'indicadores': counters, 'acoes': actions,
        'recentes': sorted(recentes, key=lambda row: row[0], reverse=True)[:12],
        'pendentes': sorted(pendentes, key=lambda row: row[0])[:12],
    })


@login_required
def entidade_lista(request, entidade):
    config = ENTITY.get(entidade)
    if not config:
        raise Http404
    qs = _queryset(request.user, config)
    status = request.GET.get('status')
    busca = request.GET.get('q', '').strip()
    if status in TurismoStatus.values:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(**{f"{config['search']}__icontains": busca})
    return render(request, 'painel/turismo/lista.html', {
        'config': config, 'entidade': entidade, 'objetos': qs.order_by('-atualizado_em'),
        'status_atual': status, 'busca': busca,
        'status_choices': TurismoStatus.choices,
        'pode_criar': _allowed(request.user, f"{config['prefix']}_CADASTRAR"),
    })


@login_required
def entidade_nova(request, entidade):
    config = ENTITY[entidade]
    require(request.user, f"{config['prefix']}_CADASTRAR")
    form = _form(config, request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.usuario_criador = obj.usuario_atualizador = request.user
        if isinstance(obj, GuiaTuristico):
            obj.usuario = request.user
        obj.save()
        form.save_m2m()
        messages.success(request, f"{config['label']} salvo como rascunho.")
        return redirect('painel:turismo_entidade_detalhe', entidade=entidade, uuid=obj.uuid)
    return render(request, 'painel/turismo/form.html', {
        'form': form, 'titulo': f"Novo {config['label'].lower()}",
        'entidade': entidade, 'config': config,
    })


@login_required
def entidade_detalhe(request, entidade, uuid):
    config = ENTITY[entidade]
    obj = get_object_or_404(_queryset(request.user, config), uuid=uuid)
    return render(request, 'painel/turismo/detalhe.html', {
        'objeto': obj, 'config': config, 'entidade': entidade,
        'pode_moderar': _allowed(request.user, f"{config['prefix']}_MODERAR") or
                         _allowed(request.user, f"{config['prefix']}_PUBLICAR"),
        'pode_enviar': _allowed(request.user, f"{config['prefix']}_ENVIAR_ANALISE"),
        'pode_publicar': _allowed(request.user, f"{config['prefix']}_PUBLICAR"),
        'pode_pausar': _allowed(request.user, f"{config['prefix']}_PAUSAR"),
    })


@login_required
def entidade_editar(request, entidade, uuid):
    config = ENTITY[entidade]
    obj = get_object_or_404(_queryset(request.user, config), uuid=uuid)
    form = _form(config, request.POST or None, request.FILES or None, instance=obj, user=request.user)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.usuario_atualizador = request.user
        obj.save()
        form.save_m2m()
        messages.success(request, f"{config['label']} atualizado.")
        return redirect('painel:turismo_entidade_detalhe', entidade=entidade, uuid=obj.uuid)
    return render(request, 'painel/turismo/form.html', {
        'form': form, 'titulo': f"Editar {config['label'].lower()}",
        'entidade': entidade, 'config': config, 'objeto': obj,
    })


@login_required
def entidade_remover(request, entidade, uuid):
    config = ENTITY[entidade]
    obj = get_object_or_404(_queryset(request.user, config), uuid=uuid)
    if request.method == 'POST':
        obj.ativo = False
        obj.usuario_atualizador = request.user
        obj.save(update_fields=['ativo', 'usuario_atualizador', 'atualizado_em'])
        messages.success(request, f"{config['label']} arquivado.")
        return redirect('painel:turismo_entidade_lista', entidade=entidade)
    return render(request, 'painel/turismo/remover.html', {
        'objeto': obj, 'config': config, 'entidade': entidade,
    })


@login_required
def entidade_status(request, entidade, uuid):
    if request.method != 'POST':
        raise PermissionDenied
    config = ENTITY[entidade]
    obj = get_object_or_404(config['model'].all_objects.filter(ativo=True), uuid=uuid)
    if not pode_editar(request.user, obj, config['own'], config['all']) and not (
        _allowed(request.user, f"{config['prefix']}_MODERAR") or
        _allowed(request.user, f"{config['prefix']}_PUBLICAR")
    ):
        raise PermissionDenied
    try:
        if isinstance(obj, GuiaTuristico) and request.POST.get('status') == TurismoStatus.PUBLICADO:
            require(request.user, 'TURISMO_GUIA_VALIDAR')
        alterar_status(obj, request.user, request.POST.get('status'))
        if isinstance(obj, GuiaTuristico) and obj.status == TurismoStatus.PUBLICADO and not obj.verificado:
            obj.verificado = True
            obj.save(update_fields=['verificado', 'atualizado_em'])
        messages.success(request, 'Status atualizado.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:turismo_entidade_detalhe', entidade=entidade, uuid=uuid)


# Aliases estáveis mantêm compatibilidade com rotas e integrações existentes.
@login_required
def local_novo(request):
    require(request.user, 'TURISMO_LOCAL_CADASTRAR')
    form = LocalIdentificacaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        local = form.save(commit=False)
        local.categoria_legada = ''
        local.status = TurismoStatus.RASCUNHO
        local.etapa_atual = 1
        local.usuario_criador = local.usuario_atualizador = request.user
        local.responsavel_administrativo = request.user
        local.save()
        messages.success(request, 'Rascunho criado. Continue preenchendo o cadastro.')
        destino = 2 if request.POST.get('acao') == 'continuar' else 1
        return redirect('painel:turismo_local_etapa', uuid=local.uuid, etapa=destino)
    return render(request, 'painel/turismo/local_wizard.html', {
        'form': form, 'etapa': 1, 'etapas': LOCAL_STEPS,
        'titulo_etapa': LOCAL_STEPS[0][1], 'descricao_etapa': LOCAL_STEPS[0][2],
        'progresso': 10, 'novo': True,
    })


def _local_wizard(request, uuid):
    base = LocalTuristico.all_objects.filter(ativo=True)
    if _allowed(request.user, 'TURISMO_LOCAL_EDITAR_TODOS') or _allowed(request.user, 'TURISMO_LOCAL_MODERAR'):
        return get_object_or_404(base, uuid=uuid)
    if _allowed(request.user, 'TURISMO_LOCAL_EDITAR_PROPRIOS') or _allowed(request.user, 'TURISMO_LOCAL_CADASTRAR'):
        return get_object_or_404(base, uuid=uuid, usuario_criador=request.user)
    raise PermissionDenied


@login_required
def local_etapa(request, uuid, etapa):
    if etapa not in range(1, 11):
        raise Http404
    local = _local_wizard(request, uuid)
    if etapa > local.etapa_atual + 1:
        messages.info(request, 'Conclua a etapa atual antes de avançar.')
        return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=local.etapa_atual)

    form = None
    extra = {}
    if etapa in LOCAL_STEP_FORMS:
        form_class = LOCAL_STEP_FORMS[etapa]
        kwargs = {'instance': local}
        if etapa == 9:
            kwargs['usuario'] = request.user
        form = form_class(request.POST or None, request.FILES or None, **kwargs)
        if request.method == 'POST' and request.POST.get('item_tipo') is None and form.is_valid():
            local = form.save(commit=False)
            local.usuario_atualizador = request.user
            local.etapa_atual = max(local.etapa_atual, etapa)
            local.save()
            form.save_m2m()
            if etapa == 5 and 'imagem_principal' in request.FILES:
                processar_imagem_principal(local)
            messages.success(request, f'Etapa {etapa} salva.')
            if request.POST.get('acao') == 'continuar':
                proxima = min(10, etapa + 1)
                local.etapa_atual = max(local.etapa_atual, proxima)
                local.save(update_fields=['etapa_atual', 'atualizado_em'])
                return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=proxima)
            return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=etapa)

    if etapa == 6:
        foto_form = GaleriaUploadForm(
            request.POST or None if request.POST.get('item_tipo') == 'foto' else None,
            request.FILES or None,
        )
        if request.method == 'POST' and request.POST.get('item_tipo') == 'foto':
            require(request.user, 'TURISMO_FOTO_CADASTRAR')
            if foto_form.is_valid():
                inicio = local.fotos.filter(ativo=True).count()
                for indice, imagem in enumerate(foto_form.cleaned_data['imagens'], inicio + 1):
                    TurismoFoto.objects.create(
                        local=local, imagem=imagem,
                        texto_alternativo=f"{foto_form.cleaned_data['texto_alternativo']} — {imagem.name}",
                        credito=foto_form.cleaned_data['credito'], ordem=indice,
                        usuario_criador=request.user, usuario_atualizador=request.user,
                    )
                local.etapa_atual = max(local.etapa_atual, 6)
                local.save(update_fields=['etapa_atual', 'atualizado_em'])
                messages.success(request, 'Imagem adicionada à galeria.')
                return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=6)
        if request.method == 'POST' and request.POST.get('acao') == 'continuar':
            local.etapa_atual = max(local.etapa_atual, 7)
            local.save(update_fields=['etapa_atual', 'atualizado_em'])
            return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=7)
        extra.update({'foto_form': foto_form, 'fotos': local.fotos.filter(ativo=True).order_by('ordem')})

    if etapa == 7:
        video_form = LocalVideoForm(
            request.POST or None if request.POST.get('item_tipo') == 'video' else None,
        )
        playlist_form = LocalPlaylistForm(
            request.POST or None if request.POST.get('item_tipo') == 'playlist' else None,
            request.FILES or None,
        )
        if request.method == 'POST' and request.POST.get('item_tipo') == 'video':
            require(request.user, 'TURISMO_VIDEO_CADASTRAR')
            if video_form.is_valid():
                video = video_form.save(commit=False)
                video.local = local
                video.usuario_criador = video.usuario_atualizador = request.user
                video.save()
                if video.destaque:
                    local.videos.exclude(pk=video.pk).update(destaque=False)
                messages.success(request, 'Vídeo adicionado.')
                return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=7)
        if request.method == 'POST' and request.POST.get('item_tipo') == 'playlist':
            require(request.user, 'TURISMO_PLAYLIST_CADASTRAR')
            if playlist_form.is_valid():
                playlist = playlist_form.save(commit=False)
                playlist.local = local
                playlist.usuario_criador = playlist.usuario_atualizador = request.user
                playlist.save()
                messages.success(request, 'Playlist adicionada.')
                return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=7)
        if request.method == 'POST' and request.POST.get('acao') == 'continuar':
            local.etapa_atual = max(local.etapa_atual, 8)
            local.save(update_fields=['etapa_atual', 'atualizado_em'])
            return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=8)
        extra.update({
            'video_form': video_form, 'playlist_form': playlist_form,
            'videos': local.videos.filter(ativo=True).order_by('ordem'),
            'playlists': local.playlists.filter(ativo=True),
        })

    if etapa == 8:
        contato_form = ContatoTurismoForm(
            request.POST or None if request.POST.get('item_tipo') == 'contato' else None,
        )
        rede_form = RedeSocialTurismoForm(
            request.POST or None if request.POST.get('item_tipo') == 'rede' else None,
        )
        if request.method == 'POST' and request.POST.get('item_tipo') in {'contato', 'rede'}:
            item_form = contato_form if request.POST['item_tipo'] == 'contato' else rede_form
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.local = local
                item.usuario_criador = item.usuario_atualizador = request.user
                item.save()
                messages.success(request, 'Canal público adicionado.')
                return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=8)
        extra.update({
            'contato_form': contato_form, 'rede_form': rede_form,
            'contatos': local.contatos.filter(ativo=True),
            'redes': local.redes_sociais_itens.filter(ativo=True),
        })

    if etapa == 10:
        erros_publicacao = []
        try:
            validar_publicacao_local(local)
        except ValidationError as exc:
            erros_publicacao = exc.messages
        if request.method == 'POST':
            acao = request.POST.get('acao')
            if acao == 'rascunho':
                messages.success(request, 'Cadastro mantido como rascunho.')
                return redirect('painel:turismo_dashboard')
            novo_status = TurismoStatus.PUBLICADO if acao == 'publicar' else TurismoStatus.EM_ANALISE
            try:
                alterar_status(local, request.user, novo_status)
                messages.success(request, 'Local publicado.' if novo_status == TurismoStatus.PUBLICADO else 'Local enviado para análise.')
                return redirect('painel:turismo_entidade_detalhe', entidade='locais', uuid=uuid)
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        extra.update({
            'erros_publicacao': erros_publicacao,
            'pode_publicar': _allowed(request.user, 'TURISMO_LOCAL_PUBLICAR'),
        })
    if etapa == 3:
        extra['map_config'] = MapService().frontend_config()

    return render(request, 'painel/turismo/local_wizard.html', {
        'local': local, 'form': form, 'etapa': etapa, 'etapas': LOCAL_STEPS,
        'titulo_etapa': LOCAL_STEPS[etapa - 1][1],
        'descricao_etapa': LOCAL_STEPS[etapa - 1][2],
        'progresso': etapa * 10, **extra,
    })


@login_required
def local_geocodificar(request, uuid):
    _local_wizard(request, uuid)
    endereco = request.GET.get('endereco', '')[:500]
    try:
        ponto = GeocodingService().geocode(endereco)
    except Exception:
        return JsonResponse({'erro': 'Serviço de endereço indisponível. Digite as coordenadas manualmente.'}, status=503)
    if not ponto:
        return JsonResponse({'erro': 'Endereço não encontrado. Nenhuma coordenada foi alterada.'}, status=404)
    return JsonResponse({
        'latitude': ponto.latitude, 'longitude': ponto.longitude, 'descricao': ponto.label,
    })


def local_editar(request, uuid): return entidade_editar(request, 'locais', uuid)
def local_status(request, uuid): return entidade_status(request, 'locais', uuid)
def guia_novo(request): return entidade_nova(request, 'guias')
def video_novo(request): return entidade_nova(request, 'videos')
def playlist_nova(request): return entidade_nova(request, 'playlists')


@login_required
def local_fotos(request, uuid):
    config = ENTITY['locais']
    local = get_object_or_404(_queryset(request.user, config), uuid=uuid)
    form = TurismoFotoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        require(request.user, 'TURISMO_FOTO_CADASTRAR')
        if form.is_valid():
            foto = form.save(commit=False)
            foto.local = local
            foto.usuario_criador = foto.usuario_atualizador = request.user
            foto.save()
            messages.success(request, 'Foto adicionada.')
            return redirect('painel:turismo_local_fotos', uuid=uuid)
    return render(request, 'painel/turismo/midias.html', {
        'objeto': local, 'form': form, 'itens': local.fotos.filter(ativo=True),
        'titulo': 'Fotos do local', 'entidade': 'locais',
    })


@login_required
def local_imagem_editar(request, uuid, imagem_uuid):
    local = _local_wizard(request, uuid)
    foto = get_object_or_404(local.fotos.filter(ativo=True), uuid=imagem_uuid)
    if foto.usuario_criador_id == request.user.pk:
        require(request.user, 'TURISMO_FOTO_EDITAR_PROPRIAS')
    else:
        require(request.user, 'TURISMO_FOTO_MODERAR')
    form = TurismoFotoForm(request.POST or None, request.FILES or None, instance=foto)
    if request.method == 'POST' and form.is_valid():
        foto = form.save(commit=False)
        foto.usuario_atualizador = request.user
        foto.save()
        if foto.principal:
            local.fotos.exclude(pk=foto.pk).update(principal=False)
            local.imagem_principal = foto.imagem
            local.imagem_texto_alternativo = foto.texto_alternativo
            local.imagem_credito = foto.credito
            local.imagem_legenda = foto.legenda
            local.usuario_atualizador = request.user
            local.save(update_fields=[
                'imagem_principal', 'imagem_texto_alternativo', 'imagem_credito',
                'imagem_legenda', 'usuario_atualizador', 'atualizado_em',
            ])
            processar_imagem_principal(local)
        messages.success(request, 'Imagem atualizada.')
        return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=6)
    return render(request, 'painel/turismo/item_form.html', {
        'form': form, 'local': local, 'titulo': 'Editar imagem',
    })


@login_required
def local_imagem_remover(request, uuid, imagem_uuid):
    local = _local_wizard(request, uuid)
    foto = get_object_or_404(local.fotos.filter(ativo=True), uuid=imagem_uuid)
    if foto.usuario_criador_id == request.user.pk:
        require(request.user, 'TURISMO_FOTO_EXCLUIR_PROPRIAS')
    else:
        require(request.user, 'TURISMO_FOTO_MODERAR')
    if request.method != 'POST':
        raise PermissionDenied
    foto.ativo = False
    foto.usuario_atualizador = request.user
    foto.save(update_fields=['ativo', 'usuario_atualizador', 'atualizado_em'])
    messages.success(request, 'Imagem removida da galeria.')
    return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=6)


@login_required
def local_item_remover(request, uuid, tipo, item_uuid):
    if request.method != 'POST':
        raise PermissionDenied
    local = _local_wizard(request, uuid)
    relations = {
        'video': (local.videos, 'TURISMO_VIDEO_EXCLUIR_PROPRIOS'),
        'playlist': (local.playlists, 'TURISMO_PLAYLIST_EDITAR_PROPRIAS'),
        'contato': (local.contatos, 'TURISMO_LOCAL_EDITAR_PROPRIOS'),
        'rede': (local.redes_sociais_itens, 'TURISMO_LOCAL_EDITAR_PROPRIOS'),
    }
    if tipo not in relations:
        raise Http404
    manager, permission = relations[tipo]
    item = get_object_or_404(manager.filter(ativo=True), uuid=item_uuid)
    if item.usuario_criador_id != request.user.pk:
        raise PermissionDenied
    require(request.user, permission)
    item.ativo = False
    item.usuario_atualizador = request.user
    item.save(update_fields=['ativo', 'usuario_atualizador', 'atualizado_em'])
    etapa = 7 if tipo in {'video', 'playlist'} else 8
    messages.success(request, 'Item removido.')
    return redirect('painel:turismo_local_etapa', uuid=uuid, etapa=etapa)


@login_required
def playlist_videos(request, uuid):
    config = ENTITY['playlists']
    playlist = get_object_or_404(_queryset(request.user, config), uuid=uuid)
    form = TurismoPlaylistVideoForm(request.POST or None, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.playlist = playlist
        item.save()
        messages.success(request, 'Vídeo adicionado à playlist.')
        return redirect('painel:turismo_playlist_videos', uuid=uuid)
    return render(request, 'painel/turismo/midias.html', {
        'objeto': playlist, 'form': form, 'itens': playlist.itens.select_related('video'),
        'titulo': 'Vídeos da playlist', 'entidade': 'playlists',
    })


@login_required
def local_relacionados(request, uuid, tipo):
    local = get_object_or_404(_queryset(request.user, ENTITY['locais']), uuid=uuid)
    if tipo not in {'videos', 'playlists'}:
        raise Http404
    config = ENTITY[tipo]
    return render(request, 'painel/turismo/lista.html', {
        'config': config, 'entidade': tipo,
        'objetos': getattr(local, tipo).filter(ativo=True).order_by('-atualizado_em'),
        'status_choices': TurismoStatus.choices,
        'pode_criar': _allowed(request.user, f"{config['prefix']}_CADASTRAR"),
    })


@login_required
def acao_status(request, entidade, uuid, status):
    if request.method != 'POST':
        raise PermissionDenied
    config = ENTITY.get(entidade)
    if not config:
        raise Http404
    obj = get_object_or_404(config['model'].all_objects.filter(ativo=True), uuid=uuid)
    if not pode_editar(request.user, obj, config['own'], config['all']) and not (
        _allowed(request.user, f"{config['prefix']}_MODERAR") or
        _allowed(request.user, f"{config['prefix']}_PUBLICAR")
    ):
        raise PermissionDenied
    try:
        if isinstance(obj, GuiaTuristico) and status == TurismoStatus.PUBLICADO:
            require(request.user, 'TURISMO_GUIA_VALIDAR')
        alterar_status(obj, request.user, status)
        if isinstance(obj, GuiaTuristico) and status == TurismoStatus.PUBLICADO:
            obj.verificado = True
            obj.save(update_fields=['verificado', 'atualizado_em'])
        messages.success(request, 'Status atualizado.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:turismo_entidade_detalhe', entidade=entidade, uuid=uuid)


def turismo_home(request):
    locais = LocalTuristico.objects.filter(
        status=TurismoStatus.PUBLICADO,
    ).order_by('-destaque_home', '-publicado_em')
    return render(request, 'publico/turismo/home.html', {
        'locais': locais[:12],
        'guias': GuiaTuristico.objects.filter(status=TurismoStatus.PUBLICADO, verificado=True)[:6],
        'empresas': EmpresaTuristica.objects.filter(status=TurismoStatus.PUBLICADO).select_related('empresa')[:6],
        'roteiros': RoteiroTuristico.objects.filter(status=TurismoStatus.PUBLICADO)[:6],
        'experiencias': ExperienciaTuristica.objects.filter(status=TurismoStatus.PUBLICADO)[:6],
        'videos': TurismoVideo.objects.filter(status=TurismoStatus.PUBLICADO)[:6],
        'playlists': TurismoPlaylist.objects.filter(status=TurismoStatus.PUBLICADO)[:6],
    })


def locais_publicos(request):
    locais = LocalTuristico.objects.filter(
        status=TurismoStatus.PUBLICADO,
    ).order_by('-destaque_home', 'nome')
    return render(request, 'publico/turismo/locais.html', {'locais': locais})


def local_publico(request, slug):
    local = get_object_or_404(
        LocalTuristico.objects.prefetch_related(
            Prefetch('fotos', queryset=TurismoFoto.objects.filter(status=TurismoStatus.PUBLICADO)),
            Prefetch('videos', queryset=TurismoVideo.objects.filter(status=TurismoStatus.PUBLICADO)),
            Prefetch('playlists', queryset=TurismoPlaylist.objects.filter(status=TurismoStatus.PUBLICADO)),
            Prefetch('contatos', queryset=ContatoTurismo.objects.filter(status=TurismoStatus.PUBLICADO, publico=True)),
            Prefetch('redes_sociais_itens', queryset=RedeSocialTurismo.objects.filter(status=TurismoStatus.PUBLICADO, publico=True)),
        ), slug=slug, status=TurismoStatus.PUBLICADO,
    )
    map_url = ''
    if local.visibilidade_localizacao == 'PUBLICA' and local.latitude is not None and local.longitude is not None:
        map_url = MapService().public_url(local.latitude, local.longitude, local.nome)
    return render(request, 'publico/turismo/local.html', {'local': local, 'map_url': map_url, 'share_object': local, 'share_type': 'turismo'})


def guias_publicos(request):
    return render(request, 'publico/turismo/guias.html', {
        'guias': GuiaTuristico.objects.filter(status=TurismoStatus.PUBLICADO, verificado=True),
    })


def guia_publico(request, slug):
    guia = get_object_or_404(GuiaTuristico.objects, slug=slug, status=TurismoStatus.PUBLICADO, verificado=True)
    return render(request, 'publico/turismo/guia.html', {'guia': guia})


def roteiros_publicos(request):
    return render(request, 'publico/turismo/roteiros.html', {
        'roteiros': RoteiroTuristico.objects.filter(status=TurismoStatus.PUBLICADO),
    })


def roteiro_publico(request, slug):
    roteiro = get_object_or_404(
        RoteiroTuristico.objects.prefetch_related('locais', 'guias'),
        slug=slug, status=TurismoStatus.PUBLICADO,
    )
    return render(request, 'publico/turismo/roteiro.html', {'roteiro': roteiro})
