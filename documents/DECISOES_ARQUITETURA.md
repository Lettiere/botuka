# Decisoes de Arquitetura

Formato:

- Data
- Decisao
- Motivo
- Impacto
- Status
- Modulos afetados

## 2026-07-11 - Projetos Django independentes por dominio

- Decisao: cada diretorio de negocio sera um projeto Django independente.
- Motivo: permitir subdominios, deploys e evolucao isolada.
- Impacto: cada modulo tera `manage.py`, settings, apps, templates, static, media e dependencias proprias.
- Status: aprovado como direcao.
- Modulos afetados: todos os modulos de negocio.

## 2026-07-11 - Porta local propria por projeto

- Decisao: cada projeto tera sua propria porta local.
- Motivo: evitar conflitos e facilitar execucao paralela.
- Impacto: portas devem ser documentadas antes da criacao do modulo.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - Subdominio futuro por projeto

- Decisao: cada projeto tera futuramente subdominio proprio.
- Motivo: separar dominios de negocio e deploy.
- Impacto: ALLOWED_HOSTS e CSRF devem ser configurados por projeto.
- Status: planejado.
- Modulos afetados: todos.

## 2026-07-11 - Ambiente virtual proprio por projeto

- Decisao: cada projeto tera `.venv` propria.
- Motivo: isolar dependencias.
- Impacto: nao compartilhar `.venv` entre projetos.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - API na porta 7799

- Decisao: `botuka_api` usara a porta definitiva `7799`.
- Motivo: reservar a ultima porta da faixa para API central.
- Impacto: a API fica isolada na ultima porta reservada da faixa local.
- Status: aprovado.
- Modulos afetados: botuka_api e consumidores da API.

## 2026-07-11 - Usuario centralizado

- Decisao: usuario sera centralizado.
- Motivo: evitar duplicidade de identidade e permissoes inconsistentes.
- Impacto: modulos secundarios nao devem criar tabela propria de usuario central.
- Status: aprovado como direcao.
- Modulos afetados: todos.

## 2026-07-11 - Nao duplicar tabela de usuario

- Decisao: nao serao criadas tabelas de usuario duplicadas.
- Motivo: consistencia e seguranca.
- Impacto: usar API, SSO ou consultas controladas.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - PostgreSQL como banco definitivo

- Decisao: PostgreSQL sera o banco definitivo.
- Motivo: suporte a schemas, robustez e producao.
- Impacto: SQLite fica apenas como transitorio local em projetos incompletos.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - Schema proprio por dominio

- Decisao: cada dominio tera schema proprio.
- Motivo: isolar propriedade de tabelas.
- Impacto: migrations so devem ser geradas pelo projeto proprietario.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - Pasta documents como fonte principal

- Decisao: `documents` sera a fonte principal de documentacao.
- Motivo: separar documentacao arquitetural da pasta `docs` existente.
- Impacto: alteracoes arquiteturais devem atualizar esta pasta.
- Status: aprovado.
- Modulos afetados: todos.

## 2026-07-11 - Preservar docs existente

- Decisao: o diretorio `docs` existente sera preservado.
- Motivo: evitar perda ou mistura de documentacao legada.
- Impacto: nao apagar, mover ou renomear `docs` nesta etapa.
- Status: aprovado.
- Modulos afetados: documentacao.

## 2026-07-11 - botuka_core nao vira projeto automaticamente

- Decisao: `botuka_core` nao sera transformado automaticamente em projeto Django.
- Motivo: ele contem codigo compartilhado/base e precisa de decisao propria.
- Impacto: nao criar `manage.py` em `botuka_core` sem aprovacao.
- Status: aprovado.
- Modulos afetados: botuka_core e consumidores.

## 2026-07-11 - Possivel erro em botuka_dasboard

- Decisao: `botuka_dasboard` contem possivel erro de nome e nao sera renomeado sem aprovacao.
- Motivo: evitar quebra de referencias e mudancas destrutivas.
- Impacto: documentar nome recomendado `botuka_dashboard`, preservando o diretorio atual.
- Status: pendente de decisao.
- Modulos afetados: botuka_dasboard.
