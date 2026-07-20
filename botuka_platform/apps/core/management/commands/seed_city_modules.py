from django.core.management.base import BaseCommand
from apps.media.models import Canal
from apps.news.models import CategoriaNoticia
from apps.sports.models import Modalidade

NEWS=['Cidade','Cultura','Educação','Saúde pública','Economia','Empreendedorismo','Turismo','Esportes','Eventos','Meio ambiente','Tecnologia','História','Mobilidade','Serviços públicos','Comunidade','Entrevistas','Opinião identificada']
SPORTS=['Futebol','Futsal','Basquete','Vôlei','Atletismo','Ciclismo','Natação','Artes marciais','Skate','Tênis','Corrida','E-sports']
class Command(BaseCommand):
    help='Cria catálogos iniciais seguros de YTv, News e Esportes.'
    def handle(self,*args,**options):
        Canal.objects.update_or_create(slug='botuka-ytv',defaults={'nome':'YTv Botuka','descricao':'Canal audiovisual oficial do BOTUKA.','plataforma':'YOUTUBE','oficial':True,'ativo':True})
        for ordem,nome in enumerate(NEWS):CategoriaNoticia.objects.update_or_create(nome=nome,defaults={'ordem':ordem,'ativo':True})
        for ordem,nome in enumerate(SPORTS):Modalidade.objects.update_or_create(nome=nome,defaults={'ordem':ordem,'ativo':True})
        self.stdout.write(self.style.SUCCESS('Catálogos iniciais sincronizados.'))
