document.addEventListener('submit', async (event) => {
  const form = event.target.closest('[data-interest-form]');
  if (!form || !window.fetch) return;
  event.preventDefault();
  const button = form.querySelector('[data-interest-button]');
  button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    });
    if (response.redirected) {
      window.location.assign(response.url);
      return;
    }
    if (!response.ok) throw new Error('request failed');
    const data = await response.json();
    button.textContent = data.interesse_ativo ? 'Desmarcar interesse' : 'Eu vou!';
    const count = document.querySelector('[data-interest-count]');
    if (count) count.textContent = `${data.total_interessados} pessoa${data.total_interessados === 1 ? '' : 's'} demonstraram interesse.`;
  } catch (_) {
    form.submit();
    return;
  } finally {
    button.disabled = false;
  }
});
