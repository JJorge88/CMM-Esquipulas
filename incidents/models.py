from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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


class SeguimientoIncidente(models.Model):
    incidente = models.ForeignKey(
        Incidente,
        on_delete=models.CASCADE,
        related_name="seguimientos",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="seguimientos_incidentes",
    )
    fecha_hora = models.DateTimeField(default=timezone.now)
    observacion = models.TextField()
    estado_anterior = models.CharField(
        max_length=14,
        choices=Incidente.Estado.choices,
        blank=True,
    )
    estado_nuevo = models.CharField(
        max_length=14,
        choices=Incidente.Estado.choices,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("fecha_hora", "id")
        verbose_name = "seguimiento de incidente"
        verbose_name_plural = "seguimientos de incidentes"

    def __str__(self):
        fecha = self.fecha_hora.strftime("%d/%m/%Y %H:%M")
        return f"{self.incidente} - {fecha} - {self.usuario.username}"
