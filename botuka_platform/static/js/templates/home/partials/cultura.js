$(document).ready(function () {
    // Click on card (but not links inside card)
    $('.botuka-card').on('click', function (e) {
      if ($(e.target).closest('a').length) return;
      const url = $(this).data('url');
      if (url && url !== '#') {
        window.location.href = url;
      }
    });
  });
