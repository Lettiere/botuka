from django.core.management.base import BaseCommand
from apps.core.models import Perfil, Permissao, PerfilPermissao

ROLES = {
    'ROOT': ['*'], 'MASTER': ['*'], 'MODERADOR_GERAL': ['moderacao.gerenciar'],
    'ESPORTES_GESTOR': ['sports.gerenciar', 'sports.publicar'], 'ESPORTES_EDITOR': ['sports.criar', 'sports.editar'],
    'CLUBE_GESTOR': ['sports.clube.gerenciar'], 'EQUIPE_GESTOR': ['sports.equipe.gerenciar'],
    'ARBITRO': ['sports.disputa.arbitrar'], 'MESARIO': ['sports.disputa.registrar'], 'ATLETA': ['sports.atleta.editar'],
    'YTV_GESTOR': ['media.gerenciar', 'media.publicar'], 'YTV_PRODUTOR': ['media.criar', 'media.editar'],
    'YTV_APRESENTADOR': ['media.apresentar'], 'YTV_EDITOR': ['media.editar'], 'YTV_OPERADOR_TRANSMISSAO': ['media.transmitir'],
    'NEWS_EDITOR_CHEFE': ['news.gerenciar', 'news.publicar'], 'NEWS_EDITOR': ['news.editar', 'news.publicar'],
    'NEWS_REPORTER': ['news.criar'], 'NEWS_REVISOR': ['news.revisar'],
    'PREFEITURA_GESTOR': ['government.gerenciar', 'government.publicar'],
    'PREFEITURA_EDITOR': ['government.criar', 'government.editar'], 'PREFEITURA_REVISOR': ['government.revisar'],
}

class Command(BaseCommand):
    help = 'Registra perfis e permissões dos módulos da cidade.'
    def handle(self, *args, **options):
        all_codes = sorted({c for codes in ROLES.values() for c in codes if c != '*'})
        perms = {c: Permissao.objects.update_or_create(codigo=c, defaults={'nome': c, 'descricao': c, 'ativo': True})[0] for c in all_codes}
        for role, codes in ROLES.items():
            perfil = Perfil.objects.update_or_create(nome=role, defaults={'descricao': role, 'ativo': True})[0]
            for code in (all_codes if codes == ['*'] else codes):
                PerfilPermissao.objects.update_or_create(perfil=perfil, permissao=perms[code], defaults={'ativo': True})
        self.stdout.write(self.style.SUCCESS('Perfis e permissões sincronizados.'))
