from .utils import clean_text


def organization(site_url, image_url):
    return {
        '@type': 'Organization',
        '@id': f'{site_url}/#organization',
        'name': 'BOTUKA',
        'url': f'{site_url}/',
        'logo': {'@type': 'ImageObject', 'url': image_url},
    }


def website(site_url, description, organization_id):
    return {
        '@type': 'WebSite',
        '@id': f'{site_url}/#website',
        'url': f'{site_url}/',
        'name': 'BOTUKA',
        'description': description,
        'publisher': {'@id': organization_id},
        'inLanguage': 'pt-BR',
    }


def webpage(url, title, description, image, *, page_type='WebPage'):
    data = {
        '@type': page_type,
        '@id': f'{url}#webpage',
        'url': url,
        'name': title,
        'description': description,
        'inLanguage': 'pt-BR',
    }
    if image:
        data['primaryImageOfPage'] = {'@type': 'ImageObject', 'url': image}
    return data


def breadcrumb_schema(items):
    return {
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': index, 'name': item['name'], 'item': item['url']}
            for index, item in enumerate(items, 1)
        ],
    }


def compact(data):
    if isinstance(data, dict):
        return {key: compact(value) for key, value in data.items() if value not in (None, '', [], {})}
    if isinstance(data, list):
        return [compact(value) for value in data if value not in (None, '', [], {})]
    return data


def text(value, limit=300):
    return clean_text(value, limit)
