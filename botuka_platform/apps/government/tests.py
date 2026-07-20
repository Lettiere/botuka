from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.core.domain import EditorialStatus
from apps.government.models import OrgaoPublico,OrgaoUsuario,AcaoPublica,AcaoAtualizacao

class GovernmentTests(TestCase):
    def setUp(self):
        U=get_user_model();self.gestor=U.objects.create_user('gestor',password='x');self.outro=U.objects.create_user('outro',password='x');self.orgao=OrgaoPublico.objects.create(tipo=OrgaoPublico.Tipo.PREFEITURA,nome='Prefeitura de Botucatu');OrgaoUsuario.objects.create(orgao=self.orgao,usuario=self.gestor,funcao=OrgaoUsuario.Funcao.GESTOR,gestor=True,pode_publicar=True)
    def acao(self,**kw):
        d=dict(orgao=self.orgao,autor=self.gestor,tipo=AcaoPublica.Tipo.PROJETO,titulo='Projeto futuro',descricao='Descrição oficial',cidade='Botucatu');d.update(kw);return AcaoPublica(**d)
    def test_orgao_nao_verificado_nao_publica(self):
        with self.assertRaises(ValidationError):self.acao(status=EditorialStatus.PUBLICADO).save()
    def test_oficial_publico_identificado(self):
        self.orgao.verificado=True;self.orgao.save();a=self.acao(status=EditorialStatus.PUBLICADO);a.save();r=self.client.get(reverse('government_public:acao',args=[a.slug]));self.assertEqual(r.status_code,200);self.assertContains(r,'Conteúdo oficial publicado por')
    def test_atualizacao(self):
        a=self.acao();a.save();u=AcaoAtualizacao.objects.create(acao=a,titulo='Etapa 1',descricao='Iniciada',percentual=10,data='2026-08-01',autor=self.gestor);self.assertEqual(u.percentual,10)
    def test_terceiro_nao_vinculado(self):self.assertFalse(OrgaoUsuario.objects.filter(orgao=self.orgao,usuario=self.outro).exists())
