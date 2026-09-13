from django import forms
from django.contrib.auth.models import User

from accounts.models import PerfilUsuario

from .models import (
    AsignacionTurno, InstitucionApoyo, RecursoInstitucional, TipoRecurso, Turno,
)


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


class InstitucionForm(forms.ModelForm):
    class Meta:
        model = InstitucionApoyo
        fields = (
            "nombre", "siglas", "telefono", "correo_electronico",
            "direccion", "activa",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "siglas": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "correo_electronico": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, permitir_estado=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not permitir_estado:
            self.fields.pop("activa")


class FiltroInstitucionesForm(forms.Form):
    busqueda = forms.CharField(
        required=False, label="Buscar",
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "Nombre, siglas o teléfono",
        }),
    )
    estado = forms.ChoiceField(
        required=False, label="Estado",
        choices=(("", "Todas"), ("activa", "Activas"), ("inactiva", "Inactivas")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class RecursoForm(forms.ModelForm):
    class Meta:
        model = RecursoInstitucional
        fields = (
            "nombre", "tipo", "codigo_interno", "marca", "modelo",
            "numero_serie", "ubicacion", "descripcion", "estado", "activo",
        )
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "codigo_interno": forms.TextInput(attrs={"class": "form-control"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "ubicacion": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, permitir_estado=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].queryset = TipoRecurso.objects.filter(
            activo=True
        ).order_by("nombre")
        if not permitir_estado:
            self.fields.pop("activo")

    def clean_codigo_interno(self):
        valor = self.cleaned_data["codigo_interno"]
        if valor and RecursoInstitucional.objects.filter(
            codigo_interno=valor
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este código interno ya está registrado.")
        return valor

    def clean_numero_serie(self):
        valor = self.cleaned_data["numero_serie"]
        if valor and RecursoInstitucional.objects.filter(
            numero_serie=valor
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este número de serie ya está registrado.")
        return valor


class FiltroRecursosForm(forms.Form):
    busqueda = forms.CharField(
        required=False, label="Buscar",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nombre, código, marca, serie o ubicación",
        }),
    )
    tipo = forms.ModelChoiceField(
        required=False, queryset=TipoRecurso.objects.order_by("nombre"),
        empty_label="Todos los tipos",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    estado = forms.ChoiceField(
        required=False,
        choices=(("", "Todos los estados"), *RecursoInstitucional.Estado.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    activo = forms.ChoiceField(
        required=False, label="Disponibilidad",
        choices=(("", "Todos"), ("activo", "Activos"), ("inactivo", "Inactivos")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class TipoRecursoForm(forms.ModelForm):
    class Meta:
        model = TipoRecurso
        fields = ("nombre", "descripcion", "activo")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class FiltroTiposRecursoForm(forms.Form):
    busqueda = forms.CharField(
        required=False, label="Buscar",
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "Nombre o descripción",
        }),
    )
