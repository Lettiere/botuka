from dataclasses import dataclass

from django.db.models import Q

from .normalizers import accent_variants, normalize, terms
from .registry import default_registry
from .semantics import is_semantic_term, semantic_variants


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


def _values(value, parts):
    if value is None:
        return []

    if hasattr(value, 'all'):
        values = []
        for item in value.all():
            values.extend(_values(item, parts))
        return values

    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(_values(item, parts))
        return values

    if not parts:
        return [str(value)]

    current = getattr(value, parts[0], '')

    # RelatedManager/ManyRelatedManager possuem .all() e também podem ser
    # callable; não devem ser executados como função.
    if callable(current) and not hasattr(current, 'all'):
        current = current()

    return _values(current, parts[1:])


def _value(obj, field):
    return ' '.join(
        value for value in _values(obj, field.split('__'))
        if value
    )


def _matches_semantic_term(obj, spec, term):
    variants = set(semantic_variants(term))

    for field in spec.fields:
        field_tokens = set(terms(_value(obj, field), limit=256))
        if variants.intersection(field_tokens):
            return True

    return False


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

                for semantic_term in semantic_variants(term):
                    for field in spec.fields:
                        for variant in accent_variants(semantic_term):
                            term_query |= Q(**{f'{field}__icontains': variant})

                queryset = queryset.filter(term_query)
            objects = list(queryset.distinct()) if content_terms or any(term in aliases for term in query_terms) else []

            semantic_terms = [
                term for term in content_terms
                if is_semantic_term(term)
            ]

            if semantic_terms:
                objects = [
                    obj for obj in objects
                    if all(
                        _matches_semantic_term(obj, spec, term)
                        for term in semantic_terms
                    )
                ]

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
                related_normalized = normalize(related)
                summary_normalized = normalize(summaries)
                content_normalized = normalize(content)

                title_tokens = set(terms(title, limit=256))
                related_tokens = set(terms(related, limit=256))
                summary_tokens = set(terms(summaries, limit=256))
                content_tokens = set(terms(content, limit=256))

                for term in query_terms:
                    if not is_semantic_term(term):
                        score += 140 if term in title_normalized else 0
                        score += 60 if term in related_normalized else 0
                        score += 25 if term in summary_normalized else 0
                        score += 8 if term in content_normalized else 0
                        continue

                    for semantic_term in semantic_variants(term):
                        is_literal = semantic_term == term

                        if semantic_term in title_tokens:
                            score += 140 if is_literal else 90

                        if semantic_term in related_tokens:
                            score += 720 if is_literal else 650

                        if semantic_term in summary_tokens:
                            score += 25 if is_literal else 15

                        if semantic_term in content_tokens:
                            score += 8 if is_literal else 4
                results.append(SearchResult(
                    kind=spec.key, kind_label=spec.label, icon=spec.icon,
                    object_id=str(obj.uuid), score=score, **presented,
                ))
        results.sort(key=lambda item: (-item.score, item.title.casefold(), item.kind))
        return results, counts
