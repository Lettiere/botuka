import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


CAPACIDADES = (
    'PRESTAR_SERVICOS', 'VENDER_PRODUTOS', 'PUBLICAR_VAGAS', 'PUBLICAR_ARTIGOS',
    'PUBLICAR_NOTICIAS', 'PUBLICAR_EVENTOS', 'PUBLICAR_CULTURA', 'PUBLICAR_TURISMO',
    'PUBLICAR_COMUNICADOS', 'PUBLICAR_ACOES_PUBLICAS', 'PUBLICAR_ESPORTES',
    'GERENCIAR_CLUBE', 'GERENCIAR_ATLETAS', 'GERENCIAR_CAMPEONATOS',
    'REGISTRAR_JOGOS', 'REGISTRAR_RESULTADOS', 'HOMOLOGAR_RESULTADOS',
    'PUBLICAR_YTV', 'GERENCIAR_CANAL_YTV', 'GERENCIAR_EQUIPE', 'RECEBER_LEADS',
)

FUNCOES = (
    'PROPRIETARIO', 'ADMINISTRADOR_INSTITUCIONAL', 'GESTOR', 'EDITOR', 'REVISOR',
    'COLABORADOR', 'MARKETING', 'RH', 'FINANCEIRO', 'ATLETA', 'TECNICO',
    'ARBITRO', 'ORGANIZADOR', 'MIDIA',
)


def seed(apps, schema_editor):
    Capacidade = apps.get_model('organizations', 'Capacidade')
    EmpresaFuncao = apps.get_model('organizations', 'EmpresaFuncao')
    for codigo in CAPACIDADES:
        nome = codigo.replace('_', ' ').title()
        Capacidade.objects.update_or_create(codigo=codigo, defaults={'nome': nome, 'descricao': nome, 'exige_aprovacao': True, 'ativo': True})
    for codigo in FUNCOES:
        nome = codigo.replace('_', ' ').title()
        EmpresaFuncao.objects.update_or_create(codigo=codigo, defaults={'nome': nome, 'descricao': nome, 'ativo': True})


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_seed_papeis_globais'),
        ('core', '0004_auditoria_fundacao_autorizacao'),
        ('organizations', '0012_assinatura_limite_servicos_contratado'),
    ]

    operations = [
        migrations.AddField(model_name='empresa', name='tipo_organizacao', field=models.CharField(choices=[('EMPRESA_PRIVADA','Empresa privada'),('PROFISSIONAL','Profissional'),('ASSOCIACAO','Associação'),('ONG','ONG'),('CLUBE','Clube'),('ORGANIZADOR_ESPORTIVO','Organizador esportivo'),('INSTITUICAO_ENSINO','Instituição de ensino'),('ORGAO_PUBLICO','Órgão público'),('SECRETARIA','Secretaria'),('PREFEITURA','Prefeitura'),('AUTARQUIA','Autarquia'),('FUNDACAO','Fundação'),('MIDIA','Mídia'),('CANAL_YTV','Canal YTV'),('PARCEIRO_OFICIAL','Parceiro oficial'),('OUTRO','Outro')], db_column='platform_empresa_tipo_organizacao', default='EMPRESA_PRIVADA', max_length=30, verbose_name='tipo de organização')),
        migrations.AddField(model_name='empresa', name='status_institucional', field=models.CharField(choices=[('COMUM','Comum'),('EM_ANALISE','Em análise'),('INSTITUCIONAL','Institucional'),('OFICIAL','Oficial'),('SUSPENSA','Suspensa')], db_column='platform_empresa_status_institucional', default='COMUM', max_length=20, verbose_name='status institucional')),
        migrations.AddField(model_name='empresa', name='institucional', field=models.BooleanField(db_column='platform_empresa_institucional', default=False)),
        migrations.AddField(model_name='empresa', name='oficial', field=models.BooleanField(db_column='platform_empresa_oficial', default=False)),
        migrations.AddField(model_name='empresa', name='parceira_oficial', field=models.BooleanField(db_column='platform_empresa_parceira_oficial', default=False)),
        migrations.AddField(model_name='empresa', name='selo_oficial', field=models.BooleanField(db_column='platform_empresa_selo_oficial', default=False)),
        migrations.AddField(model_name='empresa', name='verificada_institucionalmente', field=models.BooleanField(db_column='platform_empresa_verificada_institucional', default=False)),
        migrations.AddField(model_name='empresa', name='autorizada_em', field=models.DateTimeField(blank=True, db_column='platform_empresa_autorizada_em', null=True)),
        migrations.AddField(model_name='empresa', name='observacao_institucional', field=models.TextField(blank=True, db_column='platform_empresa_observacao_institucional')),
        migrations.AddField(model_name='empresa', name='autorizada_por', field=models.ForeignKey(blank=True, db_column='platform_empresa_autorizada_por_fk', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='empresas_institucionais_autorizadas', to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name='empresausuario', name='funcao', field=models.CharField(choices=[('PROPRIETARIO','Proprietário'),('ADMINISTRADOR','Administrador'),('ADMINISTRADOR_INSTITUCIONAL','Administrador institucional'),('GERENTE','Gerente'),('GESTOR','Gestor'),('EDITOR','Editor'),('REVISOR','Revisor'),('COLABORADOR','Colaborador'),('ATENDENTE','Atendente'),('MARKETING','Marketing'),('RH','Recursos humanos'),('FINANCEIRO','Financeiro'),('ATLETA','Atleta'),('TECNICO','Técnico'),('ARBITRO','Árbitro'),('ORGANIZADOR','Organizador'),('MIDIA','Mídia')], db_column='platform_empresa_usuario_funcao', default='COLABORADOR', max_length=40, verbose_name='função')),
        migrations.AddField(model_name='empresausuario', name='entrou_em', field=models.DateTimeField(db_column='platform_empresa_usuario_entrou_em', default=django.utils.timezone.now)),
        migrations.AddField(model_name='empresausuario', name='escopo', field=models.CharField(choices=[('PROPRIO','Próprio'),('EQUIPE','Equipe'),('ORGANIZACAO','Organização'),('GLOBAL','Global')], db_column='platform_empresa_usuario_escopo', default='ORGANIZACAO', max_length=20)),
        migrations.AddField(model_name='empresausuario', name='observacoes', field=models.TextField(blank=True, db_column='platform_empresa_usuario_observacoes')),
        migrations.AddField(model_name='empresausuario', name='convidado_por', field=models.ForeignKey(blank=True, db_column='platform_empresa_usuario_convidado_por_fk', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='membros_empresa_convidados', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='empresausuario', name='autorizado_por', field=models.ForeignKey(blank=True, db_column='platform_empresa_usuario_autorizado_por_fk', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='membros_empresa_autorizados', to=settings.AUTH_USER_MODEL)),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
