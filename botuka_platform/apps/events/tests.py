from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.organizations.models import Empresa, EmpresaUsuario

from .forms import EventoForm
from .models import Evento, HistoricoEvento, InteresseEvento


class EventTestMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='events@example.com', email='events@example.com', password='safe-test-pass',
        )
        self.other = get_user_model().objects.create_user(
            username='other@example.com', email='other@example.com', password='safe-test-pass',
        )

    def grant(self, user, *codes):
        access, _ = AcessoModulo.objects.get_or_create(
            usuario=user, modulo='events',
            defaults={'concedido_por': self.user, 'justificativa': 'Teste automatizado'},
        )
        for code in codes:
            permission = Permissao.objects.get(codigo=code)
            ConcessaoPermissao.objects.get_or_create(
                usuario=user, permissao=permission,
                defaults={'acesso': access, 'concedida_por': self.user, 'justificativa': 'Teste automatizado'},
            )
        return access

    def event(self, **overrides):
        data = {
            'titulo': 'Festival local', 'resumo': 'Evento público real.',
            'descricao': 'Descrição pública.', 'inicio': timezone.now() + timedelta(days=3),
            'local': 'Centro', 'proprietario': self.user,
            'responsavel_edicao': self.user, 'criador_registro': self.user,
            'status': Evento.Status.PUBLICADO, 'publico': True, 'permitir_interesse': True,
        }
        data.update(overrides)
        return Evento.objects.create(**data)


class EventPermissionTests(EventTestMixin, TestCase):
    def test_user_without_permission_gets_403(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('painel:eventos_lista')).status_code, 403)

    def test_granted_permission_applies_and_revocation_blocks_next_request(self):
        access = self.grant(self.user, 'events.acessar')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('painel:eventos_lista')).status_code, 200)
        access.status = AcessoModulo.Status.SUSPENSO
        access.save()
        self.assertEqual(self.client.get(reverse('painel:eventos_lista')).status_code, 403)

    def test_anonymous_panel_user_is_sent_to_login(self):
        response = self.client.get(reverse('painel:eventos_lista'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)

    def test_company_scope_uses_official_relationship(self):
        self.grant(self.user, 'events.acessar', 'events.criar_empresa')
        allowed = Empresa.objects.create(nome_fantasia='Permitida', usuario_proprietario=self.user)
        denied = Empresa.objects.create(nome_fantasia='Negada', usuario_proprietario=self.other)
        EmpresaUsuario.objects.create(empresa=allowed, usuario=self.user, administrador=True)
        form = EventoForm(user=self.user)
        self.assertIn(allowed, form.fields['empresa_promotora'].queryset)
        self.assertNotIn(denied, form.fields['empresa_promotora'].queryset)

    def test_common_user_cannot_transfer_owner(self):
        self.grant(self.user, 'events.acessar', 'events.criar_proprio')
        form = EventoForm(data={
            'titulo': 'Tentativa', 'resumo': 'Resumo suficiente', 'descricao': 'Descrição',
            'inicio': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'local': 'Centro', 'publico': True, 'proprietario': self.other.pk,
            'responsavel_edicao': self.other.pk, 'permitir_interesse': True,
            'modalidade_participacao_futura': 'NAO_DEFINIDA',
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('proprietario', form.errors)


class EventInterestTests(EventTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.evento = self.event()
        self.client.force_login(self.user)

    def toggle(self):
        return self.client.post(reverse('events:interesse', args=[self.evento.slug]))

    def test_interest_toggle_has_no_duplicate_and_keeps_history(self):
        self.assertEqual(self.toggle().status_code, 302)
        self.assertEqual(self.toggle().status_code, 302)
        self.assertEqual(InteresseEvento.objects.filter(evento=self.evento, usuario=self.user).count(), 1)
        item = InteresseEvento.objects.get(evento=self.evento, usuario=self.user)
        self.assertFalse(item.ativo)
        self.assertIsNotNone(item.cancelado_em)
        self.assertEqual(HistoricoEvento.objects.filter(evento=self.evento).count(), 2)

    def test_get_never_changes_interest(self):
        response = self.client.get(reverse('events:interesse', args=[self.evento.slug]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(InteresseEvento.objects.exists())

    def test_frontend_user_id_is_ignored(self):
        self.client.post(reverse('events:interesse', args=[self.evento.slug]), {'usuario': self.other.pk})
        self.assertTrue(InteresseEvento.objects.filter(usuario=self.user).exists())
        self.assertFalse(InteresseEvento.objects.filter(usuario=self.other).exists())

    def test_draft_private_ended_or_disabled_event_rejects_interest(self):
        for values in (
            {'status': Evento.Status.RASCUNHO},
            {'publico': False},
            {'inicio': timezone.now() - timedelta(hours=1)},
            {'permitir_interesse': False},
        ):
            event = self.event(titulo=f"Evento {len(Evento.objects.all())}", **values)
            response = self.client.post(reverse('events:interesse', args=[event.slug]))
            self.assertIn(response.status_code, (403, 404))

    def test_anonymous_interest_preserves_return_url(self):
        self.client.logout()
        url = reverse('events:interesse', args=[self.evento.slug])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)

    def test_public_page_shows_count_but_not_people(self):
        InteresseEvento.objects.create(evento=self.evento, usuario=self.other)
        response = Client().get(self.evento.get_absolute_url())
        self.assertContains(response, '1 pessoa demonstraram interesse')
        self.assertNotContains(response, self.other.email)
        self.assertNotContains(response, self.other.get_full_name())
        self.assertNotContains(response, 'checkout', status_code=200)

    def test_interest_does_not_create_ticket_registration_or_reservation(self):
        self.toggle()
        installed_models = {model.__name__ for model in Evento._meta.apps.get_models()}
        self.assertNotIn('Ingresso', installed_models)
        self.assertNotIn('InscricaoConfirmada', installed_models)
        self.assertNotIn('PresencaConfirmada', installed_models)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('events:interesse', args=[self.evento.slug])).status_code, 403)
