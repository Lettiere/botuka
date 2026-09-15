# Gestão — Negócios — checkpoint

## Arquitetura confirmada

- Backends reais: Produtos, Serviços, Agenda/Agendamentos e Recrutamento/Vagas.
- Recortes globais na `/gestao/`: `Produto`, `Servico`, `AgendaProfissional`, `AgendaProfissionalServico`, `Agendamento` e `Vaga`.
- A `/gestao/` permanece somente leitura e restrita a MASTER. Operações continuam no `/painel/`, sob escopo empresarial e serviços de domínio.
- Ofertas, pedidos e checkout transacional independentes: **BACKEND NÃO EXISTENTE — NÃO IMPLEMENTADO**.

## Relações e segurança

- Produto usa a FK real `empresa_proprietaria`; também suporta titular pessoa física.
- Serviço usa a FK real `empresa` e valida coerência com `prestador_tipo`.
- Agenda deriva a empresa por `AgendaProfissional.empresa_usuario.empresa`; profissional autônomo usa `usuario_autonomo`.
- `AgendaProfissionalServico` valida que profissional e serviço pertencem ao mesmo contexto empresarial/autônomo.
- Agendamentos continuam mutáveis somente pelo motor da Agenda, com transações e histórico. Não existe atalho operacional global porque as rotas exigem contexto de empresa.
- Nenhuma cobrança, pagamento, gateway ou regra do BOTUKA Pay foi alterada.

## UX e performance

- Busca, filtro por status/ativo, datas, paginação e detalhe para os seis recortes.
- Listagens identificam empresa/titular, classificação, valores relevantes, status e atualização.
- Cadeias empresariais da Agenda usam `select_related`; descrições, requisitos e outros textos pesados usam `defer` nas listagens.
- Links operacionais reais para Produtos, Serviços e Vagas. Agenda exibe a exigência de selecionar empresa em vez de inventar URL global.

## Testes e limitações ambientais

- Testes específicos da Gestão de Negócios: 4/4 aprovados.
- Regressão ampliada original: 366/370 aprovados.
- Diagnóstico objetivo reproduzido em uma execução de 126 testes: 122 aprovados,
  três erros ambientais de Serviços e uma falha ambiental da Agenda.
- `ServiceTaxonomyCatalogTests.test_dry_run_faz_rollback_integral` consulta a
  sequence PostgreSQL `services_setor_tb_services_setor_id_seq`, inexistente no
  SQLite.
- `ServiceTaxonomyCatalogTests.test_aplicacao_e_idempotente` é corretamente
  bloqueado pela proteção do comando, que exige host loopback, confirmação e nome
  exato do banco local; o banco SQLite em memória não atende esse contrato.
- `RolloutSafetyTests.test_lotes_reais_sao_disjuntos_e_editorial_e_bloqueado`
  exige `lote_implementacao_segura.csv` e os demais lotes no diretório externo
  `_auditoria_cbo`, ausente neste worktree.
- `AgendaConcorrenciaTests.test_duas_requisicoes_concorrentes_criam_apenas_uma_reserva`
  foi reproduzido no SQLite compartilhado: uma thread recebe `database table is
  locked`, portanto não chega ao resultado funcional esperado. A garantia de
  bloqueio concorrente deve ser validada em PostgreSQL.
- Matriz funcional compatível após o diagnóstico: 236/236 aprovada nesta retomada
  (Gestão de Negócios, Serviços e Agenda, excluídos somente os quatro cenários
  ambientais acima).
- `apps.gestao` completo: 87/87 aprovado.
- `manage.py check`: aprovado, sem issues; `makemigrations --check --dry-run`:
  nenhuma mudança; `git diff --check`: aprovado.
- Essas quatro limitações não foram mascaradas nem provocaram mudança de regra de negócio.

## Pendência humana

- Validar visualmente a densidade da navegação horizontal dos seis recortes em celular.
- Executar os quatro testes ambientais no ambiente PostgreSQL preparado e, para rollout CBO, disponibilizar os lotes de auditoria esperados.
