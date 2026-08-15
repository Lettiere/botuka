from django.core.paginator import Paginator
from django.shortcuts import render

from .forms import GlobalSearchForm
from .service import GlobalSearchService


def global_search(request):
    form = GlobalSearchForm(request.GET)
    query = ''
    results, counts = [], {}
    selected_type = request.GET.get('tipo', '').strip()[:40]
    service = GlobalSearchService()
    if form.is_valid():
        query = form.cleaned_data['q'].strip()
        if query:
            results, counts = service.search(query)
            if selected_type and selected_type in counts:
                results = [item for item in results if item.kind == selected_type]
            else:
                selected_type = ''
    page = Paginator(results, 20).get_page(request.GET.get('page'))
    groups = [
        {'key': spec.key, 'label': spec.label, 'count': counts.get(spec.key, 0)}
        for spec in service.registry if counts.get(spec.key)
    ]
    return render(request, 'publico/busca/resultados.html', {
        'form': form, 'query': query, 'results': page.object_list,
        'page_obj': page, 'total': page.paginator.count, 'groups': groups,
        'selected_type': selected_type,
    })
