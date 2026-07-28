from apps.news.selectors import obter_home_noticias


def obter_noticias():
    noticias = obter_home_noticias()
    return (
        noticias["manchete"],
        noticias["destaques"],
        noticias["recentes"],
        noticias["agro"],
        noticias["universidade"],
        noticias["colunistas"],
    )
