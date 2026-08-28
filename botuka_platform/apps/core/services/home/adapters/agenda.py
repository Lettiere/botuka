from apps.agenda.public_services import empresas_agendaveis


def obter_empresas_com_agenda():
    return empresas_agendaveis(limite=6)
