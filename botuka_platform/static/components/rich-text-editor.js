document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-richtext]').forEach((root) => {
    if (root.dataset.ready) return;
    root.dataset.ready = 'true';

    const source = root.querySelector('[data-richtext-source]');
    const editor = root.querySelector('[data-richtext-editor]');
    if (!source || !editor) return;

    editor.innerHTML = source.value;
    source.hidden = true;

    editor.querySelectorAll('.richtext-youtube').forEach((marker) => {
      const id = (marker.dataset.youtubeId || '').trim();

      if (!/^[A-Za-z0-9_-]{11}$/.test(id)) {
        marker.remove();
        return;
      }

      const box = document.createElement('div');
      box.className = 'richtext-youtube-placeholder';
      box.contentEditable = 'false';
      box.dataset.youtubeId = id;

      const label = document.createElement('strong');
      label.textContent = '▶ Vídeo do YouTube';

      const code = document.createElement('span');
      code.textContent = `youtube.com/watch?v=${id}`;

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'richtext-youtube-placeholder__remove';
      remove.textContent = 'Remover';

      remove.addEventListener('click', () => {
        box.remove();
        sync();
      });

      box.append(label, code, remove);
      marker.replaceWith(box);
    });

    let savedRange = null;

    const sync = () => {
      const clone = editor.cloneNode(true);

      clone.querySelectorAll('.richtext-youtube-placeholder').forEach((box) => {
        const id = (box.dataset.youtubeId || '').trim();

        if (!/^[A-Za-z0-9_-]{11}$/.test(id)) {
          box.remove();
          return;
        }

        const marker = document.createElement('div');
        marker.className = 'richtext-youtube';
        marker.dataset.youtubeId = id;

        box.replaceWith(marker);
      });

      source.value = clone.innerHTML;
    };

    const saveSelection = () => {
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return;

      const range = selection.getRangeAt(0);

      if (
        editor.contains(range.startContainer) &&
        editor.contains(range.endContainer)
      ) {
        savedRange = range.cloneRange();
      }
    };

    const restoreSelection = () => {
      if (!savedRange) {
        editor.focus();
        return false;
      }

      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange);
      return true;
    };

    const youtubeId = (value) => {
      try {
        const url = new URL(value);

        if (url.protocol !== 'https:') return null;

        const host = url.hostname.toLowerCase().replace(/\.$/, '');
        let id = '';

        if (host === 'youtu.be') {
          id = url.pathname.split('/').filter(Boolean)[0] || '';
        } else if (
          host === 'youtube.com' ||
          host === 'www.youtube.com' ||
          host === 'm.youtube.com'
        ) {
          if (url.pathname === '/watch') {
            id = url.searchParams.get('v') || '';
          } else {
            const parts = url.pathname.split('/').filter(Boolean);

            if (
              parts.length >= 2 &&
              (parts[0] === 'shorts' || parts[0] === 'embed')
            ) {
              id = parts[1];
            }
          }
        } else {
          return null;
        }

        return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
      } catch (_) {
        return null;
      }
    };

    const insertYoutubePreview = (id) => {
      restoreSelection();

      const box = document.createElement('div');
      box.className = 'richtext-youtube-placeholder';
      box.contentEditable = 'false';
      box.dataset.youtubeId = id;

      const label = document.createElement('strong');
      label.textContent = '▶ Vídeo do YouTube';

      const code = document.createElement('span');
      code.textContent = `youtube.com/watch?v=${id}`;

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'richtext-youtube-placeholder__remove';
      remove.textContent = 'Remover';

      remove.addEventListener('click', () => {
        box.remove();
        sync();
      });

      box.append(label, code, remove);

      const range = savedRange;

      if (range) {
        range.deleteContents();
        range.insertNode(box);

        const spacer = document.createElement('p');
        spacer.innerHTML = '<br>';
        box.after(spacer);

        range.setStart(spacer, 0);
        range.collapse(true);

        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);

        savedRange = range.cloneRange();
      } else {
        editor.appendChild(box);

        const spacer = document.createElement('p');
        spacer.innerHTML = '<br>';
        editor.appendChild(spacer);
      }

      sync();
    };

    editor.addEventListener('input', sync);
    editor.addEventListener('keyup', saveSelection);
    editor.addEventListener('mouseup', saveSelection);
    editor.addEventListener('focus', saveSelection);

    root.closest('form')?.addEventListener('submit', sync);

    root.querySelectorAll('[data-command]').forEach((button) => {
      button.addEventListener('mousedown', saveSelection);

      button.addEventListener('click', () => {
        let value = button.dataset.value || null;

        if (button.dataset.command === 'createLink') {
          value = window.prompt('Informe uma URL HTTPS:');
          if (!value || !/^https:\/\//i.test(value)) return;
        }

        restoreSelection();
        editor.focus();

        document.execCommand(
          button.dataset.command,
          false,
          value
        );

        sync();
        saveSelection();
      });
    });

    const youtubeButton = root.querySelector('[data-youtube-insert]');

    if (youtubeButton) {
      youtubeButton.addEventListener('mousedown', saveSelection);

      youtubeButton.addEventListener('click', () => {
        const value = window.prompt(
          'Cole o link HTTPS do vídeo do YouTube:'
        );

        if (!value) return;

        const id = youtubeId(value.trim());

        if (!id) {
          window.alert(
            'Informe um link válido de vídeo do YouTube, Shorts ou youtu.be.'
          );
          return;
        }

        insertYoutubePreview(id);
      });
    }
  });
});
