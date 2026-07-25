import re

from django.core.exceptions import ValidationError


def normalizar_cpf(value):
    return re.sub(r'\D', '', value or '')


def cpf_valido(value):
    cpf = normalizar_cpf(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * ((tamanho + 1) - i) for i in range(tamanho))
        digito = 11 - (soma % 11)
        if digito >= 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False
    return True


def validar_cpf(value):
    if value and not cpf_valido(value):
        raise ValidationError('Informe um CPF válido.')
