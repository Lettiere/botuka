# Modulos BOTUKA

Status baseado no levantamento inicial de `D:\www\Botuka`.

| Nome | Diretorio | Objetivo | Situacao atual | Projeto Django | Home publica | Painel | Banco | Autenticacao | Porta | Schema | Dependencias | Proximo passo |
|---|---|---|---|---|---|---|---|---|---:|---|---|---|
| BOTUKA Platform | botuka_platform | Plataforma central, home, usuarios, painel e gestao. | funcional | Sim | Sim | Sim | SQLite/env; precisa PostgreSQL obrigatorio | Central atual | 7700 | platform | Django, DRF e apps internos | Remover fallback silencioso SQLite e preparar PostgreSQL/schema. |
| BOTUKA Servicos | botuka_services | Modulo de servicos. | incompleto | Sim | Sim | Nao | SQLite | Nao integrado definitivamente | 7701 | services | Django; requirements em pasta/ausente na raiz | Criar painel, requirements.txt raiz, .venv propria e PostgreSQL. |
| BOTUKA Classificados | botuka_classificados | Classificados e anuncios. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7702 | classified | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Curriculos | botuka_curriculos | Curriculos e perfis profissionais. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7703 | resume | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Dashboard | botuka_dasboard | Dashboard executivo/operacional. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7704 | dashboard | Planejadas | Decidir renomeacao para `botuka_dashboard` antes de criar projeto. |
| BOTUKA Empregos | botuka_empregos | Vagas e candidaturas. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7705 | jobs | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Empresas | botuka_empresas | Empresas, organizacoes e negocios. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7706 | organizations | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Eventos | botuka_eventos | Eventos locais. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7707 | events | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Gastronomia | botuka_gastronomia | Gastronomia, estabelecimentos e ofertas. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7708 | gastronomy | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Imoveis | botuka_imoveis | Imoveis e anuncios imobiliarios. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7709 | realestate | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Mobilidade | botuka_mobilidade | Mobilidade, rotas, viagens e veiculos. | incompleto | Sim | Nao roteada no padrao | Nao | SQLite | Nao integrado definitivamente | 7710 | mobility | Django; requirements em pasta | Criar website/painel no padrao e migrar banco para PostgreSQL. |
| BOTUKA Turismo | botuka_turismo | Turismo regional. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7711 | tourism | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA Veiculos | botuka_veiculos | Veiculos, anuncios e servicos relacionados. | vazio | Nao | Nao | Nao | Planejado | Planejada via central | 7712 | vehicles | Planejadas | Criar fundacao Django quando priorizado. |
| BOTUKA API | botuka_api | API interna e futura camada de integracao/autenticacao. | vazio | Nao | Nao | Nao | Planejado | Futura camada central | 7799 | api | Planejadas | Proximo projeto recomendado: criar fundacao Django na porta 7799. |
| BOTUKA Core | botuka_core | Codigo compartilhado, referencias comuns e possiveis pacotes base. | compartilhado | Nao | Nao | Nao | Nao aplicavel | Nao aplicavel | N/A | core | Codigo Python/base | Analisar antes de reutilizar; nao transformar automaticamente em projeto Django. |

## Observacoes

- `botuka_core` nao deve receber `manage.py` sem decisao arquitetural.
- `botuka_dasboard` parece conter erro de digitacao. O nome recomendado e `botuka_dashboard`, mas o diretorio atual deve ser preservado ate aprovacao explicita.
- Projetos secundarios nao devem duplicar tabela de usuario.
