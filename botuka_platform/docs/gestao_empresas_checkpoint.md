# Checkpoint — Empresas na Gestão

## Estado

Segunda rodada, Fase 3, concluída em 14/09/2026 após auditoria, refinamento, testes e reauditoria.

## Auditado e existente

- domínio real `Empresa`, propriedade, equipe, solicitações/reivindicações, capacidades, endereços e links;
- cadastros legados `Organizacao`, `Unidade` e `Endereco`;
- catálogos `Capacidade` e `EmpresaFuncao`;
- formulários e fluxos operacionais já existentes no Painel;
- serviços institucionais, permissões granulares e regras de soft-delete.

## Faltava

- central global de Empresa com lista, filtros, detalhe, criação, edição e inativação;
- administração segura da equipe, fila de solicitações e análise de capacidades;
- detalhe e status POST reversível para os três cadastros legados;
- reativação de vínculo de equipe;
- administração dos catálogos globais de capacidade e função empresarial;
- testes administrativos específicos.

## Implementado

- CRUD administrativo de Empresa, com busca, filtros, paginação e soft-delete;
- detalhe consolidado com propriedade histórica somente leitura, equipe, solicitações, capacidades, endereços e links;
- criação/edição/inativação/reativação de vínculos, protegendo o proprietário atual;
- fila filtrável e análise validada de solicitações;
- análise de capacidade com motivo obrigatório para rejeição e metadados coerentes de aprovação;
- CRUD sem exclusão física de `Capacidade` e `EmpresaFuncao`, exclusivo de MASTER;
- detalhe e alternância POST de status de `Organizacao`, `Unidade` e `Endereco`.
- listagem executiva com filtros por tipo, origem, categoria, cidade e existência de propriedade atual;
- classificação, localidade, responsável, origem e datas essenciais expostas na tabela;
- CNAEs e metadados cadastrais, de localização e publicação consolidados no detalhe;
- criação central registra o vínculo administrativo do proprietário inicial;
- proprietário e origem ficam protegidos na edição, impedindo transferência silenciosa;
- filtros da fila de solicitações preservados durante a paginação.

`EmpresaPropriedade` permanece histórico somente leitura: não existe serviço seguro de transferência a reutilizar. `EmpresaUsuarioFuncao` e `EmpresaUsuarioPermissao` permanecem sob os serviços institucionais auditados, sem edição direta. Links e endereços da Empresa mantêm os fluxos operacionais existentes no Painel; não foram duplicados. Entidades de plano, assinatura e limites pertencem às áreas comercial/financeira correspondentes. CNAEs são exibidos no detalhe e sua manutenção permanece na taxonomia empresarial.

## Arquivos da etapa

- `apps/gestao/company_views.py`
- `apps/gestao/forms.py`
- `apps/gestao/urls.py`
- `apps/gestao/views.py`
- `apps/gestao/test_companies.py`
- `templates/gestao/empresas/`
- `templates/gestao/crud/detail.html`
- `templates/gestao/crud/list.html`
- `templates/gestao/components/sidebar.html`

## Permissões e proteção

- Empresa, equipe e solicitações: `empresas.gerenciar`;
- legados: `organizacoes.gerenciar`;
- catálogos globais: MASTER;
- todas as mutações de status exigem POST e CSRF;
- proprietário atual não pode ser removido pelo CRUD de equipe;
- nenhuma exclusão física empresarial foi adicionada.

## Validação final

- testes focados de Empresas: 14 aprovados;
- regressão `apps.gestao`: 63 aprovados;
- `manage.py check`: aprovado;
- `makemigrations --check --dry-run`: nenhuma alteração detectada;
- `git diff --check`: aprovado;
- URLs reversas, permissões, métodos POST/CSRF, mensagens, filtros, paginação e estados vazios auditados;
- queries relacionais principais usam `select_related`/`Exists`, listagens são paginadas e os limites críticos de consultas possuem teste;
- nenhum TODO/FIXME introduzido;
- nenhum erro conhecido introduzido permanece.

## Pendências reais

Transferência de propriedade continua deliberadamente somente leitura até existir serviço de domínio auditado. A validação visual final em navegadores e dispositivos reais continua sendo decisão humana. Não houve commit, push nem acesso à produção.
