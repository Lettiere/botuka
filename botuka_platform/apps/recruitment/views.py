from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from uuid import uuid4
from pathlib import Path
import csv

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone

from apps.organizations.permissions import empresas_disponiveis_para_usuario
from apps.organizations.models import Empresa
from .forms import (CandidaturaForm, ContatoPublicoForm, CursoForm,
                    CurriculoPrivacidadeForm, ExperienciaForm, FormacaoForm,
                    HabilidadeForm, IdiomaForm, InformacaoAdicionalForm,
                    PerfilProfissionalForm, ProjetoForm, PublicacaoCurriculoForm,
                    VagaForm)
from .models import (Candidatura, CandidaturaHistorico, Curso, Curriculo, CurriculoInformacaoAdicional,
                     CurriculoPrivacidade, Experiencia, Formacao, Habilidade,
                     Idioma, Projeto, Vaga)
from .services import (calcular_progresso, concluir_curriculo, curriculo_para_candidatura, curriculo_para_painel, curriculo_publico)
from .services.curriculum import atualizar_etapa_atual
from .permissions import pode_administrar_vaga, vagas_administraveis
from .selectors import indicadores_vagas, painel_vagas
from .services.vacancies import alterar_status, configurar_responsavel, registrar_acao
from apps.core.seo.page_builders import curriculo_seo, listing_seo, vaga_seo
from apps.core.attribute_forms import atributo_formset


def _vaga_usuario(usuario, uuid):
    return get_object_or_404(vagas_administraveis(usuario), uuid=uuid)


@login_required
def vaga_lista(request):
    base = vagas_administraveis(request.user)
    filtradas = painel_vagas(request.user, request.GET)
    page_obj = Paginator(filtradas, 20).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'painel/vagas/lista.html', {
        'titulo': 'Gerenciar vagas', 'vagas': page_obj.object_list,
        'page_obj': page_obj, 'total_filtrado': page_obj.paginator.count,
        'querystring': query.urlencode(),
        'indicadores': indicadores_vagas(base),
        'empresas': empresas_disponiveis_para_usuario(request.user).filter(ativo=True),
        'status_opcoes': Vaga.Status.choices,
    })


@login_required
def vagas_exportar(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="vagas.csv"'
    writer = csv.writer(response)
    writer.writerow(['Título', 'Responsável', 'Status', 'Modalidade', 'Contrato', 'Cidade', 'Estado', 'Atualização'])
    for vaga in painel_vagas(request.user, request.GET):
        writer.writerow([
            vaga.titulo, vaga.responsavel_publico, vaga.get_status_display(),
            vaga.modalidade, vaga.tipo_contrato, vaga.cidade, vaga.estado,
            vaga.atualizado_em.strftime('%d/%m/%Y %H:%M'),
        ])
    return response


@login_required
def vaga_criar(request):
    form = VagaForm(request.POST or None, usuario=request.user)
    atributos = atributo_formset('vaga', instance=form.instance, data=request.POST or None)
    if request.method == 'POST' and form.is_valid() and atributos.is_valid():
        try:
            with transaction.atomic():
                vaga = form.save(commit=False)
                configurar_responsavel(
                    vaga, request.user,
                    form.cleaned_data['empresa']
                    if form.cleaned_data['tipo_responsavel'] == 'EMPRESA' else None,
                )
                vaga.status = Vaga.Status.RASCUNHO
                vaga.save()
                atributos.instance = vaga
                atributos.save()
                registrar_acao(vaga, request.user, 'criacao', request)
                if request.POST.get('acao') == 'publicar':
                    alterar_status(vaga, request.user, Vaga.Status.PUBLICADA, request)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, 'Vaga cadastrada com sucesso.')
            return redirect('painel:vaga_detalhe', uuid=vaga.uuid)
    return render(request, 'painel/recruitment/form.html', {
        'titulo': 'Nova vaga', 'form': form, 'atributos': atributos, 'atributo_contexto': 'vaga',
    })


@login_required
def vaga_detalhe(request, uuid):
    return render(request, 'painel/vagas/detalhe.html', {'vaga': _vaga_usuario(request.user, uuid)})


@login_required
def vaga_editar(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not pode_administrar_vaga(request.user, vaga): raise PermissionDenied
    form = VagaForm(request.POST or None, instance=vaga, usuario=request.user)
    atributos = atributo_formset('vaga', instance=vaga, data=request.POST or None)
    if request.method == 'POST' and form.is_valid() and atributos.is_valid():
        try:
            with transaction.atomic():
                vaga = form.save(commit=False)
                configurar_responsavel(
                    vaga, request.user,
                    form.cleaned_data['empresa']
                    if form.cleaned_data['tipo_responsavel'] == 'EMPRESA' else None,
                )
                vaga.save()
                atributos.save()
                registrar_acao(vaga, request.user, 'edicao', request)
                if request.POST.get('acao') == 'publicar' and vaga.status != Vaga.Status.PUBLICADA:
                    alterar_status(vaga, request.user, Vaga.Status.PUBLICADA, request)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, 'Vaga atualizada com sucesso.')
            return redirect('painel:vaga_detalhe', uuid=vaga.uuid)
    return render(request, 'painel/recruitment/form.html', {
        'titulo': 'Editar vaga', 'form': form, 'atributos': atributos, 'atributo_contexto': 'vaga',
    })


@login_required
def vaga_status(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not pode_administrar_vaga(request.user, vaga): raise PermissionDenied
    status = request.POST.get('status')
    if status not in Vaga.Status.values: raise Http404
    try:
        alterar_status(vaga, request.user, status, request)
        messages.success(request, f'Vaga alterada para {vaga.get_status_display().lower()}.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:vaga_detalhe', uuid=vaga.uuid)


def _acao_status(request, uuid, status):
    if request.method != 'POST':
        raise PermissionDenied
    vaga = _vaga_usuario(request.user, uuid)
    try:
        alterar_status(vaga, request.user, status, request)
        messages.success(request, f'Vaga alterada para {vaga.get_status_display().lower()}.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:vaga_detalhe', uuid=vaga.uuid)


@login_required
def vaga_publicar(request, uuid):
    return _acao_status(request, uuid, Vaga.Status.PUBLICADA)


@login_required
def vaga_pausar(request, uuid):
    return _acao_status(request, uuid, Vaga.Status.PAUSADA)


@login_required
def vaga_encerrar(request, uuid):
    return _acao_status(request, uuid, Vaga.Status.ENCERRADA)


@login_required
def vaga_excluir(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not pode_administrar_vaga(request.user, vaga): raise PermissionDenied
    registrar_acao(vaga, request.user, 'exclusao', request)
    vaga.delete()
    return redirect('painel:vagas_lista')


@login_required
def vaga_remover(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not pode_administrar_vaga(request.user, vaga):
        raise PermissionDenied
    if request.method == 'POST':
        return vaga_excluir(request, uuid)
    return render(request, 'painel/vagas/remover.html', {'vaga': vaga})


@login_required
def vaga_auditoria(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not pode_administrar_vaga(request.user, vaga):
        raise PermissionDenied
    return render(request, 'painel/vagas/auditoria.html', {
        'vaga': vaga,
        'registros': vaga.auditoria.select_related('usuario'),
    })


@login_required
def vaga_duplicar(request, uuid):
    original = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not pode_administrar_vaga(request.user, original):
        raise PermissionDenied
    original.pk = None
    original.uuid = uuid4()
    original.slug = ''
    original.titulo = f'Cópia de {original.titulo}'[:180]
    original.status = Vaga.Status.RASCUNHO
    original.publicado_em = None
    original.usuario_criador = request.user
    original.save()
    registrar_acao(original, request.user, 'duplicacao', request)
    messages.success(request, 'Vaga duplicada como rascunho.')
    return redirect('painel:vaga_editar', uuid=original.uuid)


def vagas_publicas(request):
    queryset = Vaga.objects.filter(
        Q(empresa__isnull=False, empresa__ativo=True, empresa__perfil_publico=True,
          empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True)
        | Q(perfil_pessoa_fisica__isnull=False, perfil_pessoa_fisica__is_active=True),
        status=Vaga.Status.PUBLICADA, publicado_em__isnull=False,
    ).filter(Q(encerramento__isnull=True) | Q(encerramento__gte=timezone.localdate())).select_related('empresa', 'perfil_pessoa_fisica').prefetch_related('atributos_adicionais')
    q = request.GET.get('q', '').strip()[:100]
    if q: queryset = queryset.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q) | Q(requisitos__icontains=q) | Q(empresa__nome_fantasia__icontains=q) | Q(bairro__icontains=q) | Q(atributos_adicionais__valor__icontains=q) | Q(atributos_adicionais__nome_personalizado__icontains=q)).distinct()
    if request.GET.get('modalidade'): queryset = queryset.filter(modalidade__iexact=request.GET['modalidade'][:30])
    if request.GET.get('contrato'): queryset = queryset.filter(tipo_contrato__iexact=request.GET['contrato'][:40])
    if request.GET.get('bairro'): queryset = queryset.filter(bairro__iexact=request.GET['bairro'][:100])
    if request.GET.get('pcd') == '1': queryset = queryset.filter(aceita_pcd=True)
    ordem = request.GET.get('ordem')
    queryset = queryset.order_by('encerramento' if ordem == 'prazo' else 'titulo' if ordem == 'az' else '-publicado_em')
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    seo = listing_seo(request, 'Vagas em Botucatu | BOTUKA', 'Oportunidades de emprego publicadas por empresas de Botucatu e região.')
    return render(request, 'publico/vagas/lista.html', {'vagas': page.object_list, 'page_obj': page, 'total': page.paginator.count, 'seo': seo})


def vaga_publica(request, slug):
    vaga = get_object_or_404(
        Vaga.objects.select_related('empresa', 'perfil_pessoa_fisica').prefetch_related('atributos_adicionais').filter(
            Q(encerramento__isnull=True) | Q(encerramento__gte=timezone.localdate())
        ), slug=slug, status=Vaga.Status.PUBLICADA,
    )
    return render(request, 'publico/vagas/detalhe.html', {'vaga': vaga, 'share_object': vaga, 'share_type': 'vaga', 'seo': vaga_seo(request, vaga)})


def _curriculo_publicado(uuid):
    objeto = get_object_or_404(
        Curriculo.objects.select_related(
            'privacidade',
            'usuario',
        ).prefetch_related(
            'experiencia_set',
            'formacao_set',
            'curso_set',
            'habilidades',
            'idiomas',
            'projetos',
        ),
        uuid=uuid,
        status=Curriculo.Status.CONCLUIDO,
        visibilidade=Curriculo.Visibilidade.PUBLICO,
        ativo=True,
        excluido_em__isnull=True,
    )

    dto = curriculo_publico(objeto)

    if dto is None:
        raise Http404

    return objeto, dto


def curriculo_publico_view(request, uuid):
    objeto, dto = _curriculo_publicado(uuid)

    usuario = objeto.usuario

    nome_publico = (
        usuario.nome_exibicao
        or usuario.get_full_name()
        or usuario.get_username()
    )

    public_url = request.build_absolute_uri(
        reverse('recruitment_public:curriculo', args=[objeto.uuid])
    )

    download_url = request.build_absolute_uri(
        reverse(
            'recruitment_public:curriculo_download',
            args=[objeto.uuid],
        )
    )

    foto_url = request.build_absolute_uri(
        usuario.foto.url
        if usuario.foto
        else static('img/default/curriculo-social-default.png')
    )

    return render(request, 'publico/vagas/curriculo.html', {
        'curriculo': dto,
        'objeto': objeto,
        'usuario_curriculo': usuario,
        'nome_publico': nome_publico,
        'foto_url': foto_url,
        'public_url': public_url,
        'download_url': download_url,
        'seo': curriculo_seo(request, objeto),
    })


def curriculo_publico_pdf(request, uuid):
    objeto, dto = _curriculo_publicado(uuid)

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable,
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except ImportError as exc:
        raise Http404('Gerador de PDF indisponível.') from exc

    from xml.sax.saxutils import escape

    usuario = objeto.usuario

    nome_publico = (
        usuario.nome_exibicao
        or usuario.get_full_name()
        or usuario.get_username()
    )

    nome_arquivo = slugify(
        f'curriculo-{nome_publico}'
    ) or 'curriculo-profissional'

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{nome_arquivo}.pdf"'
    )
    response['Cache-Control'] = 'private, no-store, max-age=0'

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='CurriculoNome',
        parent=styles['Title'],
        alignment=TA_CENTER,
        fontSize=21,
        leading=25,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name='CurriculoCargo',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name='CurriculoSecao',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        spaceBefore=12,
        spaceAfter=5,
        textColor=colors.HexColor('#166534'),
    ))

    styles.add(ParagraphStyle(
        name='CurriculoItemTitulo',
        parent=styles['Heading3'],
        fontSize=11,
        leading=14,
        spaceBefore=6,
        spaceAfter=2,
    ))

    styles.add(ParagraphStyle(
        name='CurriculoTexto',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=5,
    ))

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f'Currículo de {nome_publico}',
        author=nome_publico,
    )

    story = []

    def safe(value):
        return escape(str(value or '')).replace('\n', '<br/>')

    def section(title):
        story.append(Paragraph(safe(title), styles['CurriculoSecao']))
        story.append(HRFlowable(
            width='100%',
            thickness=0.6,
            color=colors.HexColor('#cbd5e1'),
            spaceAfter=6,
        ))

    try:
        foto_pdf_path = (
            usuario.foto.path
            if usuario.foto
            else str(
                Path(settings.BASE_DIR)
                / 'static'
                / 'img'
                / 'default'
                / 'curriculo-social-default.png'
            )
        )

        image = Image(
            foto_pdf_path,
            width=3.2 * cm,
            height=3.2 * cm,
        )
        image.hAlign = 'CENTER'
        story.append(image)
        story.append(Spacer(1, 8))
    except Exception:
        pass

    story.append(Paragraph(
        safe(nome_publico),
        styles['CurriculoNome'],
    ))

    story.append(Paragraph(
        safe(
            dto.titulo_profissional
            or dto.area_profissional
            or 'Perfil profissional'
        ),
        styles['CurriculoCargo'],
    ))

    localizacao = ' · '.join(filter(None, [
        dto.cidade,
        dto.estado,
    ]))

    contatos = ' · '.join(filter(None, [
        dto.email,
        dto.telefone,
        localizacao,
    ]))

    if contatos:
        story.append(Paragraph(
            safe(contatos),
            styles['CurriculoCargo'],
        ))

    links = []

    if dto.linkedin:
        links.append(f'LinkedIn: {dto.linkedin}')
    if dto.github:
        links.append(f'GitHub: {dto.github}')
    if dto.portfolio:
        links.append(f'Portfólio: {dto.portfolio}')
    if dto.site_profissional:
        links.append(f'Site: {dto.site_profissional}')

    if links:
        story.append(Paragraph(
            '<br/>'.join(safe(item) for item in links),
            styles['CurriculoTexto'],
        ))

    if dto.objetivo_profissional:
        section('Objetivo profissional')
        story.append(Paragraph(
            safe(dto.objetivo_profissional),
            styles['CurriculoTexto'],
        ))

    if dto.resumo:
        section('Resumo profissional')
        story.append(Paragraph(
            safe(dto.resumo),
            styles['CurriculoTexto'],
        ))

    if dto.experiencias:
        section('Experiências profissionais')

        for item in dto.experiencias:
            titulo = ' — '.join(filter(None, [
                item.get('cargo'),
                item.get('empresa'),
            ]))

            story.append(Paragraph(
                safe(titulo),
                styles['CurriculoItemTitulo'],
            ))

            periodo = ' a '.join(filter(None, [
                item.get('inicio'),
                'Atual' if item.get('atual') else item.get('fim'),
            ]))

            if periodo:
                story.append(Paragraph(
                    safe(periodo),
                    styles['CurriculoTexto'],
                ))

            if item.get('descricao'):
                story.append(Paragraph(
                    safe(item['descricao']),
                    styles['CurriculoTexto'],
                ))

    if dto.formacoes:
        section('Formação acadêmica')

        for item in dto.formacoes:
            story.append(Paragraph(
                safe(item.get('curso')),
                styles['CurriculoItemTitulo'],
            ))

            detalhes = ' · '.join(filter(None, [
                item.get('instituicao'),
                item.get('nivel'),
            ]))

            if detalhes:
                story.append(Paragraph(
                    safe(detalhes),
                    styles['CurriculoTexto'],
                ))

    if dto.cursos:
        section('Cursos e certificações')

        for item in dto.cursos:
            story.append(Paragraph(
                safe(item.get('nome')),
                styles['CurriculoItemTitulo'],
            ))

            detalhes = ' · '.join(filter(None, [
                item.get('instituicao'),
                (
                    f"{item.get('carga_horaria')} horas"
                    if item.get('carga_horaria')
                    else ''
                ),
            ]))

            if detalhes:
                story.append(Paragraph(
                    safe(detalhes),
                    styles['CurriculoTexto'],
                ))

    if dto.habilidades:
        section('Habilidades')

        valores = []

        for item in dto.habilidades:
            valor = item.get('nome', '')

            if item.get('nivel'):
                valor += f" — {item['nivel']}"

            valores.append(valor)

        story.append(Paragraph(
            safe(' • '.join(valores)),
            styles['CurriculoTexto'],
        ))

    if dto.idiomas:
        section('Idiomas')

        valores = []

        for item in dto.idiomas:
            valor = item.get('nome', '')

            if item.get('nivel'):
                valor += f" — {item['nivel']}"

            valores.append(valor)

        story.append(Paragraph(
            safe(' • '.join(valores)),
            styles['CurriculoTexto'],
        ))

    if dto.projetos:
        section('Projetos')

        for item in dto.projetos:
            story.append(Paragraph(
                safe(item.get('titulo')),
                styles['CurriculoItemTitulo'],
            ))

            if item.get('descricao'):
                story.append(Paragraph(
                    safe(item['descricao']),
                    styles['CurriculoTexto'],
                ))

            if item.get('url'):
                story.append(Paragraph(
                    safe(item['url']),
                    styles['CurriculoTexto'],
                ))

    document.build(story)

    return response


@login_required
def candidatar(request, slug):
    vaga = get_object_or_404(Vaga.objects, slug=slug, status=Vaga.Status.PUBLICADA)
    curriculo = Curriculo.objects.filter(
        usuario=request.user, ativo=True, excluido_em__isnull=True,
        status=Curriculo.Status.CONCLUIDO,
        visibilidade__in=[Curriculo.Visibilidade.CANDIDATURAS, Curriculo.Visibilidade.PUBLICO],
    ).first()
    if curriculo is None:
        request.session['candidatura_pendente_slug'] = vaga.slug
        messages.info(
            request,
            'Para se candidatar, crie e publique seu currículo. A vaga ficará salva enquanto você conclui o assistente.',
        )
        curriculo_existente = _curriculo_usuario(request.user)
        if curriculo_existente:
            etapa = max(1, min(curriculo_existente.etapa_atual or 1, 10))
            etapa_lista = {
                3: 'painel:curriculo_experiencias',
                4: 'painel:curriculo_formacoes',
                5: 'painel:curriculo_cursos',
                6: 'painel:curriculo_habilidades',
                7: 'painel:curriculo_idiomas',
                8: 'painel:curriculo_projetos',
            }.get(etapa)
            if etapa_lista:
                return redirect(etapa_lista)
            return redirect('painel:curriculo_etapa', etapa=etapa)
        return redirect('painel:curriculo_novo')
    form = CandidaturaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                candidatura = form.save(commit=False); candidatura.vaga = vaga; candidatura.usuario = request.user; candidatura.curriculo = curriculo; candidatura.save()
            messages.success(request, 'Candidatura enviada.')
        except (IntegrityError,):
            messages.error(request, 'Você já possui uma candidatura ativa para esta vaga.')
        return redirect('recruitment_public:vaga', slug=slug)
    return render(request, 'painel/recruitment/form.html', {'titulo': 'Candidatar-se', 'form': form})


@login_required
def minhas_candidaturas(request):
    return render(request, 'painel/candidaturas/lista.html', {'candidaturas': Candidatura.objects.filter(usuario=request.user).select_related('vaga')})


@login_required
def candidaturas_empresa(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not pode_administrar_vaga(request.user, vaga):
        raise PermissionDenied
    registrar_acao(vaga, request.user, 'visualizacao_candidaturas', request)
    return render(request, 'painel/candidaturas/lista.html', {'candidaturas': vaga.candidaturas.select_related('usuario', 'curriculo'), 'vaga': vaga})



@login_required
def candidatura_curriculo(request, uuid, candidatura_uuid):
    vaga = _vaga_usuario(request.user, uuid)

    candidatura = get_object_or_404(
        vaga.candidaturas.select_related(
            'usuario',
            'curriculo',
        ).prefetch_related(
            'historico__usuario',
        ),
        uuid=candidatura_uuid,
        ativo=True,
        excluido_em__isnull=True,
    )

    snapshot = candidatura.curriculo_snapshot

    if not snapshot:
        snapshot = curriculo_para_candidatura(
            candidatura.curriculo
        ).serializar()

    registrar_acao(
        vaga,
        request.user,
        'visualizacao_curriculo_candidato',
        request,
        candidatura=str(candidatura.uuid),
        candidato=str(candidatura.usuario_id),
        snapshot_versao=candidatura.snapshot_versao,
    )

    contexto = {
        'vaga': vaga,
        'candidatura': candidatura,
        'candidato': candidatura.usuario,
        'curriculo': snapshot,
        'historico': candidatura.historico.select_related('usuario'),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(
            request,
            'painel/candidaturas/partials/curriculo_modal.html',
            contexto,
        )

    return render(
        request,
        'painel/candidaturas/curriculo.html',
        contexto,
    )


@login_required
def candidaturas_exportar(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not pode_administrar_vaga(request.user, vaga):
        raise PermissionDenied
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="candidaturas-{vaga.uuid}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Candidato', 'E-mail', 'Status', 'Data'])
    for candidatura in vaga.candidaturas.select_related('usuario'):
        writer.writerow([
            candidatura.usuario.get_full_name() or candidatura.usuario.get_username(),
            candidatura.usuario.email, candidatura.get_status_display(),
            candidatura.criado_em.strftime('%d/%m/%Y %H:%M'),
        ])
    registrar_acao(vaga, request.user, 'exportacao_candidatos', request)
    return response


@login_required
def candidatura_status(request, uuid, candidatura_uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not pode_administrar_vaga(request.user, vaga):
        raise PermissionDenied
    candidatura = get_object_or_404(vaga.candidaturas, uuid=candidatura_uuid)
    novo_status = request.POST.get('status')
    if novo_status not in Candidatura.Status.values:
        raise Http404
    anterior = candidatura.status
    candidatura.status = novo_status
    candidatura.save(update_fields=['status', 'atualizado_em'])
    CandidaturaHistorico.objects.create(
        candidatura=candidatura, usuario=request.user,
        status_anterior=anterior, status_novo=novo_status,
        observacao=request.POST.get('observacao', '').strip()[:1000],
    )
    registrar_acao(vaga, request.user, 'candidatura_status', request, candidatura=str(candidatura.uuid), status_anterior=anterior, status_novo=novo_status)
    messages.success(request, 'Candidatura atualizada.')
    return redirect('painel:candidaturas_empresa', uuid=vaga.uuid)


def _curriculo_usuario(usuario):
    return Curriculo.objects.filter(usuario=usuario, ativo=True, excluido_em__isnull=True).first()


@login_required
def curriculo_detalhe(request):
    curriculo = _curriculo_usuario(request.user)
    return render(request, 'painel/curriculo/index.html', {
        'curriculo': curriculo,
        'progresso': calcular_progresso(curriculo) if curriculo else None,
    })


@login_required
def curriculo_novo(request):
    if _curriculo_usuario(request.user):
        return redirect('painel:curriculo_etapa', etapa=1)
    form = ContatoPublicoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            curriculo = form.save(commit=False)
            curriculo.usuario = request.user
            curriculo.etapa_atual = 2
            curriculo.status = Curriculo.Status.EM_PREENCHIMENTO
            curriculo.save()
        messages.success(request, 'Currículo criado. Continue preenchendo as próximas etapas.')
        if request.POST.get('acao') == 'salvar':
            return redirect('painel:curriculo')
        return redirect('painel:curriculo_etapa', etapa=2)
    return render(request, 'painel/curriculo/etapa.html', {
        'form': form, 'etapa': 1, 'total_etapas': 10, 'curriculo': None,
        'progresso': None, 'titulo': ETAPAS[1][0], 'back_url_name': 'painel:curriculo',
        'descricao': ETAPAS[1][2], 'proxima_etapa_nome': ETAPA_NOMES[2],
        'header_subtitle': f'Etapa 1 de 10 · {ETAPA_NOMES[1]}',
        'breadcrumb_atual': 'Etapa 1 de 10',
    })


ETAPAS = {
    1: ('Dados pessoais', ContatoPublicoForm, 'Informe seus dados de contato e localização. Você controlará a exibição dessas informações na etapa de privacidade.'),
    2: ('Objetivo profissional', PerfilProfissionalForm, 'Apresente seu objetivo, sua área de atuação e um resumo dos seus principais diferenciais profissionais.'),
    3: ('Experiências', None, 'Conte sua trajetória profissional, incluindo cargos, empresas, períodos e principais responsabilidades.'),
    4: ('Formação acadêmica', None, 'Informe sua formação acadêmica. Essas informações ajudam empresas a encontrarem seu perfil.'),
    5: ('Cursos e certificações', None, 'Adicione cursos, treinamentos e certificações relevantes para seus objetivos profissionais.'),
    6: ('Habilidades', None, 'Destaque seus conhecimentos técnicos e comportamentais, com nível e categoria.'),
    7: ('Idiomas', None, 'Informe os idiomas que conhece e seu nível de domínio em cada um deles.'),
    8: ('Projetos', None, 'Apresente projetos e trabalhos que demonstrem sua experiência e suas habilidades.'),
    9: ('Informações adicionais', InformacaoAdicionalForm, 'Acrescente disponibilidade, CNH, trabalho voluntário, premiações e outras informações relevantes.'),
    10: ('Privacidade e publicação', PublicacaoCurriculoForm, 'Escolha quem poderá visualizar seu currículo e quais dados de contato poderão ser exibidos.'),
}

ETAPA_NOMES = {numero: dados[0] for numero, dados in ETAPAS.items()}


@login_required
def curriculo_etapa(request, etapa):
    if etapa not in ETAPAS: raise Http404
    curriculo = _curriculo_usuario(request.user)
    if not curriculo: return redirect('painel:curriculo_novo')
    redirects = {3: 'painel:curriculo_experiencias', 4: 'painel:curriculo_formacoes',
                 5: 'painel:curriculo_cursos', 6: 'painel:curriculo_habilidades',
                 7: 'painel:curriculo_idiomas', 8: 'painel:curriculo_projetos'}
    if etapa in redirects: return redirect(redirects[etapa])
    titulo, form_class, descricao = ETAPAS[etapa]
    if etapa == 9:
        instance, _ = CurriculoInformacaoAdicional.objects.get_or_create(curriculo=curriculo)
        form = form_class(request.POST or None, instance=instance)
        privacy_form = None
    elif etapa == 10:
        privacy = CurriculoPrivacidade.objects.filter(curriculo=curriculo).first()
        if privacy is None:
            privacy = CurriculoPrivacidade(curriculo=curriculo)
        form = form_class(request.POST or None, instance=curriculo)
        privacy_form = CurriculoPrivacidadeForm(request.POST or None, instance=privacy, prefix='privacidade')
    else:
        form = form_class(request.POST or None, instance=curriculo)
        privacy_form = None
    if request.method == 'POST' and form.is_valid() and (privacy_form is None or privacy_form.is_valid()):
        with transaction.atomic():
            form.save()
            if privacy_form: privacy_form.save()
            proxima_etapa = min(etapa + 1, 10)
            atualizar_etapa_atual(curriculo, proxima_etapa)
            if request.POST.get('acao') == 'concluir':
                try:
                    concluir_curriculo(curriculo)
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect('painel:curriculo_etapa', etapa=10)
                else:
                    messages.success(request, 'Currículo concluído com sucesso.')
                    return redirect('painel:curriculo_visualizar')
        messages.success(request, 'Etapa salva com sucesso.')
        if request.POST.get('acao') == 'continuar':
            return redirect('painel:curriculo_etapa', etapa=proxima_etapa)
        return redirect('painel:curriculo')
    return render(request, 'painel/curriculo/etapa.html', {
        'form': form, 'privacy_form': privacy_form, 'titulo': titulo,
        'etapa': etapa, 'total_etapas': 10, 'curriculo': curriculo,
        'progresso': calcular_progresso(curriculo), 'etapas': ETAPAS,
        'descricao': descricao,
        'header_subtitle': f'Etapa {etapa} de 10 · {titulo}',
        'breadcrumb_atual': f'Etapa {etapa} de 10',
        'etapa_anterior_nome': ETAPA_NOMES.get(etapa - 1),
        'proxima_etapa_nome': ETAPA_NOMES.get(etapa + 1),
        'back_url_name': (
            'painel:curriculo' if etapa == 1 else
            'painel:curriculo_projetos' if etapa == 9 else
            'painel:curriculo_etapa'
        ),
        'back_etapa': etapa - 1,
        'back_url_usa_etapa': etapa not in {1, 9},
    })


@login_required
def curriculo_editar(request):
    return redirect('painel:curriculo_etapa', etapa=1)


def _itens(request, config, item_uuid=None, remover=False):
    model = config['model']
    form_class = config['form']
    titulo = config['titulo']
    etapa = config['etapa']
    lista_url = config['lista_url']
    curriculo = _curriculo_usuario(request.user)
    if not curriculo:
        if item_uuid: raise Http404
        return redirect('painel:curriculo_novo')
    queryset = model.objects.filter(curriculo=curriculo, ativo=True, excluido_em__isnull=True)
    item = get_object_or_404(queryset, uuid=item_uuid) if item_uuid else None
    if remover:
        if request.method == 'POST':
            item.delete()
            messages.success(request, 'Item removido com sucesso.')
            return redirect(lista_url)
        return render(request, 'painel/curriculo/remover.html', {
            'item': item, 'item_nome': getattr(item, config['label_field']),
            'titulo': titulo, 'lista_url_name': lista_url,
        })
    form = form_class(request.POST or None, request.FILES or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            registro = form.save(commit=False)
            registro.curriculo = curriculo
            registro.save()
            atualizar_etapa_atual(curriculo, min(etapa + 1, 10))
        messages.success(request, 'Item salvo com sucesso.')
        if request.POST.get('acao') == 'continuar':
            return redirect(config['next_url'], **config.get('next_kwargs', {}))
        return redirect(lista_url)
    return render(request, 'painel/curriculo/itens.html', {
        'titulo': titulo, 'form': form, 'itens': queryset, 'item': item,
        'etapa': etapa, 'progresso': calcular_progresso(curriculo),
        'curriculo': curriculo, 'lista_url_name': lista_url,
        'novo_url_name': config['novo_url'], 'editar_url_name': config['editar_url'],
        'remover_url_name': config['remover_url'], 'next_url_name': config['next_url'],
        'back_url_name': config['back_url'], 'item_partial': config['partial'],
        'back_etapa': config.get('back_etapa'), 'next_etapa': config.get('next_etapa'),
        'descricao': config['descricao'],
        'header_subtitle': f'Etapa {etapa} de 10 · {titulo}',
        'breadcrumb_atual': f'Etapa {etapa} de 10',
        'etapa_anterior_nome': ETAPA_NOMES.get(etapa - 1),
        'proxima_etapa_nome': ETAPA_NOMES.get(etapa + 1),
        'modo_formulario': item is not None or request.resolver_match.url_name == config['novo_route'],
    })


def _crud(config):
    def view(request, uuid=None):
        return _itens(
            request, config, uuid,
            request.resolver_match.url_name == config['remover_route'],
        )
    return login_required(view)

ITEM_CONFIGS = (
    (Experiencia, ExperienciaForm, 3, 'experiencia', 'experiencias', 'titulo', 'painel:curriculo_etapa', 'painel:curriculo_formacoes'),
    (Formacao, FormacaoForm, 4, 'formacao', 'formacoes', 'titulo', 'painel:curriculo_experiencias', 'painel:curriculo_cursos'),
    (Curso, CursoForm, 5, 'curso', 'cursos', 'titulo', 'painel:curriculo_formacoes', 'painel:curriculo_habilidades'),
    (Habilidade, HabilidadeForm, 6, 'habilidade', 'habilidades', 'nome', 'painel:curriculo_cursos', 'painel:curriculo_idiomas'),
    (Idioma, IdiomaForm, 7, 'idioma', 'idiomas', 'nome', 'painel:curriculo_habilidades', 'painel:curriculo_projetos'),
    (Projeto, ProjetoForm, 8, 'projeto', 'projetos', 'titulo', 'painel:curriculo_idiomas', 'painel:curriculo_etapa'),
)


def _item_config(model, form, etapa, singular, plural, label_field, back_url, next_url):
    prefix = f'curriculo_{singular}'
    feminine = singular in {'experiencia', 'formacao', 'habilidade'}
    novo_suffix = 'nova' if feminine else 'novo'
    config = {
        'model': model, 'form': form, 'titulo': ETAPA_NOMES[etapa],
        'descricao': ETAPAS[etapa][2], 'etapa': etapa,
        'label_field': label_field, 'lista_url': f'painel:curriculo_{plural}',
        'novo_url': f'painel:{prefix}_{novo_suffix}',
        'editar_url': f'painel:{prefix}_editar',
        'remover_url': f'painel:{prefix}_remover',
        'novo_route': f'{prefix}_{novo_suffix}',
        'remover_route': f'{prefix}_remover',
        'back_url': back_url, 'next_url': next_url,
        'partial': f'painel/curriculo/{singular}_item.html',
    }
    if etapa == 3:
        config['back_etapa'] = 2
    if etapa == 8:
        config['next_etapa'] = 9
        config['next_kwargs'] = {'etapa': 9}
    return config


(_EXPERIENCIA, _FORMACAO, _CURSO, _HABILIDADE, _IDIOMA, _PROJETO) = [
    _item_config(*args) for args in ITEM_CONFIGS
]
curriculo_experiencias = _crud(_EXPERIENCIA)
curriculo_formacoes = _crud(_FORMACAO)
curriculo_cursos = _crud(_CURSO)
curriculo_habilidades = _crud(_HABILIDADE)
curriculo_idiomas = _crud(_IDIOMA)
curriculo_projetos = _crud(_PROJETO)


@login_required
def curriculo_visualizar(request):
    curriculo = _curriculo_usuario(request.user)

    if not curriculo:
        return redirect('painel:curriculo_novo')

    public_url = ''
    download_url = ''

    if (
        curriculo.status == Curriculo.Status.CONCLUIDO
        and curriculo.visibilidade == Curriculo.Visibilidade.PUBLICO
    ):
        public_url = request.build_absolute_uri(
            reverse(
                'recruitment_public:curriculo',
                args=[curriculo.uuid],
            )
        )

        download_url = request.build_absolute_uri(
            reverse(
                'recruitment_public:curriculo_download',
                args=[curriculo.uuid],
            )
        )

    return render(request, 'painel/curriculo/preview.html', {
        'curriculo': curriculo_para_painel(curriculo),
        'progresso': calcular_progresso(curriculo),
        'objeto': curriculo,
        'public_url': public_url,
        'download_url': download_url,
    })
curriculo_preview = curriculo_visualizar
