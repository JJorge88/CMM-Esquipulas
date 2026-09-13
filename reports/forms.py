from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from incidents.models import Incidente
from operations.models import InstitucionApoyo, RecursoInstitucional


class FiltrosReportesForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False, label="Fecha desde",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    fecha_hasta = forms.DateField(
        required=False, label="Fecha hasta",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    estado = forms.ChoiceField(
        required=False, choices=(), label="Estado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tipo = forms.ChoiceField(
        required=False, choices=(), label="Tipo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    prioridad = forms.ChoiceField(
        required=False, choices=(), label="Prioridad",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    operador = forms.ModelChoiceField(
        required=False, queryset=User.objects.none(), label="Operador",
        empty_label="Todos los operadores",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    institucion = forms.ModelChoiceField(
        required=False, queryset=InstitucionApoyo.objects.none(),
        label="Institución", empty_label="Todas las instituciones",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    camara = forms.ModelChoiceField(
        required=False, queryset=RecursoInstitucional.objects.none(),
        label="Cámara", empty_label="Todas las cámaras",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        presentes = set(
            Incidente.objects.order_by().values_list("estado", flat=True).distinct()
        )
        self.fields["estado"].choices = [
            ("", "Todos los estados"),
            *((valor, etiqueta) for valor, etiqueta in Incidente.Estado.choices
              if valor in presentes),
        ]
        for campo, atributo, etiqueta in (
            ("tipo", "tipo_incidente", "Todos los tipos"),
            ("prioridad", "prioridad", "Todas las prioridades"),
        ):
            valores = Incidente.objects.order_by(atributo).values_list(
                atributo, flat=True
            ).distinct()
            self.fields[campo].choices = [("", etiqueta), *((v, v) for v in valores)]
        self.fields["operador"].queryset = User.objects.filter(
            incidentes_asignados__isnull=False
        ).distinct().order_by("username")
        self.fields["institucion"].queryset = InstitucionApoyo.objects.filter(
            participaciones_incidentes__isnull=False
        ).distinct().order_by("nombre")
        self.fields["camara"].queryset = RecursoInstitucional.objects.filter(
            Q(tipo__es_camara=True) | Q(incidentes_detectados__isnull=False)
        ).select_related("tipo").distinct().order_by("nombre", "pk")

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("fecha_desde"), datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            self.add_error(
                "fecha_hasta", "La fecha final debe ser igual o posterior a la inicial."
            )
        return datos

    def criterios(self):
        datos = self.cleaned_data
        return {
            "fecha_desde": datos["fecha_desde"],
            "fecha_hasta": datos["fecha_hasta"],
            "estado": datos["estado"] or None,
            "tipo": datos["tipo"] or None,
            "prioridad": datos["prioridad"] or None,
            "operador_id": datos["operador"].pk if datos["operador"] else None,
            "institucion_id": datos["institucion"].pk if datos["institucion"] else None,
            "camara_id": datos["camara"].pk if datos["camara"] else None,
        }

    def resumen_activos(self):
        datos = self.cleaned_data
        etiquetas_estado = dict(Incidente.Estado.choices)
        resumen = []
        if datos["fecha_desde"] or datos["fecha_hasta"]:
            desde = datos["fecha_desde"].strftime("%d/%m/%Y") if datos["fecha_desde"] else "Inicio"
            hasta = datos["fecha_hasta"].strftime("%d/%m/%Y") if datos["fecha_hasta"] else "Actualidad"
            resumen.append(("Período", f"{desde} - {hasta}"))
        for campo, etiqueta in (
            ("estado", "Estado"), ("tipo", "Tipo"), ("prioridad", "Prioridad"),
        ):
            if datos[campo]:
                valor = etiquetas_estado[datos[campo]] if campo == "estado" else datos[campo]
                resumen.append((etiqueta, valor))
        for campo, etiqueta in (
            ("operador", "Operador"), ("institucion", "Institución"),
            ("camara", "Cámara"),
        ):
            if datos[campo]:
                resumen.append((etiqueta, str(datos[campo])))
        return resumen
