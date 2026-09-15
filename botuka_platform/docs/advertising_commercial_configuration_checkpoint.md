# Checkpoint — configuração comercial da publicidade

Data: 2026-09-13

## Escopo validado

- Área própria do Painel Botuka protegida pela regra central de Master.
- CRUD de planos, preços, prioridade, exclusividade, limites, frequência, duração e estado ativo.
- CRUD de posicionamentos, contexto, dimensões desktop/mobile, proporção, tamanho, formatos e tipos permitidos.
- Regras exibidas no formulário de upload do anunciante.
- Validação backend de tipo, extensão, MIME, tamanho, dimensões estritas e compatibilidade com todos os posicionamentos.
- Alterações de preço afetam novas contratações; valores materializados em contratações existentes permanecem imutáveis.
- Nenhuma mudança em BOTUKA Pay ou no gateway router.

## Gates

- Migration `advertising.0005` aplicada somente no banco local de auditoria.
- `manage.py check`: positivo.
- `makemigrations --check --dry-run`: sem alterações.
- `migrate --plan`: sem operações pendentes.
- Advertising + Payments + Analytics + navegação Master: 45/45 testes.
