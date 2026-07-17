# Portas e URLs

Padrao definitivo de portas locais dos projetos BOTUKA.

| Projeto | Diretorio | Porta | URL local | Subdominio futuro | Schema | Status | Observacoes |
|---|---:|---:|---|---|---|---|---|
| BOTUKA Platform | botuka_platform | 7700 | http://127.0.0.1:7700/ | botuka.com.br | platform | existente | Projeto funcional; schema ainda deve ser confirmado no PostgreSQL. |
| BOTUKA Servicos | botuka_services | 7701 | http://127.0.0.1:7701/ | servicos.botuka.com.br | services | incompleto | Possui website; precisa painel e PostgreSQL. |
| BOTUKA Classificados | botuka_classificados | 7702 | http://127.0.0.1:7702/ | classificados.botuka.com.br | classified | planejado | Diretorio vazio no levantamento. |
| BOTUKA Curriculos | botuka_curriculos | 7703 | http://127.0.0.1:7703/ | curriculos.botuka.com.br | resume | planejado | Diretorio vazio no levantamento. |
| BOTUKA Dashboard | botuka_dasboard | 7704 | http://127.0.0.1:7704/ | dashboard.botuka.com.br | dashboard | planejado | Diretorio atual tem possivel erro de digitacao; nome recomendado: `botuka_dashboard`. Nao renomear sem decisao explicita. |
| BOTUKA Empregos | botuka_empregos | 7705 | http://127.0.0.1:7705/ | empregos.botuka.com.br | jobs | planejado | Diretorio vazio no levantamento. |
| BOTUKA Empresas | botuka_empresas | 7706 | http://127.0.0.1:7706/ | empresas.botuka.com.br | organizations | planejado | Diretorio vazio no levantamento. |
| BOTUKA Eventos | botuka_eventos | 7707 | http://127.0.0.1:7707/ | eventos.botuka.com.br | events | planejado | Diretorio vazio no levantamento. |
| BOTUKA Gastronomia | botuka_gastronomia | 7708 | http://127.0.0.1:7708/ | gastronomia.botuka.com.br | gastronomy | planejado | Diretorio vazio no levantamento. |
| BOTUKA Imoveis | botuka_imoveis | 7709 | http://127.0.0.1:7709/ | imoveis.botuka.com.br | realestate | planejado | Diretorio vazio no levantamento. |
| BOTUKA Mobilidade | botuka_mobilidade | 7710 | http://127.0.0.1:7710/ | mobilidade.botuka.com.br | mobility | incompleto | Projeto Django existente; precisa adequar ao padrao. |
| BOTUKA Turismo | botuka_turismo | 7711 | http://127.0.0.1:7711/ | turismo.botuka.com.br | tourism | planejado | Diretorio vazio no levantamento. |
| BOTUKA Veiculos | botuka_veiculos | 7712 | http://127.0.0.1:7712/ | veiculos.botuka.com.br | vehicles | planejado | Diretorio vazio no levantamento. |
| BOTUKA API | botuka_api | 7799 | http://127.0.0.1:7799/ | api.botuka.com.br | api | planejado | Porta definitiva da API. |

## Regras

- Uma porta por projeto.
- Nenhuma porta pode ser reutilizada.
- A API sempre usa a porta `7799`.
- Novas portas devem seguir a sequencia a partir de `7713`.
- A porta deve ser atualizada neste documento antes da criacao do modulo.
- A porta nao deve ficar fixa em `settings.py`.
- A execucao local deve ocorrer por `runserver`.
- Nao utilizar a porta `7002`.

Exemplo:

```powershell
python manage.py runserver 7701
```

Os schemas listados sao planejamento inicial e nao significam que ja existem no PostgreSQL.
