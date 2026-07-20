from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from apps.sports.models import Modalidade,Estilo,Categoria,OrganizacaoEsportiva,Equipe,Atleta,Campeonato,ParticipanteCampeonato,Disputa,Classificacao

class SportsTests(TestCase):
    def setUp(self):
        U=get_user_model();self.dono=U.objects.create_user('clube',password='x');self.outro=U.objects.create_user('outro',password='x');self.modalidade=Modalidade.objects.create(nome='Futebol');self.estilo=Estilo.objects.create(modalidade=self.modalidade,nome='Campo');self.categoria=Categoria.objects.create(modalidade=self.modalidade,nome='Adulto');self.org=OrganizacaoEsportiva.objects.create(usuario_responsavel=self.dono,tipo=OrganizacaoEsportiva.Tipo.CLUBE,nome='Clube A',cidade='Botucatu');self.equipe=Equipe.objects.create(organizacao=self.org,modalidade=self.modalidade,estilo=self.estilo,categoria=self.categoria,nome='Equipe A',cidade='Botucatu')
    def test_hierarquia_e_atleta_publico(self):
        a=Atleta.objects.create(equipe=self.equipe,nome_publico='Atleta A',modalidade=self.modalidade,publico=True);self.assertEqual(a.equipe,self.equipe);self.assertNotIn('cpf',[f.name for f in Atleta._meta.fields])
    def test_campeonato_disputa_resultado_classificacao(self):
        c=Campeonato.objects.create(organizacao=self.org,modalidade=self.modalidade,nome='Municipal',formato='Pontos',data_inicial=timezone.localdate());p=ParticipanteCampeonato.objects.create(campeonato=c,equipe=self.equipe);d=Disputa.objects.create(campeonato=c,tipo='JOGO',participante_a=p,data_hora=timezone.now(),status=Disputa.Status.ENCERRADA,placar_a=1);cl=Classificacao.objects.create(campeonato=c,participante=p,posicao=1,pontos=3);self.assertEqual(d.placar_a,1);self.assertEqual(cl.posicao,1)
    def test_participante_duplicado_bloqueado(self):
        from django.db import IntegrityError,transaction
        c=Campeonato.objects.create(organizacao=self.org,modalidade=self.modalidade,nome='Copa',formato='Mata-mata',data_inicial=timezone.localdate());ParticipanteCampeonato.objects.create(campeonato=c,equipe=self.equipe)
        with self.assertRaises((IntegrityError, ValidationError)),transaction.atomic():ParticipanteCampeonato.objects.create(campeonato=c,equipe=self.equipe)
    def test_isolamento_organizacao(self):self.assertNotEqual(self.org.usuario_responsavel,self.outro)
