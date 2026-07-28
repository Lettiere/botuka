"""Normalização e apresentação segura de telefones públicos."""

import re


def normalizar_telefone(numero, ddi_padrao='55'):
    raw = str(numero or '').strip()
    international = raw.startswith('+') or raw.startswith('00')
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if not international and len(digits) in (10, 11):
        digits = f'{ddi_padrao}{digits}'
    return digits if 10 <= len(digits) <= 15 else ''


def telefone_eh_celular(numero):
    digits = normalizar_telefone(numero)
    nacional = digits[2:] if digits.startswith('55') else digits
    return len(nacional) == 11 and nacional[2] == '9'


def formatar_telefone(numero):
    digits = normalizar_telefone(numero)
    if digits.startswith('55') and len(digits) in (12, 13):
        local = digits[2:]
        if len(local) == 11:
            return f'({local[:2]}) {local[2:7]}-{local[7:]}'
        return f'({local[:2]}) {local[2:6]}-{local[6:]}'
    return f'+{digits}' if digits else ''


def telefone_para_whatsapp(numero):
    digits = normalizar_telefone(numero)
    return f'https://wa.me/{digits}' if digits and telefone_eh_celular(digits) else ''
