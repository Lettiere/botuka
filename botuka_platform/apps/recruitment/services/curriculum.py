from dataclasses import dataclass

from django.utils import timezone

from apps.recruitment.models import Curriculo


@dataclass(frozen=True)
class ProgressoCurriculo:
    percentual: int
    etapa_atual: int
    etapas_concluidas: tuple[int, ...]
    etapas_pendentes: tuple[int, ...]
    proxima_etapa: int | None
    pode_concluir: bool
    status: str


def _tem_info_adicional(curriculo):
    try:
        info = curriculo.informacoes_adicionais
    except Curriculo.informacoes_adicionais.RelatedObjectDoesNotExist:
        return False
    return any((info.possui_cnh, info.categorias_cnh, info.veiculo_proprio,
                info.disponibilidade_horario, info.trabalho_voluntario,
                info.premiacoes, info.interesses_profissionais, info.observacoes))


def calcular_progresso(curriculo):
    concluidas = []
    if curriculo.titulo_profissional and curriculo.area_profissional and curriculo.resumo:
        concluidas.append(1)
    if any((curriculo.telefone_publico, curriculo.email_publico, curriculo.cidade,
            curriculo.estado, curriculo.linkedin, curriculo.portfolio,
            curriculo.site_profissional, curriculo.github)):
        concluidas.append(2)
    if curriculo.experiencia_set.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(3)
    if curriculo.formacao_set.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(4)
    if curriculo.curso_set.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(5)
    if curriculo.habilidades.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(6)
    if curriculo.idiomas.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(7)
    if curriculo.projetos.filter(ativo=True, excluido_em__isnull=True).exists(): concluidas.append(8)
    if _tem_info_adicional(curriculo): concluidas.append(9)
    if hasattr(curriculo, 'privacidade'): concluidas.append(10)
    pendentes = tuple(numero for numero in range(1, 11) if numero not in concluidas)
    pode_concluir = 1 in concluidas and 10 in concluidas
    status = Curriculo.Status.CONCLUIDO if curriculo.status == Curriculo.Status.CONCLUIDO else (Curriculo.Status.EM_PREENCHIMENTO if concluidas else Curriculo.Status.RASCUNHO)
    return ProgressoCurriculo(len(concluidas) * 10, curriculo.etapa_atual, tuple(concluidas), pendentes, pendentes[0] if pendentes else None, pode_concluir, status)


def atualizar_etapa_atual(curriculo, etapa):
    curriculo.etapa_atual = max(1, min(int(etapa), 10))
    if curriculo.status == Curriculo.Status.RASCUNHO:
        curriculo.status = Curriculo.Status.EM_PREENCHIMENTO
    curriculo.save(update_fields=['etapa_atual', 'status', 'atualizado_em'])


def concluir_curriculo(curriculo):
    progresso = calcular_progresso(curriculo)
    if not progresso.pode_concluir:
        raise ValueError('Preencha o perfil profissional e configure a privacidade antes de concluir.')
    curriculo.status = Curriculo.Status.CONCLUIDO
    curriculo.concluido_em = timezone.now()
    curriculo.save(update_fields=['status', 'concluido_em', 'atualizado_em'])
    return calcular_progresso(curriculo)
