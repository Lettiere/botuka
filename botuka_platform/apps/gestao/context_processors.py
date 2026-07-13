"""Context processors globais do BOTUKA."""

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse


SOCIAL_CONFIG_KEYS = {
    'facebook': 'social.facebook_url',
    'instagram': 'social.instagram_url',
    'linkedin': 'social.linkedin_url',
    'youtube': 'social.youtube_url',
    'tiktok': 'social.tiktok_url',
}


def get_config_values(keys: dict[str, str]) -> dict[str, str]:
    """Busca configurações ativas sem quebrar páginas durante migrations."""

    try:
        from apps.core.models import ConfiguracaoSistema

        configs = ConfiguracaoSistema.objects.filter(chave__in=keys.values())
        values = {config.chave: config.valor for config in configs}
        return {name: values.get(key, '') for name, key in keys.items()}
    except Exception:
        return {name: '' for name in keys}


def public_urls(request):
    """Disponibiliza URLs públicas centralizadas para templates."""
    contatos_data = cache.get('botuka_contatos_topbar')

    if contatos_data is None:
        contatos_data = {
            'contatos': [],
            'redes': [],
            'telefone': None,
            'whatsapp': None,
            'email': None,
        }

        try:
            from apps.core.models import ContatoInstitucional

            contatos = list(
                ContatoInstitucional.objects.filter(ativo=True).order_by('ordem', 'nome')
            )
            tipos_rede = {
                ContatoInstitucional.Tipo.FACEBOOK,
                ContatoInstitucional.Tipo.INSTAGRAM,
                ContatoInstitucional.Tipo.LINKEDIN,
                ContatoInstitucional.Tipo.YOUTUBE,
                ContatoInstitucional.Tipo.TIKTOK,
                ContatoInstitucional.Tipo.X,
            }
            contatos_data['contatos'] = [
                contato for contato in contatos if contato.exibir_topbar and contato.tipo not in tipos_rede
            ]
            contatos_data['redes'] = [
                contato for contato in contatos if contato.exibir_topbar and contato.tipo in tipos_rede
            ]
            contatos_data['telefone'] = next(
                (contato for contato in contatos_data['contatos'] if contato.tipo == ContatoInstitucional.Tipo.TELEFONE),
                None,
            )
            contatos_data['whatsapp'] = next(
                (contato for contato in contatos_data['contatos'] if contato.tipo == ContatoInstitucional.Tipo.WHATSAPP),
                None,
            )
            contatos_data['email'] = next(
                (contato for contato in contatos_data['contatos'] if contato.tipo == ContatoInstitucional.Tipo.EMAIL),
                None,
            )
            cache.set('botuka_contatos_topbar', contatos_data, 300)
        except Exception:
            pass

    return {
        'PLATFORM_URL': settings.PLATFORM_URL,
        'SERVICES_URL': settings.SERVICES_URL,
        'PUBLIC_BASE_URL': settings.PUBLIC_BASE_URL,
        'SOCIAL_LINKS': get_config_values(SOCIAL_CONFIG_KEYS),
        'botuka_contatos': contatos_data['contatos'],
        'botuka_redes_sociais': contatos_data['redes'],
        'botuka_telefone': contatos_data['telefone'],
        'botuka_whatsapp': contatos_data['whatsapp'],
        'botuka_email': contatos_data['email'],
    }


def publicar_options(request):
    """Disponibiliza opções do botão publicar conforme permissões."""

    user = getattr(request, 'user', None)
    tem_permissao = getattr(user, 'tem_permissao', None)
    can = lambda code: bool(callable(tem_permissao) and tem_permissao(code))

    options = [
        ('Publicar serviço', 'bi-tools', 'painel:servicos_lista', 'servicos.criar'),
        ('Publicar produto', 'bi-bag-plus', 'painel:produtos_lista', 'produtos.criar'),
        ('Criar empresa', 'bi-buildings', 'painel:empresas_lista', 'empresas.criar'),
        ('Publicar vaga', 'bi-briefcase', 'painel:vagas_lista', 'vagas.criar'),
        ('Criar currículo', 'bi-file-earmark-person', 'painel:curriculo', 'curriculo.editar'),
        ('Criar evento', 'bi-calendar-plus', 'painel:eventos_lista', 'eventos.criar'),
        ('Publicar na rede social', 'bi-share', 'painel:rede_social', 'rede_social.acessar'),
    ]

    allowed_options = []
    for label, icon, url_name, permission in options:
        if can(permission):
            allowed_options.append(
                {
                    'label': label,
                    'icon': icon,
                    'url': reverse(url_name),
                    'permission': permission,
                }
            )

    return {'PUBLICAR_OPTIONS': allowed_options}
