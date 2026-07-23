(function () {
  'use strict';

  window.Botuka = window.Botuka || {};

  window.Botuka.getCookie = function (name) {
    var prefix = name + '=';
    var cookie = document.cookie.split(';').map(function (value) { return value.trim(); })
      .find(function (value) { return value.startsWith(prefix); });
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  };

  window.Botuka.csrfFetch = async function (url, options) {
    options = options || {};
    var headers = new Headers(options.headers || {});
    var method = (options.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
      var token = window.Botuka.getCookie('csrftoken');
      if (token) headers.set('X-CSRFToken', token);
    }
    var response = await fetch(url, Object.assign({}, options, {
      headers: headers,
      credentials: options.credentials || 'same-origin'
    }));
    if (response.status === 403) window.dispatchEvent(new CustomEvent('botuka:csrf-failed'));
    return response;
  };

  window.Botuka.showToast = function (message) {
    var toastElement = document.getElementById('appToast');
    var toastText = document.getElementById('toastText');
    if (!toastElement || !toastText || !window.bootstrap) return;
    toastText.textContent = message;
    new window.bootstrap.Toast(toastElement, { delay: 2800 }).show();
  };
  window.showToast = window.Botuka.showToast;

  function setTheme(theme) {
    var normalized = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', normalized);
    try { window.localStorage.setItem('botuka-theme', normalized); } catch (error) { /* storage indisponível */ }
    var icon = document.getElementById('themeIcon');
    if (icon) icon.className = normalized === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
  }

  document.addEventListener('DOMContentLoaded', function () {
    var themeButton = document.getElementById('themeToggle');
    setTheme(document.documentElement.getAttribute('data-theme'));
    if (themeButton) {
      themeButton.addEventListener('click', function () {
        setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
      });
    }

    var year = document.getElementById('year');
    if (year) year.textContent = new Date().getFullYear();

    var skipTarget = document.getElementById('conteudo-publico');
    if (skipTarget) {
      document.querySelector('.skip-link')?.addEventListener('click', function () {
        window.setTimeout(function () { skipTarget.focus({ preventScroll: true }); }, 0);
      });
    }

    document.querySelectorAll('img:not([loading])').forEach(function (img) {
      if (img.getAttribute('fetchpriority') !== 'high') img.loading = 'lazy';
      img.decoding = 'async';
    });

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('on');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: .12 });
      document.querySelectorAll('.reveal').forEach(function (element) { observer.observe(element); });
    }
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('#mainSearch, #headerSearch');
    if (!form) return;
    var input = form.querySelector('input');
    if (input && !input.value.trim()) {
      event.preventDefault();
      window.Botuka.showToast('Digite o que você procura na cidade.');
    }
  });

  document.addEventListener('click', function (event) {
    var scrollButton = event.target.closest('[data-city-scroll]');
    if (scrollButton) {
      var strip = document.getElementById(scrollButton.dataset.cityScroll);
      if (strip) strip.scrollBy({ left:(Number(scrollButton.dataset.direction) || 1) * Math.min(strip.clientWidth * .85, 620), behavior:'smooth' });
      return;
    }

    var videoButton = event.target.closest('[data-video-src]');
    if (videoButton) {
      var source = videoButton.dataset.videoSrc || '';
      var shell = videoButton.closest('[data-video-shell]');
      if (shell && source.startsWith('https://www.youtube-nocookie.com/embed/')) {
        var iframe = document.createElement('iframe');
        iframe.src = source;
        iframe.title = videoButton.getAttribute('aria-label') || 'Vídeo da YTv Botuka';
        iframe.loading = 'lazy';
        iframe.allow = 'accelerometer; encrypted-media; picture-in-picture';
        iframe.allowFullscreen = true;
        shell.replaceChildren(iframe);
      }
      return;
    }

    var copy = event.target.closest('[data-copy-url]');
    if (copy && navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href).then(function () { window.Botuka.showToast('Link copiado.'); });
      return;
    }

    var share = event.target.closest('[data-share-native]');
    if (share && navigator.share) {
      navigator.share({ title:share.dataset.shareTitle || document.title, url:window.location.href }).catch(function () {});
      return;
    }

    if (event.target.closest('[data-close-mobile-ad]')) document.querySelector('[data-mobile-ad]')?.remove();
  });

  window.addEventListener('botuka:csrf-failed', function () {
    window.alert('Sua sessão ou formulário expirou. Atualize a página e tente novamente.');
  });
})();
