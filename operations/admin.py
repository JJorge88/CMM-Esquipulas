from django.contrib import admin

from .models import InstitucionApoyo


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
