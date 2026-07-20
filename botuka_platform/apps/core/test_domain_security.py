from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.core.domain import validar_documento_publico, validar_imagem_publica
from apps.government.models import AcaoPublica, OrgaoPublico, OrgaoUsuario
from apps.sports.models import (
    Campeonato, Categoria, Disputa, Equipe, Estilo, Modalidade,
    OrganizacaoEsportiva, ParticipanteCampeonato,
)


def grant(user, role, *codes):
    profile = Perfil.objects.create(nome=role)
    user.perfil = profile
    user.save(update_fields=["perfil"])
    for code in codes:
        permission = Permissao.objects.create(codigo=code, nome=code)
        PerfilPermissao.objects.create(perfil=profile, permissao=permission)


class SportsIsolationHTTPTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("sports_owner", password="x")
        self.other = User.objects.create_user("sports_other", password="x")
        grant(self.owner, "CLUBE_GESTOR_HTTP", "sports.clube.gerenciar")
        self.modality = Modalidade.objects.create(nome="Modalidade HTTP")
        self.own_org = OrganizacaoEsportiva.objects.create(usuario_responsavel=self.owner, tipo="CLUBE", nome="Clube próprio", cidade="Botucatu")
        self.other_org = OrganizacaoEsportiva.objects.create(usuario_responsavel=self.other, tipo="CLUBE", nome="Clube terceiro", cidade="Botucatu")
        self.client.force_login(self.owner)

    def test_listagem_isola_organizacao(self):
        response = self.client.get(reverse("painel:sports_organizacaoesportiva_lista"))
        self.assertContains(response, "Clube próprio")
        self.assertNotContains(response, "Clube terceiro")

    def test_criacao_cross_tenant_e_fk_sao_bloqueadas(self):
        response = self.client.post(reverse("painel:sports_equipe_novo"), {
            "organizacao": self.other_org.pk, "modalidade": self.modality.pk,
            "nome": "Equipe invasora", "cidade": "Botucatu", "ativo": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Equipe.objects.filter(nome="Equipe invasora").exists())

    def test_rascunho_e_organizacao_nao_verificada_nao_sao_publicos(self):
        championship = Campeonato.objects.create(organizacao=self.own_org, modalidade=self.modality, nome="Copa privada", formato="Pontos", data_inicial=timezone.localdate())
        self.assertEqual(self.client.get(reverse("sports_public:campeonato", args=[championship.slug])).status_code, 404)
        championship.status = Campeonato.Status.AGENDADO
        championship.save()
        self.assertEqual(self.client.get(reverse("sports_public:campeonato", args=[championship.slug])).status_code, 404)
        self.own_org.verificado = True
        self.own_org.save()
        self.assertEqual(self.client.get(reverse("sports_public:campeonato", args=[championship.slug])).status_code, 200)


class GovernmentIsolationHTTPTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.editor = User.objects.create_user("gov_editor", password="x")
        self.other = User.objects.create_user("gov_other", password="x")
        grant(self.editor, "PREFEITURA_EDITOR_HTTP", "government.criar", "government.editar")
        self.own_org = OrgaoPublico.objects.create(tipo="SECRETARIA", nome="Órgão próprio")
        self.other_org = OrgaoPublico.objects.create(tipo="SECRETARIA", nome="Órgão terceiro")
        OrgaoUsuario.objects.create(orgao=self.own_org, usuario=self.editor, funcao="EDITOR", editor=True)
        self.own_action = AcaoPublica.objects.create(orgao=self.own_org, autor=self.editor, tipo="PROJETO", titulo="Ação própria", descricao="Descrição", cidade="Botucatu")
        AcaoPublica.objects.create(orgao=self.other_org, autor=self.other, tipo="PROJETO", titulo="Ação terceira", descricao="Descrição", cidade="Botucatu")
        self.client.force_login(self.editor)

    def test_listagem_isola_orgao(self):
        response = self.client.get(reverse("painel:government_acaopublica_lista"))
        self.assertContains(response, "Ação própria")
        self.assertNotContains(response, "Ação terceira")

    def test_criacao_em_orgao_terceiro_bloqueada(self):
        response = self.client.post(reverse("painel:government_acaopublica_novo"), {
            "orgao": self.other_org.pk, "tipo": "PROJETO", "titulo": "Ação invasora",
            "descricao": "Descrição", "cidade": "Botucatu", "situacao": "PLANEJADA",
            "status": "RASCUNHO", "ativo": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AcaoPublica.objects.filter(titulo="Ação invasora").exists())

    def test_publicacao_exige_permissao_e_vinculo_pode_publicar(self):
        permission = Permissao.objects.create(codigo="government.publicar", nome="government.publicar")
        PerfilPermissao.objects.create(perfil=self.editor.perfil, permissao=permission)
        self.own_org.verificado = True
        self.own_org.save()
        self.own_action.status = "APROVADO"
        self.own_action.save()
        payload = {
            "orgao": self.own_org.pk, "tipo": "PROJETO", "titulo": self.own_action.titulo,
            "resumo": "", "descricao": "Descrição", "objetivo": "", "publico_alvo": "",
            "local": "", "bairro": "", "cidade": "Botucatu", "inicio_previsto": "",
            "conclusao_prevista": "", "situacao": "PLANEJADA", "status": "PUBLICADO",
            "destaque": "", "ativo": "on",
        }
        url = reverse("painel:government_acaopublica_editar", args=[self.own_action.uuid])
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        vinculo = OrgaoUsuario.objects.get(orgao=self.own_org, usuario=self.editor)
        vinculo.pode_publicar = True
        vinculo.save()
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.own_action.refresh_from_db()
        self.assertEqual(self.own_action.status, "PUBLICADO")


class SportsHierarchyValidationTests(TestCase):
    def test_estilo_de_modalidade_diferente_e_rejeitado(self):
        first = Modalidade.objects.create(nome="Primeira modalidade")
        second = Modalidade.objects.create(nome="Segunda modalidade")
        style = Estilo.objects.create(modalidade=first, nome="Estilo divergente")
        with self.assertRaises(ValidationError):
            Categoria.objects.create(modalidade=second, estilo=style, nome="Categoria inválida")

    def test_participante_de_outro_campeonato_e_rejeitado_na_disputa(self):
        user = get_user_model().objects.create_user("sports_validation", password="x")
        modality = Modalidade.objects.create(nome="Modalidade de validação")
        org = OrganizacaoEsportiva.objects.create(usuario_responsavel=user, tipo="CLUBE", nome="Clube validação", cidade="Botucatu")
        team = Equipe.objects.create(organizacao=org, modalidade=modality, nome="Equipe validação", cidade="Botucatu")
        first = Campeonato.objects.create(organizacao=org, modalidade=modality, nome="Primeiro campeonato", formato="Pontos", data_inicial=timezone.localdate())
        second = Campeonato.objects.create(organizacao=org, modalidade=modality, nome="Segundo campeonato", formato="Pontos", data_inicial=timezone.localdate())
        participant = ParticipanteCampeonato.objects.create(campeonato=first, equipe=team)
        with self.assertRaises(ValidationError):
            Disputa.objects.create(campeonato=second, tipo="JOGO", participante_a=participant, data_hora=timezone.now())


class UploadSecurityTests(TestCase):
    def test_imagem_com_mime_ou_assinatura_falsos_e_rejeitada(self):
        fake_mime = SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\nresto", content_type="text/html")
        with self.assertRaises(ValidationError):
            validar_imagem_publica(fake_mime)
        fake_signature = SimpleUploadedFile("foto.png", b"<script>alert(1)</script>", content_type="image/png")
        with self.assertRaises(ValidationError):
            validar_imagem_publica(fake_signature)

    def test_documento_com_assinatura_falsa_e_rejeitado(self):
        fake = SimpleUploadedFile("edital.pdf", b"nao e pdf", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validar_documento_publico(fake)
