// O conteúdo abaixo foi removido pois não pertence a um arquivo JavaScript.
// O código continha trechos de HTML, scripts e recursos que devem estar em arquivos .html ou templates,
// não em arquivos .js dedicados a scripts JavaScript puros.
//
// Se necessário, apenas scripts reais (JavaScript puro ou jQuery) deste bloco podem ser extraídos
// para serem mantidos aqui. Sugestão de estrutura correta:

(function(){
  const root = document.documentElement;
  const themeButton = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  const storedTheme = localStorage.getItem('botuka-theme') || 'light';

  function setTheme(theme){
    root.setAttribute('data-theme', theme);
    localStorage.setItem('botuka-theme', theme);
    themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
  }

  setTheme(storedTheme);

  if (themeButton) {
    themeButton.addEventListener('click', function(){
      setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
  }
})();

function showToast(message){
  $('#toastText').text(message);
  const toast = new bootstrap.Toast(document.getElementById('appToast'), { delay: 2800 });
  toast.show();
}

$(function(){
  $('#year').text(new Date().getFullYear());

  $('a[href^="#"]').on('click', function(e){
    const target = $(this.getAttribute('href'));
    if(target.length){
      e.preventDefault();
      $('html, body').animate({ scrollTop: target.offset().top - 82 }, 520);
    }
  });

  $('#mainSearch, #headerSearch').on('submit', function(e){
    e.preventDefault();
    const value = $(this).find('input').val().trim();
    if(!value){
      showToast('Digite o que você procura na cidade.');
      return;
    }
    showToast('Buscando "' + value + '" na região — protótipo visual.');
  });

  $('#loginForm').on('submit', function(e){
    e.preventDefault();
    showToast('Login demonstrativo — sem backend conectado.');
    bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
  });

  $('.feed-link, .price-pill, .publish-option, .map-pin, .map-filter, .quick-chip').on('click', function(e){
    if(!$(this).attr('href') || $(this).attr('href') === '#'){
      e.preventDefault();
      showToast('Ação demonstrativa do protótipo.');
    }
  });

  $('.map-filter').on('click', function(){
    $('.map-filter').removeClass('active');
    $(this).addClass('active');
  });

  const observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        entry.target.classList.add('on');
        observer.unobserve(entry.target);
      }
    });
  }, {threshold:.12});

  document.querySelectorAll('.reveal').forEach(function(el){
    observer.observe(el);
  });
});
