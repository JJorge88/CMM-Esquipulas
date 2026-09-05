from django.contrib import admin

from .models import Incidente


@admin.register(Incidente)
class IncidenteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fecha_hora_reporte",
        "tipo_incidente",
        "prioridad",
        "estado",
        "operador_responsable",
    )
    list_filter = (
        "estado",
        "prioridad",
        "tipo_incidente",
        "fecha_hora_reporte",
    )
    search_fields = (
        "ubicacion",
        "descripcion",
        "operador_responsable__username",
    )
    list_select_related = ("operador_responsable",)
