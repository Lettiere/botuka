from apps.products.public_catalog import produtos_para_home


def obter_produtos_destaque():
    return produtos_para_home(8)
