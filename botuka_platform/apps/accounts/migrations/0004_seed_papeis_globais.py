from django.db import migrations


PAPEIS = {
    'MASTER': 'Acesso raiz de negócio da plataforma BOTUKA.',
    'ADMIN_GLOBAL': 'Administração global limitada a permissões explicitamente delegadas.',
    'SUPORTE_GLOBAL': 'Suporte operacional sem acesso automático a dados sensíveis.',
    'AUDITOR_GLOBAL': 'Auditoria global em modo somente leitura.',
}

PERMISSOES = {
    'institucional.gerenciar': 'Gerenciar identidade institucional delegada',
    'capacidades.gerenciar': 'Conceder e revogar capacidades delegadas',
    'auditoria.global.visualizar': 'Visualizar auditoria global',
    'papeis_globais.visualizar': 'Visualizar papéis globais',
    'ORGANIZACAO_VISUALIZAR': 'Visualizar organização',
    'ORGANIZACAO_EDITAR': 'Editar organização',
    'ORGANIZACAO_GERENCIAR_EQUIPE': 'Gerenciar equipe da organização',
    'ORGANIZACAO_CONVIDAR_MEMBRO': 'Convidar membro da organização',
    'ORGANIZACAO_REMOVER_MEMBRO': 'Remover membro da organização',
    'CONTEUDO_CRIAR': 'Criar conteúdo',
    'CONTEUDO_EDITAR_PROPRIO': 'Editar conteúdo próprio',
    'CONTEUDO_EDITAR_EQUIPE': 'Editar conteúdo da equipe',
    'CONTEUDO_REVISAR': 'Revisar conteúdo',
    'CONTEUDO_APROVAR': 'Aprovar conteúdo',
    'CONTEUDO_PUBLICAR': 'Publicar conteúdo',
    'CONTEUDO_DESPUBLICAR': 'Despublicar conteúdo',
    'CONTEUDO_ARQUIVAR': 'Arquivar conteúdo',
    'CONTEUDO_EXCLUIR': 'Excluir conteúdo',
    'EVENTO_CRIAR': 'Criar evento',
    'EVENTO_EDITAR': 'Editar evento',
    'EVENTO_PUBLICAR': 'Publicar evento',
    'VAGA_CRIAR': 'Criar vaga',
    'VAGA_EDITAR': 'Editar vaga',
    'VAGA_PUBLICAR': 'Publicar vaga',
    'ATLETA_GERENCIAR': 'Gerenciar atleta',
    'CLUBE_GERENCIAR': 'Gerenciar clube',
    'CAMPEONATO_CRIAR': 'Criar campeonato',
    'CAMPEONATO_EDITAR': 'Editar campeonato',
    'CAMPEONATO_PUBLICAR': 'Publicar campeonato',
    'JOGO_REGISTRAR': 'Registrar jogo',
    'RESULTADO_REGISTRAR': 'Registrar resultado',
    'RESULTADO_HOMOLOGAR': 'Homologar resultado',
    'YTV_CRIAR': 'Criar conteúdo YTV',
    'YTV_EDITAR': 'Editar conteúdo YTV',
    'YTV_PUBLICAR': 'Publicar conteúdo YTV',
    'PERMISSAO_DELEGAR': 'Delegar permissão organizacional',
}


def seed(apps, schema_editor):
    Perfil = apps.get_model('core', 'Perfil')
    Permissao = apps.get_model('core', 'Permissao')
    for nome, descricao in PAPEIS.items():
        Perfil._base_manager.update_or_create(nome=nome, defaults={'descricao': descricao, 'ativo': True, 'removido_em': None})
    for codigo, nome in PERMISSOES.items():
        Permissao._base_manager.update_or_create(codigo=codigo, defaults={'nome': nome, 'descricao': nome, 'ativo': True, 'removido_em': None})


class Migration(migrations.Migration):
    dependencies = [('accounts', '0003_usuario_biografia_usuario_cidade_usuario_cpf_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
