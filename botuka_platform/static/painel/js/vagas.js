document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-jobs-filter-toggle]').forEach((button) => {
    const panel = button.closest('.jobs-panel');
    if (!panel) return;
    button.addEventListener('click', () => {
      const open = panel.classList.toggle('is-open');
      button.setAttribute('aria-expanded', String(open));
      button.querySelector('span').textContent = open ? 'Ocultar filtros' : 'Mostrar filtros';
    });
  });

  document.querySelectorAll('[data-job-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.jobConfirm)) event.preventDefault();
    });
  });
});
