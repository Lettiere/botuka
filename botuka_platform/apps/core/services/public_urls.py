"""Construção central e segura de URLs públicas."""

import ipaddress
from urllib.parse import urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import DisallowedHost


def _canonical_base_url() -> str:
    """Retorna a origem pública configurada, se ela for uma URL HTTP(S) válida."""

    raw = str(
        getattr(settings, "PUBLIC_BASE_URL", "")
        or getattr(settings, "SITE_URL", "")
        or ""
    ).strip()
    if not raw:
        return ""

    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("PUBLIC_BASE_URL/SITE_URL deve ser uma URL HTTP(S) válida.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("PUBLIC_BASE_URL/SITE_URL contém uma porta inválida.") from exc
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))


def _is_loopback(hostname: str) -> bool:
    host = (hostname or "").rstrip(".").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_public_absolute_url(request, value) -> str:
    """Retorna uma URL pública absoluta usando o host canônico configurado."""

    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlsplit(raw)

    if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.hostname:
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("A URL pública contém uma porta inválida.") from exc
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("A URL pública não pode conter credenciais.")
        return raw

    if parsed.scheme or parsed.netloc:
        raise ValueError("A URL pública deve usar HTTP(S) ou um caminho local.")

    path = raw if raw.startswith("/") else f"/{raw}"

    if request is None:
        return path

    base_url = _canonical_base_url()
    canonical_host = urlsplit(base_url).hostname if base_url else ""
    request_netloc = ""
    try:
        request_host = request.get_host()
        request_hostname = urlsplit(f"//{request_host}").hostname or ""
        request_netloc = request_host
    except (DisallowedHost, ValueError):
        forwarded = request.META.get("HTTP_X_FORWARDED_HOST", "")
        raw_host = (
            forwarded
            if getattr(settings, "USE_X_FORWARDED_HOST", False) and forwarded
            else request.META.get("HTTP_HOST", "")
        )
        try:
            raw_parsed = urlsplit(f"//{raw_host}")
            request_hostname = raw_parsed.hostname or ""
            raw_parsed.port
            request_netloc = raw_host if _is_loopback(request_hostname) else ""
        except ValueError:
            request_hostname = request_netloc = ""

    # Loopback é uma origem pública válida durante o desenvolvimento. Fora dele,
    # somente o host canônico pode ser refletido em metadados, QR codes e shares.
    if _is_loopback(request_hostname) or (
        canonical_host
        and request_hostname.rstrip(".").lower() == canonical_host.rstrip(".").lower()
    ):
        if request_netloc and _is_loopback(request_hostname):
            absolute = urlunsplit((request.scheme, request_netloc, path, "", ""))
        else:
            absolute = request.build_absolute_uri(path)
    elif base_url:
        absolute = urljoin(base_url, path.lstrip("/"))
    else:
        return path

    parsed_absolute = urlsplit(absolute)

    return urlunsplit(
        (
            parsed_absolute.scheme,
            parsed_absolute.netloc,
            parsed_absolute.path,
            parsed_absolute.query,
            "",
        )
    )
