# BOTUKA Pay — checkpoint multigateway

Data: 2026-09-13

## Estado validado

- `PUBLICIDADE`, `MENSALIDADE`, `PLANO`, `ASSINATURA` e
  `COBRANCA_INSTITUCIONAL` são roteadas para `c6`.
- `PRODUTO`, `SERVICO` e `PRESTACAO_SERVICO` são roteadas para
  `mercado_pago`.
- O modo local usa adapters fake sem credenciais. Fora desse modo, configuração
  ausente produz erro explícito de gateway indisponível.
- A integração C6 externa está pendente de documentação técnica oficial e
  credenciais de homologação. Nenhum endpoint, payload ou método de autenticação
  C6 foi presumido.

## Auditoria de documentação

Mercado Pago:

- Orders API: `POST /v1/orders` e `GET /v1/orders/{id}`;
- autenticação Bearer e `X-Idempotency-Key`;
- `external_reference`;
- PIX, cartão e boleto;
- cancelamento de order e reembolso;
- webhook autenticado pelo manifesto
  `id:<data.id>;request-id:<x-request-id>;ts:<ts>;` com HMAC-SHA256.

Fontes oficiais:

- https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api/overview
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/pix
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-management/refunds-cancellations
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/notifications

C6:

- material público confirma oferta de APIs para PIX e boleto a software houses;
- não foi localizada referência técnica pública suficiente para fixar endpoints,
  payloads, OAuth/mTLS, webhooks, idempotência ou sandbox.

Fonte pública:

- https://cms-assets-p.c6bank.com.br/uploads/c6-bank-expande-programa-de-relacionamento-voltado-para-software-houses.pdf

## Validações

- migration `payments.0003` aplicada localmente após auditoria do SQL e backfill
  seguro em fases;
- `migrate --plan`: limpo;
- `makemigrations --check --dry-run`: limpo;
- `manage.py check`: limpo;
- testes Payments + Advertising + configuração CSRF: 31/31;

## Baseline geral

Mesmo ambiente temporário e PostgreSQL local:

| Execução | Descobertos | Executados | Falhas | Erros |
|---|---:|---:|---:|---:|
| Commit base `c8bcf4a306dddc6f067257d04afb98a300bfd302` | 937 | 923 | 46 | 13 |
| Branch atual | 962 | 948 | 46 | 12 |

O erro adicional do snapshot-base é a ausência de `.env.example` no recorte
temporário. As 46 falhas e 12 erros comuns são preexistentes no mesmo runner.
Não foi identificada regressão nova ou alterada causada pela arquitetura
multigateway.
