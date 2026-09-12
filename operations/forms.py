from django import forms
from django.contrib.auth.models import User

from accounts.models import PerfilUsuario

from .models import AsignacionTurno, Turno


class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ("nombre", "hora_inicio", "hora_fin", "activo")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "hora_inicio": forms.TimeInput(format="%H:%M", attrs={"class": "form-control", "type": "time"}),
            "hora_fin": forms.TimeInput(format="%H:%M", attrs={"class": "form-control", "type": "time"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AsignacionForm(forms.ModelForm):
    operador = forms.ModelChoiceField(
        label="Operador", queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = AsignacionTurno
        fields = ("operador", "turno", "fecha", "observacion")
        widgets = {
            "turno": forms.Select(attrs={"class": "form-select"}),
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operador"].queryset = User.objects.filter(
            is_active=True, perfil__rol=PerfilUsuario.Rol.OPERADOR
        ).order_by("first_name", "last_name", "username")
        self.fields["turno"].queryset = Turno.objects.order_by("hora_inicio", "nombre")


class FiltroTurnosForm(forms.Form):
    nombre = forms.CharField(
        required=False, label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar turno"}),
    )
    activo = forms.ChoiceField(
        required=False, label="Estado",
        choices=(("", "Todos"), ("si", "Activo"), ("no", "Inactivo")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class FiltroAsignacionesForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False, label="Desde",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    fecha_hasta = forms.DateField(
        required=False, label="Hasta",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    turno = forms.ModelChoiceField(
        required=False, queryset=Turno.objects.order_by("hora_inicio", "nombre"),
        empty_label="Todos los turnos",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    operador = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(asignaciones_turno__isnull=False).distinct().order_by("username"),
        empty_label="Todos los operadores",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, mostrar_operador=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not mostrar_operador:
            self.fields.pop("operador")

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("fecha_desde"), datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            self.add_error("fecha_hasta", "La fecha final debe ser igual o posterior a la inicial.")
        return datos
