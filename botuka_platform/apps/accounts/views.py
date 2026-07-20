from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.services import obter_url_pos_login

Usuario = get_user_model()


@require_POST
def login_usuario(request):
    email = request.POST.get("email", "").strip().lower()
    senha = request.POST.get("password", "")
    redirect_to = request.POST.get("next") or request.GET.get("next") or "home"

    user = authenticate(request, username=email, password=senha)

    if user is not None:
        login(request, user)
        messages.success(request, "Login realizado com sucesso.")
        if redirect_to != "home" and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(redirect_to)

        return redirect(obter_url_pos_login(user))

    messages.error(request, "E-mail ou senha inválidos.")
    return redirect("home")


def cadastro_usuario(request):
    if request.method != "POST":
        return redirect("home")

    nome = request.POST.get("nome", "").strip()
    email = request.POST.get("email", "").strip().lower()
    senha = request.POST.get("password", "")
    senha_confirmacao = request.POST.get("password_confirm", "")

    if not nome or not email or not senha:
        messages.error(request, "Preencha todos os campos obrigatórios.")
        return redirect("home")

    if senha != senha_confirmacao:
        messages.error(request, "As senhas não conferem.")
        return redirect("home")

    if Usuario.objects.filter(username=email).exists():
        messages.error(request, "Este e-mail já está cadastrado.")
        return redirect("home")

    user = Usuario.objects.create_user(
        username=email,
        email=email,
        password=senha,
        first_name=nome,
    )

    login(request, user)
    messages.success(request, "Conta criada com sucesso. Bem-vindo ao BOTUKA!")
    return redirect(obter_url_pos_login(user))


@require_POST
def logout_usuario(request):
    logout(request)
    messages.success(request, "Você saiu da sua conta.")
    return redirect("home")
