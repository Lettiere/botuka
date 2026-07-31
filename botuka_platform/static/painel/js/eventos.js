document.addEventListener('DOMContentLoaded', () => {
  const input = document.querySelector('#id_imagem_principal');
  const preview = document.querySelector('[data-event-cover-preview]');
  const name = document.querySelector('[data-event-cover-name]');
  if (!input || !preview) return;
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    const image = document.createElement('img');
    image.src = URL.createObjectURL(file);
    image.alt = 'Prévia da imagem selecionada';
    preview.replaceChildren(image);
    if (name) name.textContent = file.name;
  });
});
