from django import template

register = template.Library()

GROUPS = {
    'accounts': 'access', 'auth': 'access',
    'organizations': 'organizations', 'services': 'services',
    'recruitment': 'recruitment', 'news': 'content', 'events': 'content',
    'government': 'government', 'sports': 'sports', 'media': 'media',
    'advertising': 'advertising', 'ads': 'advertising',
    'core': 'settings', 'locations': 'settings', 'taxonomy': 'settings',
}

ICONS = {
    'accounts': 'bi-people', 'auth': 'bi-shield-lock',
    'organizations': 'bi-buildings', 'services': 'bi-tools',
    'recruitment': 'bi-briefcase', 'news': 'bi-newspaper',
    'events': 'bi-calendar-event', 'government': 'bi-bank',
    'sports': 'bi-trophy', 'media': 'bi-play-btn',
    'advertising': 'bi-megaphone', 'ads': 'bi-megaphone',
    'core': 'bi-gear', 'locations': 'bi-geo-alt', 'taxonomy': 'bi-tags',
}


@register.filter
def admin_group(app_label):
    return GROUPS.get(str(app_label), 'settings')


@register.filter
def admin_model_group(model):
    object_name = model.get('object_name', '') if isinstance(model, dict) else getattr(model, 'object_name', '')
    app_label = (
        getattr(model.get('model'), '_meta', None).app_label
        if isinstance(model, dict) and model.get('model')
        else getattr(model, 'app_label', '')
    )
    if object_name in {'Auditoria', 'LogEntry'}:
        return 'audit'
    return admin_group(app_label)


@register.filter
def admin_icon(app_label):
    return ICONS.get(str(app_label), 'bi-grid')
