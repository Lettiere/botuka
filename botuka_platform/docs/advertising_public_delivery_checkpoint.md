# Checkpoint — entrega pública de publicidade

Data: 2026-09-13

## Fluxo validado

- Seleção centralizada no service de Advertising por posicionamento e contexto.
- Elegibilidade exige campanha ativa, aprovação, cobrança paga e período vigente.
- Níveis: Takeover (0), Premium (1), Plus (2), Segmentado (3) e Standard (4).
- Exclusividade, prioridade, rotação por menor entrega e frequência móvel de 24 horas.
- Identidade estável por sessão para anônimos e por usuário para autenticados.
- Componente reutilizável para texto, imagem, MP4 e WebM.
- Takeover responsivo com overlay, fechamento e duração configurável.
- Uma seleção/impressão por posicionamento em cada resposta.
- Redirect público por UUID com destino restrito a HTTP/HTTPS e sem credenciais na URL.
- Eventos idempotentes `ad_impression` e `ad_click` integrados ao Analytics mediante consentimento.

## Gates

- Migration `advertising.0004` aplicada somente no PostgreSQL local de auditoria.
- `manage.py check`: positivo.
- `makemigrations --check --dry-run`: sem alterações.
- `migrate --plan`: sem operações pendentes.
- Advertising + Payments + Analytics + navegação afetada: 42/42 testes.
