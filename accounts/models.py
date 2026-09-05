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
