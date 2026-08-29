# Auditoria global de RLS PostgreSQL

Data: 2026-08-29
Branch: `feature/rls-postgresql`
HEAD auditado: `84be31c3`

## Escopo e limitação

A inspeção local cobriu as 234 tabelas de aplicação presentes no PostgreSQL e
os 225 models carregados pelo registry Django. O inventário informado de
produção contém 251 tabelas. Portanto, 17 tabelas de produção não existem
neste banco local e não puderam ser classificadas sem acessar produção.

O banco local usa `sawaya` como owner/migration role e possui a runtime role
`botuka_app`, criada exclusivamente para desenvolvimento com `LOGIN`,
`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT` e `NOBYPASSRLS`.
A migration `social.0007_rls_policies` foi aplicada localmente. Exatamente duas
tabelas têm RLS habilitado, ambas com `FORCE ROW LEVEL SECURITY = false`, e as
quatro políticas esperadas estão materializadas.

A matriz completa, por tabela, está em `rls_global_audit.csv`. Ela combina
relacionamentos do catálogo PostgreSQL, correspondência com models Django e
classificação semântica conservadora. Casos de maior impacto foram validados
contra views, services, permissions, admin, agregações e fluxos cross-user.

## Resultado local

| Grupo | Descrição | Tabelas |
|---|---|---:|
| A | USER_OWNED_PRIVATE | 1 |
| B | COMPANY_SCOPED | 14 |
| C | PUBLIC_READ_PRIVATE_WRITE | 87 |
| D | PARTICIPANT_SCOPED | 21 |
| E | ADMIN_OR_WORKFLOW | 31 |
| F | SYSTEM_GLOBAL | 76 |
| G | DEFER | 4 |
| **Total local** |  | **234** |

## Políticas existentes preservadas

- `public.social_post_save_tb`: política de proprietário
  `social_post_save_owner_policy`.
- `public.social_block_tb`: políticas assimétricas
  `social_block_select_policy`, `social_block_insert_policy` e
  `social_block_delete_policy`.

A migration `apps/social/migrations/0007_rls_policies.py` usa `botuka_app`,
`app.user_id`, `ENABLE ROW LEVEL SECURITY`, não usa `FORCE`, e possui reverse
para desabilitar RLS e remover as quatro políticas.
Os testes reais por conexão direta como `botuka_app` comprovaram que:

- sem `app.user_id`, `social_post_save_tb` não expõe registros;
- usuários 3 e 5 ficam isolados, e o usuário 5 não visualiza o registro do
  usuário 3;
- escrita forjada em nome de outro usuário é bloqueada pelo PostgreSQL;
- em `social_block_tb`, inserção forjada é bloqueada e inserção legítima pelo
  bloqueador funciona;
- o rollback remove integralmente a inserção de teste e o contexto
  `app.user_id` não vaza para a transação seguinte.

A conexão Django local continua usando `sawaya`. Como essa role é owner e
`FORCE=false`, consultas ORM pela conexão padrão não constituem prova de
enforcement. As evidências acima foram obtidas diretamente com `botuka_app`.

## Tabelas que não devem receber RLS de usuário

As 76 tabelas do grupo F são catálogos, configuração, referência ou estado
global do sistema. O detalhamento nominal está no CSV. RLS dependente de
`app.user_id` nelas introduziria indisponibilidade sem criar isolamento útil.
Exemplo confirmado: `CNPJConsulta` é cache global consultado por CNPJ, inclusive
em fluxos que não pertencem a um usuário específico.

## Casos adiados

- `events.events_interesseevento`: contagem pública, métricas e acesso de
  gestores a interessados de terceiros.
- `services.services_servico_favorito_tb`: propriedade direta, mas o Django
  Admin atual requer consulta global.
- `public.social_notification_tb`: leitura do destinatário, porém inserções
  legítimas são cross-user e de sistema.
- `public.recruitment_curriculo_tb`: visibilidade pública/privada e leitura por
  recrutadores autorizados.

Outros grupos D e E também exigem políticas por participante, empresa ou papel;
uma comparação simples com `app.user_id` não é segura.

## Próximo lote

Nenhuma nova tabela foi aprovada nesta execução. A única tabela local que
classifica diretamente como A já está coberta pela migration existente. As
candidatas seguintes precisam antes de um contrato explícito para admin,
serviços cross-user e jobs.

Uma política futura para `ServicoFavorito`, por exemplo, teria `USING` e
`WITH CHECK` por `usuario_id = NULLIF(current_setting('app.user_id', true),
'')::bigint`, mas não deve ser criada enquanto o acesso administrativo não
tiver uma estratégia separada e testada. Isso é uma proposta de desenho, não
SQL aprovado para execução.

## Rollback

O rollback transacional dos testes reais foi comprovado, inclusive com
contagem final zero em `social_block_tb` e ausência de vazamento de
`app.user_id`. Para rollback da implantação local, o reverse da migration
`0007` desabilita RLS nas duas tabelas e remove somente as quatro políticas
nomeadas. Uma migration futura deve repetir esse padrão, sem `FORCE`, sem troca
de owner e sem alterar migrations já aplicadas.
## Condições para continuar

A paridade local de role, permissões e policies foi concluída. Antes de decidir
qualquer novo lote:

1. Obter o inventário somente de nomes `schema.table` das 17 tabelas de
   produção ainda não identificadas nominalmente.
2. Fechar e revisar a documentação desta etapa.
3. Decidir separadamente se haverá próximo lote de RLS.
4. Se houver, definir primeiro o contrato administrativo de `ServicoFavorito`
   ou selecionar outra candidata sem leitura global/cross-user.
5. Somente após nova aprovação criar migration sequencial e reversível.

Nenhuma nova policy foi aprovada nesta etapa.
