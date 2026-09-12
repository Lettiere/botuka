from .normalizers import normalize


SEMANTIC_GROUPS = (
    frozenset({
        'bar',
        'boteco',
        'buteco',
        'barzinho',
        'pub',
        'botequim',
        'choperia',
    }),
)


def is_semantic_term(term):
    normalized = normalize(term)
    return any(normalized in group for group in SEMANTIC_GROUPS)


def semantic_variants(term):
    normalized = normalize(term)

    for group in SEMANTIC_GROUPS:
        if normalized in group:
            return tuple(
                [normalized]
                + sorted(value for value in group if value != normalized)
            )

    return (normalized,)
