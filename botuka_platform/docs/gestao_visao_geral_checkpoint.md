# Gestão — visão geral — checkpoint final (Etapas 5–12)

## Estado da primeira versão

A primeira versão funcional completa da `/gestao/` está fechada para o escopo das
Etapas 5–12. A central administrativa reutiliza os domínios e serviços existentes,
mantém autorização no backend e não cria operações para as quais o produto ainda
não possui backend seguro.

## Módulos disponíveis

- **Taxonomias:** taxonomia empresarial (categorias, subcategorias, CNAEs e
  mapeamentos) e acesso à taxonomia própria de produtos.
- **Localidades:** países, estados, cidades e bairros.
- **Conteúdo:** artigos/notícias, categorias editoriais, eventos, vídeos/YuBotuka e
  turismo.
- **Negócios:** empresas, equipe e solicitações; produtos, serviços, agendamentos e
  vagas.
- **Publicidade:** campanhas, planos, posições, segmentações, criativos,
  contratações, entregas e auditoria.
- **Financeiro:** cobranças, itens, pagamentos, transações, webhooks e chaves de
  idempotência.
- **Inteligência:** GA4, analytics interno e trilhas de auditoria.
- **Sistema e acesso:** usuários, perfis, permissões, contatos e configurações.

## CRUDs completos e operações administrativas

- Empresas, vínculos de equipe, solicitações, capacidades e funções empresariais,
  respeitando propriedade histórica e soft-delete.
- Usuários, perfis e permissões nos limites dos serviços auditados; senha nunca é
  exibida e contas novas recebem senha inutilizável.
- Categorias/subcategorias empresariais, CNAEs e mapeamentos CNAE, com status
  lógico e proteção do CNAE principal.
- Países, estados, cidades e bairros, com hierarquia validada e status lógico.
- Configurações e contatos institucionais conforme permissões existentes.
- Moderação/configuração publicitária pelos serviços próprios já existentes.

Todas as mutações auditadas usam POST com CSRF. Não foi adicionada exclusão física
nem mutação por GET.

## Áreas somente leitura

- Conteúdo, produtos, serviços, agenda e vagas na visão global da Gestão; as
  operações editoriais/empresariais continuam nos fluxos próprios.
- Cobranças, pagamentos, transações, webhooks e idempotência.
- Eventos analíticos, agregados e auditorias.
- Propriedade histórica da empresa, relações pessoais sem serviço auditado
  (`UsuarioCapacidade`, `UsuarioPerfil`, `UsuarioGrupo`, `UsuarioPermissao`) e
  dados financeiros/publicitários históricos.
- Payloads, headers, metadata e valores de configuração sensíveis são omitidos.

## Backends inexistentes e integrações pendentes

- Pedidos/checkout central independente: **backend inexistente — não implementado**.
- Filas e saúde operacional administrativa: **backend inexistente — não
  implementado**.
- C6: endpoints, credenciais e transporte reais permanecem pendentes de integração;
  nada foi inventado. Mercado Pago continua sendo usado no escopo já suportado.
- GA4 Data API depende de propriedade e credenciais externas; sem configuração, a
  interface preserva o estado indisponível seguro.
- Edição dos campos JSON técnicos do CNAE permanece fora desta primeira versão.

## Regressão e validações finais

- Regressão principal atualizada — Gestão + Advertising + Payments + Analytics:
  **104/104 aprovados**.
- Produtos: **58/58 aprovados**.
- Organizations + Taxonomy + Accounts: **135/135 aprovados**.
- Conteúdo (News + Media + Events + Tourism + Government): **133/133 aprovados**.
- Agenda: a regressão real do card empresarial foi corrigida e retestada; **130/131
  aprovados no SQLite**, restando somente o cenário concorrente dependente de
  PostgreSQL descrito abaixo.
- Descoberta global: **1.037 testes encontrados; 1.023 executados; 1 falha e 11
  erros**, todos classificados como ambientais/preexistentes e não relacionados às
  Etapas 5–12.
- `manage.py check`: aprovado, sem issues.
- `manage.py makemigrations --check --dry-run`: aprovado, nenhuma mudança.
- `git diff --check`: aprovado.
- Referências literais de templates nos módulos auditados: **30 verificadas, zero
  ausentes**.

## Falhas ambientais/preexistentes da descoberta global

- SQLite não reproduz o bloqueio concorrente/constraint do PostgreSQL no teste de
  duas reservas simultâneas da Agenda e retorna `database table is locked`.
- Testes de matriz RLS/executor `worker` exigem conexões PostgreSQL independentes;
  aliases SQLite espelhados disputam a mesma tabela.
- Testes do catálogo de serviços consultam sequence PostgreSQL, exigem host/banco
  local nominal e um diretório externo `_auditoria_cbo` que não existe neste
  worktree.
- Seeds demonstrativos recusam corretamente o nome URI do banco SQLite em memória,
  que não integra sua allowlist defensiva.

Essas ocorrências não foram mascaradas e nenhuma regra de negócio foi relaxada para
fazê-las passar. A validação PostgreSQL integral permanece indicada quando houver o
executor local e os artefatos externos correspondentes.

## Auditoria final

- Reverses e links da sidebar cobertos pelas suítes HTTP; o atalho “Gerenciar
  Agenda” e o indicador “Serviços vinculados” foram restaurados e retestados.
- Permissões MASTER/não-MASTER permanecem tanto na apresentação quanto no backend.
- Listagens usam paginação e filtros reais; detalhes e dashboards usam
  `select_related`/`prefetch_related` nos relacionamentos relevantes e o dashboard
  MASTER conserva teste de teto de queries.
- Nenhum template literal ausente, import quebrado, segredo codificado ou
  TODO/FIXME/HACK/XXX foi introduzido nos módulos das Etapas 5–12.

## Prioridades da próxima rodada visual/funcional

1. Rodar os cenários concorrentes e a matriz RLS em PostgreSQL com os quatro
   executores reais de teste.
2. Refinar consistência visual, responsividade e estados vazios das telas centrais,
   sem duplicar os fluxos operacionais do Painel.
3. Evoluir os backends ausentes de pedidos/checkout e saúde/filas antes de criar
   telas administrativas correspondentes.
4. Concluir integrações externas de C6 e GA4 em ambiente seguro e adicionar testes
   contratuais dos provedores.
5. Avaliar um serviço auditado específico antes de permitir mutação das relações de
   usuário hoje somente leitura e, depois, tratar a edição técnica do CNAE.

## Checkpoints confirmados

- `docs/gestao_taxonomia_checkpoint.md`
- `docs/gestao_localidades_checkpoint.md`
- `docs/gestao_conteudo_checkpoint.md`
- `docs/gestao_negocios_checkpoint.md`
- `docs/gestao_publicidade_checkpoint.md`
- `docs/gestao_financeiro_checkpoint.md`
- `docs/gestao_analytics_checkpoint.md`
- `docs/gestao_sistema_checkpoint.md`

Nenhum commit ou push foi realizado e produção não foi acessada.
