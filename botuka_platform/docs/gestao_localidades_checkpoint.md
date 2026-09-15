# Gestão — Localidades — checkpoint

- Auditado: `Pais`, `Estado`, `Cidade` e `Bairro`, com relações hierárquicas protegidas pelos FKs e ModelForms.
- Segunda rodada, Fase 6, concluída em 14/09/2026.
- Existia: CRUD genérico com busca e paginação, sem experiência hierárquica dedicada.
- Implementado: listagem, busca por nome/códigos/sigla, filtros por pais, status e hierarquia, paginação, detalhe, criação, edição e ativação/inativação lógica para as quatro entidades.
- Novos filhos aceitam apenas pais ativos; edição preserva o pai legado inativo e reativação de filho exige pai ativo.
- Detalhes exibem filhos ativos e inativos e contabilizam consumidores ativos conhecidos.
- Códigos ISO e siglas são normalizados em maiúsculas.
- Listas relacionais usam `select_related`; o filtro de bairro recebe cidade por texto para não carregar uma lista integral de cidades.
- Permissão: `localidades.gerenciar`; mutações exclusivamente POST/CSRF.
- Testes focados: 10/10 aprovados em `test_locations_management`, `LocalityManagementTests` e `apps.locations`.
- Regressão completa `apps.gestao`: 77/77 aprovada.
- `manage.py check`, deriva de migrations e `git diff --check`: aprovados.
