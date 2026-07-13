# Integracoes

## Aviso de Seguranca

Nunca registrar tokens reais, credenciais de API, chaves privadas, cookies, dados de sessao, CPF, CNPJ de clientes ou dados pessoais neste documento.

| Integracao | Finalidade | Modulo consumidor | Provider | Variaveis de ambiente | Status | Documentacao | Responsavel |
|---|---|---|---|---|---|---|---|
| Consulta CNPJ | Preencher/validar dados empresariais. | botuka_empresas, botuka_platform, botuka_api | Receita Federal ou provider equivalente | CNPJ_PROVIDER, CNPJ_API_URL, CNPJ_API_TOKEN | planejado | A definir | Arquitetura/Produto |
| Receita Federal ou equivalente | Fonte de dados cadastrais. | botuka_api | A definir | CNPJ_PROVIDER, CNPJ_API_URL, CNPJ_API_TOKEN | planejado | A definir | Arquitetura |
| Consulta CEP | Preencher enderecos. | Todos os modulos com endereco | ViaCEP ou provider equivalente | CEP_PROVIDER, CEP_API_URL, CEP_API_TOKEN | planejado | A definir | Arquitetura |
| Emissao fiscal futura | NFSe/NFe e documentos fiscais. | Empresas, servicos, commerce futuro | A definir | FISCAL_PROVIDER, FISCAL_API_URL, FISCAL_API_TOKEN | planejado | A definir | Fiscal/Arquitetura |
| Mapas e geolocalizacao | Mapas, rotas e pontos locais. | mobilidade, turismo, imoveis, platform | A definir | MAPS_PROVIDER, MAPS_API_KEY | planejado | A definir | Produto |
| Pagamentos | Cobrancas, planos e transacoes. | platform e modulos comerciais | A definir | PAYMENT_PROVIDER, PAYMENT_API_KEY | planejado | A definir | Financeiro/Arquitetura |
| Notificacoes | Avisos internos e push futuro. | Todos | A definir | NOTIFICATION_PROVIDER, NOTIFICATION_TOKEN | planejado | A definir | Produto |
| Email | Recuperacao, avisos e comunicacao. | Todos | SMTP/provider | EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD | planejado | A definir | Operacao |
| WhatsApp | Atendimento e notificacoes. | platform, empresas, servicos | A definir | WHATSAPP_PROVIDER, WHATSAPP_API_URL, WHATSAPP_TOKEN | planejado | A definir | Atendimento |
| Autenticacao central | Login e autorizacao. | Todos | botuka_platform / botuka_api | BOTUKA_API_URL, BOTUKA_API_TOKEN | planejado | AUTENTICACAO.md | Arquitetura |
| API interna BOTUKA | Integracao entre projetos. | Todos | botuka_api | BOTUKA_API_URL, BOTUKA_API_TOKEN | planejado | A definir | Arquitetura |

Tokens reais devem ficar somente em variaveis de ambiente seguras.
