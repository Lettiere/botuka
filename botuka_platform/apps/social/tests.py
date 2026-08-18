import json
import tempfile
import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from apps.analytics.models import AnalyticsEvent
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa
from apps.organizations.permissions import (
    empresas_gerenciaveis_para_usuario, usuario_pode_editar_empresa,
    usuario_pode_publicar_por_empresa,
)

from .models import (
    EmpresaSeguidor, SocialBlock, SocialConversationRequest, SocialFollow,
    SocialFollowRequest, SocialPost, SocialPostComment, SocialPostLike,
    SocialPostSave, SocialProfile, SocialStory,
)
from .selectors import (
    contagem_seguidores_empresa, contagem_seguidores_perfil, posts_do_perfil,
    posts_visiveis_para, stories_ativos_para,
    empresas_sugeridas_para, seguidores_da_empresa, seguidores_do_perfil,
    perfis_sugeridos_para,
)
from .services import (
    bloquear_perfil, comentar_post, compartilhar_conteudo, criar_post, criar_story,
    curtir_post, decidir_follow_request, deixar_de_seguir_empresa,
    deixar_de_seguir_usuario, descurtir_post, get_or_create_social_profile,
    decidir_solicitacao_conversa, pode_ver_post, remover_post, remover_post_salvo,
    remover_story, salvar_post, seguir_empresa, seguir_usuario,
    sincronizar_perfil_publico, solicitar_ou_enviar_conversa,
)


@override_settings(ROOT_URLCONF='config.urls_social', LOGIN_URL='http://127.0.0.1:7700/conta/login/')
class SocialBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            'social-owner', password='x', nome_exibicao='Pessoa Social',
            email='private@example.com', telefone='11999999999', cpf='52998224725',
            biografia='Biografia pública', data_nascimento='1990-01-01',
        )
        cls.target = User.objects.create_user('social.target', password='x', first_name='Pessoa', last_name='Alvo')
        cls.third = User.objects.create_user('social-target', password='x')
        cls.owner_profile = get_or_create_social_profile(cls.owner)
        cls.target_profile = get_or_create_social_profile(cls.target)
        country = Pais.objects.create(nome='Brasil Social', codigo_iso_2='SS', codigo_iso_3='SOC')
        state = Estado.objects.create(pais=country, nome='Estado Social', sigla='SO')
        city = Cidade.objects.create(estado=state, nome='Cidade Social')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.target, nome_fantasia='Empresa Social',
            status=Empresa.Status.ATIVA, ativo=True, perfil_publico=True,
            cidade=city, estado=state,
        )


class SocialProfileTests(SocialBase):
    def test_cria_profile_para_usuario(self):
        self.assertEqual(get_or_create_social_profile(self.owner).pk, self.owner_profile.pk)

    def test_slug_unico_e_colisao_resolvida(self):
        third = get_or_create_social_profile(self.third)
        self.assertNotEqual(third.slug, self.target_profile.slug)

    def test_profile_nao_copia_dados_privados(self):
        values = vars(self.owner_profile)
        self.assertFalse({'email', 'telefone', 'cpf', 'endereco', 'data_nascimento'} & values.keys())

    def test_get_absolute_url(self):
        self.assertEqual(self.owner_profile.get_absolute_url(), f'/social/@{self.owner_profile.slug}/')

    def test_nome_publico_com_fallbacks(self):
        self.assertEqual(self.owner_profile.nome_publico, 'Pessoa Social')
        self.target_profile.nome_exibicao = ''
        self.target_profile.usuario.nome_exibicao = ''
        self.assertEqual(self.target_profile.nome_publico, 'Pessoa Alvo')

    @override_settings(ROOT_URLCONF='config.urls')
    def test_cadastro_cria_profile_explicitamente(self):
        response = self.client.post(reverse('accounts:cadastro'), {
            'nome': 'Nova Pessoa', 'email': 'nova@example.com',
            'password': 'Senha-forte-123', 'password_confirm': 'Senha-forte-123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SocialProfile.objects.filter(usuario__username='nova@example.com').exists())


class SocialFollowTests(SocialBase):
    def test_usuario_segue_outro(self):
        relation, created = seguir_usuario(self.owner, self.target_profile)
        self.assertTrue(created)
        self.assertEqual(relation.seguidor, self.owner_profile)

    def test_duplicidade_idempotente(self):
        seguir_usuario(self.owner, self.target_profile)
        _, created = seguir_usuario(self.owner, self.target_profile)
        self.assertFalse(created)
        self.assertEqual(SocialFollow.objects.count(), 1)

    def test_constraint_de_duplicidade(self):
        SocialFollow.objects.create(seguidor=self.owner_profile, seguido=self.target_profile)
        with self.assertRaises(IntegrityError):
            SocialFollow.objects.create(seguidor=self.owner_profile, seguido=self.target_profile)

    def test_auto_follow_bloqueado(self):
        with self.assertRaises(ValidationError):
            seguir_usuario(self.owner, self.owner_profile)

    def test_deixar_de_seguir(self):
        seguir_usuario(self.owner, self.target_profile)
        self.assertEqual(deixar_de_seguir_usuario(self.owner, self.target_profile), 1)
        self.assertFalse(SocialFollow.objects.exists())

    def test_anonimo_nao_segue_via_service(self):
        with self.assertRaises(PermissionDenied):
            seguir_usuario(AnonymousUser(), self.target_profile)

    def test_anonimo_nao_segue_via_view(self):
        response = self.client.post(reverse('social:follow_profile', args=[self.target_profile.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SocialFollow.objects.exists())

    def test_post_usa_request_user_como_ator(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('social:follow_profile', args=[self.target_profile.uuid]), {'usuario': self.third.pk})
        relation = SocialFollow.objects.get()
        self.assertEqual(relation.seguidor.usuario, self.owner)

    def test_get_nao_altera_estado(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('social:follow_profile', args=[self.target_profile.uuid]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(SocialFollow.objects.exists())

    def test_contagens_e_selectors(self):
        seguir_usuario(self.owner, self.target_profile)
        self.assertEqual(contagem_seguidores_perfil(self.target_profile), 1)
        self.assertEqual(list(seguidores_do_perfil(self.target_profile)), [self.owner_profile])


class CompanyFollowTests(SocialBase):
    def test_usuario_segue_empresa(self):
        relation, created = seguir_empresa(self.owner, self.company)
        self.assertTrue(created)
        self.assertEqual(relation.usuario, self.owner)

    def test_empresa_duplicidade_idempotente(self):
        seguir_empresa(self.owner, self.company)
        _, created = seguir_empresa(self.owner, self.company)
        self.assertFalse(created)
        self.assertEqual(EmpresaSeguidor.objects.count(), 1)

    def test_deixar_de_seguir_empresa(self):
        seguir_empresa(self.owner, self.company)
        self.assertEqual(deixar_de_seguir_empresa(self.owner, self.company), 1)

    def test_anonimo_nao_segue_empresa(self):
        with self.assertRaises(PermissionDenied):
            seguir_empresa(AnonymousUser(), self.company)

    def test_follow_nao_concede_acesso_administrativo(self):
        seguir_empresa(self.owner, self.company)
        self.assertFalse(usuario_pode_editar_empresa(self.owner, self.company))
        self.assertFalse(usuario_pode_publicar_por_empresa(self.owner, self.company))

    def test_follow_nao_lista_empresa_como_gerenciavel(self):
        seguir_empresa(self.owner, self.company)
        self.assertFalse(empresas_gerenciaveis_para_usuario(self.owner).filter(pk=self.company.pk).exists())

    def test_proprietario_independe_de_follow(self):
        self.assertTrue(usuario_pode_editar_empresa(self.target, self.company))
        self.assertFalse(EmpresaSeguidor.objects.filter(usuario=self.target, empresa=self.company).exists())

    def test_contagem_e_selector_de_empresa(self):
        seguir_empresa(self.owner, self.company)
        self.assertEqual(contagem_seguidores_empresa(self.company), 1)
        self.assertEqual(list(seguidores_da_empresa(self.company)), list(EmpresaSeguidor.objects.filter(usuario=self.owner)))


class PublicProfileTests(SocialBase):
    def test_pagina_publica_nao_expoe_pii(self):
        response = self.client.get(self.owner_profile.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        for private in ('private@example.com', '11999999999', '52998224725', '1990-01-01'):
            self.assertNotContains(response, private)

    def test_perfil_privado_oculta_biografia(self):
        self.owner_profile.visibilidade = SocialProfile.Visibilidade.PRIVADO
        self.owner_profile.save(update_fields=['visibilidade'])
        response = self.client.get(self.owner_profile.get_absolute_url())
        self.assertNotContains(response, 'Biografia pública')
        self.assertContains(response, 'Este perfil é privado')

    def test_botao_seguir_para_usuario_diferente(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.target_profile.get_absolute_url())
        self.assertContains(response, '>Seguir<', html=False)

    def test_dono_nao_recebe_botao_seguir(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.owner_profile.get_absolute_url())
        self.assertNotContains(response, 'social/perfis/')

    @override_settings(ROOT_URLCONF='config.urls')
    def test_empresa_publica_exibe_follow_sem_quebrar_acoes(self):
        response = self.client.get(self.company.get_absolute_url())
        self.assertContains(response, 'seguidores')
        self.assertContains(response, 'Sobre a empresa')


@override_settings(ENABLE_ANALYTICS=True)
class SocialAnalyticsTests(SocialBase):
    def setUp(self):
        self.client.force_login(self.owner)
        self.client.cookies['botuka_consent'] = json.dumps({
            'version': '2026-07-25', 'analytics': True,
            'expiresAt': time.time() * 1000 + 60000,
        })

    def test_follow_e_unfollow_user_registram_eventos(self):
        self.client.post(reverse('social:follow_profile', args=[self.target_profile.uuid]))
        self.client.post(reverse('social:unfollow_profile', args=[self.target_profile.uuid]))
        self.assertEqual(set(AnalyticsEvent.objects.values_list('event_name', flat=True)), {'follow_user', 'unfollow_user'})

    def test_follow_e_unfollow_company_registram_eventos(self):
        self.client.post(reverse('social:follow_company', args=[self.company.uuid]))
        self.client.post(reverse('social:unfollow_company', args=[self.company.uuid]))
        self.assertEqual(set(AnalyticsEvent.objects.values_list('event_name', flat=True)), {'follow_company', 'unfollow_company'})

    def test_analytics_nao_registra_pii_nos_metadados(self):
        self.client.post(reverse('social:follow_profile', args=[self.target_profile.uuid]))
        event = AnalyticsEvent.objects.get()
        self.assertEqual(set(event.metadata), {'context', 'page_type'})
        serialized = json.dumps(event.metadata)
        for private in ('email', 'telefone', 'cpf', 'username', 'slug'):
            self.assertNotIn(private, serialized)


class SocialExperienceTests(SocialBase):
    def test_home_social_publica_usa_template_exclusivo(self):
        response = self.client.get(reverse('social:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'social/feed.html')

    def test_seguindo_exige_login(self):
        self.assertEqual(self.client.get(reverse('social:following')).status_code, 302)

    @override_settings(ROOT_URLCONF='config.urls')
    def test_alias_antigo_redireciona_para_rota_social(self):
        self.client.force_login(self.owner)
        response = self.client.get('/painel/seguindo/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://127.0.0.1:7800/social/seguindo/')

    def test_seguindo_exibe_pessoas_e_empresas_reais(self):
        seguir_usuario(self.owner, self.target_profile)
        seguir_empresa(self.owner, self.company)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('social:following'))
        self.assertContains(response, self.target_profile.nome_publico)
        self.assertContains(response, self.company.nome_fantasia)

    def test_usuario_atual_e_seguido_nao_entram_nas_sugestoes(self):
        seguir_usuario(self.owner, self.target_profile)
        ids = set(perfis_sugeridos_para(self.owner).values_list('usuario_id', flat=True))
        self.assertNotIn(self.owner.pk, ids)
        self.assertNotIn(self.target.pk, ids)

    def test_perfil_privado_e_inativo_nao_entram_nas_sugestoes(self):
        self.target_profile.visibilidade = SocialProfile.Visibilidade.PRIVADO
        self.target_profile.save(update_fields=['visibilidade'])
        self.owner_profile.ativo = False
        self.owner_profile.save(update_fields=['ativo'])
        ids = set(perfis_sugeridos_para().values_list('pk', flat=True))
        self.assertNotIn(self.target_profile.pk, ids)
        self.assertNotIn(self.owner_profile.pk, ids)

    def test_empresa_seguida_nao_entra_nas_sugestoes(self):
        seguir_empresa(self.owner, self.company)
        ids = set(empresas_sugeridas_para(self.owner).values_list('pk', flat=True))
        self.assertNotIn(self.company.pk, ids)

    def test_preferencias_de_tema_estao_na_pagina_sem_dados_pessoais(self):
        response = self.client.get(reverse('social:home'))
        self.assertContains(response, 'data-social-theme="light"')
        self.assertContains(response, 'data-color-mode="standard"')
        self.assertContains(response, 'data-theme="black-white"')
        self.assertNotContains(response, 'private@example.com')

    def test_diretorios_e_explorar_abrem(self):
        for name in ('explore', 'people', 'companies'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f'social:{name}')).status_code, 200)


class SocialRuntimeIsolationTests(SimpleTestCase):
    def test_raiz_social_redireciona_e_rotas_sociais_resolvem(self):
        self.assertEqual(resolve('/', urlconf='config.urls_social').url_name, 'social_runtime_root')
        self.assertEqual(resolve('/social/', urlconf='config.urls_social').view_name, 'social:home')

    def test_runtime_social_nao_registra_rotas_platform(self):
        for path in ('/admin/', '/painel/', '/empresas/', '/vagas/', '/eventos/', '/servicos/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path, urlconf='config.urls_social')

    def test_service_worker_platform_nao_esta_no_runtime_social(self):
        with self.assertRaises(Resolver404):
            resolve('/service-worker.js', urlconf='config.urls_social')

    def test_rotas_de_descoberta_oficial_sao_sociais(self):
        for kind in ('eventos', 'vagas', 'empresas', 'servicos', 'noticias'):
            self.assertEqual(resolve(f'/social/conteudos/{kind}/', urlconf='config.urls_social').view_name, 'social:official_list')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='botuka-social-tests-'))
class SocialContentTests(SocialBase):
    @staticmethod
    def image(name='foto.png'):
        return SimpleUploadedFile(name, b'\x89PNG\r\n\x1a\n' + b'0' * 32, content_type='image/png')

    def test_sincronizacao_platform_social_e_slug_estavel_sem_pii(self):
        slug = self.owner_profile.slug
        self.owner.nome_exibicao = 'Nome Atualizado'
        self.owner.biografia = 'Nova bio'
        self.owner.save()
        profile = sincronizar_perfil_publico(self.owner, origem='platform')
        self.assertEqual((profile.nome_exibicao, profile.biografia, profile.slug), ('Nome Atualizado', 'Nova bio', slug))
        self.assertFalse({'email', 'telefone', 'cpf', 'endereco', 'data_nascimento'} & vars(profile).keys())
        sincronizar_perfil_publico(self.owner, origem='social', nome_exibicao='Nome Social', biografia='Bio Social')
        self.owner.refresh_from_db()
        self.assertEqual((self.owner.nome_exibicao, self.owner.biografia), ('Nome Social', 'Bio Social'))

    def test_post_fica_sete_dias_no_feed_mas_permanece_no_perfil(self):
        post = criar_post(self.owner, imagem=self.image(), legenda='Foto real')
        self.assertAlmostEqual((post.feed_ate - post.publicado_em).total_seconds(), 7 * 86400, delta=2)
        self.assertIn(post, posts_visiveis_para(self.owner))
        SocialPost.objects.filter(pk=post.pk).update(feed_ate=timezone.now() - timedelta(seconds=1))
        post.refresh_from_db()
        self.assertNotIn(post, posts_visiveis_para(self.owner))
        self.assertIn(post, posts_do_perfil(self.owner_profile, self.owner))

    def test_story_expira_em_24_horas(self):
        story = criar_story(self.owner, imagem=self.image('story.png'))
        self.assertAlmostEqual((story.expira_em - story.publicado_em).total_seconds(), 86400, delta=2)
        self.assertIn(story, stories_ativos_para(self.owner))
        SocialStory.objects.filter(pk=story.pk).update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertFalse(stories_ativos_para(self.owner).filter(pk=story.pk).exists())

    def test_viewers_e_remocao_logica_respeitam_ownership(self):
        post = criar_post(self.owner, imagem=self.image('viewer.png'))
        story = criar_story(self.owner, imagem=self.image('viewer-story.png'))
        self.assertEqual(self.client.get(reverse('social:post_detail', args=[post.uuid])).status_code, 200)
        self.assertEqual(self.client.get(reverse('social:story_detail', args=[story.uuid])).status_code, 200)
        with self.assertRaises(PermissionDenied):
            remover_post(self.target, post)
        with self.assertRaises(PermissionDenied):
            remover_story(self.target, story)
        remover_post(self.owner, post)
        remover_story(self.owner, story)
        self.assertEqual(self.client.get(reverse('social:post_detail', args=[post.uuid])).status_code, 404)
        self.assertEqual(self.client.get(reverse('social:story_detail', args=[story.uuid])).status_code, 404)

    def test_solicitacao_conversa_aceite_mensagem_e_recusa(self):
        post = criar_post(self.owner, imagem=self.image('message.png'))
        pedido, created = solicitar_ou_enviar_conversa(self.owner, self.target, texto='Olá', post=post)
        self.assertTrue(created)
        self.assertEqual(pedido.status, SocialConversationRequest.Status.PENDENTE)
        decidir_solicitacao_conversa(self.target, pedido, True)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, SocialConversationRequest.Status.ACEITA)
        self.assertEqual(pedido.conversa.mensagens.get().post, post)
        mensagem, is_request = solicitar_ou_enviar_conversa(self.owner, self.target, texto='Depois do aceite')
        self.assertFalse(is_request)
        self.assertEqual(mensagem.conversa, pedido.conversa)
        recusada, _ = solicitar_ou_enviar_conversa(self.owner, self.third, texto='Pedido')
        decidir_solicitacao_conversa(self.third, recusada, False)
        with self.assertRaises(PermissionDenied):
            solicitar_ou_enviar_conversa(self.owner, self.third, texto='Spam')

    def test_bloqueio_impede_solicitacao_de_conversa(self):
        bloquear_perfil(self.owner, self.target_profile)
        with self.assertRaises(PermissionDenied):
            solicitar_ou_enviar_conversa(self.target, self.owner, texto='Não permitido')

    def test_curtir_descurtir_comentar_salvar_e_remover(self):
        post = criar_post(self.owner, imagem=self.image())
        _, created = curtir_post(self.target, post)
        self.assertTrue(created)
        self.assertFalse(curtir_post(self.target, post)[1])
        self.assertEqual(SocialPostLike.objects.filter(post=post).count(), 1)
        self.assertEqual(descurtir_post(self.target, post), 1)
        comment = comentar_post(self.target, post, 'Comentário seguro')
        self.assertEqual(comment.texto, 'Comentário seguro')
        with self.assertRaises(ValidationError):
            comentar_post(self.target, post, '<script>alert(1)</script>')
        self.assertTrue(salvar_post(self.target, post)[1])
        self.assertFalse(salvar_post(self.target, post)[1])
        self.assertEqual(remover_post_salvo(self.target, post), 1)

    def test_follow_privado_cria_pedido_aprovavel_e_recusavel(self):
        self.target_profile.visibilidade = SocialProfile.Visibilidade.PRIVADO
        self.target_profile.save(update_fields=['visibilidade'])
        request, created = seguir_usuario(self.owner, self.target_profile)
        self.assertTrue(created)
        self.assertIsInstance(request, SocialFollowRequest)
        self.assertFalse(SocialFollow.objects.exists())
        decidir_follow_request(self.target, request, True)
        self.assertTrue(SocialFollow.objects.filter(seguidor=self.owner_profile, seguido=self.target_profile).exists())
        SocialFollow.objects.all().delete()
        second = SocialFollowRequest.objects.create(solicitante=self.owner_profile, destinatario=self.target_profile)
        decidir_follow_request(self.target, second, False)
        self.assertFalse(SocialFollow.objects.exists())

    def test_bloqueio_remove_relacoes_e_impede_interacao(self):
        seguir_usuario(self.owner, self.target_profile)
        bloquear_perfil(self.owner, self.target_profile)
        self.assertTrue(SocialBlock.objects.filter(bloqueador=self.owner_profile, bloqueado=self.target_profile).exists())
        self.assertFalse(SocialFollow.objects.exists())
        with self.assertRaises(PermissionDenied):
            seguir_usuario(self.target, self.owner_profile)

    def test_visibilidade_e_perfil_privado_prevalecem(self):
        public = criar_post(self.owner, imagem=self.image('public.png'))
        followers = criar_post(self.owner, imagem=self.image('followers.png'), visibilidade=SocialPost.Visibilidade.SEGUIDORES)
        mine = criar_post(self.owner, imagem=self.image('mine.png'), visibilidade=SocialPost.Visibilidade.SOMENTE_EU)
        self.assertTrue(pode_ver_post(self.target, public))
        self.assertFalse(pode_ver_post(self.target, followers))
        self.assertFalse(pode_ver_post(self.target, mine))
        self.owner_profile.visibilidade = SocialProfile.Visibilidade.PRIVADO
        self.owner_profile.save(update_fields=['visibilidade'])
        self.assertFalse(pode_ver_post(self.target, public))
        seguir_usuario(self.target, self.owner_profile)
        pending = SocialFollowRequest.objects.get(solicitante=self.target_profile, destinatario=self.owner_profile)
        decidir_follow_request(self.owner, pending, True)
        self.assertTrue(pode_ver_post(self.target, public))
        self.assertTrue(pode_ver_post(self.target, followers))

    def test_compartilhar_empresa_mantem_referencia_sem_conceder_gestao(self):
        post = compartilhar_conteudo(self.owner, self.company)
        self.assertEqual(post.conteudo, self.company)
        self.assertEqual(Empresa.objects.filter(pk=self.company.pk).count(), 1)
        self.assertFalse(usuario_pode_editar_empresa(self.owner, self.company))

    @override_settings(ROOT_URLCONF='config.urls')
    def test_login_cross_runtime_allowlist_e_open_redirect(self):
        good = self.client.get(reverse('accounts:login'), {'next': 'http://127.0.0.1:7800/social/'})
        self.assertIn('next=http%3A%2F%2F127.0.0.1%3A7800%2Fsocial%2F', good.url)
        bad = self.client.get(reverse('accounts:login'), {'next': 'https://evil.example/phishing'})
        self.assertNotIn('evil.example', bad.url)
