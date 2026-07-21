# SEO técnico, indexação e mensuração — BOTUKA

## Arquitetura

A implementação está centralizada em `botuka_platform/apps/core/seo/`. Views públicas usam builders por segmento e enviam um único objeto `seo` ao template. O context processor fornece fallback global e marca automaticamente `/painel/`, `/gestao/`, `/conta/`, `/admin/` e `/offline/` como `noindex,nofollow`.

Os parciais em `templates/seo/` geram metadados, JSON-LD e integrações opcionais. O fallback social é `static/img/seo/botuka-default-1200x630.png`; o SVG ao lado é somente a fonte editável.

## Variáveis de ambiente

Consulte `.env.example`. Em produção, configure `SITE_URL=https://botuka.com.br`. IDs vazios nunca carregam scripts.

- `GOOGLE_TAG_MANAGER_ID`: container no formato `GTM-...`.
- `GOOGLE_ANALYTICS_ID`: fallback direto `G-...`, usado somente sem GTM.
- `META_PIXEL_ID`: Pixel opcional.
- `MICROSOFT_CLARITY_ID`: Clarity opcional.
- `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION`, `META_DOMAIN_VERIFICATION` e `PINTEREST_DOMAIN_VERIFICATION`: verificações opcionais.
- `ENABLE_ANALYTICS=False` e `ENABLE_MARKETING_TAGS=False`: permanecem desativados por padrão.

Além da flag e de um ID válido, analytics e marketing exigem consentimento explícito. Preferências são armazenadas no cookie `botuka_consent`, sem dados pessoais.

## GTM, GA4, Meta e Clarity

O GTM é preferencial. Quando um GTM válido estiver configurado, GA4 direto não é carregado. Meta Pixel e Clarity também dependem das respectivas flags/categorias de consentimento. Não configure a mesma integração diretamente e dentro do GTM.

Esta camada técnica não substitui análise jurídica de bases legais, política de privacidade, retenção ou fornecedores.

## Eventos dataLayer

Use:

```javascript
window.botukaTrack('view_service', {
  content_type: 'service',
  content_id: 'identificador-interno-nao-sensivel',
  category: 'categoria',
  city: 'Botucatu'
});
```

Campos permitidos: `content_type`, `content_id`, `content_name`, `category`, `city`, `neighborhood`, `business_type`, `page_type`, `method` e `link_type`.

Nunca enviar CPF, CNPJ, e-mail, telefone, nome completo de usuário, endereço particular, senha, tokens, texto livre ou dados de autenticação.

## Como adicionar SEO a uma view

Use `build_seo()` ou um builder em `page_builders.py`, passando somente informações públicas e visíveis. Canonical e imagens são normalizadas para URLs absolutas. Protocolos diferentes de HTTP/HTTPS são rejeitados.

```python
context['seo'] = build_seo(
    request,
    title='Título natural | BOTUKA',
    description=objeto.resumo,
    image=objeto.imagem,
    breadcrumbs=[...],
    schemas=[...],
)
```

## Dados estruturados

O JSON-LD usa `@graph`, é serializado no servidor e escapa caracteres capazes de encerrar o elemento `<script>`. Não adicionar nota agregada, preço, endereço, oferta ou coordenadas sem dados reais e conteúdo correspondente visível.

Schemas atualmente preparados:

- Home: `Organization`, `WebSite`, `WebPage`.
- Empresa: `LocalBusiness`.
- Serviço: `Service`.
- Notícia: `NewsArticle`.
- Vaga: `JobPosting`.
- YTv: `VideoObject` quando há vídeo incorporável.
- Prefeitura: `GovernmentOffice`, `GovernmentOrganization` ou `Event`.
- Esportes: `SportsEvent` e `Person`, quando aplicável.
- Páginas hierárquicas: `BreadcrumbList`.

## Robots e sitemaps

- `/robots.txt`
- `/sitemap.xml`
- `/sitemaps/static.xml`
- `/sitemaps/empresas.xml`
- `/sitemaps/servicos.xml`
- `/sitemaps/noticias.xml`
- `/sitemaps/categorias-noticias.xml`
- `/sitemaps/vagas.xml`
- `/sitemaps/ytv-programas.xml` e `/sitemaps/ytv-episodios.xml`
- `/sitemaps/esportes-modalidades.xml`, `/sitemaps/esportes-equipes.xml`, `/sitemaps/esportes-atletas.xml`, `/sitemaps/esportes-campeonatos.xml` e `/sitemaps/esportes-jogos.xml`
- `/sitemaps/prefeitura-orgaos.xml` e `/sitemaps/prefeitura-acoes.xml`

Painel, gestão, autenticação, QR codes, previews e currículos não entram no sitemap. Robots e `noindex` não substituem autenticação ou autorização.

## Search Console e validação

1. Configure a verificação sem versionar o token real.
2. Envie `https://botuka.com.br/sitemap.xml`.
3. Inspecione exemplos de cada segmento.
4. Monitore cobertura, rich results e Core Web Vitals.
5. Valide JSON-LD no Rich Results Test e Schema Markup Validator.
6. Valide compartilhamento no Facebook Sharing Debugger e LinkedIn Post Inspector.
7. Execute Lighthouse e PageSpeed Insights em mobile e desktop.

## Deploy

1. Criar backup do código e banco.
2. Publicar código revisado.
3. Configurar apenas IDs aprovados no `.env`.
4. Executar `manage.py check` e `manage.py makemigrations --check`.
5. Coletar estáticos conforme o procedimento operacional.
6. Reiniciar somente o serviço da plataforma.
7. Validar robots, sitemap, canonical, compartilhamento e ausência de tags vazias.

## Rollback

Restaure o backup de código correspondente, reverta as variáveis de integração, recolha os estáticos e reinicie somente a plataforma. Alterações desta etapa não exigem migration nem rollback de banco.
