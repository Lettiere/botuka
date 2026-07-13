document.addEventListener('submit', (event) => {
  const form = event.target.closest('[data-cnpj-form]');
  if (!form) {
    return;
  }

  event.preventDefault();
  const output = document.querySelector(form.dataset.output);
  const formData = new FormData(form);

  fetch('/painel/empresas/ajax/consultar-cnpj/', {
    method: 'POST',
    body: formData,
    headers: {'X-Requested-With': 'XMLHttpRequest'},
  })
    .then((response) => response.json())
    .then((data) => {
      if (output) {
        output.textContent = JSON.stringify(data, null, 2);
      }
    })
    .catch(() => {
      if (output) {
        output.textContent = 'Não foi possível consultar o CNPJ.';
      }
    });
});
