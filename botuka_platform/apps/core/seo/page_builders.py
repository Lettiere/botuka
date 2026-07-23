from django.conf import settings
from django.urls import reverse

from .builders import breadcrumb, build_seo
from .schemas import compact, text
from .utils import image_url, safe_absolute_url


def home_seo(request):
    return build_seo(
        request,
        title='BOTUKA — Empresas, serviços, eventos e notícias de Botucatu',
        description=settings.SITE_DEFAULT_DESCRIPTION,
        image_alt='BOTUKA — Sua cidade em um só lugar',
        page_type='WebPage',
    )


def listing_seo(request, title, description, *, robots=None):
    filtered = any(key != 'page' for key in request.GET)
    return build_seo(
        request,
        title=title,
        description=description,
        robots=robots or ('noindex,follow' if filtered else 'index,follow'),
        breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, title.split('|')[0].strip(), request.path)],
    )


def empresa_seo(request, empresa):
    title = f'{empresa.nome_fantasia} em {empresa.cidade} | BOTUKA'
    description = empresa.descricao_curta or empresa.descricao_completa
    image = empresa.imagem_capa or empresa.logo
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
    image = next((item.imagem for item in servico.imagens.all() if item.principal), None)
    if not image:
        image = next((item.imagem for item in servico.imagens.all()), None)
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


def artigo_seo(request, artigo):
    image = artigo.imagem_social or artigo.imagem_capa
    url = safe_absolute_url(request, request.path)
    author = artigo.autor.get_full_name() or 'Equipe BOTUKA'
    schema = compact({'@type': 'NewsArticle', '@id': f'{url}#article', 'headline': artigo.titulo,
                      'description': text(artigo.resumo or artigo.subtitulo or artigo.conteudo),
                      'image': [image_url(request, image)], 'datePublished': artigo.publicado_em.isoformat() if artigo.publicado_em else None,
                      'dateModified': artigo.atualizado_em.isoformat(), 'author': {'@type': 'Person', 'name': author},
                      'publisher': {'@id': f'{settings.SITE_URL.rstrip("/")}/#organization'}, 'mainEntityOfPage': url})
    return build_seo(request, title=artigo.titulo_seo or f'{artigo.titulo} | BOTUKA',
                     description=artigo.descricao_seo or artigo.resumo or artigo.subtitulo or artigo.conteudo,
                     image=image, image_alt=artigo.titulo, content_type='article', published_time=artigo.publicado_em,
                     modified_time=artigo.atualizado_em, author=author, section=artigo.categoria.nome,
                     tags=[artigo.categoria.nome],
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Notícias', reverse('news_public:home')), breadcrumb(request, artigo.categoria.nome, reverse('news_public:categoria', args=[artigo.categoria.slug])), breadcrumb(request, artigo.titulo, request.path)], schemas=[schema])


def vaga_seo(request, vaga):
    url = safe_absolute_url(request, request.path)
    schema = compact({'@type': 'JobPosting', '@id': f'{url}#job', 'title': vaga.titulo,
                      'description': text(vaga.descricao, 5000),
                      'datePosted': vaga.publicado_em.isoformat() if vaga.publicado_em else None,
                      'validThrough': vaga.encerramento.isoformat() if vaga.encerramento else None,
                      'employmentType': vaga.tipo_contrato,
                      'hiringOrganization': {'@type': 'Organization', 'name': vaga.empresa.nome_fantasia,
                                             'sameAs': safe_absolute_url(request, reverse('publico:empresa', args=[vaga.empresa.slug]))},
                      'jobLocation': {'@type': 'Place', 'address': {'@type': 'PostalAddress', 'addressLocality': vaga.cidade, 'addressRegion': vaga.estado, 'addressCountry': 'BR'}}})
    return build_seo(request, title=f'{vaga.titulo} em {vaga.cidade} | BOTUKA', description=vaga.descricao,
                     image=vaga.empresa.logo or vaga.empresa.imagem_capa,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'Vagas', reverse('recruitment_public:vagas')), breadcrumb(request, vaga.titulo, request.path)],
                     schemas=[schema], published_time=vaga.publicado_em, modified_time=vaga.atualizado_em)


def media_seo(request, obj, *, kind='programa'):
    title = getattr(obj, 'titulo', None) or getattr(obj, 'nome', 'YTv Botuka')
    description = getattr(obj, 'descricao', '')
    image = getattr(obj, 'thumbnail', None) or getattr(obj, 'imagem', None)
    schemas = []
    if kind == 'episodio' and getattr(obj, 'embed_url', ''):
        schemas.append(compact({'@type': 'VideoObject', 'name': title, 'description': text(description),
                                'thumbnailUrl': [image_url(request, image)],
                                'uploadDate': obj.publicado_em.isoformat() if obj.publicado_em else None,
                                'embedUrl': obj.embed_url, 'duration': str(obj.duracao) if obj.duracao else None}))
    return build_seo(request, title=f'{title} | YTv Botuka', description=description or 'Conteúdo audiovisual local da YTv Botuka.', image=image,
                     breadcrumbs=[breadcrumb(request, 'Início', reverse('home')), breadcrumb(request, 'YTv Botuka', reverse('media_public:home')), breadcrumb(request, title, request.path)], schemas=schemas,
                     published_time=getattr(obj, 'publicado_em', None), modified_time=getattr(obj, 'atualizado_em', None))


def government_seo(request, obj, *, kind='acao'):
    title = obj.titulo if kind == 'acao' else obj.nome
    description = (obj.resumo or obj.descricao) if kind == 'acao' else obj.descricao
    image = obj.imagem if kind == 'acao' else obj.logotipo
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
    image = getattr(obj, 'imagem', None) or getattr(obj, 'foto', None)
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
