from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_usuario, name="login"),
    path("cadastro/", views.cadastro_usuario, name="cadastro"),
    path("logout/", views.logout_usuario, name="logout"),
    path(
        "recuperar-senha/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset_form.html",
            email_template_name="auth/password_reset_email.html",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "recuperar-senha/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "nova-senha/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "nova-senha/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
