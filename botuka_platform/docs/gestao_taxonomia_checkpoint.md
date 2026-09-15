# Gestão — Taxonomia empresarial — checkpoint

- Auditado: `Categoria`, `Subcategoria`, `CNAE`, `SubcategoriaCNAE` e `EmpresaCNAE`; taxonomia empresarial mantida separada da taxonomia de produtos.
- Existia: CRUD genérico de categorias/subcategorias e painel próprio da taxonomia de produtos.
- Segunda rodada, Fase 5, concluída em 14/09/2026.
- Implementado: listas hierárquicas, busca, filtros relacionais, ordenação, paginação, detalhe, criação, edição e status lógico de categorias, subcategorias, CNAEs e mapeamentos.
- Detalhes exibem subcategorias, mapeamentos e empresas efetivamente vinculadas.
- Seletores de criação aceitam apenas pais/CNAEs/empresas ativos, preservando o valor atual durante edição de legado inativo.
- `EmpresaCNAE` valida um único principal ativo tanto no formulário quanto na reativação por status.
- Filtros de empresa e CNAE são textuais; nenhuma lista integral desses domínios é carregada na página.
- Permissão: `categorias.gerenciar`, validada no backend; mutações exclusivamente POST/CSRF.
- Exclusão: nenhuma exclusão física foi adicionada.
- Testes focados: `apps.gestao.test_business_taxonomy` — 8/8 aprovados.
- Regressão `apps.gestao` — 69/69 aprovados.
- Pendência de refinamento: edição dos campos JSON técnicos do CNAE permanece fora desta primeira versão.
