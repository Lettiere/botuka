# ACL mínima dos executores PostgreSQL

Este diretório materializa somente os privilégios observados e homologados para botuka_app, botuka_worker e botuka_internal.

sawaya é o executor maintenance/owner no ambiente homologado e não recebe grants por este artefato. Não existe role operacional botuka_maintenance no estado validado.

## Segurança

- Não contém credenciais, host, IP, nome fixo de banco ou caminho local.
- O GRANT é idempotente e limitado ao banco atual e aos objetos enumerados.
- Inclui DELETE em public.django_session e SELECT em services.services_servico_avaliacao_tb para botuka_app.
- Preserva SELECT/INSERT/DELETE dos posts salvos e SELECT/INSERT/DELETE dos bloqueios sociais protegidos pelas policies existentes.
- Inclui INSERT/DELETE de django_session para botuka_internal, exigidos pela criação, rotação e exclusão de sessão nas rotas internas.
- Inclui UPDATE de platform.platform_usuario_tb para botuka_internal, limitado à permissão de tabela exigida pelo update_fields=["last_login"] do login Django.
- Não altera RLS, policies, owners, default privileges ou atributos de roles.

## Aplicação

1. Faça snapshot das ACLs do banco-alvo.
2. Confirme as três roles e a conexão no banco correto.
3. Execute apply_minimum_executor_acl.sql como role de manutenção.
4. Valide aliases e suítes de autenticação, serviços, painel, worker e RLS.

## Rollback

rollback_minimum_executor_acl.sql remove os grants enumerados. Se algum privilégio já existia antes, restaure o snapshot ACL em vez de executar o rollback integral.

## Origem

O artefato foi comparado com a matriz homologada de 211 tabelas e 38 sequences. Foram acrescentadas as necessidades comprovadas depois da captura: leitura de avaliações de serviço, operações protegidas pelas quatro policies Social existentes e ciclo de sessão do executor internal.
