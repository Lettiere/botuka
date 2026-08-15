import re
import unicodedata

from django.utils.html import strip_tags

ACCENTS = {
    'a': ('a', 'á', 'à', 'â', 'ã'), 'e': ('e', 'é', 'ê'),
    'i': ('i', 'í'), 'o': ('o', 'ó', 'ô', 'õ'),
    'u': ('u', 'ú', 'ü'), 'c': ('c', 'ç'),
}


def normalize(value):
    text = strip_tags(str(value or '')).casefold()
    text = unicodedata.normalize('NFKD', text)
    return ' '.join(''.join(char for char in text if not unicodedata.combining(char)).split())


def terms(value, limit=8):
    return list(dict.fromkeys(re.findall(r'[\w-]+', normalize(value), flags=re.UNICODE)))[:limit]


def accent_variants(term, limit=32):
    term = term.casefold()
    variants = [term]
    for index, char in enumerate(term):
        for replacement in ACCENTS.get(char, ())[1:]:
            variants.append(f'{term[:index]}{replacement}{term[index + 1:]}')
    bases = list(variants)
    for value in bases:
        if value.endswith('cao'):
            variants.append(f'{value[:-3]}ção')
        if value.endswith('coes'):
            variants.append(f'{value[:-4]}ções')
        if value.endswith('ao'):
            variants.append(f'{value[:-2]}ão')
    return tuple(dict.fromkeys(variants))[:limit]
