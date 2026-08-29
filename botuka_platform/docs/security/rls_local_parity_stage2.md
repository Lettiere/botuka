# RLS PostgreSQL — etapa local 2

Data: 2026-08-29

Branch: `feature/rls-postgresql`

HEAD base: `84be31c3`

## PostgreSQL local

- Engine Django: `django.db.backends.postgresql`
- Banco: `botuka1`
- Host: `127.0.0.1`
- Porta: `5432`
- Owner/migration role: `sawaya`
- Runtime role: `botuka_app`
- Servidor: PostgreSQL 18.3, 64-bit, Windows
- Nenhuma senha foi registrada neste relatório.

`botuka_app` foi criada exclusivamente no PostgreSQL local com `LOGIN`,
`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT` e `NOBYPASSRLS`.
Possui `CONNECT` em `botuka1`, `USAGE` nos schemas de aplicação, DML nas
tabelas, `USAGE`/`SELECT` nas sequences e default privileges equivalentes para
objetos futuros criados por `sawaya`.

Todas as 234 tabelas de aplicação locais pertencem a `sawaya`.

## Schemas e tabelas

| Schema | Tabelas |
|---|---:|
| agenda | 7 |
| core | 18 |
| events | 3 |
| government | 6 |
| media | 30 |
| news | 22 |
| platform | 29 |
| public | 82 |
| services | 20 |
| sports | 10 |
| taxonomy | 7 |
| **Total de aplicação** | **234** |

Também existem `api` sem tabelas e os schemas internos `pg_catalog` e
`information_schema`.

## Migrations e diferença estrutural

- A migration `social.0007_rls_policies` foi aplicada localmente com sucesso.
- Essa migration cria policies e habilita RLS; ela não cria tabelas.
- Logo, a diferença entre 251 tabelas informadas em produção e 234 locais não
  é causada por migrations de criação de tabelas pendentes neste checkout.
- Todos os apps do projeto que possuem migrations aparecem no plano aplicado.

A causa nominal das 17 tabelas não pode ser determinada sem a lista de
`schema.table` de produção. As hipóteses ainda compatíveis são artefatos
exclusivos de produção, migrations/código fora deste HEAD, tabelas manuais ou
diferença no critério de contagem. Nenhuma tabela foi criada manualmente.

## Role e policies

`social.0007` foi aplicada pelo fluxo de migrations, sem criação manual de
policy. O estado local confirmado é:

- exatamente duas tabelas com RLS habilitado;
- `FORCE ROW LEVEL SECURITY = false` nas duas;
- `public.social_post_save_tb` com `social_post_save_owner_policy`;
- `public.social_block_tb` com `social_block_select_policy`,
  `social_block_insert_policy` e `social_block_delete_policy`.

Nenhum owner foi alterado e nenhuma nova policy funcional foi criada.
## Testes executados

Os 11 testes automatizados de `apps.core.test_rls_security` passaram. Eles
validam middleware, contexto transacional, identidade autenticada/anônima,
rollback e invariantes da migration existente. `manage.py check` também passou
sem issues.

Testes reais por conexão direta como `botuka_app` comprovaram:

- `social_post_save_tb` sem `app.user_id`: nenhuma linha visível;
- usuário 3: somente o próprio registro visível;
- usuário 5: registro do usuário 3 invisível;
- escrita forjada do usuário 5 com `usuario_id=3`: bloqueada pelo PostgreSQL;
- contexto `app.user_id`: sem vazamento após rollback;
- `social_block_tb`: tentativa forjada pelo usuário 5 com bloqueador do usuário
  3 bloqueada;
- inserção legítima pelo usuário 3 visível dentro da transação;
- rollback concluído e contagem final de `social_block_tb` igual a zero.

O Django local permanece configurado com `DB_USER=sawaya`. Como `sawaya` é
owner das tabelas e `FORCE=false`, testes ORM pela conexão padrão não são
descritos como prova de enforcement RLS.
## Segredos / credenciais

A matriz mascarada está em `secret_audit_local.csv`. Ela não contém valores,
somente arquivo, linha, tipo, versionamento, classificação, risco, consumidor
provável e recomendação.

- Ocorrências classificadas: 65.
- Críticas: 3.
- Altas: 5.
- Baixas/falsos positivos/exemplos: 57.
- Ocorrências atuais ou históricas possivelmente reais: 8.
- Itens históricos que exigem rotação: 2.

Achados materiais:

- `.env` local, não versionado: `SECRET_KEY` e `DB_PASSWORD` não-placeholder.
- Três backups locais de `.env`: cópias de `SECRET_KEY` não-placeholder.
- `botuka_core/.env`: `SECRET_KEY` não-placeholder.
- Commit histórico `c8bc7ffa`: `.env` e `botuka_core/.env` continham
  `SECRET_KEY` não-placeholder. As duas chaves devem ser tratadas como expostas
  e rotacionadas nos ambientes consumidores.
- `.env.example` e `botuka_finance/.env.example`: placeholders ou campos
  vazios, sem evidência de segredo real.
- `documents/AMBIENTES.md:34`: URL de credencial classificada como exemplo.
- Literais de password em testes e código de dependências/ambientes virtuais:
  falsos positivos. Ambientes virtuais versionados são um problema de higiene
  do repositório, mas não evidenciaram segredo por esses matches.

Não houve rotação, remoção, edição de `.env`, reescrita de histórico ou
alteração de `.gitignore`.

## Próximo passo

1. Fechar e revisar a documentação da paridade local concluída.
2. Obter inventário somente de nomes `schema.table` da produção para explicar
   nominalmente as 17 tabelas ausentes.
3. Decidir separadamente, sob nova autorização, se haverá próximo lote de RLS;
   nenhuma nova policy foi aprovada nesta etapa.
4. Rotacionar as duas `SECRET_KEY` históricas após identificar consumidores;
   qualquer higienização de histórico deve ser uma etapa separada e autorizada.

Nenhuma nova policy funcional deve ser considerada antes de nova decisão.
