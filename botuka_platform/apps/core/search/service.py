from dataclasses import dataclass

from django.db.models import Q

from .normalizers import accent_variants, normalize, terms
from .registry import default_registry


@dataclass(frozen=True)
class SearchResult:
    kind: str
    kind_label: str
    icon: str
    object_id: str
    title: str
    summary: str
    category: str
    owner: str
    location: str
    url: str
    image: str
    extra: object
    score: int


def _value(obj, field):
    current = obj
    for part in field.split('__'):
        current = getattr(current, part, '')
        if hasattr(current, 'all'):
            current = current.all()
        if callable(current):
            current = current()
        if current is None:
            return ''
    if hasattr(current, 'all'):
        return ' '.join(str(item) for item in current.all())
    if hasattr(current, '__iter__') and current.__class__.__name__ == 'QuerySet':
        return ' '.join(str(item) for item in current)
    return str(current)


class GlobalSearchService:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()

    def search(self, query):
        query = ' '.join(str(query or '').strip().split())[:120]
        query_terms = terms(query)
        if not query_terms:
            return [], {}
        results = []
        counts = {}
        for spec in self.registry:
            queryset = spec.queryset()
            aliases = {normalize(item) for item in spec.aliases}
            content_terms = [term for term in query_terms if term not in aliases]
            for term in content_terms:
                term_query = Q()
                for field in spec.fields:
                    for variant in accent_variants(term):
                        term_query |= Q(**{f'{field}__icontains': variant})
                queryset = queryset.filter(term_query)
            objects = list(queryset.distinct()) if content_terms or any(term in aliases for term in query_terms) else []
            counts[spec.key] = len(objects)
            for obj in objects:
                presented = spec.presenter(obj)
                title = presented['title']
                title_normalized = normalize(title)
                query_normalized = normalize(query)
                summaries = ' '.join(_value(obj, field) for field in spec.summary_fields)
                content = ' '.join(_value(obj, field) for field in spec.content_fields)
                related = ' '.join(_value(obj, field) for field in spec.related_fields)
                score = 0
                if title_normalized == query_normalized:
                    score += 1000
                elif title_normalized.startswith(query_normalized):
                    score += 700
                elif query_normalized in title_normalized:
                    score += 500
                for term in query_terms:
                    score += 140 if term in title_normalized else 0
                    score += 60 if term in normalize(related) else 0
                    score += 25 if term in normalize(summaries) else 0
                    score += 8 if term in normalize(content) else 0
                results.append(SearchResult(
                    kind=spec.key, kind_label=spec.label, icon=spec.icon,
                    object_id=str(obj.uuid), score=score, **presented,
                ))
        results.sort(key=lambda item: (-item.score, item.title.casefold(), item.kind))
        return results, counts
