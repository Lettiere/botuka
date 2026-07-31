from django.db import migrations


PERMISSIONS = {
    'events.acessar': ('Acesso', 'Acessar Eventos', 'Abre o módulo e permite visualizar a navegação.', 10),
    'events.visualizar': ('Acesso', 'Visualizar eventos próprios', 'Lista eventos dentro do escopo autorizado.', 10),
    'events.criar_proprio': ('Conteúdo', 'Criar evento próprio', 'Cria evento em nome do próprio usuário.', 20),
    'events.criar_empresa': ('Conteúdo', 'Criar para empresa vinculada', 'Cria eventos somente para empresas gerenciáveis pelo usuário.', 20),
    'events.editar_proprios': ('Conteúdo', 'Editar eventos próprios', 'Edita registros dos quais é proprietário ou responsável.', 20),
    'events.editar_empresa': ('Conteúdo', 'Editar eventos da empresa', 'Edita eventos das empresas dentro do escopo.', 20),
    'events.atribuir_responsavel': ('Associação', 'Atribuir proprietário e responsável', 'Permite atribuir outro usuário autorizado.', 40),
    'events.enviar_analise': ('Fluxo', 'Enviar para análise', 'Envia um rascunho para moderação.', 20),
    'events.publicar': ('Fluxo', 'Publicar eventos', 'Torna público um evento aprovado.', 40),
    'events.moderar': ('Moderação', 'Moderar eventos', 'Visualiza todos os eventos no escopo de moderação.', 30),
    'events.aprovar': ('Moderação', 'Aprovar eventos', 'Aprova eventos enviados para análise.', 30),
    'events.rejeitar': ('Moderação', 'Rejeitar eventos', 'Rejeita eventos com acesso ao fluxo.', 30),
    'events.pausar': ('Fluxo', 'Pausar eventos', 'Retira temporariamente um evento da publicação.', 30),
    'events.arquivar': ('Fluxo', 'Arquivar eventos', 'Arquiva eventos sem apagar seu histórico.', 30),
    'events.restaurar': ('Fluxo', 'Restaurar eventos', 'Restaura um evento arquivado para rascunho.', 30),
    'events.excluir': ('Administração', 'Excluir eventos', 'Permite exclusão lógica controlada.', 40),
    'events.gerenciar_interessados': ('Interesse', 'Gerenciar interessados', 'Visualiza apenas dados limitados dos interessados.', 30),
    'events.visualizar_metricas': ('Interesse', 'Visualizar métricas', 'Visualiza totais e evolução real de interesses.', 20),
    'events.gerenciar_inscricoes': ('Futuro', 'Gerenciar inscrições futuras', 'Permissão reservada; inscrições internas ainda não existem.', 40),
    'events.gerenciar_ingressos': ('Futuro', 'Gerenciar ingressos futuros', 'Permissão reservada; checkout e ingressos ainda não existem.', 50),
}


def seed(apps, schema_editor):
    Permissao = apps.get_model('core', 'Permissao')
    for code, (group, name, description, criticality) in PERMISSIONS.items():
        Permissao.objects.update_or_create(
            codigo=code,
            defaults={
                'modulo': 'events', 'grupo': group, 'nome': name,
                'descricao': description, 'criticidade': criticality,
                'protegida': criticality >= 40, 'ativo': True, 'removido_em': None,
            },
        )


def unseed(apps, schema_editor):
    apps.get_model('core', 'Permissao').objects.filter(codigo__in=PERMISSIONS).update(ativo=False)


class Migration(migrations.Migration):
    dependencies = [('events', '0001_initial'), ('core', '0007_seed_access_management_permissions')]
    operations = [migrations.RunPython(seed, unseed)]
