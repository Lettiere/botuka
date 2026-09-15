from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import PROTECT
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.locations.models import Bairro, Cidade, Estado, Pais


class GestaoLocationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('locations-master', password='x')
        cls.operator = User.objects.create_user('locations-operator', password='x')
        cls.outsider = User.objects.create_user('locations-outsider', password='x')
        for module, code in (('gestao', 'gestao.acessar'), ('localidades', 'localidades.gerenciar')):
            access = AcessoModulo.objects.create(
                usuario=cls.operator, modulo=module, concedido_por=cls.master,
                justificativa='Teste de localidades',
            )
            permission, _ = Permissao.objects.get_or_create(
                codigo=code, defaults={'modulo': module, 'nome': code},
            )
            ConcessaoPermissao.objects.create(
                acesso=access, usuario=cls.operator, permissao=permission,
                concedida_por=cls.master, justificativa='Teste',
            )
        cls.country = Pais.objects.create(
            nome='Brasil Localidades', nome_oficial='República Federativa do Brasil',
            codigo_iso_2='BL', codigo_iso_3='BRL',
        )
        cls.state = Estado.objects.create(
            pais=cls.country, nome='São Paulo Localidades', sigla='SL', codigo_ibge='35',
        )
        cls.city = Cidade.objects.create(
            estado=cls.state, nome='Botucatu Localidades', codigo_ibge='3507506',
        )
        cls.neighborhood = Bairro.objects.create(cidade=cls.city, nome='Centro Localidades')

    def test_lists_search_filters_hierarchy_and_reverse(self):
        self.client.force_login(self.operator)
        cases = (
            ('paises', {'q': 'BL'}, self.country.nome),
            ('estados', {'pais': self.country.pk, 'q': 'SL'}, self.state.nome),
            ('cidades', {'pais': self.country.pk, 'estado': self.state.pk, 'q': '3507506'}, self.city.nome),
            ('bairros', {'pais': self.country.pk, 'estado': self.state.pk, 'cidade': 'Botucatu'}, self.neighborhood.nome),
        )
        for kind, params, expected in cases:
            with self.subTest(kind=kind):
                response = self.client.get(reverse(f'gestao:{kind}_lista'), {**params, 'ativo': '1'})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)
                self.assertEqual(self.client.get(reverse(
                    f'gestao:{kind}_detalhe', args=[getattr(self, {
                        'paises': 'country', 'estados': 'state',
                        'cidades': 'city', 'bairros': 'neighborhood',
                    }[kind]).pk],
                )).status_code, 200)

    def test_create_edit_normalization_and_duplicates(self):
        self.client.force_login(self.operator)
        response = self.client.post(reverse('gestao:paises_novo'), {
            'nome': 'Argentina Localidades', 'nome_oficial': '',
            'codigo_iso_2': 'ar', 'codigo_iso_3': 'arg', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('gestao:paises_lista'))
        country = Pais.objects.get(nome='Argentina Localidades')
        self.assertEqual((country.codigo_iso_2, country.codigo_iso_3), ('AR', 'ARG'))
        duplicate = self.client.post(reverse('gestao:paises_novo'), {
            'nome': 'Outro país', 'nome_oficial': '',
            'codigo_iso_2': 'AR', 'codigo_iso_3': 'ZZZ', 'ativo': 'on',
        })
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, 'já existe')
        response = self.client.post(reverse('gestao:estados_editar', args=[self.state.pk]), {
            'pais': self.country.pk, 'nome': self.state.nome,
            'sigla': 'sl', 'codigo_ibge': '35', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('gestao:estados_lista'))
        self.state.refresh_from_db()
        self.assertEqual(self.state.sigla, 'SL')

    def test_inactive_parent_is_rejected_on_create_but_preserved_on_edit(self):
        self.country.delete()
        self.client.force_login(self.operator)
        invalid = self.client.post(reverse('gestao:estados_novo'), {
            'pais': self.country.pk, 'nome': 'Estado inválido', 'sigla': 'EI',
            'codigo_ibge': '', 'ativo': 'on',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Faça uma escolha válida')
        preserved = self.client.post(reverse('gestao:estados_editar', args=[self.state.pk]), {
            'pais': self.country.pk, 'nome': 'Estado legado preservado',
            'sigla': 'SL', 'codigo_ibge': '35', 'ativo': 'on',
        })
        self.assertRedirects(preserved, reverse('gestao:estados_lista'))
        self.state.refresh_from_db()
        self.assertEqual(self.state.pais, self.country)

    def test_inactive_state_and_city_are_rejected_for_new_children_and_legacy_is_preserved(self):
        self.client.force_login(self.operator)
        self.state.delete()
        invalid_city = self.client.post(reverse('gestao:cidades_novo'), {
            'estado': self.state.pk, 'nome': 'Cidade inválida',
            'codigo_ibge': '', 'ativo': 'on',
        })
        self.assertContains(invalid_city, 'Faça uma escolha válida')
        preserved_city = self.client.post(reverse('gestao:cidades_editar', args=[self.city.pk]), {
            'estado': self.state.pk, 'nome': self.city.nome,
            'codigo_ibge': self.city.codigo_ibge, 'ativo': 'on',
        })
        self.assertRedirects(preserved_city, reverse('gestao:cidades_lista'))
        self.state.ativo = True
        self.state.removido_em = None
        self.state.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])
        self.city.delete()
        invalid_neighborhood = self.client.post(reverse('gestao:bairros_novo'), {
            'cidade': self.city.pk, 'nome': 'Bairro inválido', 'ativo': 'on',
        })
        self.assertContains(invalid_neighborhood, 'Faça uma escolha válida')
        preserved_neighborhood = self.client.post(reverse(
            'gestao:bairros_editar', args=[self.neighborhood.pk],
        ), {'cidade': self.city.pk, 'nome': self.neighborhood.nome, 'ativo': 'on'})
        self.assertRedirects(preserved_neighborhood, reverse('gestao:bairros_lista'))

    def test_hierarchy_foreign_keys_are_protected_and_child_duplicates_are_rejected(self):
        self.assertIs(Estado._meta.get_field('pais').remote_field.on_delete, PROTECT)
        self.assertIs(Cidade._meta.get_field('estado').remote_field.on_delete, PROTECT)
        self.assertIs(Bairro._meta.get_field('cidade').remote_field.on_delete, PROTECT)
        self.client.force_login(self.operator)
        cases = (
            ('estados_novo', {'pais': self.country.pk, 'nome': self.state.nome,
                              'sigla': 'XX', 'codigo_ibge': '', 'ativo': 'on'}),
            ('cidades_novo', {'estado': self.state.pk, 'nome': self.city.nome,
                              'codigo_ibge': '', 'ativo': 'on'}),
            ('bairros_novo', {'cidade': self.city.pk, 'nome': self.neighborhood.nome,
                              'ativo': 'on'}),
        )
        for url_name, data in cases:
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(f'gestao:{url_name}'), data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'já existe')

    def test_status_is_post_csrf_soft_and_reversible(self):
        self.client.force_login(self.operator)
        for kind, instance in (
            ('paises', self.country), ('estados', self.state),
            ('cidades', self.city), ('bairros', self.neighborhood),
        ):
            url = reverse(f'gestao:{kind}_status', args=[instance.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            self.client.post(url)
            instance.refresh_from_db()
            self.assertFalse(instance.ativo)
            self.assertIsNotNone(instance.removido_em)
            self.assertTrue(type(instance).all_objects.filter(pk=instance.pk).exists())
            self.client.post(url)
            instance.refresh_from_db()
            self.assertTrue(instance.ativo)
            self.assertIsNone(instance.removido_em)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.operator)
        self.assertEqual(csrf.post(reverse('gestao:paises_status', args=[self.country.pk])).status_code, 403)

    def test_child_cannot_be_reactivated_while_parent_is_inactive(self):
        self.state.delete()
        self.city.delete()
        self.client.force_login(self.operator)
        response = self.client.post(reverse('gestao:cidades_status', args=[self.city.pk]))
        self.assertRedirects(response, reverse('gestao:cidades_detalhe', args=[self.city.pk]))
        self.city.refresh_from_db()
        self.assertFalse(self.city.ativo)
        self.assertContains(
            self.client.get(reverse('gestao:cidades_detalhe', args=[self.city.pk])),
            'Inativo',
        )

    def test_permissions_pagination_and_bounded_queries(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('gestao:paises_lista')).status_code, 403)
        self.assertEqual(self.client.post(reverse('gestao:paises_status', args=[self.country.pk])).status_code, 403)
        Bairro.objects.bulk_create([
            Bairro(cidade=self.city, nome=f'Bairro página {index}') for index in range(26)
        ])
        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('gestao:bairros_lista'))
            self.assertTrue(response.context['page_obj'].has_next())
            self.assertEqual(len(response.context['page_obj'].object_list), 25)
        self.assertLessEqual(len(queries), 18)
