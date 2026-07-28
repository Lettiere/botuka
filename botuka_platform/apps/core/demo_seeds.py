"""Dados exclusivamente fictícios e idempotentes para desenvolvimento local."""
from datetime import timedelta
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import connection
from django.utils import timezone


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
LOCAL_DATABASES = {
    name.strip()
    for name in os.environ.get("BOTUKA_DEMO_DATABASES", "botuka1,test_botuka1").split(",")
    if name.strip()
}


def assert_demo_database():
    database = str(connection.settings_dict.get("NAME", ""))
    host = str(connection.settings_dict.get("HOST", ""))
    if database not in LOCAL_DATABASES or host not in LOCAL_HOSTS:
        raise RuntimeError(
            f"Seeds bloqueados fora da allowlist local (database={database!r}, host={host!r})."
        )
    if str(getattr(settings, "APP_ENV", "")).lower() == "production":
        raise RuntimeError("Seeds demonstrativos são proibidos em produção.")
    if not settings.DEBUG:
        raise RuntimeError("Seeds demonstrativos exigem DEBUG=True.")


def demo_user(code="gestor"):
    assert_demo_database()
    banco_teste = str(connection.settings_dict.get("NAME", "")).startswith("test_")
    user, created = get_user_model().objects.get_or_create(
        username=f"demo_{code}",
        defaults={"email": f"demo_{code}@example.invalid", "nome_exibicao": f"Usuário Demo {code.title()}"},
    )
    if banco_teste:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif created or not user.has_usable_password():
        password = os.environ.get("BOTUKA_DEMO_PASSWORD")
        if not password:
            raise RuntimeError("Defina BOTUKA_DEMO_PASSWORD no ambiente local para criar usuários demo.")
        user.set_password(password)
        user.save(update_fields=["password"])
    return user


@transaction.atomic
def seed_services_demo():
    from apps.locations.models import Cidade, Estado, Pais
    from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade, StatusCapacidadeMixin
    from apps.services.models import FormaCobranca, Profissao, Servico, Setor, TipoServico
    from apps.taxonomy.models import Categoria

    user = demo_user("servicos")
    pais, _ = Pais.objects.get_or_create(nome="Brasil", defaults={"nome_oficial": "República Federativa do Brasil", "codigo_iso_2": "BR", "codigo_iso_3": "BRA"})
    estado, _ = Estado.objects.get_or_create(pais=pais, nome="São Paulo", defaults={"sigla": "SP", "codigo_ibge": "35"})
    cidade, _ = Cidade.objects.get_or_create(estado=estado, nome="Botucatu", defaults={"codigo_ibge": "3507506"})
    capacidade, _ = Capacidade.objects.update_or_create(codigo="PRESTAR_SERVICOS", defaults={"nome": "Prestar serviços", "ativo": True})
    setor, _ = Setor.objects.update_or_create(slug="servicos-demo", defaults={"nome": "Serviços Demo", "ativo": True})
    profissao, _ = Profissao.objects.update_or_create(slug="profissional-demo", defaults={"setor": setor, "nome": "Profissional Demo", "ativo": True})
    tipo, _ = TipoServico.objects.update_or_create(slug="atendimento-demo", defaults={"nome": "Atendimento Demo", "ativo": True})
    forma, _ = FormaCobranca.objects.update_or_create(slug="por-servico-demo", defaults={"nome": "Por serviço Demo", "ativo": True})
    gastronomia, _ = Categoria.objects.update_or_create(
        slug="gastronomia", defaults={"nome": "Gastronomia", "descricao": "Bares e restaurantes da cidade.", "ativo": True, "removido_em": None}
    )
    empresas = []
    for i in range(1, 21):
        empresa, _ = Empresa.all_objects.update_or_create(
            slug=f"empresa-demo-{i:02d}",
            defaults={
                "usuario_proprietario": user, "tipo_cadastro": Empresa.TipoCadastro.EMPRESA,
                "razao_social": f"Empresa Demonstração {i:02d} Ltda.", "nome_fantasia": f"Empresa Demo {i:02d}",
                "cpf_cnpj": _cnpj_demo(i), "descricao_curta": "Empresa fictícia criada para demonstração local.",
                "email": f"empresa{i:02d}@example.invalid", "status": Empresa.Status.ATIVA,
                "cidade": cidade, "estado": cidade.estado,
                "categoria_empresa": gastronomia if i <= 6 else None,
                "verificada": i <= 8, "perfil_publico": True, "ativo": True, "excluido_em": None,
            },
        )
        EmpresaCapacidade.objects.update_or_create(
            empresa=empresa, capacidade=capacidade,
            defaults={"status": StatusCapacidadeMixin.Status.APROVADA, "ativo": True},
        )
        empresas.append(empresa)
    for i in range(1, 31):
        pj = i % 2 == 0
        status = Servico.Status.PUBLICADO if i <= 24 else (
            Servico.Status.RASCUNHO if i <= 26 else Servico.Status.PENDENTE if i <= 28 else Servico.Status.PAUSADO
        )
        Servico.all_objects.update_or_create(
            slug=f"servico-demo-{i:02d}",
            defaults={
                "usuario_responsavel": user, "empresa": empresas[(i - 1) % len(empresas)] if pj else None,
                "prestador_tipo": Servico.PrestadorTipo.EMPRESA if pj else Servico.PrestadorTipo.PESSOA_FISICA,
                "setor": setor, "profissao": profissao, "tipo_servico": tipo, "forma_cobranca": forma,
                "titulo": f"Serviço demonstrativo {i:02d}", "descricao_curta": "Atendimento fictício para validar a HOME local.",
                "descricao_completa": "Conteúdo de demonstração sem dados pessoais reais.",
                "status": status,
                "publicado_em": timezone.now() if i <= 24 else None, "destaque": i <= 6,
                "ativo": True, "excluido_em": None,
            },
        )
    return {"empresas": 20, "servicos": 30}


@transaction.atomic
def seed_recruitment_demo():
    from apps.organizations.models import Empresa
    from apps.recruitment.models import Curriculo, Vaga

    user = demo_user("recrutamento")
    empresas = list(Empresa.objects.filter(slug__startswith="empresa-demo-").order_by("slug")[:15])
    if not empresas:
        seed_services_demo(); empresas = list(Empresa.objects.filter(slug__startswith="empresa-demo-")[:15])
    hoje = timezone.localdate()
    for i, empresa in enumerate(empresas, 1):
        status = Vaga.Status.PUBLICADA if i <= 12 else Vaga.Status.EM_ANALISE if i == 13 else Vaga.Status.PAUSADA if i == 14 else Vaga.Status.RASCUNHO
        Vaga.all_objects.update_or_create(
            slug=f"vaga-demo-{i:02d}", defaults={"empresa": empresa, "usuario_criador": user, "usuario_responsavel": user,
            "titulo": f"Oportunidade demonstrativa {i:02d}", "descricao": "Vaga fictícia para testes locais.",
            "tipo_contrato": "CLT", "modalidade": "PRESENCIAL", "cidade": "Botucatu", "estado": "SP",
            "inicio": hoje - timedelta(days=2), "encerramento": hoje + timedelta(days=30),
            "status": status,
            "publicado_em": timezone.now() if i <= 12 else None, "ativo": True, "excluido_em": None})
    for i in range(1, 11):
        candidato = demo_user(f"candidato{i:02d}")
        Curriculo.all_objects.update_or_create(usuario=candidato, defaults={"titulo_profissional": f"Profissional Demo {i:02d}",
            "resumo": "Perfil profissional inteiramente fictício para demonstração.", "cidade": "Botucatu", "estado": "SP",
            "publico": False, "ativo": True, "excluido_em": None})
    return {"vagas": 15, "curriculos": 10}


@transaction.atomic
def seed_sports_demo():
    from apps.sports.models import (Atleta, Campeonato, Categoria, Classificacao, Disputa, Equipe, Estilo,
        Modalidade, OrganizacaoEsportiva, ParticipanteCampeonato)
    user = demo_user("esportes"); agora = timezone.now(); hoje = timezone.localdate()
    modalidade, _ = Modalidade.objects.update_or_create(slug="futebol-demo", defaults={"nome":"Futebol Demo","ordem":90,"ativo":True,"excluido_em":None})
    estilo, _ = Estilo.objects.update_or_create(slug="campo-demo", defaults={"modalidade":modalidade,"nome":"Campo Demo","ativo":True,"excluido_em":None})
    categoria, _ = Categoria.objects.update_or_create(slug="adulto-demo", defaults={"modalidade":modalidade,"estilo":estilo,"nome":"Adulto Demo","genero":"MISTO","ativo":True,"excluido_em":None})
    orgs=[]; equipes=[]
    for i in range(1,9):
        org,_=OrganizacaoEsportiva.objects.update_or_create(slug=f"organizacao-esportiva-demo-{i:02d}",defaults={"usuario_responsavel":user,"tipo":"CLUBE","nome":f"Clube Demo {i:02d}","cidade":"Botucatu","verificado":True,"ativo":True,"excluido_em":None}); orgs.append(org)
    for i in range(1,17):
        equipe,_=Equipe.objects.update_or_create(slug=f"equipe-demo-{i:02d}",defaults={"organizacao":orgs[(i-1)%8],"modalidade":modalidade,"estilo":estilo,"categoria":categoria,"nome":f"Equipe Demo {i:02d}","cidade":"Botucatu","ativo":True,"excluido_em":None}); equipes.append(equipe)
        Atleta.objects.update_or_create(nome_publico=f"Atleta Demo {i:02d}",defaults={"equipe":equipe,"modalidade":modalidade,"estilo":estilo,"categoria":categoria,"publico":True,"ativo":True,"excluido_em":None})
    for c in range(1,5):
        camp,_=Campeonato.objects.update_or_create(slug=f"campeonato-demo-{c:02d}",defaults={"organizacao":orgs[c-1],"modalidade":modalidade,"estilo":estilo,"categoria":categoria,"nome":f"Campeonato Demo {c:02d}","formato":"Pontos corridos","data_inicial":hoje+timedelta(days=c),"data_final":hoje+timedelta(days=40+c),"status":"AGENDADO","localidade":"Botucatu","ativo":True,"excluido_em":None})
        parts=[]
        for pos,equipe in enumerate(equipes[(c-1)*4:c*4],1):
            p,_=ParticipanteCampeonato.objects.update_or_create(campeonato=camp,equipe=equipe,defaults={"ativo":True,"excluido_em":None}); parts.append(p)
            Classificacao.objects.update_or_create(campeonato=camp,participante=p,defaults={"posicao":pos,"pontos":4-pos,"ativo":True,"excluido_em":None})
        for j in range(4):
            encerrada=j<2
            Disputa.objects.update_or_create(campeonato=camp,rodada=f"Demo {j+1}",defaults={"tipo":"PARTIDA","participante_a":parts[j%4],"participante_b":parts[(j+1)%4],"data_hora":agora+timedelta(days=j+1) if not encerrada else agora-timedelta(days=j+1),"local":"Estádio Demo","status":"ENCERRADA" if encerrada else "AGENDADA","placar_a":2 if encerrada else None,"placar_b":1 if encerrada else None,"resultado_textual":"2 a 1" if encerrada else "","ativo":True,"excluido_em":None})
    return {"organizacoes_esportivas":8,"equipes":16,"atletas":16,"campeonatos":4,"disputas":16}


@transaction.atomic
def seed_media_demo():
    from apps.media.models import Canal, Episodio, Programa, Transmissao
    canal,_=Canal.objects.update_or_create(slug="botuka-ytv",defaults={"nome":"YTv Botuka","descricao":"Canal audiovisual demonstrativo do BOTUKA.","oficial":True,"ativo":True,"excluido_em":None})
    nomes=["BOTUKA Esportes","Podcast BOTUKA","BOTUKA Entrevista","Nossa Cidade","Turismo na Cuesta","Empreendedores"]
    programas=[]
    for nome in nomes:
        slug="demo-"+nome.lower().replace(" ","-").replace("á","a")
        p,_=Programa.objects.update_or_create(slug=slug,defaults={"canal":canal,"nome":nome,"descricao":"Programa fictício para ambiente local.","ativo":True,"excluido_em":None}); programas.append(p)
    for i in range(1,16):
        ep,_=Episodio.objects.update_or_create(slug=f"episodio-demo-{i:02d}",defaults={"programa":programas[(i-1)%6],"titulo":f"Episódio demonstrativo {i:02d}","descricao":"Conteúdo audiovisual fictício.","numero":i,"tipo":"PODCAST" if i%3==0 else "VIDEO","youtube_url":"https://www.youtube.com/watch?v=pSLAu3Kj_dg" if i==1 else "","status":"PUBLICADO" if i<=12 else "AGENDADO","publicado_em":timezone.now()-timedelta(days=i) if i<=12 else None,"data_programada":timezone.now()+timedelta(days=i) if i>12 else None,"destaque":i<=4,"ativo":True,"excluido_em":None})
        if i==13: Transmissao.objects.update_or_create(episodio=ep,defaults={"data_prevista":timezone.now()+timedelta(hours=2),"url_ao_vivo":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","status":"AGENDADA","ativo":True,"excluido_em":None})
    return {"canais":1,"programas":6,"episodios":15}


@transaction.atomic
def seed_news_demo():
    from apps.news.models import Artigo, CategoriaNoticia
    user=demo_user("news"); nomes=["Cidade","Cultura","Educação","Saúde pública","Economia","Empreendedorismo","Turismo","Esportes"]
    categorias=[]
    for i,nome in enumerate(nomes):
        c=CategoriaNoticia.objects.filter(nome__iexact=nome).first()
        if c:
            c.ordem=i;c.ativo=True;c.excluido_em=None;c.save()
        else:
            slug="demo-news-"+str(i+1);c=CategoriaNoticia.objects.create(slug=slug,nome=nome,ordem=i,ativo=True)
        categorias.append(c)
    for i in range(1,21):
        status="PUBLICADO" if i<=14 else ("EM_REVISAO" if i<=17 else "DESPUBLICADO" if i==18 else "RASCUNHO")
        Artigo.objects.update_or_create(slug=f"artigo-demo-{i:02d}",defaults={"autor":user,"categoria":categorias[(i-1)%len(categorias)],"titulo":f"Conteúdo demonstrativo da cidade {i:02d}","resumo":"Artigo fictício sem atribuição a pessoas reais.","conteudo":"Material criado exclusivamente para validar o ambiente local do BOTUKA.","status":status,"destaque":i<=5,"publicado_em":timezone.now()-timedelta(days=i) if status=="PUBLICADO" else None,"ativo":True,"excluido_em":None})
    return {"categorias_news":8,"artigos":20}


@transaction.atomic
def seed_government_demo():
    from apps.government.models import AcaoPublica, OrgaoPublico
    user=demo_user("prefeitura"); orgaos=[]
    for i in range(1,5):
        o,_=OrgaoPublico.objects.update_or_create(slug=f"orgao-publico-demo-{i:02d}",defaults={"tipo":"SECRETARIA" if i>1 else "PREFEITURA","nome":f"Órgão Público Demonstrativo {i:02d}","sigla":f"DEMO{i}","descricao":"Órgão inteiramente fictício para testes locais.","verificado":True,"ativo":True,"excluido_em":None}); orgaos.append(o)
    hoje=timezone.localdate()
    for i in range(1,13):
        tipo = "EVENTO" if i <= 2 else "PROJETO"
        complemento = {1: " — Festival cultural", 2: " — Encontro esportivo", 3: " — Parque demonstrativo", 4: " — Praça demonstrativa"}.get(i, "")
        AcaoPublica.objects.update_or_create(slug=f"acao-publica-demo-{i:02d}",defaults={"orgao":orgaos[(i-1)%4],"autor":user,"publicador":user,"tipo":tipo,"titulo":f"Ação pública demonstrativa {i:02d}{complemento}","resumo":"Conteúdo oficial fictício e claramente demonstrativo.","descricao":"Ação criada somente para testes do ambiente local.","local":"Centro Demonstrativo" if i <= 4 else "","bairro":"Centro" if i <= 4 else "","cidade":"Botucatu","inicio_previsto":hoje+timedelta(days=i),"conclusao_prevista":hoje+timedelta(days=60+i),"situacao":"AGENDADA" if i <= 2 else ("PLANEJADA" if i%2 else "EM_ANDAMENTO"),"status":"PUBLICADO" if i<=10 else "RASCUNHO","destaque":i<=4,"publicado_em":timezone.now() if i<=10 else None,"ativo":True,"excluido_em":None})
    return {"orgaos_publicos":4,"acoes_publicas":12}


@transaction.atomic
def seed_home_demo():
    assert_demo_database()
    return {**seed_services_demo(), **seed_recruitment_demo(), **seed_sports_demo(), **seed_media_demo(), **seed_news_demo(), **seed_government_demo()}
def _cnpj_demo(indice):
    base = [int(char) for char in f'99000000{indice:04d}']
    for pesos in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        resto = sum(numero * peso for numero, peso in zip(base, pesos)) % 11
        base.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, base))
