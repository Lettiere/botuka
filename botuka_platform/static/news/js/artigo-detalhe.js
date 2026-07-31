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
          await navigator.clipboard.writeText(page.dataset.publicUrl);
          announce('Link copiado para a área de transferência.');
        } catch (_error) {
          const input = document.createElement('textarea');
          input.value = page.dataset.publicUrl;
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
          await navigator.share({title: document.title, url: page.dataset.publicUrl});
        } catch (error) {
          if (error.name !== 'AbortError') announce('Não foi possível compartilhar agora.');
        }
      });
    }

    page.querySelectorAll('[data-comment-text]').forEach(function (textarea) {
      const counter = textarea.closest('form').querySelector('[data-comment-counter]');
      const update = function () { counter.textContent = textarea.value.length + '/1000'; };
      textarea.addEventListener('input', update);
      update();
    });
    page.addEventListener('click', function (event) {
      const trigger = event.target.closest('[data-reply-to],[data-edit-comment],[data-report-comment]');
      const cancel = event.target.closest('[data-cancel-reply],[data-cancel-edit],[data-cancel-report]');
      const toggle = event.target.closest('[data-replies-toggle]');
      if (trigger) {
        const key = trigger.dataset.replyTo || trigger.dataset.editComment || trigger.dataset.reportComment;
        const type = trigger.dataset.replyTo ? 'reply' : (trigger.dataset.editComment ? 'edit' : 'report');
        const form = page.querySelector('[data-' + type + '-form="' + key + '"]');
        if (form) { form.hidden = false; form.querySelector('textarea').focus(); }
      } else if (cancel) {
        cancel.closest('form').hidden = true;
      } else if (toggle) {
        const replies = toggle.nextElementSibling;
        replies.hidden = !replies.hidden;
        toggle.setAttribute('aria-expanded', String(!replies.hidden));
        toggle.textContent = replies.hidden ? toggle.textContent.replace('Ocultar', 'Ver') : toggle.textContent.replace('Ver', 'Ocultar');
      }
    });
    page.querySelectorAll('[data-confirm-comment]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!window.confirm('Excluir este comentário?')) event.preventDefault();
      });
    });
    page.querySelectorAll('.comment-form,.comment-inline-form').forEach(function (form) {
      form.addEventListener('submit', function () {
        const button = form.querySelector('button[type="submit"]');
        if (button) { button.disabled = true; button.textContent = 'Enviando...'; }
      });
    });
  });
})();
