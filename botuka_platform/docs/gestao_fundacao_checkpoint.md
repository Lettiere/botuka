# Checkpoint — Fundação da Gestão

## Estado

Etapa 1 concluída em 13/09/2026 após auditoria, correção, testes e reauditoria.

## Auditado

- template base, sidebar e topbar da `/gestao/`;
- breadcrumbs e mensagens do Django;
- responsividade da navegação administrativa;
- acesso base à Gestão e visibilidade do menu por permissão;
- logout e ações de ativação/desativação quanto a método HTTP e CSRF;
- URLs usadas pelos componentes compartilhados;
- testes relacionados de CSRF, conta, navegação do painel e integração da Gestão com Turismo.

## Já existia

- `templates/gestao/base.html` e componentes básicos;
- middleware e decorators de acesso administrativo;
- mensagens de sucesso/erro;
- layout responsivo básico;
- endpoint de logout restrito a POST;
- proteção POST na alternância de status das taxonomias de produto.

## Faltava ou estava inconsistente

- a sidebar chamava o logout por link GET, incompatível com o endpoint;
- ativação/desativação de usuários e contatos aceitava GET;
- links administrativos eram exibidos sem considerar permissões;
- o menu móvel não era recolhível e ocupava a página inteira;
- breadcrumbs não tinham um contrato comum e páginas de acesso os duplicavam;
- alertas não tinham semântica acessível nem fechamento explícito;
- os testes CSRF não declaravam o acesso a banco que passou a ocorrer durante a entrega de publicidade;
- testes de navegação esperavam um rótulo anterior ao atual “Cadastro completo”.

## Implementado

- formulários POST com token CSRF para logout e mudanças de status;
- `require_POST` nas quatro views mutáveis auditadas;
- sidebar condicionada às permissões de domínio;
- navegação móvel off-canvas com abertura, fechamento, backdrop, Escape e atributos ARIA;
- breadcrumb base extensível e breadcrumbs específicos sem duplicação;
- alertas com papéis acessíveis e botão de fechamento;
- testes focados da fundação e atualização dos contratos de regressão relacionados.

## Arquivos alterados

- `apps/gestao/views.py`
- `apps/gestao/test_foundation.py`
- `apps/core/test_csrf_security.py`
- `apps/core/test_panel_navigation.py`
- `templates/gestao/base.html`
- `templates/gestao/components/alerts.html`
- `templates/gestao/components/sidebar.html`
- `templates/gestao/components/topbar.html`
- `templates/gestao/crud/list.html`
- `templates/gestao/usuarios/acessos.html`
- `templates/gestao/usuarios/acesso_form.html`

## Regras de permissão

- entrada na Gestão: MASTER ou `gestao.acessar`;
- a sidebar só mostra cada área quando o usuário possui sua permissão de domínio;
- desativar usuário: `usuarios.desativar`;
- ativar usuário: `usuarios.editar`;
- ativar/desativar contato: `contatos.ativar`;
- a proteção continua no backend; ocultar links não substitui autorização.

## Testes e validações

- `manage.py test apps.gestao`: 12 testes, aprovados;
- regressão combinada de Gestão, CSRF, conta, navegação do painel e integração de Turismo: 39 testes, aprovados;
- `manage.py check`: aprovado, sem issues;
- `git diff --check`: aprovado;
- busca por logout GET e links GET para mutações auditadas: nenhum resultado;
- busca por TODO/FIXME introduzido: nenhum resultado;
- revisão manual do diff: aprovada;
- nenhuma URL foi renomeada e nenhum link legado foi removido.

O log “Serviço meteorológico indisponível” na regressão é produzido deliberadamente pelo teste de fallback com `TimeoutError`; o teste passou.

## Pendências reais

Nenhuma pendência conhecida da Etapa 1. A configuração temporária local de testes precisou usar o executor de manutenção e desabilitar os middlewares de roteamento/RLS no overlay em `/tmp`, porque aliases espelhados abrem conexões separadas; isso não altera arquivos ou arquitetura da aplicação.
