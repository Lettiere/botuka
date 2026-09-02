from types import SimpleNamespace
from django.conf import settings
from django.urls import reverse
from django.templatetags.static import static

from .builders import breadcrumb, build_seo
from .schemas import compact, text
from .utils import first_value, image_url, iso_duration, safe_absolute_url, youtube_thumbnail


def home_seo(request):
    return build_seo(
        request,
        title='BOTUKA — Empresas, serviços, eventos e notícias de Botucatu',
        description=settings.SITE_DEFAULT_DESCRIPTION,
        image_alt='BOTUKA — Sua cidade em um só lugar',
        page_type='WebPage',
    )



def curriculo_seo(request, curriculo):
    usuario = curriculo.usuario

    nome = (
        usuario.nome_exibicao
        or usuario.get_full_name()
        or usuario.get_username()
    )

    titulo_profissional = (
        curriculo.titulo_profissional
        or curriculo.area_profissional
        or 'Perfil profissional'
    )

    title = f'{nome} — {titulo_profissional} | BOTUKA'

    description = text(
        curriculo.resumo
        or curriculo.objetivo_profissional
        or f'Currículo profissional de {nome} no BOTUKA.'
    )

    foto = (
        usuario.foto
        if usuario.foto
        else SimpleNamespace(
            url=static('img/default/curriculo-social-default.png')
        )
    )
    url = safe_absolute_url(request, request.path)

    endereco = compact({
        '@type': 'PostalAddress',
        'addressLocality': curriculo.cidade or None,
        'addressRegion': curriculo.estado or None,
        'addressCountry': 'BR',
    })

    same_as = [
        item for item in (
            curriculo.linkedin,
            curriculo.github,
            curriculo.portfolio,
            curriculo.site_profissional,
        )
        if item
    ]

    habilidades = [
        item.nome
        for item in curriculo.habilidades.filter(
            ativo=True,
            excluido_em__isnull=True,
        )[:30]
    ]

    schema = compact({
        '@type': 'Person',
        '@id': f'{url}#person',
        'name': nome,
        'jobTitle': titulo_profissional,
        'description': description,
        'url': url,
        'image': image_url(request, foto),
        'address': endereco,
        'sameAs': same_as or None,
        'knowsAbout': habilidades or None,
    })

    return build_seo(
        request,
        title=title,
        description=description,
        image=foto,
        image_alt=f'Foto profissional de {nome}',
        robots='noindex,follow,max-image-preview:large',
        breadcrumbs=[
            breadcrumb(request, 'Início', reverse('home')),
            breadcrumb(request, 'Currículo profissional', request.path),
        ],
        schemas=[schema],
        modified_time=curriculo.atualizado_em,
    )



def listing_seo(request, title, description, *, robots=None):
    filtered = any(key != 'page' for key in request.GET)
    return build_seo(
        request,
        title=title,
        description=description,
        robots=robots or ('noindex,follow' if filtered else 'index,follow,max-image-preview:large'),
        breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, title.split('|')[0].strip(), request.path)],
    )


def empresa_seo(request, empresa):
    title = f'{empresa.nome_fantasia} em {empresa.cidade} | BOTUKA'
    description = empresa.descricao_curta or empresa.descricao_completa
    image = [getattr(empresa, 'imagem_social', None), empresa.imagem_capa, empresa.logo]
    url = safe_absolute_url(request, request.path)
    schema = compact({
        '@type': 'LocalBusiness',
        '@id': f'{url}#business',
        'name': empresa.nome_fantasia,
        'description': text(description),
        'url': url,
        'image': image_url(request, image),
        'areaServed': {'@type': 'City', 'name': str(empresa.cidade)},
    })
    return build_seo(request, title=title, description=description, image=image,
                     image_alt=f'{empresa.nome_fantasia} em {empresa.cidade}',
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Empresas', reverse('publico:empresas')), breadcrumb(request, empresa.nome_fantasia, request.path)],
                     schemas=[schema], modified_time=empresa.atualizado_em)


def servico_seo(request, servico):
    service_images = list(servico.imagens.all())
    image = [
        getattr(servico, 'imagem_social', None),
        next((item.imagem for item in service_images if item.principal), None),
        *(item.imagem for item in service_images),
    ]
    url = safe_absolute_url(request, request.path)
    provider = servico.empresa.nome_fantasia if servico.empresa_id else 'Prestador autônomo'
    schema = compact({'@type': 'Service', '@id': f'{url}#service', 'name': servico.titulo,
                      'description': text(servico.descricao_curta or servico.descricao_completa),
                      'url': url, 'image': image_url(request, image),
                      'provider': {'@type': 'Organization' if servico.empresa_id else 'Person', 'name': provider},
                      'serviceType': str(servico.tipo_servico)})
    return build_seo(request, title=f'{servico.titulo} em Botucatu | BOTUKA',
                     description=servico.descricao_curta or servico.descricao_completa, image=image,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Serviços', reverse('publico:servicos')), breadcrumb(request, servico.titulo, request.path)],
                     schemas=[schema], published_time=servico.publicado_em, modified_time=servico.atualizado_em)


def product_seo(request, produto):
    image_item = produto.imagem_principal
    image = [produto.imagem_social, image_item.imagem if image_item else None]
    url = safe_absolute_url(request, request.path)
    seller = (
        produto.empresa_proprietaria.nome_fantasia or produto.empresa_proprietaria.razao_social
        if produto.empresa_proprietaria_id else produto.proprietario.get_full_name()
    )
    offer = None
    if produto.preco is not None and not produto.preco_sob_consulta:
        offer = compact({
            '@type': 'Offer', 'priceCurrency': produto.moeda,
            'price': str(produto.preco_promocional or produto.preco),
            'availability': {
                'DISPONIVEL': 'https://schema.org/InStock',
                'SOB_ENCOMENDA': 'https://schema.org/PreOrder',
                'ESGOTADO': 'https://schema.org/OutOfStock',
                'INDISPONIVEL': 'https://schema.org/Discontinued',
            }.get(produto.disponibilidade),
            'url': url,
        })
    schema = compact({
        '@type': 'Product', '@id': f'{url}#product', 'name': produto.nome,
        'description': text(produto.descricao_seo or produto.descricao_curta or produto.descricao_completa),
        'url': url, 'image': [image_url(request, image)], 'sku': produto.sku or None,
        'brand': {'@type': 'Brand', 'name': produto.marca} if produto.marca else None,
        'offers': offer,
        'seller': {'@type': 'Organization' if produto.empresa_proprietaria_id else 'Person', 'name': seller or 'BOTUKA'},
    })
    video_schemas = [
        compact({
            '@type': 'VideoObject',
            'name': video.titulo or produto.nome,
            'description': produto.descricao_curta,
            'embedUrl': video.embed_url,
            'contentUrl': video.url,
            'uploadDate': video.criado_em.isoformat() if video.criado_em else None,
        })
        for video in produto.videos.all()[:8]
    ]
    return build_seo(
        request, title=produto.titulo_seo or f'{produto.nome} | Botuka',
        description=produto.descricao_seo or produto.descricao_curta or produto.descricao_completa,
        image=image, image_alt=(image_item.texto_alternativo if image_item else produto.nome),
        breadcrumbs=[breadcrumb(request, 'Início', reverse('home')),
                     breadcrumb(request, 'Produtos', request.path),
                     breadcrumb(request, produto.nome, request.path)],
        schemas=[schema, *video_schemas], published_time=produto.publicado_em, modified_time=produto.atualizado_em,
    )


def artigo_seo(request, artigo):
    relacionadas = artigo.imagens.filter(
        ativo=True, excluido_em__isnull=True,
    ).order_by('-capa', 'ordem', 'id')
    image = [
        artigo.imagem_social,
        artigo.imagem_capa,
        *(
            first_value(relacionada.arquivo, relacionada.url_externa)
            for relacionada in relacionadas
        ),
    ]
    url = safe_absolute_url(request, request.path)
    author = (
        artigo.autor_editorial.nome
        if getattr(artigo, 'autor_editorial_id', None)
        else artigo.autor.get_full_name() or 'Equipe BOTUKA'
    )
    schema_type = 'NewsArticle' if getattr(artigo, 'tipo_editorial', 'NOTICIA') == 'NOTICIA' else 'Article'
    schema = compact({'@type': schema_type, '@id': f'{url}#article', 'headline': artigo.titulo,
                      'description': text(artigo.resumo or artigo.subtitulo or artigo.conteudo),
                      'image': [image_url(request, image)], 'datePublished': artigo.publicado_em.isoformat() if artigo.publicado_em else None,
                      'dateModified': artigo.atualizado_em.isoformat() if artigo.atualizado_em else None, 'author': {'@type': 'Person', 'name': author},
                      'publisher': {'@id': f'{safe_absolute_url(request, "/").rstrip("/")}/#organization'}, 'mainEntityOfPage': url,
                      'articleSection': artigo.categoria.nome,
                      'keywords': [tag.nome for tag in artigo.tags.all()] if hasattr(artigo, 'tags') else None})
    return build_seo(request, title=artigo.titulo_seo or f'{artigo.titulo} | BOTUKA',
                     description=artigo.descricao_seo or artigo.resumo or artigo.subtitulo or artigo.conteudo,
                     image=image, image_alt=artigo.texto_alternativo_imagem or artigo.titulo, content_type='article', published_time=artigo.publicado_em,
                     modified_time=artigo.atualizado_em, author=author, section=artigo.categoria.nome,
                     tags=[artigo.categoria.nome],
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Notícias', reverse('news_public:home')), breadcrumb(request, artigo.categoria.nome, reverse('news_public:categoria', args=[artigo.categoria.slug])), breadcrumb(request, artigo.titulo, request.path)], schemas=[schema])


def vaga_seo(request, vaga):
    contratante = vaga.responsavel_publico
    url = safe_absolute_url(request, request.path)
    contratante_url = (
        safe_absolute_url(request, reverse('publico:empresa', args=[vaga.empresa.slug]))
        if vaga.empresa_id else None
    )
    imagem = (
        [getattr(vaga, 'imagem_social', None), vaga.empresa.imagem_capa, vaga.empresa.logo]
        if vaga.empresa_id else [getattr(vaga, 'imagem_social', None)]
    )
    schema = compact({'@type': 'JobPosting', '@id': f'{url}#job', 'title': vaga.titulo,
                      'description': text(vaga.descricao, 5000),
                      'datePosted': vaga.publicado_em.isoformat() if vaga.publicado_em else None,
                      'validThrough': vaga.encerramento.isoformat() if vaga.encerramento else None,
                      'employmentType': vaga.tipo_contrato,
        'hiringOrganization': {'@type': 'Organization', 'name': contratante,
                                             'sameAs': contratante_url},
                      'jobLocation': {'@type': 'Place', 'address': {'@type': 'PostalAddress', 'addressLocality': vaga.cidade, 'addressRegion': vaga.estado, 'addressCountry': 'BR'}}})
    return build_seo(request, title=f'{vaga.titulo} em {vaga.cidade} | BOTUKA', description=vaga.descricao,
                     image=imagem,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Vagas', reverse('recruitment_public:vagas')), breadcrumb(request, vaga.titulo, request.path)],
                     schemas=[schema], published_time=vaga.publicado_em, modified_time=vaga.atualizado_em)


def media_seo(request, obj, *, kind='programa'):
    title = getattr(obj, 'titulo_seo', None) or getattr(obj, 'titulo', None) or getattr(obj, 'nome', 'YoBotuka')
    description = getattr(obj, 'descricao_seo', None) or getattr(obj, 'descricao_curta', None) or getattr(obj, 'descricao', '')
    youtube_source = getattr(obj, 'video_id', '') or getattr(obj, 'youtube_url', '') or getattr(obj, 'url_ao_vivo', '')
    image = [
        getattr(obj, 'imagem_compartilhamento', None),
        getattr(obj, 'imagem_social', None),
        getattr(obj, 'thumbnail', None),
        getattr(obj, 'imagem', None),
        youtube_thumbnail(youtube_source),
        getattr(getattr(obj, 'programa', None), 'imagem', None),
        getattr(getattr(obj, 'canal', None), 'capa', None),
        getattr(getattr(obj, 'canal', None), 'logotipo', None),
    ]
    schemas = []
    if kind in {'episodio', 'video'} and getattr(obj, 'embed_url', ''):
        published_at = (
            getattr(obj, 'publicado_em', None)
            or getattr(obj, 'inicio', None)
            or getattr(obj, 'data_prevista', None)
        )
        schemas.append(compact({'@type': 'VideoObject', 'name': title, 'description': text(description),
                                'thumbnailUrl': [image_url(request, image)],
                                'uploadDate': published_at.isoformat() if published_at else None,
                                'embedUrl': obj.embed_url,
                                'duration': iso_duration(getattr(obj, 'duracao', None)),
                                'contentUrl': getattr(obj, 'youtube_url', None),
                                'publisher': {'@id': f'{safe_absolute_url(request, "/").rstrip("/")}/#organization'}}))
    is_video = kind in {'episodio', 'video'}
    return build_seo(request, title=f'{title} | YoBotuka', description=description or 'Conteúdo audiovisual local do YoBotuka.', image=image,
                     content_type='video.other' if is_video else 'website',
                     video_url=getattr(obj, 'embed_url', '') if is_video else None,
                     video_mime_type='text/html' if is_video and getattr(obj, 'embed_url', '') else None,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'YoBotuka', reverse('media_public:yubotuka_home')), breadcrumb(request, title, request.path)], schemas=schemas,
                     published_time=getattr(obj, 'publicado_em', None), modified_time=getattr(obj, 'atualizado_em', None))


def tourism_seo(request, obj, *, kind='local'):
    title = getattr(obj, 'nome', None) or getattr(obj, 'titulo', None) or str(obj)
    description = first_value(
        getattr(obj, 'descricao_seo', None), getattr(obj, 'descricao_curta', None),
        getattr(obj, 'resumo', None), getattr(obj, 'apresentacao', None),
        getattr(obj, 'descricao_completa', None), getattr(obj, 'descricao', None),
    )
    gallery_image = None
    try:
        photo = obj.fotos.all().order_by('-principal', 'ordem', 'id').first()
        gallery_image = photo.imagem if photo else None
    except (AttributeError, TypeError):
        pass
    image = [
        getattr(obj, 'imagem_social', None),
        getattr(obj, 'imagem_principal', None), getattr(obj, 'capa', None),
        gallery_image, getattr(getattr(obj, 'categoria', None), 'imagem', None),
        getattr(obj, 'foto', None),
    ]
    url = safe_absolute_url(request, request.path)
    schema_type = 'TouristAttraction' if kind == 'local' else 'WebPage'
    localizacao_publica = (
        kind == 'local'
        and getattr(obj, 'visibilidade_localizacao', '') == 'PUBLICA'
    )
    schema = compact({
        '@type': schema_type, '@id': f'{url}#tourism', 'name': title,
        'description': text(description), 'url': url, 'image': image_url(request, image),
        'telephone': getattr(obj, 'telefone_publico', None),
        'address': compact({'@type': 'PostalAddress', 'streetAddress': ' '.join(filter(None, [getattr(obj, 'logradouro', ''), getattr(obj, 'numero', '')])),
                            'addressLocality': getattr(obj, 'cidade', None), 'addressRegion': getattr(obj, 'estado', None), 'postalCode': getattr(obj, 'cep', None), 'addressCountry': 'BR'}) if localizacao_publica else None,
        'geo': compact({'@type': 'GeoCoordinates', 'latitude': str(obj.latitude), 'longitude': str(obj.longitude)}) if localizacao_publica and getattr(obj, 'latitude', None) is not None and getattr(obj, 'longitude', None) is not None else None,
    })
    return build_seo(request, title=f'{title} | Botuka', description=description, image=image,
                     image_alt=getattr(obj, 'imagem_texto_alternativo', None) or title,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Turismo', reverse('tourism_public:home')), breadcrumb(request, title, request.path)],
                     schemas=[schema], published_time=getattr(obj, 'publicado_em', None), modified_time=getattr(obj, 'atualizado_em', None))


def event_seo(request, evento):
    url = safe_absolute_url(request, request.path)
    image = [getattr(evento, 'imagem_social', None), getattr(evento, 'imagem_principal', None)]
    location = compact({
        '@type': 'Place', 'name': evento.local,
        'address': evento.endereco or None,
    })
    schema = compact({
        '@type': 'Event', '@id': f'{url}#event', 'name': evento.titulo,
        'description': text(evento.resumo or evento.descricao), 'url': url,
        'image': [image_url(request, image)], 'startDate': evento.inicio.isoformat(),
        'endDate': evento.fim.isoformat() if evento.fim else None,
        'eventStatus': 'https://schema.org/EventCancelled' if evento.status == 'CANCELADO' else 'https://schema.org/EventScheduled',
        'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
        'location': location,
        'organizer': {'@type': 'Organization', 'name': evento.organizador} if evento.organizador else None,
    })
    return build_seo(
        request, title=f'{evento.titulo} | Botuka', description=evento.resumo or evento.descricao,
        image=image, image_alt=evento.imagem_alt or evento.titulo,
        breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Eventos', reverse('events:lista')), breadcrumb(request, evento.titulo, request.path)],
        schemas=[schema], published_time=evento.publicado_em, modified_time=evento.atualizado_em,
    )


def government_seo(request, obj, *, kind='acao'):
    title = obj.titulo if kind == 'acao' else obj.nome
    description = (obj.resumo or obj.descricao) if kind == 'acao' else obj.descricao
    image = [
        getattr(obj, 'imagem_social', None),
        obj.imagem if kind == 'acao' else obj.logotipo,
    ]
    schema_type = 'Event' if kind == 'acao' and obj.tipo == obj.Tipo.EVENTO else ('GovernmentOffice' if kind == 'orgao' else 'GovernmentOrganization')
    schema = compact({'@type': schema_type, 'name': title, 'description': text(description), 'url': safe_absolute_url(request, request.path), 'image': image_url(request, image),
                      'startDate': obj.inicio_previsto.isoformat() if kind == 'acao' and obj.inicio_previsto else None,
                      'endDate': obj.conclusao_prevista.isoformat() if kind == 'acao' and obj.conclusao_prevista else None,
                      'location': {'@type': 'Place', 'name': obj.local or obj.cidade} if kind == 'acao' and (obj.local or obj.cidade) else None})
    return build_seo(request, title=f'{title} | BOTUKA', description=description, image=image,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Prefeitura', reverse('government_public:home')), breadcrumb(request, title, request.path)], schemas=[schema],
                     published_time=getattr(obj, 'publicado_em', None), modified_time=obj.atualizado_em)


def sports_seo(request, obj, *, kind):
    title = getattr(obj, 'nome', None) or getattr(obj, 'nome_publico', None) or str(obj)
    description = getattr(obj, 'descricao', None) or getattr(obj, 'biografia', None) or f'Informações sobre {title} no esporte local.'
    image = [
        getattr(obj, 'imagem_social', None),
        getattr(obj, 'imagem', None),
        getattr(obj, 'foto', None),
    ]
    schemas = []
    if kind == 'campeonato':
        schemas.append(compact({'@type': 'SportsEvent', 'name': title, 'description': text(description),
                                'startDate': obj.data_inicial.isoformat(), 'endDate': obj.data_final.isoformat() if obj.data_final else None,
                                'location': {'@type': 'Place', 'name': obj.localidade} if obj.localidade else None,
                                'image': image_url(request, image)}))
    elif kind == 'atleta':
        schemas.append(compact({'@type': 'Person', 'name': obj.nome_publico, 'description': text(obj.biografia), 'image': image_url(request, image)}))
    return build_seo(request, title=f'{title} | Esportes BOTUKA', description=description, image=image,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Esportes', reverse('sports_public:home')), breadcrumb(request, title, request.path)], schemas=schemas,
                     modified_time=getattr(obj, 'atualizado_em', None))
