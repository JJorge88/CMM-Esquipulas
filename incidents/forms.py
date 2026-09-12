from django import forms
from django.core.exceptions import ValidationError

from .models import Incidente


class IncidenteForm(forms.ModelForm):
    class Meta:
        model = Incidente
        fields = (
            "fecha_hora_reporte",
            "ubicacion",
            "tipo_incidente",
            "prioridad",
            "descripcion",
        )
        labels = {
            "fecha_hora_reporte": "Fecha y hora del reporte",
            "ubicacion": "Ubicación",
            "tipo_incidente": "Tipo de incidente",
            "prioridad": "Prioridad",
            "descripcion": "Descripción del incidente",
        }
        widgets = {
            "fecha_hora_reporte": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "ubicacion": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_incidente": forms.TextInput(attrs={"class": "form-control"}),
            "prioridad": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            ),
        }


class FiltroIncidentesForm(forms.Form):
    busqueda = forms.CharField(
        required=False,
        label="Búsqueda general",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ubicación, descripción o tipo"}
        ),
    )
    estado = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos los estados"), *Incidente.Estado.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tipo = forms.ChoiceField(
        required=False,
        label="Tipo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    prioridad = forms.ChoiceField(
        required=False,
        label="Prioridad",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha_desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipos = Incidente.objects.order_by("tipo_incidente").values_list(
            "tipo_incidente", flat=True
        ).distinct()
        prioridades = Incidente.objects.order_by("prioridad").values_list(
            "prioridad", flat=True
        ).distinct()
        self.fields["tipo"].choices = [
            ("", "Todos los tipos"), *((valor, valor) for valor in tipos)
        ]
        self.fields["prioridad"].choices = [
            ("", "Todas las prioridades"),
            *((valor, valor) for valor in prioridades),
        ]

    def clean(self):
        datos = super().clean()
        desde = datos.get("fecha_desde")
        hasta = datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            raise ValidationError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
        return datos
