(function () {
  'use strict';
  var stored = null;
  try { stored = window.localStorage.getItem('botuka-theme'); } catch (error) { stored = null; }
  document.documentElement.setAttribute('data-theme', stored === 'dark' ? 'dark' : 'light');
})();
