# Banco de Dados

## Aviso de Seguranca

Nunca registrar senhas de banco, usuarios reais, strings de conexao com credenciais, tokens, dados pessoais, CPF, CNPJ de clientes ou chaves privadas neste documento.

## Padrao Planejado

- Banco definitivo: PostgreSQL.
- SQLite e permitido apenas temporariamente em projetos locais incompletos.
- SQLite nao deve ser fallback silencioso em producao.
- Cada modulo deve possuir schema proprio.
- Tabelas centrais nao devem ser duplicadas.
- Apenas o projeto proprietario de uma tabela deve gerar migrations dessa tabela.
- Projetos secundarios podem consumir dados por API ou models `managed=False` quando aprovado.
- Migrations nao devem cruzar projetos de forma descontrolada.

## Schemas

| Schema | Modulo proprietario | Finalidade | Projeto que gera migration | Projetos consumidores | Status |
|---|---|---|---|---|---|
| core | botuka_core / decisao futura | Referencias compartilhadas e tabelas comuns aprovadas. | A definir | Todos, quando aprovado | planejado |
| platform | botuka_platform | Usuarios, identidade central, painel e plataforma principal. | botuka_platform | Todos por API/SSO/consulta aprovada | existente/planejado no PostgreSQL |
| services | botuka_services | Servicos e prestadores. | botuka_services | platform, api | planejado |
| classified | botuka_classificados | Classificados. | botuka_classificados | platform, api | planejado |
| resume | botuka_curriculos | Curriculos. | botuka_curriculos | platform, empregos, api | planejado |
| dashboard | botuka_dasboard | Dashboards e indicadores. | botuka_dasboard | platform, api | planejado |
| jobs | botuka_empregos | Vagas e candidaturas. | botuka_empregos | platform, curriculos, api | planejado |
| organizations | botuka_empresas | Empresas e organizacoes. | botuka_empresas | platform, services, api | planejado |
| events | botuka_eventos | Eventos. | botuka_eventos | platform, api | planejado |
| gastronomy | botuka_gastronomia | Gastronomia. | botuka_gastronomia | platform, api | planejado |
| realestate | botuka_imoveis | Imoveis. | botuka_imoveis | platform, api | planejado |
| mobility | botuka_mobilidade | Mobilidade. | botuka_mobilidade | platform, api | planejado |
| tourism | botuka_turismo | Turismo. | botuka_turismo | platform, api | planejado |
| vehicles | botuka_veiculos | Veiculos. | botuka_veiculos | platform, api | planejado |
| api | botuka_api | Integracao interna, autenticacao futura e contratos API. | botuka_api | Todos | planejado |

## Convencoes Fisicas

Tabela:

```text
schema_nome_tb
```

Chave primaria:

```text
schema_nome_id
```

Indice:

```text
schema_nome_idx_descricao
```

Foreign key:

```text
schema_nome_fk_descricao
```
