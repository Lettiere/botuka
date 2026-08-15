(function() {
  // simples swap login/cadastro sem dependências externas
  var loginSection = document.getElementById('loginFormSection');
  var cadastroSection = document.getElementById('cadastroFormSection');
  var toCadastro = document.getElementById('showCadastroForm');
  var toLogin = document.getElementById('showLoginForm');
  if (loginSection && cadastroSection) {
    // Mostra login por padrão
    loginSection.style.display = "block";
    cadastroSection.style.display = "none";
    // Troca
    if (toCadastro) {
      toCadastro.onclick = function() {
        loginSection.style.display = "none";
        cadastroSection.style.display = "block";
      };
    }
    if (toLogin) {
      toLogin.onclick = function() {
        cadastroSection.style.display = "none";
        loginSection.style.display = "block";
      };
    }
  }
})();
