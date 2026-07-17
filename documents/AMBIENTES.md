# Ambientes

## Aviso de Seguranca

Nunca registrar valores reais de credenciais, tokens, `SECRET_KEY`, senha de banco, cookies, dados de sessao, chaves privadas ou dados pessoais neste documento.

## Ambientes Previos

| Ambiente | Uso | Caracteristicas |
|---|---|---|
| local | Desenvolvimento individual | Porta local propria, `.env` local, `.venv` propria, logs locais. |
| homologacao | Validacao antes de producao | Dados controlados, secrets separados, subdominios ou hosts de teste. |
| producao | Operacao publica | Secrets por ambiente, PostgreSQL, reverse proxy, HTTPS e monitoramento. |

## Cada Projeto Deve Possuir

- `.env` local nao versionado.
- `.env.example` versionado.
- `requirements.txt` proprio.
- `.venv` propria.
- settings proprios.
- conexao propria.
- porta propria.
- logs proprios.

## Variaveis Esperadas

| Variavel | Finalidade | Exemplo ficticio |
|---|---|---|
| DJANGO_SECRET_KEY | Chave da aplicacao Django. | trocar-por-chave-segura |
| DJANGO_DEBUG | Liga/desliga debug. | True |
| DJANGO_ALLOWED_HOSTS | Hosts permitidos. | 127.0.0.1,localhost |
| DJANGO_CSRF_TRUSTED_ORIGINS | Origens confiaveis CSRF. | http://127.0.0.1:7700 |
| DATABASE_URL | URL completa do banco, quando adotada. | postgresql://usuario:senha@localhost:5432/botuka |
| DATABASE_HOST | Host do PostgreSQL. | localhost |
| DATABASE_PORT | Porta do PostgreSQL. | 5432 |
| DATABASE_NAME | Nome do banco. | botuka |
| DATABASE_USER | Usuario do banco. | botuka_user |
| DATABASE_PASSWORD | Senha do banco. | alterar |
| DATABASE_SCHEMA | Schema do modulo. | services |
| SESSION_COOKIE_DOMAIN | Dominio de sessao, se compartilhado. | .botuka.com.br |
| SESSION_COOKIE_NAME | Nome do cookie de sessao. | botuka_sessionid |
| BOTUKA_API_URL | URL da API interna. | http://127.0.0.1:7799 |
| BOTUKA_API_TOKEN | Token tecnico quando aprovado. | vazio-no-exemplo |
| CNPJ_PROVIDER | Provider de consulta CNPJ. | receita-ou-provider |
| CNPJ_API_URL | URL da API de CNPJ. | https://provider.example/api |
| CNPJ_API_TOKEN | Token do provider CNPJ. | vazio-no-exemplo |

## Regras de .env

- `.env.example` contem apenas nomes e exemplos ficticios.
- `.env` contem valores reais.
- `.env` nunca deve ser enviado ao Git.
- Tokens devem ser diferentes por ambiente.
- `SECRET_KEY` nunca deve ser compartilhada sem decisao arquitetural.
- Caso sessoes entre subdominios sejam compartilhadas, isso deve estar formalmente documentado em `AUTENTICACAO.md` e `DECISOES_ARQUITETURA.md`.
