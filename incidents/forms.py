from django import forms
from django.core.exceptions import ValidationError

from operations.models import InstitucionApoyo

from .models import EvidenciaIncidente, Incidente, ParticipacionInstitucion
from .services import TRANSICIONES_PERMITIDAS


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


class SeguimientoForm(forms.Form):
    observacion = forms.CharField(
        label="Observación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
    estado_nuevo = forms.ChoiceField(
        label="Nuevo estado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, estado_actual, **kwargs):
        super().__init__(*args, **kwargs)
        permitidos = TRANSICIONES_PERMITIDAS.get(estado_actual, set())
        self.fields["estado_nuevo"].choices = [
            (valor, etiqueta)
            for valor, etiqueta in Incidente.Estado.choices
            if valor in permitidos
        ]


class EvidenciaForm(forms.ModelForm):
    class Meta:
        model = EvidenciaIncidente
        fields = ("archivo", "tipo", "descripcion", "fecha_hora")
        labels = {
            "archivo": "Archivo",
            "tipo": "Tipo de evidencia",
            "descripcion": "Descripción",
            "fecha_hora": "Fecha y hora",
        }
        widgets = {
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "fecha_hora": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
        }


class ParticipacionInstitucionForm(forms.ModelForm):
    class Meta:
        model = ParticipacionInstitucion
        fields = ("institucion", "observacion", "fecha_asignacion")
        labels = {
            "institucion": "Institución",
            "observacion": "Observación",
            "fecha_asignacion": "Fecha y hora de asignación",
        }
        widgets = {
            "institucion": forms.Select(attrs={"class": "form-select"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fecha_asignacion": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
        }

    def __init__(self, *args, incidente, **kwargs):
        super().__init__(*args, **kwargs)
        self.incidente = incidente
        self.fields["institucion"].queryset = InstitucionApoyo.objects.filter(
            activa=True
        ).order_by("nombre")

    def clean_institucion(self):
        institucion = self.cleaned_data["institucion"]
        if ParticipacionInstitucion.objects.filter(
            incidente=self.incidente, institucion=institucion
        ).exists():
            raise ValidationError(
                "Esta institución ya está asociada al incidente."
            )
        return institucion
