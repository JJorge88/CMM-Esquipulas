from django.contrib.auth.models import User
from django.db import models


class PerfilUsuario(models.Model):
    class Rol(models.TextChoices):
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
        COORDINADOR = "COORDINADOR", "Coordinador"
        OPERADOR = "OPERADOR", "Operador"
        CONSULTA = "CONSULTA", "Consulta"
        AUDITOR = "AUDITOR", "Auditor"

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    rol = models.CharField(
        max_length=13,
        choices=Rol.choices,
        default=Rol.OPERADOR,
    )
    telefono = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"


class AuditoriaAccion(models.Model):
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="auditorias_acciones",
    )
    accion = models.CharField(max_length=40)
    modulo = models.CharField(max_length=40)
    entidad = models.CharField(max_length=80, blank=True)
    entidad_id = models.CharField(max_length=80, blank=True)
    descripcion = models.TextField(blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    metodo_http = models.CharField(max_length=10, blank=True)
    ruta = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-fecha_hora", "-pk")
        verbose_name = "acción de auditoría"
        verbose_name_plural = "acciones de auditoría"

    def __str__(self):
        return f"{self.modulo}: {self.accion} ({self.fecha_hora:%d/%m/%Y %H:%M})"
