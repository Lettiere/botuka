# Auditoria de conteúdo público, QR Code e contatos

## Conteúdos

| Tipo | App / model | URL pública | URL no model | Publicação / proteção | Proprietário | Template de detalhe | Compartilhar antes | Imprimir antes | QR antes |
|---|---|---|---|---|---|---|---|---|---|
| Empresa | organizations.Empresa | `publico:empresa` | Não; rota consolidada | ativa, perfil público, não excluída | `usuario_proprietario` | `publico/empresas/detalhe.html` | Básico | Não | Painel específico |
| Serviço | services.Servico | `publico:servico` | Não; rota consolidada | publicado, ativo, não excluído | `usuario_responsavel` / empresa | `publico/servicos/detalhe.html` | Básico | Não | Painel específico |
| Vaga | recruitment.Vaga | `recruitment_public:vaga` | Não; rota consolidada | publicada, vigente, ativa | criador/responsável/empresa | `publico/vagas/detalhe.html` | Não | Não | Não |
| Notícia | news.Artigo | `news_public:artigo` | Não; rota consolidada | publicada, ativa, não excluída | autor | `publico/news/artigo.html` | Sim | Não | Não |
| Turismo | tourism.LocalTuristico | `tourism_public:local` | Não; rota consolidada | publicado, ativo, não excluído | criador/empresa responsável | `publico/turismo/local.html` | Básico | Não | Não |
| Evento | core DTO/listagem | somente listagem `/eventos/` | Não | não há model de detalhe público consolidado | variável | `publico/eventos/lista.html` | Não | Não | Não |
| YoBotuka vídeo | media.Video | `media_public:video` | `public_url` | publicado, ativo, não excluído | autor/canal | `publico/yubotuka/video.html` | Não | Não | Não |
| Episódio | media.Episodio | `media_public:episodio` | `public_url` | publicado, ativo, não excluído | responsável/programa | `publico/ytv/episodio.html` | Não | Não | Não |
| Campeonato | sports.Campeonato | `sports_public:campeonato` | Não; sitemap consolidado | organização verificada e status público | organização | `publico/sports/campeonato.html` | Não | Não | Não |
| Produtos | inexistente | inexistente | inexistente | inexistente | futuro PF/PJ | inexistente | Não | Não | Não |

Eventos não recebeu QR nesta fase porque não possui uma página pública de detalhe consolidada. O registro central não aceita tipos arbitrários.

## Contrato futuro de Produto

Um futuro `Produto` deverá fornecer UUID, slug, proprietário PF ou PJ, status público explícito, exclusão lógica, `atualizado_em` e `get_absolute_url()`. Após existir uma view pública segura, sua integração consistirá em uma entrada explícita em `PUBLIC_TYPES`; não é necessária tabela própria de QR Code.

## Telefones encontrados

| Domínio | Campos principais |
|---|---|
| accounts.Usuario | `telefone`, `celular` |
| organizations.Empresa | `telefone`, `whatsapp` |
| organizations.Organizacao / Unidade | `telefone` |
| services.Servico | `telefone_publico`, `whatsapp_publico` |
| tourism.LocalTuristico | `agendamento_telefone`, `agendamento_whatsapp`, `telefone_publico`, `whatsapp_publico` |
| sports.OrganizacaoEsportiva | `telefone`, `whatsapp` |
| government.OrgaoPublico | `telefone` |
| recruitment.Curriculo | exposição controlada por `mostrar_telefone` |
| core.ContatoInstitucional | valor condicionado ao tipo telefone/WhatsApp |

`apps.core.services.contacts` centraliza normalização, formatação, detecção de celular e URL WhatsApp. Uma migração de dados dos campos históricos deve ser planejada separadamente, porque normalizar todos os registros existentes para E.164 exige relatório de inválidos e revisão dos campos de autorização pública.
