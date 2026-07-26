from django.contrib import admin

from .models import (
    CategoriaTurismo, ContatoTurismo, EmpresaTuristica, EstruturaTurismo,
    ExperienciaTuristica,
    GuiaTuristico, LocalTuristico, RedeSocialTurismo, RoteiroTuristico,
    ServicoTurismo, TurismoFoto, TurismoPlaylist, TurismoPlaylistVideo, TurismoVideo,
)

admin.site.register([
    LocalTuristico, GuiaTuristico, TurismoFoto, TurismoVideo,
    TurismoPlaylist, TurismoPlaylistVideo, RoteiroTuristico,
    ExperienciaTuristica, EmpresaTuristica, CategoriaTurismo,
    ContatoTurismo, RedeSocialTurismo,
    EstruturaTurismo, ServicoTurismo,
])
