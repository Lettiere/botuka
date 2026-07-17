document.addEventListener('change', (event) => {
  const setor = event.target.closest('select[name="setor"]');
  const profissao = document.querySelector('select[name="profissao"]');

  if (!setor || !profissao || !setor.value) {
    return;
  }

  fetch(`/painel/servicos/ajax/profissoes/?setor=${encodeURIComponent(setor.value)}`)
    .then((response) => response.ok ? response.json() : Promise.reject())
    .then((data) => {
      profissao.innerHTML = '<option value="">---------</option>';
      data.results.forEach((item) => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = item.text;
        profissao.appendChild(option);
      });
    })
    .catch(() => {});
});
