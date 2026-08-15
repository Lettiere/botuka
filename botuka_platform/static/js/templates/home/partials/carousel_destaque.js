/**
 * Configura o carrossel para funcionar em todas as telas,
 * com navegação por botão (touch e mouse) e responsividade.
 */
(function() {
  // Bootstrap carousel já suporta responsividade;
  // Asseguramos navegação via swipe para mobile/tablet.
  function enableSwipeOnCarousel(carouselSelector) {
    var $carousel = $(carouselSelector);
    var touchStartX = null;

    $carousel.on('touchstart', function(event) {
      var e = event.originalEvent.touches[0];
      touchStartX = e.clientX;
    });

    $carousel.on('touchmove', function(event) {
      if (!touchStartX) return;
      var e = event.originalEvent.touches[0];
      var touchEndX = e.clientX;
      var delta = touchEndX - touchStartX;

      // Swipe left/right threshold (30px)
      if (Math.abs(delta) > 30) {
        if (delta > 0) {
          $carousel.carousel('prev');
        } else {
          $carousel.carousel('next');
        }
        touchStartX = null;
      }
    });

    $carousel.on('touchend', function() {
      touchStartX = null;
    });
  }

  $(function() {
    var $carousel = $('#homeShowcaseCarousel');
    $carousel.carousel();

    // Inicializa swipe para mobile/tablet
    enableSwipeOnCarousel($carousel);

    // Aumenta área do botão em mobile
    function updateCarouselButtonSize() {
      var width = window.innerWidth || document.documentElement.clientWidth;
      if (width <= 576) {
        $('.carousel-control-next, .carousel-control-prev').css({
          width: '15vw',
          minWidth: '34px',
          height: '44px'
        });
      } else {
        $('.carousel-control-next, .carousel-control-prev').css({
          width: '42px',
          height: '42px'
        });
      }
    }
    $(window).on('resize', updateCarouselButtonSize);
    updateCarouselButtonSize();
  });
})();
