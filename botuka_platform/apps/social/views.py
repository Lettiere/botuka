from django.contrib import messages
from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import get_urlconf, reverse, set_urlconf
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from urllib.parse import urlparse

from apps.organizations.models import Empresa

from .forms import SocialPostForm, SocialProfileForm, SocialStoryForm
from .models import SocialConversation, SocialConversationRequest, SocialFollowRequest, SocialMessage, SocialNotification, SocialPost, SocialProfile, SocialStory, SocialStoryReaction
from .selectors import (
    comentarios_do_post, feed_para, posts_do_perfil, posts_salvos_por,
    solicitacoes_pendentes_para, solicitacoes_conversa_para, stories_ativos_para, story_visivel_para, conversas_para,
    contagem_seguidores_perfil, conteudo_publico_para_descoberta,
    empresas_seguidas_por, empresas_sugeridas_para, perfis_seguidos_por,
    perfis_sugeridos_para, mensagens_da_conversa, notificacoes_para, contadores_sociais,
)
from .services import (
    bloquear_perfil, comentar_post, compartilhar_conteudo, criar_post, criar_story,
    curtir_post, decidir_follow_request, descurtir_post,
    deixar_de_seguir_empresa, deixar_de_seguir_usuario, get_or_create_social_profile,
    decidir_solicitacao_conversa, enviar_mensagem, pode_ver_post, remover_post,
    remover_post_salvo, remover_story, salvar_post, solicitar_ou_enviar_conversa, sincronizar_perfil_publico,
    desbloquear_perfil,
    alternar_curtida_story, denunciar, insights_story, marcar_conversa_lida,
    marcar_notificacao_lida, marcar_todas_notificacoes_lidas, reagir_story,
    registrar_evento_social, registrar_visualizacao_story, seguir_empresa,
    seguir_usuario, usuario_segue_usuario,
)


def runtime_not_found(request, exception=None):
    return HttpResponse('Página não encontrada no BOTUKA Social.', status=404, content_type='text/plain; charset=utf-8')


def runtime_forbidden(request, exception=None):
    return HttpResponse('Acesso negado no BOTUKA Social.', status=403, content_type='text/plain; charset=utf-8')


def runtime_error(request):
    return HttpResponse('Erro interno no BOTUKA Social.', status=500, content_type='text/plain; charset=utf-8')


def _redirect(request, fallback):
    target = request.POST.get('next', '')
    allowed_hosts = {request.get_host(), urlparse(settings.BOTUKA_PLATFORM_BASE_URL).netloc, urlparse(settings.BOTUKA_SOCIAL_BASE_URL).netloc}
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts, request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def profile_public(request, slug):
    profile = get_object_or_404(SocialProfile.objects.select_related('usuario', 'usuario__cidade', 'usuario__estado'), slug=slug, ativo=True)
    private = profile.visibilidade == SocialProfile.Visibilidade.PRIVADO and (not request.user.is_authenticated or request.user.pk != profile.usuario_id)
    return render(request, 'social/profile.html', {
        'profile': profile,
        'private_profile': private,
        'is_owner': request.user.is_authenticated and request.user.pk == profile.usuario_id,
        'is_following': usuario_segue_usuario(request.user, profile),
        'followers_count': contagem_seguidores_perfil(profile),
        'following_count': profile.seguindo_relacoes.count(),
        'profile_posts': posts_do_perfil(profile, request.user) if not private else [],
    })


def _social_context(request, *, section='feed'):
    profile = get_or_create_social_profile(request.user) if request.user.is_authenticated else None
    people = perfis_sugeridos_para(request.user)
    companies = empresas_sugeridas_para(request.user)
    content = conteudo_publico_para_descoberta()
    return {
        'social_profile': profile, 'social_section': section,
        'suggested_people': people, 'suggested_companies': companies,
        'discovery_content': content,
        'feed_posts': feed_para(request.user),
        'active_stories': stories_ativos_para(request.user),
        'upcoming_events': [item for item in content if item['kind'] == 'eventos'][:3],
    }


def social_home(request):
    tab = request.GET.get('tab', 'feed')
    if tab not in {'feed', 'favorites', 'events'}:
        tab = 'feed'
    context = _social_context(request, section=tab)
    if request.user.is_authenticated:
        context['following_people_count'] = request.user.social_profile.seguindo_relacoes.count()
        context['following_companies_count'] = request.user.empresas_seguidas.count()
    else:
        context['following_people_count'] = context['following_companies_count'] = 0
    context['tab'] = tab
    return render(request, 'social/feed.html', context)


def explore(request):
    return render(request, 'social/explore.html', _social_context(request, section='explore'))


def people_directory(request):
    return render(request, 'social/directory.html', {
        **_social_context(request, section='people'), 'directory_type': 'people',
    })


def company_directory(request):
    return render(request, 'social/directory.html', {
        **_social_context(request, section='companies'), 'directory_type': 'companies',
    })


@login_required
@require_POST
def follow_profile(request, uuid):
    target = get_object_or_404(SocialProfile, uuid=uuid, ativo=True)
    try:
        _, created = seguir_usuario(request.user, target)
    except ValidationError as error:
        messages.error(request, error.message)
        return _redirect(request, target.get_absolute_url())
    if created:
        registrar_evento_social(request, 'follow_user', 'social_profile', target.uuid, 'profile_page')
    return _redirect(request, target.get_absolute_url())


@login_required
@require_POST
def unfollow_profile(request, uuid):
    target = get_object_or_404(SocialProfile, uuid=uuid, ativo=True)
    if deixar_de_seguir_usuario(request.user, target):
        registrar_evento_social(request, 'unfollow_user', 'social_profile', target.uuid, 'profile_page')
    return _redirect(request, target.get_absolute_url())


def _public_company(uuid):
    return get_object_or_404(Empresa, uuid=uuid, ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA, excluido_em__isnull=True)


@login_required
@require_POST
def follow_company(request, uuid):
    company = _public_company(uuid)
    _, created = seguir_empresa(request.user, company)
    if created:
        registrar_evento_social(request, 'follow_company', 'company', company.uuid, 'company_page')
    return _redirect(request, reverse('social:company_detail', args=[company.uuid]))


@login_required
@require_POST
def unfollow_company(request, uuid):
    company = _public_company(uuid)
    if deixar_de_seguir_empresa(request.user, company):
        registrar_evento_social(request, 'unfollow_company', 'company', company.uuid, 'company_page')
    return _redirect(request, reverse('social:company_detail', args=[company.uuid]))


@login_required
def following(request):
    profile = get_or_create_social_profile(request.user)
    return render(request, 'social/following.html', {
        **_social_context(request, section='following'), 'profile': profile,
        'people': perfis_seguidos_por(profile),
        'companies': empresas_seguidas_por(request.user),
    })


@login_required
def legacy_following(request):
    return redirect('social:following')


def redirect_to_social(request, remainder=''):
    suffix = f'{remainder}' if remainder else ''
    url = f"{settings.BOTUKA_SOCIAL_BASE_URL}/social/{suffix}"
    if request.META.get('QUERY_STRING'):
        url = f"{url}?{request.META['QUERY_STRING']}"
    return redirect(url)


def redirect_legacy_profile(request, slug):
    return redirect(f'{settings.BOTUKA_SOCIAL_BASE_URL}/social/@{slug}/', permanent=True)


def redirect_legacy_following(request):
    return redirect(f'{settings.BOTUKA_SOCIAL_BASE_URL}/social/seguindo/')


@login_required
def profile_edit(request):
    profile = get_or_create_social_profile(request.user)
    form = SocialProfileForm(request.POST or None, request.FILES or None, initial={
        'nome_exibicao': request.user.nome_exibicao or profile.nome_publico,
        'biografia': request.user.biografia,
        'quem_pode_solicitar_mensagem': profile.quem_pode_solicitar_mensagem,
        'quem_pode_responder_story': profile.quem_pode_responder_story,
        'permitir_reacoes': profile.permitir_reacoes,
        'confirmacao_leitura': profile.confirmacao_leitura,
    })
    if request.method == 'POST' and form.is_valid():
        sincronizar_perfil_publico(
            request.user, origem='social', nome_exibicao=form.cleaned_data['nome_exibicao'],
            biografia=form.cleaned_data['biografia'], avatar=form.cleaned_data.get('avatar'),
        )
        profile.refresh_from_db()
        profile.quem_pode_solicitar_mensagem = form.cleaned_data['quem_pode_solicitar_mensagem']
        profile.quem_pode_responder_story = form.cleaned_data['quem_pode_responder_story']
        profile.permitir_reacoes = form.cleaned_data['permitir_reacoes']
        profile.confirmacao_leitura = form.cleaned_data['confirmacao_leitura']
        profile.save(update_fields=[
            'quem_pode_solicitar_mensagem', 'quem_pode_responder_story',
            'permitir_reacoes', 'confirmacao_leitura', 'atualizado_em',
        ])
        messages.success(request, 'Perfil público atualizado.')
        return redirect(profile.get_absolute_url())
    return render(request, 'social/profile_edit.html', {**_social_context(request, section='profile'), 'form': form})


@login_required
def post_create(request):
    form = SocialPostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = criar_post(request.user, **form.cleaned_data)
        registrar_evento_social(request, 'social_post_create', 'social_post', post.uuid, 'social_create')
        return redirect(post)
    return render(request, 'social/post_form.html', {**_social_context(request, section='create'), 'form': form, 'kind': 'post'})


@login_required
def story_create(request):
    form = SocialStoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        criar_story(request.user, **form.cleaned_data)
        return redirect('social:home')
    return render(request, 'social/post_form.html', {**_social_context(request, section='create'), 'form': form, 'kind': 'story'})


def post_detail(request, uuid):
    post = get_object_or_404(SocialPost.objects.select_related('autor', 'autor__usuario', 'conteudo_tipo'), uuid=uuid, ativo=True)
    if not pode_ver_post(request.user, post):
        raise Http404
    return render(request, 'social/post_detail.html', {
        **_social_context(request, section='post'), 'post': post,
        'comments': comentarios_do_post(post),
        'liked': request.user.is_authenticated and post.curtidas.filter(usuario=request.user).exists(),
        'saved': request.user.is_authenticated and post.salvamentos.filter(usuario=request.user).exists(),
        'is_owner': request.user.is_authenticated and post.autor.usuario_id == request.user.pk,
    })


@login_required
@require_POST
def post_delete(request, uuid):
    post = get_object_or_404(SocialPost.objects.select_related('autor'), uuid=uuid, ativo=True)
    remover_post(request.user, post)
    return redirect('social:home')


def story_detail(request, uuid):
    story = story_visivel_para(request.user, uuid)
    if not story:
        raise Http404
    sequence = list(stories_ativos_para(request.user).values_list('uuid', flat=True))
    index = sequence.index(story.uuid)
    registrar_visualizacao_story(request.user, story)
    return render(request, 'social/story_detail.html', {
        **_social_context(request, section='story'), 'story': story,
        'previous_story': sequence[index - 1] if index else None,
        'next_story': sequence[index + 1] if index + 1 < len(sequence) else None,
        'is_owner': request.user.is_authenticated and story.autor.usuario_id == request.user.pk,
        'story_liked': request.user.is_authenticated and story.curtidas.filter(usuario=request.user).exists(),
        'story_reaction': story.reacoes.filter(usuario=request.user).first() if request.user.is_authenticated else None,
        'reaction_choices': SocialStoryReaction.Tipo.choices,
        'story_insights': insights_story(request.user, story) if request.user.is_authenticated and story.autor.usuario_id == request.user.pk else None,
    })


@login_required
@require_POST
def story_like_toggle(request, uuid):
    story = get_object_or_404(SocialStory, uuid=uuid, ativo=True)
    liked = alternar_curtida_story(request.user, story)
    return JsonResponse({'liked': liked, 'count': story.curtidas.count()})


@login_required
@require_POST
def story_react(request, uuid):
    story = get_object_or_404(SocialStory, uuid=uuid, ativo=True)
    reaction = reagir_story(request.user, story, request.POST.get('reaction'))
    return JsonResponse({'reaction': reaction.tipo if reaction else None, 'count': story.reacoes.count()})


@login_required
@require_POST
def story_delete(request, uuid):
    story = get_object_or_404(stories_ativos_para(request.user), uuid=uuid)
    remover_story(request.user, story)
    return redirect('social:home')


@login_required
@require_POST
def post_like(request, uuid):
    post = get_object_or_404(SocialPost, uuid=uuid, ativo=True)
    curtir_post(request.user, post)
    return _redirect(request, post.get_absolute_url())


@login_required
@require_POST
def post_unlike(request, uuid):
    post = get_object_or_404(SocialPost, uuid=uuid, ativo=True)
    descurtir_post(request.user, post)
    return _redirect(request, post.get_absolute_url())


@login_required
@require_POST
def post_comment(request, uuid):
    post = get_object_or_404(SocialPost, uuid=uuid, ativo=True)
    comentar_post(request.user, post, request.POST.get('texto'))
    return _redirect(request, post.get_absolute_url())


@login_required
@require_POST
def post_save(request, uuid):
    post = get_object_or_404(SocialPost, uuid=uuid, ativo=True)
    salvar_post(request.user, post)
    return _redirect(request, post.get_absolute_url())


@login_required
@require_POST
def post_unsave(request, uuid):
    post = get_object_or_404(SocialPost, uuid=uuid, ativo=True)
    remover_post_salvo(request.user, post)
    return _redirect(request, post.get_absolute_url())


@login_required
def saved_posts(request):
    return render(request, 'social/saved.html', {**_social_context(request, section='saved'), 'posts': posts_salvos_por(request.user)})


@login_required
def messages_inbox(request):
    return render(request, 'social/messages.html', {
        **_social_context(request, section='messages'),
        'conversations': conversas_para(request.user),
        'conversation_requests': solicitacoes_conversa_para(request.user),
    })


@login_required
@require_POST
def conversation_request_send(request):
    target = get_object_or_404(SocialProfile, uuid=request.POST.get('destinatario'), ativo=True)
    post = get_object_or_404(SocialPost, uuid=request.POST['post'], ativo=True) if request.POST.get('post') else None
    story = story_visivel_para(request.user, request.POST.get('story')) if request.POST.get('story') else None
    if request.POST.get('story') and not story:
        raise Http404
    solicitar_ou_enviar_conversa(request.user, target.usuario, texto=request.POST.get('texto', ''), post=post, story=story)
    messages.success(request, 'Mensagem enviada ou solicitação criada.')
    return _redirect(request, 'social:messages')


@login_required
@require_POST
def conversation_request_decide(request, uuid, decision):
    pedido = get_object_or_404(SocialConversationRequest, uuid=uuid, destinatario=request.user)
    decidir_solicitacao_conversa(request.user, pedido, decision == 'aceitar')
    return redirect('social:messages')


@login_required
def conversation_detail(request, uuid):
    conversation = get_object_or_404(SocialConversation.objects.prefetch_related('participantes__social_profile'), uuid=uuid, ativo=True, participantes=request.user)
    if request.method == 'POST':
        item = enviar_mensagem(request.user, conversation, texto=request.POST.get('texto', ''))
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'id': str(item.uuid), 'text': item.texto, 'created_at': item.criado_em.isoformat(), 'status': 'delivered'})
        return redirect('social:conversation_detail', uuid=uuid)
    marcar_conversa_lida(request.user, conversation)
    return render(request, 'social/conversation_detail.html', {**_social_context(request, section='messages'), 'conversation': conversation, 'conversation_messages': mensagens_da_conversa(conversation)})


@login_required
def notifications(request):
    category = request.GET.get('filter', 'all')
    items = notificacoes_para(request.user, somente_nao_lidas=category == 'unread')
    return render(request, 'social/notifications.html', {**_social_context(request, section='notifications'), 'notifications': items, 'notification_filter': category})


@login_required
@require_POST
def notification_read(request, uuid):
    item = get_object_or_404(SocialNotification, uuid=uuid, destinatario=request.user)
    marcar_notificacao_lida(request.user, item)
    return _redirect(request, 'social:notifications')


@login_required
@require_POST
def notifications_read_all(request):
    marcar_todas_notificacoes_lidas(request.user)
    return _redirect(request, 'social:notifications')


@login_required
def realtime_state(request):
    counters = contadores_sociais(request.user)
    since = request.GET.get('since')
    newest = notificacoes_para(request.user, desde=since, limite=10)
    return JsonResponse({'event': 'state.updated', 'counters': counters, 'notifications': [{'id': str(item.uuid), 'type': item.tipo, 'destination': item.destino, 'created_at': item.criado_em.isoformat()} for item in newest]})


@login_required
@require_POST
def report_content(request, target_type, uuid):
    models = {'profile': SocialProfile, 'post': SocialPost, 'story': SocialStory, 'message': SocialMessage}
    model = models.get(target_type)
    if not model:
        raise Http404
    target = get_object_or_404(model, uuid=uuid)
    denunciar(request.user, target, motivo=request.POST.get('motivo', ''), descricao=request.POST.get('descricao', ''))
    messages.success(request, 'Denúncia registrada para análise.')
    return _redirect(request, 'social:home')


def _official_spec(kind):
    from apps.core.search.registry import default_registry
    aliases = {'empresas': 'empresas', 'servicos': 'servicos', 'produtos': 'produtos', 'eventos': 'eventos', 'vagas': 'vagas', 'noticias': 'noticias', 'turismo': 'turismo', 'esportes': 'esportes', 'yubotuka': 'videos'}
    key = aliases.get(kind)
    return next((spec for spec in default_registry() if spec.key == key), None)


def _present_official(spec, obj):
    current = get_urlconf()
    try:
        set_urlconf('config.urls')
        return spec.presenter(obj)
    finally:
        set_urlconf(current)


def official_content_list(request, kind):
    spec = _official_spec(kind)
    if not spec:
        raise Http404
    items = [{'object': obj, **_present_official(spec, obj)} for obj in spec.queryset()[:40]]
    return render(request, 'social/official_list.html', {**_social_context(request, section=kind), 'kind': kind, 'label': spec.label, 'items': items})


def official_content_detail(request, kind, identifier):
    spec = _official_spec(kind)
    if not spec:
        raise Http404
    query = {'uuid': identifier}
    if not hasattr(spec.queryset().model, 'uuid'):
        query = {'slug': identifier}
    try:
        obj = spec.queryset().get(**query)
    except (ValueError, spec.queryset().model.DoesNotExist):
        obj = get_object_or_404(spec.queryset(), slug=identifier)
    return render(request, 'social/official_detail.html', {**_social_context(request, section=kind), 'kind': kind, 'item': _present_official(spec, obj), 'object': obj, 'label': spec.label})


@login_required
def follow_requests(request):
    return render(request, 'social/follow_requests.html', {**_social_context(request, section='following'), 'requests': solicitacoes_pendentes_para(request.user)})


@login_required
@require_POST
def follow_request_decide(request, uuid, decision):
    item = get_object_or_404(SocialFollowRequest, uuid=uuid)
    decidir_follow_request(request.user, item, decision == 'aprovar')
    return redirect('social:follow_requests')


@login_required
@require_POST
def profile_block(request, uuid):
    target = get_object_or_404(SocialProfile, uuid=uuid, ativo=True)
    bloquear_perfil(request.user, target)
    return redirect('social:home')


@login_required
@require_POST
def profile_unblock(request, uuid):
    target = get_object_or_404(SocialProfile, uuid=uuid, ativo=True)
    desbloquear_perfil(request.user, target)
    return redirect(target)


@login_required
@require_POST
def share_platform_content(request, app_label, model_name, uuid):
    allowed = {('recruitment', 'vaga'), ('events', 'evento'), ('services', 'servico'), ('products', 'produto'), ('news', 'artigo'), ('tourism', 'localturistico'), ('media', 'video'), ('sports', 'campeonato'), ('organizations', 'empresa')}
    if (app_label, model_name) not in allowed:
        raise Http404
    model = apps.get_model(app_label, model_name)
    obj = get_object_or_404(model, uuid=uuid)
    for field in ('ativo',):
        if hasattr(obj, field) and not getattr(obj, field):
            raise Http404
    if hasattr(obj, 'excluido_em') and obj.excluido_em:
        raise Http404
    post = compartilhar_conteudo(request.user, obj, legenda=request.POST.get('legenda', ''))
    return redirect(post)
