# YuBotuka — implantação segura da fase 3

Este documento é somente um roteiro. Nenhum comando abaixo foi executado no servidor.

## Dependências e ordem

1. Criar backup verificável do banco PostgreSQL, dos uploads e da versão atual do código.
2. Confirmar que as migrations já homologadas do `core` e de `accounts` estão no servidor.
3. Enviar o código sem substituir `.env`, uploads, logs ou arquivos gerados no servidor.
4. Executar `python manage.py check` e `python manage.py makemigrations --check --dry-run`.
5. Conferir `python manage.py showmigrations core accounts media`.
6. Aplicar primeiro migrations pendentes de `core` e `accounts`; depois `media.0009` e `media.0010`.
7. Executar `python manage.py collectstatic --noinput`.
8. Reiniciar somente a unidade real da aplicação, após confirmar seu nome no ambiente.
9. Validar a configuração do Nginx e recarregá-lo somente se a configuração estiver válida.

As migrations da fase 3 dependem de `media.0008`. A `0009` cria o esquema; a
`0010` prepara dados e permissões. Elas não criam proprietário/autor fictício,
não mudam slugs publicados e não substituem URLs divergentes.

## Backup e pré-verificação

Substitua os marcadores pelos valores do ambiente e guarde os arquivos fora da
pasta da aplicação:

```bash
pg_dump --format=custom --file=<backup-dir>/botuka-before-yubotuka-f3.dump <database>
tar -czf <backup-dir>/botuka-media-before-yubotuka-f3.tar.gz <media-root>
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations core accounts media
python manage.py test apps.media apps.painel
```

Não usar o nome de uma unidade de serviço presumido. Antes do reinício, o
operador deve identificar e registrar a unidade que atualmente atende o BOTUKA.

## Validação pós-implantação

Validar HTTP 200/302 esperado, sem cadeia de redirects, em:

- `/`
- `/yubotuka/`
- `/yubotuka/ao-vivo/`
- `/yubotuka/transmissoes/`
- `/ytv/`
- `/painel/yubotuka/`
- `/painel/yubotuka/programas/`
- `/painel/yubotuka/transmissoes/`
- `/painel/ytv/`

Também validar login, CSRF, menu mobile, programa/temporada/episódio, workflow
de transmissão, permissões de usuário comum e gestor, atribuição de canal e a
tela de homologação dos 15 conteúdos. Confirmar especialmente que
`episodio-demo-12` mantém a URL `https://www.youtube.com/watch?v=98mhMP8ZEV0`.

## Rollback

1. Retirar a versão nova de tráfego e restaurar a versão anterior do código.
2. Se nenhuma escrita ocorreu nas tabelas novas, reverter `media` até `0008`
   somente após backup adicional e ensaio.
3. Se houve escrita, não executar `migrate media 0008` diretamente: restaurar o
   dump completo em banco separado, comparar os dados e realizar rollback
   assistido.
4. Restaurar os uploads apenas se foram alterados.
5. Recolher estáticos da versão anterior, reiniciar a unidade confirmada e
   repetir os testes HTTP.

O rollback de banco é mais arriscado que manter as tabelas novas inativas.
Preferir rollback de código quando o esquema adicional estiver íntegro e não
interferir na versão anterior.

## Arquivos da fase 3 para envio futuro

- `apps/media/models.py`
- `apps/media/forms.py`
- `apps/media/selectors.py`
- `apps/media/services.py`
- `apps/media/permissions.py`
- `apps/media/phase3_views.py`
- `apps/media/views.py`
- `apps/media/panel_urls.py`
- `apps/media/public_urls.py`
- `apps/media/yubotuka_views.py`
- `apps/media/migrations/0009_programa_categoria_editorial_programa_ordem_and_more.py`
- `apps/media/migrations/0010_preparar_dados_fase3_yubotuka.py`
- `apps/media/tests.py`
- `apps/media/test_migrations.py`
- `apps/painel/navigation.py`
- `apps/painel/tests.py`
- `apps/core/seo/page_builders.py`
- `templates/painel/yubotuka/base.html`
- `templates/painel/yubotuka/form.html`
- `templates/painel/yubotuka/program_list.html`
- `templates/painel/yubotuka/program_detail.html`
- `templates/painel/yubotuka/season_list.html`
- `templates/painel/yubotuka/season_detail.html`
- `templates/painel/yubotuka/episode_list.html`
- `templates/painel/yubotuka/episode_detail.html`
- `templates/painel/yubotuka/transmission_list.html`
- `templates/painel/yubotuka/transmission_detail.html`
- `templates/painel/yubotuka/channel_assignment_list.html`
- `templates/painel/yubotuka/legacy_list.html`
- `templates/painel/yubotuka/legacy_detail.html`
- `templates/publico/yubotuka/transmissions.html`
- `templates/publico/yubotuka/live.html`
- `templates/publico/yubotuka/transmission.html`
- `static/painel/css/yubotuka.css`
- `static/public/css/yubotuka.css`
- `static/public/js/yubotuka.js`

Antes do envio, comparar esta lista com o diff da release completa: arquivos
compartilhados podem conter mudanças homologadas das fases 1 e 2 que também
precisam acompanhar a implantação.
