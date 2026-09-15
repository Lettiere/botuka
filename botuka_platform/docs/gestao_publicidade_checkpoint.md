# Gestão — Publicidade — checkpoint

## Arquitetura preservada

- Entidades reais: `PlanoPublicitario`, `Posicionamento`, `Campanha`, `CampanhaSegmentacao`, `Criativo`, `ContratacaoPublicidade`, `EntregaPublicidade` e `AuditoriaPublicidade`.
- Níveis: 0 Impacto/Takeover, 1 Destaque Premium, 2 Destaque Plus, 3 Destaque Segmentado e 4 Standard.
- A `/gestao/` fornece os oito recortes globais somente leitura. Configuração comercial e moderação continuam nas views próprias, restritas a MASTER.
- Criação e operação do anunciante continuam no fluxo Advertising, sob escopo de empresa.

## Comercial, moderação e pagamento

- Planos preservam preço, prioridade, exclusividade, limite de anunciantes, frequência e duração.
- Posicionamentos preservam contexto, dimensões desktop/mobile, peso, formatos permitidos e compatibilidade com Takeover.
- Aprovar, rejeitar, pausar e reativar usam os serviços existentes, permissão MASTER, POST/CSRF e `AuditoriaPublicidade`.
- Pagamento não implica aprovação; campanha somente ativa quando paga, aprovada e vigente.
- Cadeia preservada: Advertising cria cobrança de origem `PUBLICIDADE` no BOTUKA Pay; `processar_pagamento` resolve o gateway pelo router, que aponta para C6.
- Nenhuma chamada direta ao C6, endpoint/autenticação inventado, alteração no Mercado Pago ou transporte C6 foi implementado.

## Criativos e entrega pública

- Criativos aceitam imagem, MP4, WebM e texto conforme cada posicionamento.
- Backend valida tipo, extensão, MIME, peso, dimensões estritas e compatibilidade de tipo.
- HTML em criativo textual agora é rejeitado explicitamente pelo modelo.
- Destino de clique permanece limitado a HTTP/HTTPS, com host e sem credenciais embutidas.
- Elegibilidade exige campanha ativa, aprovada, paga, vigente, posicionamento elegível e criativo ativo/aprovado.
- Exclusividade, prioridade, rotação por menor entrega e frequência móvel de 24 horas foram preservadas.
- Contagens de frequência e rotação foram agregadas na consulta de candidatas, removendo N+1 por campanha.
- Impressão e clique geram somente os eventos de publicidade no Analytics, condicionados ao consentimento e com deduplicação.

## Testes

- Testes focados Advertising + Payments + Gestão de Publicidade: 42/42 aprovados.
- Cobertura inclui regras comerciais, contratação, moderação, pagamento, entrega, Takeover, frequência, rotação, clique seguro, arquivos, HTML, permissões, POST/CSRF e queries.
- `apps.gestao` completo: 87/87 aprovado.
- `manage.py check`: aprovado, sem issues; `makemigrations --check --dry-run`:
  nenhuma mudança; `git diff --check`: aprovado.

## Auditoria final

- A administração central mantém paginação, busca, filtros e detalhes globais
  somente leitura para os oito recortes, enquanto configuração e moderação usam
  os fluxos reais restritos a MASTER.
- As listagens e a seleção pública carregam relacionamentos antecipadamente; o
  teste de crescimento de queries confirma ausência de N+1 por campanha.
- Mutações operacionais exigem autenticação, POST e CSRF. Escopo empresarial é
  validado no backend; aprovação, rejeição, pausa e reativação exigem MASTER.
- Nenhuma modernização geral de Analytics foi iniciada: permanecem apenas os
  eventos `ad_impression` e `ad_click`, sujeitos a consentimento e deduplicação.
- Nenhum acesso à produção, commit, push ou deploy foi realizado.

## Pendência humana

- Validar visualmente os formatos e o Takeover em navegadores/dispositivos reais com arquivos de produção representativos.
- Transporte real do C6 continua pendente de documentação oficial e credenciais de homologação.
