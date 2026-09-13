from django.contrib import admin

from .models import AuditoriaAccion, PerfilUsuario


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "nombres",
        "apellidos",
        "rol",
        "estado_usuario",
    )
    list_filter = ("rol", "usuario__is_active")
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
    )
    list_select_related = ("usuario",)

    @admin.display(description="Usuario", ordering="usuario__username")
    def username(self, perfil):
        return perfil.usuario.username

    @admin.display(description="Nombres", ordering="usuario__first_name")
    def nombres(self, perfil):
        return perfil.usuario.first_name

    @admin.display(description="Apellidos", ordering="usuario__last_name")
    def apellidos(self, perfil):
        return perfil.usuario.last_name

    @admin.display(
        boolean=True,
        description="Usuario activo",
        ordering="usuario__is_active",
    )
    def estado_usuario(self, perfil):
        return perfil.usuario.is_active


@admin.register(AuditoriaAccion)
class AuditoriaAccionAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_hora", "usuario", "accion", "modulo", "entidad", "entidad_id", "ip",
    )
    list_filter = ("modulo", "accion", "fecha_hora", "usuario")
    search_fields = (
        "usuario__username", "descripcion", "entidad", "entidad_id",
    )
    readonly_fields = (
        "usuario", "accion", "modulo", "entidad", "entidad_id",
        "descripcion", "fecha_hora", "ip", "metodo_http", "ruta",
    )
    list_select_related = ("usuario",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
