# Checkpoint — Usuários e Acessos na Gestão

## Estado

Segunda rodada, Fase 4, concluída em 14/09/2026 após auditoria, refinamento, testes e reauditoria.

## Auditado

- `Usuario`, `Perfil`, `Permissao`, `AcessoModulo` e `ConcessaoPermissao`;
- `UsuarioCapacidade`, `UsuarioGrupo`, `UsuarioPermissao` e `UsuarioPerfil`;
- serviços de concessão/revogação, papéis globais e auditoria;
- proteção de MASTER, superusuário, staff e senha.

## Mapeamento das relações

- `AcessoModulo` + `ConcessaoPermissao`: mecanismo atual, temporal e auditado; administração reutiliza `permission_services`;
- `UsuarioPerfil`: efetivo para perfis adicionais, mas sem serviço/auditoria de mutação; leitura apenas;
- `UsuarioGrupo` e `UsuarioPermissao`: pontes legadas do Django, sem serviço auditado da Gestão; leitura apenas;
- `UsuarioCapacidade`: backend real, sem serviço auditado de concessão/revogação pessoal; leitura apenas;
- papéis globais: mutações usam exclusivamente `organizations.services.institutional`.

## Implementado e corrigido

- e-mail obrigatório e conta nova com senha inutilizável;
- bloqueio de payload `is_staff` para não-MASTER;
- bloqueio de autodesativação e de edição insegura do próprio MASTER;
- contas staff/MASTER protegidas contra edição por não-MASTER;
- busca e filtros de usuário por ativo, staff e perfil, com paginação;
- detalhe otimizado com perfis adicionais, grupos/permissões legadas, acessos e capacidades pessoais somente leitura;
- detalhe e inativação/reativação POST de perfis e permissões;
- perfil MASTER e permissões protegidas não podem ser inativados;
- ação POST específica de papel global usando serviço institucional auditado;
- erros de transição de acesso tratados com mensagem sem quebrar a resposta.
- filtro por acesso vigente à Gestão e ordenação administrativa por e-mail;
- ações condicionadas à autoridade real do operador;
- detalhe consolidado com vínculos empresariais atuais, concessões vigentes e auditoria;
- edição comum preserva `is_superuser`/staff de MASTER e nunca substitui o fluxo protegido;
- perfil funcional aplicado a acesso existente passa a incorporar sua matriz inicial;
- contagem de permissões por módulo agregada sem N+1;
- abertura de formulário de autoalteração ou alteração indevida de MASTER bloqueada.

## Arquivos da etapa

- `apps/gestao/forms.py`
- `apps/gestao/views.py`
- `apps/gestao/urls.py`
- `apps/gestao/test_users_management.py`
- `templates/gestao/acessos/detail.html`
- `templates/gestao/crud/list.html`
- `templates/gestao/usuarios/detail.html`

## Permissões e segurança

- lista/detalhe de usuário: `usuarios.visualizar`;
- criação: `usuarios.criar`; edição: `usuarios.editar`; desativação: `usuarios.desativar`;
- perfis, permissões sensíveis e papéis globais: MASTER;
- acessos modulares: serviço existente e autoridade `pode_administrar_permissoes`;
- mutações de status e papel global exigem POST e CSRF;
- senha não é exibida nem editada pela Gestão;
- nenhuma relação sensível sem serviço auditado recebeu CRUD mutável;
- nenhuma exclusão física foi adicionada.

## Testes e validações

- testes focados de Usuários/Acessos e serviços: 37 aprovados;
- regressão final `apps.gestao`: 66 aprovados;
- `manage.py check`: aprovado;
- `makemigrations --check --dry-run`: nenhuma alteração detectada;
- `git diff --check`: aprovado;
- URLs reversas, permissões, filtros, paginação, POST/CSRF e serviços auditados revisados;
- queries usam `select_related`/`prefetch_related`/`Exists`/`Count`, listas são paginadas e há tetos de regressão para consultas críticas;
- nenhuma mutação por link GET, senha exposta ou TODO/FIXME introduzido.

## Pendências reais

`UsuarioCapacidade`, `UsuarioPerfil`, `UsuarioGrupo` e `UsuarioPermissao` não possuem serviço auditado próprio para mutação na Gestão; permanecem deliberadamente somente leitura. Criar CRUD direto violaria a arquitetura de autorização existente.

Não houve commit, push nem acesso à produção.
