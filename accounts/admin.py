from django.contrib import admin

from .models import PerfilUsuario


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
