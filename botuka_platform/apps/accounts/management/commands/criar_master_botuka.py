"""Cria ou atualiza, de forma segura, um usuário MASTER."""

from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.master_services import garantir_usuario_master


class Command(BaseCommand):
    help = 'Cria ou atualiza um usuário MASTER solicitando a senha de forma oculta.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='E-mail do usuário MASTER.')
        parser.add_argument('--username', help='Username; por padrão, utiliza o e-mail.')

    def handle(self, *args, **options):
        senha = getpass('Senha: ')
        confirmacao = getpass('Confirme a senha: ')
        if not senha or senha != confirmacao:
            raise CommandError('As senhas não coincidem ou estão vazias.')
        try:
            validate_password(senha)
        except ValidationError as exc:
            raise CommandError('Senha inválida: ' + ' '.join(exc.messages)) from exc

        _usuario, criado = garantir_usuario_master(
            email=options['email'],
            username=options.get('username'),
            senha=senha,
        )
        estado = 'criado' if criado else 'atualizado'
        self.stdout.write(self.style.SUCCESS(f'Usuário MASTER {estado} com sucesso.'))
