from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


@require_POST
def login_usuario(request):
    email = request.POST.get("email", "").strip().lower()
    senha = request.POST.get("password", "")

    user = authenticate(request, username=email, password=senha)

    if user is not None:
        login(request, user)
        messages.success(request, "Login realizado com sucesso.")
        return redirect("home")

    messages.error(request, "E-mail ou senha inválidos.")
    return redirect("home")


@require_POST
def cadastro_usuario(request):
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

    if User.objects.filter(username=email).exists():
        messages.error(request, "Este e-mail já está cadastrado.")
        return redirect("home")

    user = User.objects.create_user(
        username=email,
        email=email,
        password=senha,
        first_name=nome,
    )

    login(request, user)
    messages.success(request, "Conta criada com sucesso. Bem-vindo ao BOTUKA!")
    return redirect("home")


def logout_usuario(request):
    logout(request)
    messages.success(request, "Você saiu da sua conta.")
    return redirect("home")