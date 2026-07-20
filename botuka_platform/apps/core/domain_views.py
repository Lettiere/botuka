from collections.abc import Callable

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, QuerySet
from django.forms import BaseModelForm, modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .domain import auditar


PermissionMap = dict[str, tuple[str, ...]]


def crud_views(
    model,
    permission_prefix: str,
    fields: list[str],
    *,
    ownership: Callable | None = None,
    scope: Callable[[object, QuerySet], QuerySet] | None = None,
    filter_form: Callable[[object, BaseModelForm], None] | None = None,
    validate_transition: Callable[[object, str | None, str | None, object], None] | None = None,
    permissions: PermissionMap | None = None,
):
    """Cria CRUD simples exigindo políticas explícitas para domínios isolados."""

    form_class = modelform_factory(model, fields=fields)
    permissions = permissions or {}

    def allowed(user, action: str) -> bool:
        codes = {
            f"{permission_prefix}.{action}",
            f"{permission_prefix}.gerenciar",
            *permissions.get(action, ()),
        }
        return any(user.tem_permissao(code) for code in codes)

    def scoped(user):
        queryset = model.objects.all()
        return scope(user, queryset) if scope else queryset

    def make_form(user, *args, **kwargs):
        form = form_class(*args, **kwargs)
        if filter_form:
            filter_form(user, form)
        return form

    @login_required
    def lista(request):
        if not allowed(request.user, "listar") and not allowed(request.user, "criar") and not allowed(request.user, "editar"):
            raise PermissionDenied
        queryset = scoped(request.user)
        query_text = request.GET.get("q", "").strip()
        if query_text:
            searchable = [
                field.name
                for field in model._meta.fields
                if field.name in {"nome", "titulo", "descricao", "slug"}
            ]
            query = Q()
            for name in searchable:
                query |= Q(**{f"{name}__icontains": query_text})
            queryset = queryset.filter(query)
        return render(
            request,
            "painel/domain/list.html",
            {
                "titulo": model._meta.verbose_name_plural.title(),
                "objetos": queryset,
                "novo_url": reverse(
                    f"painel:{model._meta.app_label}_{model._meta.model_name}_novo"
                ),
            },
        )

    @login_required
    def novo(request):
        if not allowed(request.user, "criar"):
            raise PermissionDenied
        form = make_form(request.user, request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if hasattr(obj, "autor_id") and not obj.autor_id:
                    obj.autor = request.user
                if hasattr(obj, "usuario_responsavel_id") and not obj.usuario_responsavel_id:
                    obj.usuario_responsavel = request.user
                if hasattr(obj, "responsavel_id") and not obj.responsavel_id:
                    obj.responsavel = request.user
                if ownership and not ownership(request.user, obj):
                    raise PermissionDenied
                status = getattr(obj, "status", None)
                if status in {"PUBLICADO", "PUBLICADA", "AO_VIVO", "EM_ANDAMENTO"} and not allowed(request.user, "publicar"):
                    form.add_error("status", "Seu perfil pode criar conteúdo, mas não publicá-lo diretamente.")
                    return render(request, "painel/domain/form.html", {"titulo": f"Novo {model._meta.verbose_name}", "form": form})
                if validate_transition:
                    validate_transition(request.user, None, status, obj)
                obj.save()
                auditar(request, "CRIAR", obj, depois={"representacao": str(obj)})
            return redirect(
                f"painel:{model._meta.app_label}_{model._meta.model_name}_editar",
                uuid=obj.uuid,
            )
        return render(request, "painel/domain/form.html", {"titulo": f"Novo {model._meta.verbose_name}", "form": form})

    @login_required
    def editar(request, uuid):
        obj = get_object_or_404(scoped(request.user), uuid=uuid)
        if not allowed(request.user, "editar"):
            raise PermissionDenied
        if ownership and not ownership(request.user, obj):
            raise PermissionDenied
        previous_status = getattr(obj, "status", None)
        form = make_form(request.user, request.POST or None, request.FILES or None, instance=obj)
        if request.method == "POST" and form.is_valid():
            new_status = form.cleaned_data.get("status", previous_status)
            if new_status in {"PUBLICADO", "PUBLICADA", "AO_VIVO", "EM_ANDAMENTO"} and not allowed(request.user, "publicar"):
                form.add_error("status", "Seu perfil não pode publicar diretamente.")
                return render(request, "painel/domain/form.html", {"titulo": f"Editar {model._meta.verbose_name}", "form": form, "objeto": obj})
            if validate_transition:
                validate_transition(request.user, previous_status, new_status, obj)
            candidate = form.save(commit=False)
            if ownership and not ownership(request.user, candidate):
                raise PermissionDenied
            with transaction.atomic():
                if new_status in {"EM_REVISAO", "APROVADO"} and hasattr(candidate, "revisor_id"):
                    candidate.revisor = request.user
                if new_status in {"EM_REVISAO", "APROVADO"} and hasattr(candidate, "revisado_por_id"):
                    candidate.revisado_por = request.user
                if new_status in {"PUBLICADO", "PUBLICADA", "AO_VIVO", "EM_ANDAMENTO"} and hasattr(candidate, "publicador_id"):
                    candidate.publicador = request.user
                candidate.save()
                action = "PUBLICAR" if new_status in {"PUBLICADO", "PUBLICADA", "AO_VIVO", "EM_ANDAMENTO"} and previous_status != new_status else "ALTERAR_STATUS" if previous_status != new_status else "EDITAR"
                auditar(request, action, candidate, antes={"status": previous_status}, depois={"status": new_status})
            return redirect(request.path)
        return render(request, "painel/domain/form.html", {"titulo": f"Editar {model._meta.verbose_name}", "form": form, "objeto": obj})

    return lista, novo, editar
