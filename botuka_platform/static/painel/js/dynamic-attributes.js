document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-attribute-formset]').forEach((root) => {
    const rows = root.querySelector('[data-attribute-rows]');
    const total = root.querySelector('[name$="-TOTAL_FORMS"]');
    const template = root.querySelector('[data-attribute-empty]');
    if (!rows || !total || !template) return;

    function update(row, index) {
      row.querySelectorAll('input, select, textarea, label').forEach((element) => {
        if (element.name) element.name = element.name.replace(/__prefix__/g, index);
        if (element.id) element.id = element.id.replace(/__prefix__/g, index);
        if (element.htmlFor) element.htmlFor = element.htmlFor.replace(/__prefix__/g, index);
      });
      const order = row.querySelector('[name$="-ordem"]');
      if (order) order.value = index;
    }
    function toggleCustom(row) {
      const type = row.querySelector('[data-attribute-type]');
      const custom = row.querySelector('[data-custom-field]');
      if (!type || !custom) return;
      custom.hidden = type.value !== 'OUTRO';
      const input = custom.querySelector('input');
      if (input) input.required = type.value === 'OUTRO';
    }
    root.addEventListener('change', (event) => {
      if (event.target.matches('[data-attribute-type]')) toggleCustom(event.target.closest('[data-attribute-row]'));
    });
    root.querySelector('[data-add-attribute]').addEventListener('click', () => {
      const index = Number(total.value);
      const fragment = template.content.cloneNode(true);
      const row = fragment.querySelector('[data-attribute-row]');
      update(row, index);
      rows.appendChild(fragment);
      total.value = index + 1;
      toggleCustom(rows.lastElementChild);
    });
    root.addEventListener('change', (event) => {
      if (!event.target.matches('[name$="-DELETE"]')) return;
      event.target.closest('[data-attribute-row]').classList.toggle('is-removed', event.target.checked);
    });
    rows.querySelectorAll('[data-attribute-row]').forEach(toggleCustom);
  });
});
