# Gestão — Conteúdo — checkpoint

## Arquitetura confirmada

- Backends editoriais reais: Notícias, Eventos, YuBotuka/Mídia, Turismo e Governo institucional.
- A `/gestao/` oferece visão global MASTER somente leitura. Criação, edição e mudanças editoriais permanecem nos fluxos do `/painel/`, que aplicam escopo, permissões, transições e auditoria do domínio.
- Nenhum backend, estado editorial ou endpoint mutável foi criado nesta fase.

## Cobertura central

- Notícias: artigos e categorias editoriais.
- Eventos: eventos e seus estados reais.
- YuBotuka/Mídia: vídeos, episódios e transmissões.
- Turismo: locais, roteiros e experiências.
- Governo: órgãos públicos e conteúdo institucional.

Todas as listagens possuem busca pelos campos reais configurados, filtro de status/ativo quando existente, datas quando suportadas, paginação e detalhe. Relações exibidas usam `select_related`; corpos e descrições pesadas não são carregados nas listagens.

## Classificação dos fluxos

- Notícias/artigos: CRUD e moderação seguros disponíveis no backend operacional.
- Eventos: CRUD e mudanças de status protegidas por permissão e POST.
- YuBotuka/vídeos e transmissões: CRUD e moderação via serviços auditados; episódios possuem CRUD editorial.
- Turismo: CRUD e publicação pelos fluxos operacionais existentes.
- Governo institucional: CRUD com escopo de órgão e validação de transição editorial.
- Gestão central: somente leitura para todos os domínios acima.

## Validação da fase

- Testes focados da central e dos cinco backends editoriais: 141/141 aprovados.
- Cobertura nova valida inventário, acesso MASTER/não-MASTER, busca, filtro, detalhe, ausência de corpo pesado, links reais e estabilidade de queries por linha.
- Pendência visual: revisar em navegador real a densidade da navegação horizontal dos 11 recortes em telas pequenas.
