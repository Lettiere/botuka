document.addEventListener('click', async function (event) {
  const root = event.target.closest('[data-share-actions]');
  if (!root) return;
  const url = root.dataset.url;
  const title = root.dataset.title;

  async function copyUrl() {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(url);
      return;
    }
    const field = document.createElement('textarea');
    field.value = url;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    document.execCommand('copy');
    field.remove();
  }

  if (event.target.closest('[data-open-qr]')) {
    const modal = root.querySelector('[data-qr-modal]');
    if (typeof modal.showModal === 'function') modal.showModal();
    else modal.setAttribute('open', '');
  }
  const copy = event.target.closest('[data-copy-link]');
  if (copy) {
    try {
      await copyUrl();
      copy.textContent = 'Link copiado';
    } catch (_error) {
      window.prompt('Copie o link da publicação:', url);
    }
  }
  if (event.target.closest('[data-native-share]')) {
    try {
      if (navigator.share) await navigator.share({title: title, url: url});
      else await copyUrl();
    } catch (error) {
      if (error.name !== 'AbortError') window.prompt('Copie o link:', url);
    }
  }
});
