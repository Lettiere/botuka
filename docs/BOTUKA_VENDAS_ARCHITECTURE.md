# BOTUKA Vendas — arquitetura compartilhada

## Responsabilidades

- `botuka_platform` é o único administrador de produtos, taxonomia, mídia,
  publicação, permissões e moderação.
- `botuka_vendas` contém somente as views, URLs, templates e arquivos estáticos
  da experiência comercial pública.
- Os dois processos Django usam os mesmos models, PostgreSQL, usuário customizado
  e tabela de sessões.
- `botuka_vendas` aponta `MEDIA_ROOT` para `botuka_platform/media`. Não há cópia
  de imagens ou de registros.

## Execução local

- Plataforma/painel: `127.0.0.1:7700`
- Portal de vendas: `127.0.0.1:7710`

O inventário anterior não possuía uma porta para Vendas e não há configuração
Nginx versionada no repositório. Em produção, o proxy deve encaminhar
`vendas.botuka.com.br` para a porta 7710 e servir `/media/` a partir da origem
compartilhada ou de storage S3/CDN.

## Sessão e segurança

Os dois processos precisam usar o mesmo `SECRET_KEY`, banco,
`SESSION_COOKIE_NAME` e, em subdomínios, `SESSION_COOKIE_DOMAIN=.botuka.com.br`.
O portal nunca renderiza CPF, CNPJ completo, endereço completo, e-mail ou contato
de pessoa física. Empresas só aparecem com verificação, status ativo e capacidade
`VENDER_PRODUTOS` aprovada.

O canal empresarial pode gerar uma mensagem contextualizada para o contato
comercial. Pessoa física usa conversa interna, com participantes validados no
backend, exclusão lógica, auditoria, bloqueio, denúncia, limite de mensagens e
bloqueio inicial de URLs. Nenhuma API externa, pagamento ou regra de alimentação
faz parte desta fase.

## Deploy

1. Aplicar migrations pela plataforma.
2. Executar `collectstatic` separadamente para cada apresentação.
3. Iniciar a plataforma em 7700 e Vendas em 7710.
4. Configurar o proxy e uma única origem de mídia.
5. Confirmar cookies compartilhados e origens CSRF no domínio final.
