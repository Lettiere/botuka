document.addEventListener('change', (event) => {
  const prestador = event.target.closest('input[name="prestador_tipo"]');
  if (prestador) {
    document.querySelectorAll('.provider-card').forEach((card) => {
      const input = card.querySelector('input[name="prestador_tipo"]');
      card.classList.toggle('is-selected', Boolean(input && input.checked));
    });
    document.querySelectorAll('[data-responsavel]').forEach((panel) => {
      panel.hidden = panel.dataset.responsavel !== prestador.value;
    });
  }

  const setor = event.target.closest('select[name="setor"]');
  const area = event.target.closest('select[name="area"]');
  const areaSelect = document.querySelector('select[name="area"]');
  const profissao = document.querySelector('select[name="profissao"]');

  if (setor && areaSelect && profissao) {
    areaSelect.innerHTML = '<option value="">---------</option>';
    profissao.innerHTML = '<option value="">---------</option>';

    if (!setor.value) {
      return;
    }

    fetch(`/painel/servicos/ajax/areas/?setor=${encodeURIComponent(setor.value)}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        data.results.forEach((item) => {
          const option = document.createElement('option');
          option.value = item.id;
          option.textContent = item.text;
          areaSelect.appendChild(option);
        });
      })
      .catch(() => {});

    return;
  }

  if (area && profissao) {
    profissao.innerHTML = '<option value="">---------</option>';

    if (!area.value) {
      return;
    }

    fetch(`/painel/servicos/ajax/profissoes/?area=${encodeURIComponent(area.value)}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        data.results.forEach((item) => {
          const option = document.createElement('option');
          option.value = item.id;
          option.textContent = item.text;
          profissao.appendChild(option);
        });
      })
      .catch(() => {});
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const linkList = document.querySelector('[data-link-list]');
  const linkTemplate = document.querySelector('[data-link-template]');
  const addLink = document.querySelector('[data-add-link]');
  let totalLinks = 0;
  if (linkList && linkTemplate && addLink) {
    addLink.addEventListener('click', () => {
      if (linkList.children.length >= 15) return;
      const fragment = linkTemplate.content.cloneNode(true);
      fragment.querySelectorAll('[name]').forEach((field) => { field.name = field.name.replace('TOTAL', String(totalLinks)); });
      totalLinks += 1;
      linkList.appendChild(fragment);
    });
    linkList.addEventListener('click', (event) => {
      const button = event.target.closest('[data-remove-link]');
      if (button) button.closest('[data-link-row]').remove();
    });
  }

  const selectedProvider = document.querySelector('input[name="prestador_tipo"]:checked');
  if (selectedProvider) {
    selectedProvider.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const coverInput = document.querySelector('#imagem_capa');
  const coverName = document.querySelector('[data-cover-name]');
  if (coverInput && coverName) {
    coverInput.addEventListener('change', () => {
      coverName.textContent = coverInput.files[0]?.name || 'Nenhum arquivo selecionado';
    });
  }

  const galleryInput = document.querySelector('#galeria');
  const galleryName = document.querySelector('[data-gallery-name]');
  if (galleryInput && galleryName) {
    galleryInput.addEventListener('change', () => {
      const total = galleryInput.files.length;
      galleryName.textContent = total ? `${total} imagem(ns) selecionada(s)` : 'Nenhum arquivo selecionado';
    });
  }
});
