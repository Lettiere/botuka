from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.services.models import (
    AreaProfissional,
    Profissao,
    ProfissaoTipoServico,
    Setor,
    TipoServico,
)


class TaxonomiaSugestoesEndpointTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(username='sugestor')
        self.other = users.objects.create_user(username='outro-sugestor')
        self.client.force_login(self.user)
        self.setor = Setor.objects.create(nome='Tecnologia aprovada')
        self.area = AreaProfissional.objects.create(setor=self.setor, nome='Desenvolvimento')
        self.profissao = Profissao.objects.create(
            setor=self.setor, area=self.area, nome='Desenvolvedor',
        )

    def post(self, name, data):
        return self.client.post(
            reverse(f'painel:{name}'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_usuario_cria_e_reaproveita_proprio_setor_pendente(self):
        first = self.post('servicos_sugerir_setor', {'nome': '  Saúde   Integrada '})
        self.assertEqual(first.status_code, 201)
        item = Setor.objects.get(pk=first.json()['item']['id'])
        self.assertEqual(item.origem, Setor.Origem.USUARIO)
        self.assertEqual(item.status_catalogo, Setor.StatusCatalogo.PENDENTE)
        self.assertEqual(item.criado_por, self.user)
        second = self.post('servicos_sugerir_setor', {'nome': 'saude integrada'})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['item']['id'], item.pk)
        self.assertFalse(second.json()['created'])

    def test_nome_normalizado_aprovado_e_reutilizado(self):
        approved = Setor.objects.create(nome='Educação Pública')
        response = self.post('servicos_sugerir_setor', {'nome': ' educacao  publica '})
        self.assertEqual(response.json()['item']['id'], approved.pk)
        self.assertEqual(response.json()['status_catalogo'], Setor.StatusCatalogo.APROVADO)

    def test_pendente_de_outro_usuario_nao_e_reutilizado(self):
        alien = Setor.objects.create(
            nome='Mobilidade Urbana', origem=Setor.Origem.USUARIO,
            status_catalogo=Setor.StatusCatalogo.PENDENTE, criado_por=self.other,
        )
        response = self.post('servicos_sugerir_setor', {'nome': 'mobilidade urbana '})
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()['item']['id'], alien.pk)
        self.assertEqual(Setor.objects.filter(nome_normalizado='mobilidade urbana').count(), 2)

    def test_area_exige_setor_valido_e_nao_aceita_pendente_alheio(self):
        invalid = self.post('servicos_sugerir_area', {'nome': 'Área nova'})
        self.assertEqual(invalid.status_code, 400)
        alien = Setor.objects.create(
            nome='Setor alheio', origem=Setor.Origem.USUARIO,
            status_catalogo=Setor.StatusCatalogo.PENDENTE, criado_por=self.other,
        )
        blocked = self.post('servicos_sugerir_area', {'nome': 'Área nova', 'setor_id': alien.pk})
        self.assertEqual(blocked.status_code, 400)
        self.assertFalse(AreaProfissional.objects.filter(nome='Área nova').exists())

    def test_area_e_criada_no_setor_atual(self):
        response = self.post(
            'servicos_sugerir_area', {'nome': 'Infraestrutura', 'setor_id': self.setor.pk},
        )
        area = AreaProfissional.objects.get(pk=response.json()['item']['id'])
        self.assertEqual(area.setor, self.setor)
        self.assertEqual(area.criado_por, self.user)

    def test_profissao_exige_hierarquia_coerente(self):
        other_sector = Setor.objects.create(nome='Outro setor aprovado')
        response = self.post('servicos_sugerir_profissao', {
            'nome': 'Arquiteto de software', 'setor_id': other_sector.pk,
            'area_id': self.area.pk,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Profissao.objects.filter(nome='Arquiteto de software').exists())

    def test_profissao_e_criada_com_setor_e_area(self):
        response = self.post('servicos_sugerir_profissao', {
            'nome': 'Arquiteto de software', 'setor_id': self.setor.pk,
            'area_id': self.area.pk,
        })
        profissao = Profissao.objects.get(pk=response.json()['item']['id'])
        self.assertEqual((profissao.setor, profissao.area), (self.setor, self.area))

    def test_tipo_global_existente_cria_relacao_sem_duplicar_tipo(self):
        tipo = TipoServico.objects.create(nome='Consultoria técnica')
        response = self.post('servicos_sugerir_tipo', {
            'nome': ' consultoria tecnica ', 'profissao_id': self.profissao.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['item']['id'], tipo.pk)
        self.assertTrue(response.json()['relationship_created'])
        self.assertEqual(TipoServico.objects.filter(nome_normalizado='consultoria tecnica').count(), 1)
        relation = ProfissaoTipoServico.objects.get(profissao=self.profissao, tipo_servico=tipo)
        self.assertEqual(relation.status_catalogo, relation.StatusCatalogo.PENDENTE)
        self.assertEqual(relation.criado_por, self.user)

    def test_tipo_novo_cria_tipo_e_relacao_pendentes(self):
        response = self.post('servicos_sugerir_tipo', {
            'nome': 'Auditoria especializada', 'profissao_id': self.profissao.pk,
        })
        self.assertEqual(response.status_code, 201)
        tipo = TipoServico.objects.get(pk=response.json()['item']['id'])
        relation = ProfissaoTipoServico.objects.get(profissao=self.profissao, tipo_servico=tipo)
        self.assertEqual(tipo.status_catalogo, tipo.StatusCatalogo.PENDENTE)
        self.assertEqual(relation.status_catalogo, relation.StatusCatalogo.PENDENTE)

    def test_endpoints_exigem_autenticacao_e_post(self):
        names = (
            'servicos_sugerir_setor', 'servicos_sugerir_area',
            'servicos_sugerir_profissao', 'servicos_sugerir_tipo',
        )
        for name in names:
            with self.subTest(name=name, method='GET'):
                self.assertEqual(self.client.get(reverse(f'painel:{name}')).status_code, 405)
        self.client.logout()
        for name in names:
            with self.subTest(name=name, authentication=False):
                self.assertEqual(self.client.post(reverse(f'painel:{name}')).status_code, 302)

    def test_json_de_erro_e_sucesso_e_claro(self):
        error = self.post('servicos_sugerir_setor', {'nome': '   '})
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error['Content-Type'], 'application/json')
        self.assertFalse(error.json()['success'])
        success = self.post('servicos_sugerir_setor', {'nome': 'Setor JSON'})
        self.assertTrue(success.json()['success'])
        self.assertEqual(set(success.json()['item']), {'id', 'text'})

    def test_post_sem_csrf_e_rejeitado(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse('painel:servicos_sugerir_setor'), {'nome': 'Sem token'},
        )
        self.assertEqual(response.status_code, 403)
