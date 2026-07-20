"""Cria ou atualiza o usuário administrador MASTER."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from django.core.cache import cache

from apps.core.models import (
    ConfiguracaoSistema,
    ContatoInstitucional,
    Perfil,
    PerfilPermissao,
    Permissao,
)


class Command(BaseCommand):
    help = 'Garante perfil MASTER, permissões padrão e usuário administrador.'

    MASTER_EMAIL = 'master@botuka.com.br'
    DEFAULT_PERMISSIONS = (
        ('usuarios.visualizar', 'Visualizar usuários'),
        ('usuarios.criar', 'Criar usuários'),
        ('usuarios.editar', 'Editar usuários'),
        ('usuarios.desativar', 'Desativar usuários'),
        ('perfis.gerenciar', 'Gerenciar perfis e permissões'),
        ('organizacoes.gerenciar', 'Gerenciar organizações e unidades'),
        ('categorias.gerenciar', 'Gerenciar categorias e subcategorias'),
        ('localidades.gerenciar', 'Gerenciar localidades'),
        ('configuracoes.gerenciar', 'Gerenciar configurações'),
        ('painel.acessar', 'Acessar painel interno'),
        ('perfil.editar', 'Editar próprio perfil'),
        ('empresas.visualizar', 'Visualizar empresas'),
        ('empresas.criar', 'Criar empresas'),
        ('empresas.editar', 'Editar empresas'),
        ('publicacoes.visualizar', 'Visualizar publicações'),
        ('publicacoes.criar', 'Criar publicações'),
        ('servicos.visualizar', 'Visualizar serviços'),
        ('servicos.criar', 'Criar serviços'),
        ('produtos.visualizar', 'Visualizar produtos'),
        ('produtos.criar', 'Criar produtos'),
        ('vagas.visualizar', 'Visualizar vagas'),
        ('vagas.criar', 'Criar vagas'),
        ('curriculo.visualizar', 'Visualizar currículo'),
        ('curriculo.editar', 'Editar currículo'),
        ('eventos.visualizar', 'Visualizar eventos'),
        ('eventos.criar', 'Criar eventos'),
        ('rede_social.acessar', 'Acessar rede social'),
        ('mensagens.acessar', 'Acessar mensagens'),
        ('configuracoes.editar', 'Editar configurações pessoais'),
        ('gestao.acessar', 'Acessar gestão'),
        ('contatos.visualizar', 'Visualizar contatos institucionais'),
        ('contatos.criar', 'Criar contatos institucionais'),
        ('contatos.editar', 'Editar contatos institucionais'),
        ('contatos.ativar', 'Ativar contatos institucionais'),
        ('contatos.excluir', 'Excluir contatos institucionais'),
    )
    SOCIAL_CONFIGS = (
        ('social.facebook_url', 'URL do Facebook'),
        ('social.instagram_url', 'URL do Instagram'),
        ('social.linkedin_url', 'URL do LinkedIn'),
        ('social.youtube_url', 'URL do YouTube'),
        ('social.tiktok_url', 'URL do TikTok'),
    )
    INITIAL_CONTACTS = (
        {
            'tipo': ContatoInstitucional.Tipo.WHATSAPP,
            'nome': 'WhatsApp BOTUKA',
            'valor': '11982301985',
            'icone': 'bi-whatsapp',
            'ordem': 1,
        },
        {
            'tipo': ContatoInstitucional.Tipo.TELEFONE,
            'nome': 'Telefone BOTUKA',
            'valor': '11982301985',
            'icone': 'bi-telephone',
            'ordem': 2,
        },
        {
            'tipo': ContatoInstitucional.Tipo.EMAIL,
            'nome': 'E-mail BOTUKA',
            'valor': 'contato@botuka.com.br',
            'icone': 'bi-envelope',
            'ordem': 3,
        },
    )

    def handle(self, *args, **options):
        perfil_master, _created = Perfil.all_objects.get_or_create(
            nome='MASTER',
            defaults={'descricao': 'Acesso total ao painel interno.'},
        )
        perfil_master.ativo = True
        perfil_master.removido_em = None
        perfil_master.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])

        for codigo, nome in self.DEFAULT_PERMISSIONS:
            permissao, _created = Permissao.all_objects.get_or_create(
                codigo=codigo,
                defaults={'nome': nome},
            )
            permissao.nome = nome
            permissao.ativo = True
            permissao.removido_em = None
            permissao.save(
                update_fields=['nome', 'ativo', 'removido_em', 'atualizado_em']
            )

            vinculo, _created = PerfilPermissao.all_objects.get_or_create(
                perfil=perfil_master,
                permissao=permissao,
            )
            vinculo.ativo = True
            vinculo.removido_em = None
            vinculo.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])

        for chave, descricao in self.SOCIAL_CONFIGS:
            ConfiguracaoSistema.all_objects.get_or_create(
                chave=chave,
                defaults={'valor': '', 'descricao': descricao},
            )

        for contato_data in self.INITIAL_CONTACTS:
            contato, _created = ContatoInstitucional.objects.get_or_create(
                tipo=contato_data['tipo'],
                valor=contato_data['valor'],
                defaults={
                    'nome': contato_data['nome'],
                    'icone': contato_data['icone'],
                    'ordem': contato_data['ordem'],
                    'ativo': True,
                    'exibir_topbar': True,
                    'exibir_rodape': True,
                },
            )
            contato.nome = contato_data['nome']
            contato.icone = contato_data['icone']
            contato.ordem = contato_data['ordem']
            contato.ativo = True
            contato.exibir_topbar = True
            contato.exibir_rodape = True
            contato.save()

        cache.delete('botuka_contatos_topbar')

        Usuario = get_user_model()
        usuario, created = Usuario.objects.get_or_create(
            username=self.MASTER_EMAIL,
            defaults={
                'email': self.MASTER_EMAIL,
                'first_name': 'Master',
                'last_name': 'BOTUKA',
            },
        )
        usuario.email = self.MASTER_EMAIL
        usuario.perfil = perfil_master
        usuario.is_active = True
        usuario.is_staff = True
        usuario.is_superuser = True
        senha_configurada = os.environ.get('BOTUKA_MASTER_PASSWORD')
        if senha_configurada:
            usuario.set_password(senha_configurada)
        elif created:
            usuario.set_unusable_password()
            self.stdout.write(self.style.WARNING(
                'Usuário MASTER criado sem senha utilizável. Defina '
                'BOTUKA_MASTER_PASSWORD e execute novamente para habilitar o acesso.'
            ))
        usuario.save()

        status = 'criado' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(f'Usuário master {status} com sucesso.'))
