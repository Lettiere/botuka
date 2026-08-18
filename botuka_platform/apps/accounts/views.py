from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode, urlparse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.services import obter_url_pos_login
from apps.social.services import get_or_create_social_profile

Usuario = get_user_model()


def login_usuario(request):
    redirect_to = request.POST.get("next") or request.GET.get("next") or "home"

    if request.method == "GET":
        parametros = {"login": "1"}

        if redirect_to != "home" and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host(), urlparse(settings.BOTUKA_SOCIAL_BASE_URL).netloc},
            require_https=request.is_secure(),
        ):
            parametros["next"] = redirect_to

        return redirect(f"{reverse('home')}?{urlencode(parametros)}")

    if request.method != "POST":
        return redirect("home")

    email = request.POST.get("email", "").strip().lower()
    senha = request.POST.get("password", "")

    user = authenticate(request, username=email, password=senha)

    if user is not None:
        login(request, user)
        messages.success(request, "Login realizado com sucesso.")
        if redirect_to != "home" and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host(), urlparse(settings.BOTUKA_SOCIAL_BASE_URL).netloc},
            require_https=request.is_secure(),
        ):
            return redirect(redirect_to)

        return redirect(obter_url_pos_login(user))

    messages.error(request, "E-mail ou senha inválidos.")
    return redirect(f'{settings.BOTUKA_PLATFORM_BASE_URL}/')


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

    with transaction.atomic():
        user = Usuario.objects.create_user(
            username=email,
            email=email,
            password=senha,
            first_name=nome,
        )
        get_or_create_social_profile(user)

    login(request, user)
    messages.success(request, "Conta criada com sucesso. Bem-vindo ao BOTUKA!")
    return redirect(obter_url_pos_login(user))


@require_POST
def logout_usuario(request):
    logout(request)
    messages.success(request, "Você saiu da sua conta.")
    return redirect("home")
