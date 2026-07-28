from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from apps.news.models import Artigo, CategoriaNoticia, DestaqueEditorial, EditorialStatus, Tema
from apps.news.selectors import AGRO_SLUGS, UNIVERSIDADE_SLUGS, obter_home_noticias


class Command(BaseCommand):
    help = "Diagnostica, sem alterar dados, a composição editorial da HOME."

    def handle(self, *args, **options):
        agora = timezone.now()
        home = obter_home_noticias(agora)
        secoes = (
            ("Manchete", [home["manchete"]] if home["manchete"] else []),
            ("Destaques", home["destaques"]),
            ("Últimas", home["recentes"]),
            ("Agro", home["agro"]),
            ("Universidade e Ciência", home["universidade"]),
        )
        todos = []
        for titulo, artigos in secoes:
            self.stdout.write(self.style.MIGRATE_HEADING(titulo))
            for artigo in artigos:
                todos.append(artigo.pk)
                self.stdout.write(
                    f"- {artigo.pk} | {artigo.titulo} | "
                    f"{artigo.categoria.slug} | {artigo.publicado_em:%d/%m/%Y %H:%M}"
                )
            if not artigos:
                self.stdout.write("- nenhum item")

        repetidos = sorted({pk for pk in todos if todos.count(pk) > 1})
        self.stdout.write(f"\nIDs repetidos: {repetidos or 'nenhum'}")
        self.stdout.write("Colunistas: " + (
            ", ".join(item.autor.nome for item in home["colunistas"]) or "nenhum"
        ))
        self.stdout.write(
            "Categorias Agro encontradas: "
            + ", ".join(CategoriaNoticia.objects.filter(slug__in=AGRO_SLUGS).values_list("slug", flat=True))
        )
        self.stdout.write(
            "Temas Agro encontrados: "
            + ", ".join(Tema.objects.filter(slug__in=AGRO_SLUGS).values_list("slug", flat=True))
        )
        self.stdout.write(
            "Categorias Universidade encontradas: "
            + ", ".join(CategoriaNoticia.objects.filter(slug__in=UNIVERSIDADE_SLUGS).values_list("slug", flat=True))
        )
        self.stdout.write(
            "Destaques expirados ainda ativos: "
            + str(DestaqueEditorial.all_objects.filter(
                ativo=True, excluido_em__isnull=True, fim__lt=agora,
            ).count())
        )
        self.stdout.write(
            "Publicados sem imagem: "
            + str(Artigo.all_objects.filter(
                status=EditorialStatus.PUBLICADO, ativo=True,
                excluido_em__isnull=True,
            ).filter(Q(imagem_capa="") | Q(imagem_capa__isnull=True)).count())
        )
        duplicadas = CategoriaNoticia.all_objects.values("slug").annotate(
            total=Count("pk")
        ).filter(total__gt=1)
        self.stdout.write(
            "Slugs de categoria duplicados: "
            + (", ".join(item["slug"] for item in duplicadas) or "nenhum")
        )
