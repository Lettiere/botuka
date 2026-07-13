# Autenticacao

## Arquitetura Atual

- `botuka_platform` possui a autenticacao central atual.
- Modulos ainda nao estao integrados definitivamente a essa autenticacao.
- Usuarios nao devem ser duplicados em cada modulo.
- Nao copiar `AUTH_USER_MODEL` do `botuka_platform` para projetos secundarios sem decisao formal.

## Arquitetura Desejada

- Login central.
- API de autenticacao.
- Token de curta duracao.
- Refresh token.
- SSO entre subdominios.
- Autorizacao por modulo e capacidade.
- Sessao compartilhada somente quando tecnicamente segura.
- Projetos secundarios nao geram tabela propria de usuario central.

## Alternativas Tecnicas

1. API central com JWT.
   - Boa para independencia entre projetos.
   - Exige estrategia de refresh, revogacao e escopos.
2. OAuth2/OIDC.
   - Padrao robusto para SSO e multiplos clientes.
   - Exige provider e configuracao mais formal.
3. Sessao compartilhada entre subdominios.
   - Pode simplificar experiencia web.
   - Exige cuidado com cookie domain, CSRF, HTTPS e isolamento.
4. Model `managed=False` para consulta controlada.
   - Util para leitura de dados centrais.
   - Nao deve virar copia de usuario nem substituir decisao de autenticacao.

## Recomendacao Inicial

- `botuka_platform` permanece como identidade central.
- `botuka_api` deve evoluir como camada futura de autenticacao e integracao.
- Modulos consomem autenticacao central.
- Nao copiar o model User para os modulos.
- Nao criar tabelas de usuario duplicadas.
