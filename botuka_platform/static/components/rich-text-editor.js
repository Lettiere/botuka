document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-richtext]').forEach((root) => {
    if (root.dataset.ready) return;
    root.dataset.ready = 'true';
    const source = root.querySelector('[data-richtext-source]');
    const editor = root.querySelector('[data-richtext-editor]');
    if (!source || !editor) return;
    editor.innerHTML = source.value;
    source.hidden = true;
    const sync = () => { source.value = editor.innerHTML; };
    editor.addEventListener('input', sync);
    root.closest('form')?.addEventListener('submit', sync);
    root.querySelectorAll('[data-command]').forEach((button) => {
      button.addEventListener('click', () => {
        let value = button.dataset.value || null;
        if (button.dataset.command === 'createLink') {
          value = window.prompt('Informe uma URL HTTPS:');
          if (!value || !/^https?:\/\//i.test(value)) return;
        }
        editor.focus();
        document.execCommand(button.dataset.command, false, value);
        sync();
      });
    });
  });
});
