from django.contrib import admin

from .models import EvidenciaIncidente, Incidente, SeguimientoIncidente


class SeguimientoIncidenteInline(admin.TabularInline):
    model = SeguimientoIncidente
    fields = (
        "fecha_hora",
        "usuario",
        "observacion",
        "estado_anterior",
        "estado_nuevo",
        "fecha_creacion",
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EvidenciaIncidenteInline(admin.TabularInline):
    model = EvidenciaIncidente
    fields = (
        "archivo",
        "tipo",
        "descripcion",
        "usuario",
        "fecha_hora",
        "fecha_creacion",
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    inlines = (SeguimientoIncidenteInline, EvidenciaIncidenteInline)


@admin.register(SeguimientoIncidente)
class SeguimientoIncidenteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "incidente",
        "fecha_hora",
        "usuario",
        "estado_anterior",
        "estado_nuevo",
    )
    list_filter = ("estado_nuevo", "fecha_hora", "usuario")
    search_fields = (
        "observacion",
        "usuario__username",
        "incidente__ubicacion",
    )
    list_select_related = ("incidente", "usuario")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EvidenciaIncidente)
class EvidenciaIncidenteAdmin(admin.ModelAdmin):
    list_display = ("id", "incidente", "tipo", "fecha_hora", "usuario")
    list_filter = ("tipo", "fecha_hora", "usuario")
    search_fields = (
        "descripcion",
        "incidente__ubicacion",
        "usuario__username",
    )
    list_select_related = ("incidente", "usuario")
