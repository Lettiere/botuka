# Deploy

Este documento descreve o padrao futuro de publicacao. Nao e uma configuracao real de producao.

## Padrao Futuro

- Um servico por projeto.
- Uma porta interna por projeto.
- Reverse proxy na frente dos projetos.
- Subdominio proprio por modulo.
- Gunicorn para servir Django.
- Nginx como proxy e servidor de arquivos quando aplicavel.
- Static separado.
- Media separado.
- Logs separados.
- Banco PostgreSQL compartilhado por schemas.
- Secrets via ambiente.
- Health check por projeto.
- Migrations executadas apenas pelo projeto proprietario das tabelas.

## Exemplos Conceituais

```text
servicos.botuka.com.br -> botuka_services -> porta interna propria
api.botuka.com.br      -> botuka_api      -> porta interna propria
```

## Cuidados

- Nao rodar migrations de tabelas de outro projeto.
- Nao usar SQLite em producao.
- Nao versionar `.env`.
- Nao colocar senha ou token em arquivos de deploy.
- Nao reutilizar a mesma porta para mais de um servico.
