document.addEventListener('click', async function (event) {
  const root = event.target.closest('[data-share-actions]');
  if (!root) return;

  const url = root.dataset.url;
  const title = root.dataset.title;

  const pageContext =
    root.closest('[data-object-type]') ||
    document.querySelector('[data-analytics-event]');

  function trackShare(method) {
    if (typeof window.botukaTrack !== 'function') return;

    window.botukaTrack('share', {
      objectType:
        root.dataset.objectType ||
        pageContext?.dataset.objectType ||
        '',
      objectId:
        root.dataset.objectId ||
        pageContext?.dataset.objectId ||
        '',
      method: method,
      context:
        pageContext?.dataset.analyticsContext ||
        'share_actions',
      contentName: title || '',
    });
  }

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

    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }

    trackShare('qr');
  }

  const copy = event.target.closest('[data-copy-link]');

  if (copy) {
    try {
      await copyUrl();
      copy.textContent = 'Link copiado';
      trackShare('copy');
    } catch (_error) {
      window.prompt('Copie o link da publicação:', url);
    }
  }

  if (event.target.closest('[data-native-share]')) {
    try {
      if (navigator.share) {
        await navigator.share({
          title: title,
          url: url,
        });

        trackShare('native');
      } else {
        await copyUrl();
        trackShare('copy_fallback');
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        window.prompt('Copie o link:', url);
      }
    }
  }
});
