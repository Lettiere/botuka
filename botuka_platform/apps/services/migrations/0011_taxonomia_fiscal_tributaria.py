from django.db import migrations


SETORES_CONTABEIS = ('Contabilidade', 'Contabilidade e Finanças')


def _primeiro_por_nome(model, using, nomes, **filtros):
    for nome in nomes:
        objeto = model.objects.using(using).filter(nome__iexact=nome, **filtros).first()
        if objeto is not None:
            return objeto
    return None


def criar_taxonomia_fiscal(apps, schema_editor):
    using = schema_editor.connection.alias
    Setor = apps.get_model('services', 'Setor')
    AreaProfissional = apps.get_model('services', 'AreaProfissional')
    Profissao = apps.get_model('services', 'Profissao')
    TipoServico = apps.get_model('services', 'TipoServico')
    ProfissaoTipoServico = apps.get_model('services', 'ProfissaoTipoServico')

    analista = None
    for nome_setor in SETORES_CONTABEIS:
        analista = _primeiro_por_nome(
            Profissao,
            using,
            ('Analista fiscal', 'Analista Fiscal'),
            setor__nome__iexact=nome_setor,
        )
        if analista is not None:
            break

    setor = (
        Setor.objects.using(using).get(pk=analista.setor_id)
        if analista is not None
        else _primeiro_por_nome(Setor, using, SETORES_CONTABEIS)
    )
    if setor is None:
        setor = Setor.objects.using(using).create(
            nome='Contabilidade', slug='contabilidade', ativo=True,
        )

    area = AreaProfissional.objects.using(using).filter(
        setor_id=setor.pk, nome__iexact='Fiscal e Tributária',
    ).first()
    if area is None:
        area = AreaProfissional.objects.using(using).create(
            setor_id=setor.pk, nome='Fiscal e Tributária',
            slug='fiscal-e-tributaria', ativo=True,
        )
    elif not area.ativo:
        area.ativo = True
        area.save(using=using, update_fields=['ativo', 'atualizado_em'])

    if analista is None:
        analista = Profissao.objects.using(using).create(
            setor_id=setor.pk, area_id=area.pk, nome='Analista fiscal',
            slug='analista-fiscal', ativo=True,
        )
    else:
        campos = []
        if analista.area_id != area.pk:
            analista.area_id = area.pk
            campos.append('area')
        if not analista.ativo:
            analista.ativo = True
            campos.append('ativo')
        if campos:
            campos.append('atualizado_em')
            analista.save(using=using, update_fields=campos)

    consultor = _primeiro_por_nome(
        Profissao, using, ('Consultor tributário', 'Consultor Tributário'),
        setor_id=setor.pk,
    )
    if consultor is None:
        consultor = Profissao.objects.using(using).create(
            setor_id=setor.pk, area_id=area.pk, nome='Consultor tributário',
            slug='consultor-tributario', ativo=True,
        )

    tipo = TipoServico.objects.using(using).filter(nome__iexact='Consultoria').first()
    if tipo is None:
        tipo = TipoServico.objects.using(using).create(
            nome='Consultoria', slug='consultoria', ativo=True,
        )
    elif not tipo.ativo:
        tipo.ativo = True
        tipo.save(using=using, update_fields=['ativo', 'atualizado_em'])

    for profissao in (analista, consultor):
        vinculo, _ = ProfissaoTipoServico.objects.using(using).get_or_create(
            profissao_id=profissao.pk, tipo_servico_id=tipo.pk,
            defaults={'ativo': True},
        )
        if not vinculo.ativo:
            vinculo.ativo = True
            vinculo.save(using=using, update_fields=['ativo', 'atualizado_em'])


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0010_alter_servico_forma_cobranca_alter_servico_profissao_and_more'),
    ]

    operations = [
        migrations.RunPython(criar_taxonomia_fiscal, migrations.RunPython.noop),
    ]
