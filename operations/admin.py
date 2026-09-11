from django.contrib import admin

from .models import (
    AsignacionTurno,
    InstitucionApoyo,
    RecursoInstitucional,
    TipoRecurso,
    Turno,
)


@admin.register(InstitucionApoyo)
class InstitucionApoyoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "siglas",
        "telefono",
        "activa",
        "fecha_creacion",
    )
    list_filter = ("activa", "fecha_creacion")
    search_fields = ("nombre", "siglas", "telefono")


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "hora_inicio", "hora_fin", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(AsignacionTurno)
class AsignacionTurnoAdmin(admin.ModelAdmin):
    list_display = ("operador", "turno", "fecha", "observacion")
    list_filter = ("turno", "fecha")
    search_fields = (
        "operador__username",
        "operador__first_name",
        "operador__last_name",
        "turno__nombre",
    )
    list_select_related = ("operador", "turno")


@admin.register(TipoRecurso)
class TipoRecursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo", "fecha_creacion")
    list_filter = ("activo",)
    search_fields = ("nombre", "descripcion")


@admin.register(RecursoInstitucional)
class RecursoInstitucionalAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "tipo",
        "codigo_interno",
        "estado",
        "ubicacion",
        "activo",
    )
    list_filter = ("tipo", "estado", "activo")
    search_fields = (
        "nombre",
        "codigo_interno",
        "marca",
        "modelo",
        "numero_serie",
        "ubicacion",
    )
    list_select_related = ("tipo",)
