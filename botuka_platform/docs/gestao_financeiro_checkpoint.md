# Gestão — Financeiro / BOTUKA Pay — checkpoint

- Auditado: `Cobranca`, `ItemCobranca`, `Pagamento`, `Transacao`, `Webhook` e `ChaveIdempotencia`.
- Implementado: administração global somente leitura, com busca, filtros, paginação e detalhes sem payloads/headers/metadata sensíveis.
- Nenhum valor, identificador de gateway ou histórico pode ser editado/apagado pela Gestão.
- Roteamento existente preservado: origens institucionais/publicidade em C6; produto/serviço em Mercado Pago.
- C6: nenhum endpoint, credencial ou transporte foi inventado.
