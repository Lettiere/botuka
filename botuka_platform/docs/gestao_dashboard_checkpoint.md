# Checkpoint — Dashboard da Gestão

## Estado

Etapa 2 concluída em 13/09/2026 após auditoria, implementação, testes e reauditoria.

## Auditado

- dashboard anterior e suas consultas;
- models, estados, permissões, serviços e URLs de Advertising;
- models financeiros e regras de imutabilidade de Payments;
- eventos e agregados diários de Analytics;
- auditorias de publicidade e do núcleo;
- exposição de links e dados globais para usuários não MASTER;
- quantidade máxima de queries no carregamento MASTER.

## Já existia

- cards com contagens básicas de usuários, organizações e taxonomias;
- duas pendências de produtos;
- administração de campanhas publicitárias restrita a MASTER;
- models financeiros completos, sem interface administrativa global;
- dashboard de Analytics isolado por empresa;
- registros de auditoria do núcleo e de Advertising.

## Faltava

- métricas integradas de Advertising, Payments e Analytics;
- atividade recente auditável;
- insights derivados dos dados reais;
- pendências de campanha, criativo, pagamento e webhook;
- separação explícita de dados financeiros e analytics globais para MASTER;
- filtragem dos cards gerais pelas permissões efetivas;
- teste de limite de queries.

## Implementado

- métricas agregadas de campanhas, criativos, impressões, cliques e CTR;
- totais e valores de cobranças pagas/pendentes, falhas e webhooks inconsistentes;
- visualizações, visitantes, leads e eventos recentes de Analytics;
- pendências operacionais com links somente quando existe backend de administração;
- insights de fila publicitária, atenção financeira, CTR e conversão observada;
- atividade recente unificada a partir de `AuditoriaPublicidade` e `Auditoria`;
- cards gerais condicionados às permissões de domínio;
- teste que limita o dashboard MASTER a no máximo 45 queries, incluindo componentes globais.

## Arquivos alterados

- `apps/gestao/views.py`
- `apps/gestao/test_dashboard.py`
- `templates/gestao/dashboard.html`

## Regras de permissão

- acesso base continua sendo MASTER ou `gestao.acessar`;
- cards gerais exigem a permissão da área correspondente;
- métricas globais de Advertising, Payments, Analytics e atividades são exclusivas de MASTER;
- nenhum link para administração financeira ou analytics global foi inventado, pois esses backends ainda não possuem essas telas;
- o link de moderação publicitária reutiliza a administração MASTER existente.

## Testes e validações

- testes focados da Gestão: 15 aprovados antes do teste de queries;
- teste focado do dashboard e limite de queries: 4 aprovados;
- regressões isoladas de Advertising, Payments e Analytics: 43 aprovadas;
- validação combinada final de Gestão + Advertising + Payments + Analytics: 59 aprovadas;
- `manage.py check`: aprovado;
- `git diff --check`: aprovado;
- busca por TODO/FIXME introduzido: nenhum resultado;
- revisão de queries e links: aprovada.

## Pendências reais

Nenhuma pendência conhecida da Etapa 2. Interfaces administrativas próprias de Payments e Analytics serão tratadas nas etapas 10 e 11; o dashboard não cria substitutos nem ações perigosas.
