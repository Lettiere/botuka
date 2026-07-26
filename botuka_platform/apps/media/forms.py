from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import (
    Apresentador,
    BannerYuBotuka,
    Canal,
    CanalUsuario,
    CategoriaYuBotuka,
    ConfiguracaoYuBotuka,
    Convidado,
    DestaqueEditorial,
    Episodio,
    MotivoRejeicao,
    Patrocinador,
    Playlist,
    PlaylistVideo,
    ProgramaApresentador,
    ProgramaPatrocinador,
    Programa,
    TagYuBotuka,
    Temporada,
    Transmissao,
    TransmissaoApresentador,
    TransmissaoConvidado,
    TransmissaoPatrocinador,
    Video,
    VideoApresentador,
    VideoConvidado,
    VideoPatrocinador,
    VideoTag,
)
from .permissions import possui
from .selectors import canais_permitidos, categorias_ativas, playlists_visiveis, programas_permitidos


class VideoForm(forms.ModelForm):
    playlists = forms.ModelMultipleChoiceField(
        queryset=Playlist.objects.none(), required=False,
        help_text='O vídeo pode participar de mais de uma playlist.',
    )
    tags = forms.ModelMultipleChoiceField(queryset=TagYuBotuka.objects.none(), required=False)
    apresentadores = forms.ModelMultipleChoiceField(queryset=Apresentador.objects.none(), required=False)
    convidados = forms.ModelMultipleChoiceField(queryset=Convidado.objects.none(), required=False)
    patrocinadores = forms.ModelMultipleChoiceField(queryset=Patrocinador.objects.none(), required=False)

    class Meta:
        model = Video
        fields = (
            'titulo', 'descricao_curta', 'descricao', 'youtube_url',
            'thumbnail', 'duracao', 'categoria', 'canal', 'programa',
            'temporada', 'numero_episodio', 'tipo', 'idioma',
            'classificacao', 'formato', 'data_gravacao',
            'permitir_comentarios', 'conteudo_infantil', 'publico',
            'destaque', 'publicar_na_home', 'playlists', 'tags',
            'apresentadores', 'convidados', 'patrocinadores',
            'titulo_seo', 'descricao_seo', 'imagem_compartilhamento',
        )
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 6}),
            'data_gravacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['categoria'].queryset = categorias_ativas()
        canais = canais_permitidos(user)
        self.fields['canal'].queryset = canais
        self.fields['programa'].queryset = Programa.objects.filter(
            ativo=True, excluido_em__isnull=True, canal__in=canais,
        ).select_related('canal')
        self.fields['playlists'].queryset = playlists_visiveis(user)
        self.fields['temporada'].queryset = Temporada.objects.filter(
            ativo=True, excluido_em__isnull=True, programa__canal__in=canais,
        ).select_related('programa')
        self.fields['tags'].queryset = TagYuBotuka.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['apresentadores'].queryset = Apresentador.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['convidados'].queryset = Convidado.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['patrocinadores'].queryset = Patrocinador.objects.filter(ativo=True, excluido_em__isnull=True)
        if self.instance.pk:
            self.initial['playlists'] = Playlist.objects.filter(
                itens__video=self.instance,
            )
            self.initial['tags'] = TagYuBotuka.objects.filter(tags_videos__video=self.instance)
            self.initial['apresentadores'] = Apresentador.objects.filter(apresentadores_videos__video=self.instance)
            self.initial['convidados'] = Convidado.objects.filter(convidados_videos__video=self.instance)
            self.initial['patrocinadores'] = Patrocinador.objects.filter(patrocinadores_videos__video=self.instance)
        if not possui(self.user, 'yubotuka.video.destacar'):
            self.fields['destaque'].disabled = True
            self.fields['publicar_na_home'].disabled = True

    def save_playlists(self, video):
        selecionadas = list(self.cleaned_data['playlists'])
        PlaylistVideo.objects.filter(video=video).exclude(
            playlist__in=selecionadas,
        ).delete()
        for playlist in selecionadas:
            if not PlaylistVideo.objects.filter(playlist=playlist, video=video).exists():
                proxima_ordem = (
                    PlaylistVideo.objects.filter(playlist=playlist)
                    .order_by('-ordem').values_list('ordem', flat=True).first()
                )
                PlaylistVideo.objects.create(
                    playlist=playlist, video=video,
                    ordem=(proxima_ordem or 0) + 1,
                    adicionado_por=self.user,
                )
        self._sincronizar_relacao(VideoTag, 'tag', self.cleaned_data['tags'], video)
        self._sincronizar_relacao(VideoApresentador, 'apresentador', self.cleaned_data['apresentadores'], video)
        self._sincronizar_relacao(VideoConvidado, 'convidado', self.cleaned_data['convidados'], video)
        self._sincronizar_relacao(VideoPatrocinador, 'patrocinador', self.cleaned_data['patrocinadores'], video)

    @staticmethod
    def _sincronizar_relacao(model, campo, selecionados, video):
        ids = [obj.pk for obj in selecionados]
        model.objects.filter(video=video).exclude(**{f'{campo}_id__in': ids}).delete()
        for ordem, obj in enumerate(selecionados):
            defaults = {'ordem': ordem} if any(field.name == 'ordem' for field in model._meta.fields) else {}
            model.objects.get_or_create(video=video, **{campo: obj}, defaults=defaults)


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = CategoriaYuBotuka
        fields = ('nome', 'categoria_pai', 'icone', 'cor', 'ordem', 'ativo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = categorias_ativas()
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields['categoria_pai'].queryset = queryset


class PlaylistForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = (
            'nome', 'descricao', 'thumbnail', 'canal', 'categoria',
            'playlist_pai', 'ordem', 'ativo',
        )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['categoria'].queryset = categorias_ativas()
        self.fields['canal'].queryset = Canal.objects.filter(ativo=True, excluido_em__isnull=True)
        pais = playlists_visiveis(user)
        if self.instance.pk:
            pais = pais.exclude(pk=self.instance.pk)
        self.fields['playlist_pai'].queryset = pais


class RejeicaoForm(forms.Form):
    motivo_rejeicao = forms.ModelChoiceField(
        queryset=MotivoRejeicao.objects.filter(ativo=True, excluido_em__isnull=True),
        label='Motivo da rejeição',
    )
    observacao = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}), required=False,
        label='Orientação para correção',
    )

    def clean(self):
        cleaned = super().clean()
        motivo = cleaned.get('motivo_rejeicao')
        if motivo and motivo.exige_complemento and not cleaned.get('observacao', '').strip():
            self.add_error('observacao', 'Descreva o ajuste necessário para este motivo.')
        return cleaned


class ArquivamentoForm(forms.Form):
    motivo = forms.CharField(
        min_length=5, max_length=500,
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Motivo do arquivamento',
    )


class AgendamentoForm(forms.Form):
    data_agendamento = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Publicar em',
    )


class CanalForm(forms.ModelForm):
    class Meta:
        model = Canal
        fields = (
            'nome', 'descricao', 'logotipo', 'capa', 'youtube_url',
            'instagram_url', 'facebook_url', 'tiktok_url', 'site_url',
            'proprietario', 'ordem', 'destaque', 'ativo',
        )


class TagForm(forms.ModelForm):
    class Meta:
        model = TagYuBotuka
        fields = ('nome', 'ativo')


class PessoaForm(forms.ModelForm):
    class Meta:
        fields = ('nome', 'foto', 'biografia', 'instagram_url', 'site_url', 'ativo')


class ApresentadorForm(PessoaForm):
    class Meta(PessoaForm.Meta):
        model = Apresentador


class ConvidadoForm(PessoaForm):
    class Meta(PessoaForm.Meta):
        model = Convidado


class PatrocinadorForm(forms.ModelForm):
    class Meta:
        model = Patrocinador
        fields = ('nome', 'logotipo', 'descricao', 'site_url', 'ativo')


class BannerForm(forms.ModelForm):
    class Meta:
        model = BannerYuBotuka
        fields = ('titulo', 'imagem', 'link', 'posicao', 'ordem', 'inicio', 'fim', 'ativo')
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class MotivoRejeicaoForm(forms.ModelForm):
    class Meta:
        model = MotivoRejeicao
        fields = ('nome', 'descricao', 'exige_complemento', 'ativo')


class ConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoYuBotuka
        fields = (
            'titulo_publico', 'descricao_publica', 'quantidade_home',
            'quantidade_pagina', 'exibir_categorias', 'exibir_playlists',
        )


class DestaqueEditorialForm(forms.ModelForm):
    class Meta:
        model = DestaqueEditorial
        fields = (
            'video', 'posicao', 'canal', 'categoria', 'programa',
            'playlist', 'ordem', 'inicio', 'fim', 'ativo',
        )
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned = super().clean()
        posicao = cleaned.get('posicao')
        campo_escopo = {
            DestaqueEditorial.Posicao.CANAL: 'canal',
            DestaqueEditorial.Posicao.CATEGORIA: 'categoria',
            DestaqueEditorial.Posicao.PROGRAMA: 'programa',
            DestaqueEditorial.Posicao.PLAYLIST: 'playlist',
        }.get(posicao)
        if campo_escopo and not cleaned.get(campo_escopo):
            self.add_error(campo_escopo, 'Informe o escopo correspondente à posição.')
        inicio, fim = cleaned.get('inicio'), cleaned.get('fim')
        if inicio and fim and fim <= inicio:
            self.add_error('fim', 'O fim deve ser posterior ao início.')
        return cleaned


class ProgramaForm(forms.ModelForm):
    apresentadores = forms.ModelMultipleChoiceField(queryset=Apresentador.objects.none(), required=False)
    patrocinadores = forms.ModelMultipleChoiceField(queryset=Patrocinador.objects.none(), required=False)

    class Meta:
        model = Programa
        fields = (
            'nome', 'descricao', 'canal', 'categoria_editorial', 'imagem',
            'frequencia', 'duracao_media', 'ordem', 'apresentadores',
            'patrocinadores', 'ativo',
        )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['canal'].queryset = canais_permitidos(user)
        self.fields['categoria_editorial'].queryset = categorias_ativas()
        self.fields['apresentadores'].queryset = Apresentador.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['patrocinadores'].queryset = Patrocinador.objects.filter(ativo=True, excluido_em__isnull=True)
        if self.instance.pk:
            self.initial['apresentadores'] = Apresentador.objects.filter(apresentadores_programas__programa=self.instance)
            self.initial['patrocinadores'] = Patrocinador.objects.filter(patrocinadores_programas__programa=self.instance)

    def save_relacoes(self, programa):
        self._sync(ProgramaApresentador, 'apresentador', self.cleaned_data['apresentadores'], programa)
        self._sync(ProgramaPatrocinador, 'patrocinador', self.cleaned_data['patrocinadores'], programa)

    @staticmethod
    def _sync(model, campo, selecionados, programa):
        ids = [obj.pk for obj in selecionados]
        model.objects.filter(programa=programa).exclude(**{f'{campo}_id__in': ids}).delete()
        for ordem, objeto in enumerate(selecionados):
            model.objects.update_or_create(
                programa=programa, **{campo: objeto}, defaults={'ordem': ordem},
            )


class TemporadaForm(forms.ModelForm):
    class Meta:
        model = Temporada
        fields = (
            'programa', 'numero', 'titulo', 'descricao', 'capa',
            'data_inicial', 'data_final', 'ordem', 'encerrada', 'ativo',
        )
        labels = {'titulo': 'Nome da temporada'}
        widgets = {
            'data_inicial': forms.DateInput(attrs={'type': 'date'}),
            'data_final': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['programa'].queryset = programas_permitidos(user)


class EpisodioEditorialForm(forms.ModelForm):
    class Meta:
        model = Episodio
        fields = (
            'programa', 'temporada', 'numero', 'titulo', 'descricao',
            'data_programada', 'status', 'video_editorial', 'ativo',
        )
        labels = {
            'descricao': 'Sinopse',
            'data_programada': 'Data de exibição',
            'video_editorial': 'Vídeo associado',
        }
        widgets = {'data_programada': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        programas = programas_permitidos(user)
        self.fields['programa'].queryset = programas
        self.fields['temporada'].queryset = Temporada.objects.filter(
            ativo=True, excluido_em__isnull=True, programa__in=programas,
        ).select_related('programa')
        videos = Video.objects.filter(canal__in=canais_permitidos(user), excluido_em__isnull=True)
        if self.instance.pk and self.instance.video_editorial_id:
            videos = videos.filter(
                Q(episodio_legado__isnull=True)
                | Q(pk=self.instance.video_editorial_id)
            )
        else:
            videos = videos.filter(episodio_legado__isnull=True)
        self.fields['video_editorial'].queryset = videos


class TransmissaoForm(forms.ModelForm):
    apresentadores = forms.ModelMultipleChoiceField(queryset=Apresentador.objects.none(), required=False)
    convidados = forms.ModelMultipleChoiceField(queryset=Convidado.objects.none(), required=False)
    patrocinadores = forms.ModelMultipleChoiceField(queryset=Patrocinador.objects.none(), required=False)

    class Meta:
        model = Transmissao
        fields = (
            'titulo', 'descricao', 'canal', 'programa', 'categoria',
            'url_ao_vivo', 'thumbnail', 'data_prevista', 'local',
            'apresentadores', 'convidados', 'patrocinadores',
            'exibir_na_home', 'destaque', 'video_resultante', 'ativo',
        )
        widgets = {'data_prevista': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        canais = canais_permitidos(user)
        self.fields['canal'].queryset = canais
        self.fields['programa'].queryset = programas_permitidos(user)
        self.fields['categoria'].queryset = categorias_ativas()
        self.fields['video_resultante'].queryset = Video.objects.filter(canal__in=canais, excluido_em__isnull=True)
        self.fields['apresentadores'].queryset = Apresentador.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['convidados'].queryset = Convidado.objects.filter(ativo=True, excluido_em__isnull=True)
        self.fields['patrocinadores'].queryset = Patrocinador.objects.filter(ativo=True, excluido_em__isnull=True)
        if self.instance.pk:
            self.initial['apresentadores'] = Apresentador.objects.filter(apresentadores_transmissoes__transmissao=self.instance)
            self.initial['convidados'] = Convidado.objects.filter(convidados_transmissoes__transmissao=self.instance)
            self.initial['patrocinadores'] = Patrocinador.objects.filter(patrocinadores_transmissoes__transmissao=self.instance)
        if not possui(user, 'yubotuka.video.destacar'):
            self.fields['destaque'].disabled = True
            self.fields['exibir_na_home'].disabled = True

    def save_relacoes(self, transmissao):
        for model, campo, selecionados in (
            (TransmissaoApresentador, 'apresentador', self.cleaned_data['apresentadores']),
            (TransmissaoConvidado, 'convidado', self.cleaned_data['convidados']),
            (TransmissaoPatrocinador, 'patrocinador', self.cleaned_data['patrocinadores']),
        ):
            ids = [obj.pk for obj in selecionados]
            model.objects.filter(transmissao=transmissao).exclude(**{f'{campo}_id__in': ids}).delete()
            for ordem, objeto in enumerate(selecionados):
                model.objects.update_or_create(
                    transmissao=transmissao, **{campo: objeto}, defaults={'ordem': ordem},
                )


class CanalAtribuicaoForm(forms.Form):
    proprietario = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)
    usuario_autorizado = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)
    pode_editar = forms.BooleanField(required=False, initial=True)
    pode_moderar = forms.BooleanField(required=False)
    motivo = forms.CharField(min_length=5, max_length=500, widget=forms.Textarea(attrs={'rows': 3}))


class HomologacaoLegadoForm(forms.Form):
    autor = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)
    canal = forms.ModelChoiceField(queryset=Canal.objects.none())
    categoria = forms.ModelChoiceField(queryset=CategoriaYuBotuka.objects.none(), required=False)
    playlist = forms.ModelChoiceField(queryset=Playlist.objects.none(), required=False)
    observacao = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))
    confirmar = forms.BooleanField(label='Confirmo que comparei os dados legados e editoriais')

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['canal'].queryset = canais_permitidos(user)
        self.fields['categoria'].queryset = categorias_ativas()
        self.fields['playlist'].queryset = playlists_visiveis(user)
