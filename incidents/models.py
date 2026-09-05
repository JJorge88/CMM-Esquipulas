from django.contrib.auth.models import User
from django.db import models


class Incidente(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En seguimiento"
        CERRADO = "CERRADO", "Cerrado"

    fecha_hora_reporte = models.DateTimeField()
    ubicacion = models.CharField(max_length=255)
    tipo_incidente = models.CharField(max_length=100)
    prioridad = models.CharField(max_length=50)
    descripcion = models.TextField()
    operador_responsable = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="incidentes_asignados",
    )
    estado = models.CharField(
        max_length=14,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha_hora_reporte",)
        verbose_name = "incidente"
        verbose_name_plural = "incidentes"

    def __str__(self):
        fecha = self.fecha_hora_reporte.strftime("%d/%m/%Y %H:%M")
        return f"{self.tipo_incidente} - {self.ubicacion} ({fecha})"
