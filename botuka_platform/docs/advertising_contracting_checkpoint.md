# Checkpoint — contratação de publicidade

Data: 2026-09-13

## Escopo validado

- Campanhas restritas às empresas gerenciáveis pelo usuário; Master administra todas.
- Preço calculado no backend por plano e quantidade de dias.
- Disponibilidade, exclusividade e limite de anunciantes validados dentro da transação.
- Contratação cria `ContratacaoPublicidade` e cobrança `PUBLICIDADE` no BOTUKA Pay.
- O gateway é selecionado exclusivamente pelo router de Payments (`PUBLICIDADE -> C6`).
- Estados operacional e financeiro permanecem separados.
- Ativação exige aprovação, pagamento confirmado e período vigente.
- Aprovação, rejeição, pausa, reativação e cancelamento geram auditoria.
- Criativos aceitam imagem, MP4/WebM ou texto; HTML arbitrário não é aceito.
- Segmentação reutiliza Categoria, Subcategoria e CNAE existentes.
- Pagamento simulado só fica disponível com `DEBUG` e gateways fake habilitados.

## Gates

- `manage.py check`: positivo.
- `makemigrations --check --dry-run`: sem alterações.
- `migrate --plan`: sem operações pendentes.
- Advertising isolado: 14/14 testes.
- Advertising + Payments + navegação nova: 33/33 testes.
- Busca crítica (`TODO` e chamadas diretas a C6): zero ocorrências funcionais.

## Baseline conhecido

As falhas legadas da suíte de autorização geral relacionadas ao middleware multi-banco
e ao texto do modal de navegação permanecem classificadas como preexistentes. A
expectativa de navegação Master afetada pela inclusão de Publicidade foi atualizada e
validada.
