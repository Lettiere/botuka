# Documentacao BOTUKA

Esta pasta centraliza a documentacao de arquitetura, operacao e decisoes dos projetos BOTUKA. Ela existe para manter os modulos independentes alinhados antes da criacao de novos projetos Django, schemas, portas e integracoes.

## Indice

- [PORTAS.md](PORTAS.md): portas locais, URLs, subdominios futuros, schemas e status.
- [MODULOS.md](MODULOS.md): finalidade, situacao atual e proximos passos de cada modulo.
- [BANCO_DE_DADOS.md](BANCO_DE_DADOS.md): banco, schemas, propriedade de tabelas e regras de migrations.
- [AMBIENTES.md](AMBIENTES.md): local, homologacao, producao e variaveis esperadas.
- [AUTENTICACAO.md](AUTENTICACAO.md): login central, sessao, API, tokens e SSO.
- [INTEGRACOES.md](INTEGRACOES.md): APIs externas, providers, variaveis e status.
- [DEPLOY.md](DEPLOY.md): padrao futuro de publicacao por projeto.
- [DECISOES_ARQUITETURA.md](DECISOES_ARQUITETURA.md): decisoes importantes, motivos e impactos.
- [ENV_PADRAO.example](ENV_PADRAO.example): modelo de variaveis para novos projetos.

## Regra de Atualizacao

Antes de criar ou alterar um modulo, atualize primeiro a documentacao correspondente. Portas, schemas, subdominios, integracoes e decisoes arquiteturais devem ficar registradas aqui antes da implementacao.

## Aviso de Seguranca

Nunca registrar senhas, tokens, SECRET_KEY, credenciais de banco, chaves privadas, cookies, dados de sessao, CPF, CNPJ de clientes, enderecos particulares ou qualquer dado sensivel nestes documentos.

## Padrao dos Projetos

Cada diretorio de negocio deve evoluir para um projeto Django independente, com `manage.py`, `config/`, `apps/`, `templates/`, `static/`, `media/`, `requirements.txt`, `.env.example`, `.gitignore`, `.venv` propria, app `website`, app `painel`, porta local propria e schema PostgreSQL proprio.

Os modulos nao devem virar simples apps dentro de `botuka_platform`.

## Responsabilidades

- Arquitetura e decisoes: `DECISOES_ARQUITETURA.md`.
- Portas, URLs e subdominios: `PORTAS.md`.
- Status de modulos: `MODULOS.md`.
- Banco, schemas e propriedade das tabelas: `BANCO_DE_DADOS.md`.
- Ambientes e variaveis: `AMBIENTES.md`.
- Autenticacao e autorizacao: `AUTENTICACAO.md`.
- APIs externas e internas: `INTEGRACOES.md`.
- Publicacao e operacao: `DEPLOY.md`.
