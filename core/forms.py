from django import forms

from .models import EncaminhamentoReuniao, Iniciativa, ObjetivoEstrategico, PlanoAcao, Reuniao, Tarefa, Usuario


class BaseEmpresaForm(forms.ModelForm):
    date_fields = ()

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field_name in self.date_fields:
            if field_name in self.fields:
                self.fields[field_name].widget = forms.DateInput(attrs={"type": "date"})

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ObjetivoEstrategicoForm(BaseEmpresaForm):
    class Meta:
        model = ObjetivoEstrategico
        fields = ["nome", "descricao"]


class IniciativaForm(BaseEmpresaForm):
    date_fields = ("data_inicio", "data_fim")

    class Meta:
        model = Iniciativa
        fields = [
            "objetivo",
            "nome",
            "descricao",
            "status",
            "data_inicio",
            "data_fim",
            "responsavel",
            "dependencias",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user and self.user.empresa:
            self.fields["objetivo"].queryset = ObjetivoEstrategico.objects.filter(empresa=self.user.empresa)
            self.fields["responsavel"].queryset = Usuario.objects.filter(empresa=self.user.empresa).order_by(
                "first_name",
                "username",
            )
            self.fields["dependencias"].queryset = Iniciativa.objects.filter(empresa=self.user.empresa).order_by("nome")
            self.fields["dependencias"].widget = forms.CheckboxSelectMultiple()
            self.fields["dependencias"].widget.choices = self.fields["dependencias"].choices
        if self.instance.pk:
            self.fields["dependencias"].queryset = self.fields["dependencias"].queryset.exclude(pk=self.instance.pk)
            self.fields["dependencias"].widget.choices = self.fields["dependencias"].choices
        if self.fields["dependencias"].queryset.exists():
            self.fields["dependencias"].help_text = "Selecione uma ou mais iniciativas das quais esta depende."
        else:
            self.fields["dependencias"].help_text = (
                "Nenhuma iniciativa anterior disponivel para dependencia ainda. "
                "Crie outras iniciativas primeiro se precisar relacionar dependencias."
            )


class TarefaForm(BaseEmpresaForm):
    date_fields = ("data_vencimento",)

    class Meta:
        model = Tarefa
        fields = ["iniciativa", "nome", "responsavel", "data_vencimento", "status"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user and self.user.empresa:
            self.fields["iniciativa"].queryset = Iniciativa.objects.filter(empresa=self.user.empresa).order_by("nome")
            self.fields["responsavel"].queryset = Usuario.objects.filter(empresa=self.user.empresa).order_by(
                "first_name",
                "username",
            )


class PlanoAcaoForm(BaseEmpresaForm):
    date_fields = (
        "data_inicio_prevista",
        "data_inicio_efetiva",
        "data_fim_prevista",
        "data_fim_efetiva",
    )

    class Meta:
        model = PlanoAcao
        fields = [
            "tarefa",
            "etapa",
            "responsavel",
            "data_inicio_prevista",
            "data_inicio_efetiva",
            "data_fim_prevista",
            "data_fim_efetiva",
            "status",
            "observacoes",
        ]

    def __init__(self, *args, user=None, tarefa=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user and self.user.empresa:
            self.fields["responsavel"].queryset = Usuario.objects.filter(empresa=self.user.empresa).order_by(
                "first_name",
                "username",
            )
            self.fields["tarefa"].queryset = Tarefa.objects.filter(iniciativa__empresa=self.user.empresa).order_by("nome")
        if tarefa is not None:
            self.fields["tarefa"].initial = tarefa
            self.fields["tarefa"].queryset = Tarefa.objects.filter(pk=tarefa.pk)


class ReuniaoForm(BaseEmpresaForm):
    class Meta:
        model = Reuniao
        fields = [
            "titulo",
            "data_hora",
            "local",
            "participantes_usuarios",
            "participantes_externos",
            "pauta",
            "ata",
            "decisoes",
            "status",
        ]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["participantes_usuarios"].label = "Participantes internos"
        self.fields["participantes_externos"].label = "Participantes externos"
        self.fields["participantes_usuarios"].widget = forms.CheckboxSelectMultiple()
        if self.user and self.user.empresa:
            self.fields["participantes_usuarios"].queryset = Usuario.objects.filter(
                empresa=self.user.empresa,
            ).order_by("first_name", "username")
        self.fields["participantes_usuarios"].widget.choices = self.fields["participantes_usuarios"].choices
        self.fields["participantes_usuarios"].help_text = "Selecione os usuarios do sistema que participaram da reuniao."
        self.fields["participantes_externos"].help_text = "Inclua convidados externos, um por linha, quando houver."


class EncaminhamentoReuniaoForm(BaseEmpresaForm):
    date_fields = ("prazo",)

    class Meta:
        model = EncaminhamentoReuniao
        fields = [
            "descricao",
            "detalhes",
            "responsavel",
            "prazo",
            "tipo_geracao",
            "objetivo",
            "iniciativa_base",
        ]

    def __init__(self, *args, user=None, reuniao=None, **kwargs):
        self.reuniao = reuniao
        super().__init__(*args, user=user, **kwargs)
        if self.user and self.user.empresa:
            self.fields["responsavel"].queryset = Usuario.objects.filter(empresa=self.user.empresa).order_by(
                "first_name",
                "username",
            )
            self.fields["objetivo"].queryset = ObjetivoEstrategico.objects.filter(empresa=self.user.empresa).order_by("nome")
            self.fields["iniciativa_base"].queryset = Iniciativa.objects.filter(empresa=self.user.empresa).order_by("nome")
        self.fields["objetivo"].required = False
        self.fields["iniciativa_base"].required = False
        self.fields["objetivo"].help_text = "Use quando este encaminhamento for virar uma iniciativa."
        self.fields["iniciativa_base"].help_text = "Use quando este encaminhamento for virar uma tarefa."
