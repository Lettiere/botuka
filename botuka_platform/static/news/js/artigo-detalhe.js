(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const page = document.querySelector('.article-detail-page');
    if (!page) return;

    const article = page.querySelector('[data-article-content]');
    const body = page.querySelector('[data-article-body]');
    const progress = document.querySelector('[data-reading-progress] span');
    let ticking = false;

    function updateProgress() {
      ticking = false;
      if (!article || !progress) return;
      const rect = article.getBoundingClientRect();
      const start = window.scrollY + rect.top;
      const distance = Math.max(1, article.offsetHeight - window.innerHeight);
      const percent = Math.min(100, Math.max(0, ((window.scrollY - start) / distance) * 100));
      progress.style.width = percent + '%';
    }

    function requestProgressUpdate() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateProgress);
    }

    window.addEventListener('scroll', requestProgressUpdate, {passive: true});
    window.addEventListener('resize', requestProgressUpdate, {passive: true});
    updateProgress();

    const toc = page.querySelector('[data-article-toc]');
    const tocList = page.querySelector('[data-toc-list]');
    if (body && toc && tocList) {
      const headings = Array.from(body.querySelectorAll('h2, h3'));
      if (headings.length >= 2) {
        headings.forEach(function (heading, index) {
          if (!heading.id) heading.id = 'secao-' + (index + 1);
          const item = document.createElement('li');
          if (heading.tagName === 'H3') item.className = 'article-toc__subitem';
          const link = document.createElement('a');
          link.href = '#' + heading.id;
          link.textContent = heading.textContent;
          item.appendChild(link);
          tocList.appendChild(item);
        });
        toc.hidden = false;
      }
    }

    const tocToggle = page.querySelector('[data-toc-toggle]');
    if (tocToggle && toc) {
      tocToggle.addEventListener('click', function () {
        const collapsed = toc.classList.toggle('is-collapsed');
        tocToggle.setAttribute('aria-expanded', String(!collapsed));
      });
    }

    const status = page.querySelector('[data-share-status]');
    function announce(message) {
      if (!status) return;
      status.textContent = message;
      window.setTimeout(function () { status.textContent = ''; }, 3000);
    }

    const copyButton = page.querySelector('[data-copy-article-url]');
    if (copyButton) {
      copyButton.addEventListener('click', async function () {
        try {
          await navigator.clipboard.writeText(window.location.href);
          announce('Link copiado para a área de transferência.');
        } catch (_error) {
          const input = document.createElement('textarea');
          input.value = window.location.href;
          input.setAttribute('readonly', '');
          input.style.position = 'fixed';
          input.style.opacity = '0';
          document.body.appendChild(input);
          input.select();
          document.execCommand('copy');
          input.remove();
          announce('Link copiado para a área de transferência.');
        }
      });
    }

    const nativeShare = page.querySelector('[data-native-share]');
    if (nativeShare) {
      if (!navigator.share) nativeShare.hidden = true;
      nativeShare.addEventListener('click', async function () {
        try {
          await navigator.share({title: document.title, url: window.location.href});
        } catch (error) {
          if (error.name !== 'AbortError') announce('Não foi possível compartilhar agora.');
        }
      });
    }
  });
})();
