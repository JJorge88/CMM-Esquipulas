from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import validar_archivo_evidencia


def ruta_evidencia_incidente(instancia, nombre_archivo):
    extension = Path(nombre_archivo).suffix.lower()
    nombre_seguro = f"{uuid4().hex}{extension}"
    return (
        f"evidencias/incidentes/{instancia.incidente_id}/"
        f"{nombre_seguro}"
    )


class Incidente(models.Model):
    class Estado(models.TextChoices):
        REGISTRADO = "REGISTRADO", "Registrado"
        PENDIENTE = "PENDIENTE", "Pendiente de atención"
        EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En seguimiento"
        RESUELTO = "RESUELTO", "Resuelto"
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
        default=Estado.REGISTRADO,
    )
    resultado_cierre = models.TextField(blank=True)
    fecha_inicio_atencion = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha_hora_reporte",)
        verbose_name = "incidente"
        verbose_name_plural = "incidentes"

    def clean(self):
        super().clean()
        if self.estado == self.Estado.CERRADO and not self.resultado_cierre.strip():
            estado_anterior = None
            if self.pk:
                estado_anterior = type(self).objects.filter(pk=self.pk).values_list(
                    "estado", flat=True
                ).first()
            if estado_anterior != self.Estado.CERRADO:
                raise ValidationError({
                    "resultado_cierre": "Debe registrar el resultado para cerrar el incidente."
                })

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


class EvidenciaIncidente(models.Model):
    class Tipo(models.TextChoices):
        FOTO = "FOTO", "Fotografía"
        VIDEO = "VIDEO", "Video"
        DOCUMENTO = "DOCUMENTO", "Documento"
        OTRO = "OTRO", "Otro"

    incidente = models.ForeignKey(
        Incidente,
        on_delete=models.CASCADE,
        related_name="evidencias",
    )
    archivo = models.FileField(upload_to=ruta_evidencia_incidente)
    tipo = models.CharField(max_length=9, choices=Tipo.choices)
    descripcion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="evidencias_incidentes",
    )
    fecha_hora = models.DateTimeField(default=timezone.now)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha_hora",)
        verbose_name = "evidencia de incidente"
        verbose_name_plural = "evidencias de incidentes"

    def clean(self):
        super().clean()
        if self.archivo:
            validar_archivo_evidencia(self.archivo.name, self.tipo)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        fecha = self.fecha_hora.strftime("%d/%m/%Y %H:%M")
        return f"{self.incidente} - {self.get_tipo_display()} - {fecha}"


class ParticipacionInstitucion(models.Model):
    incidente = models.ForeignKey(
        Incidente,
        on_delete=models.CASCADE,
        related_name="participaciones_institucionales",
    )
    institucion = models.ForeignKey(
        "operations.InstitucionApoyo",
        on_delete=models.PROTECT,
        related_name="participaciones_incidentes",
    )
    fecha_asignacion = models.DateTimeField(default=timezone.now)
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("incidente", "institucion"),
                name="incidente_institucion_unica",
            ),
        )
        verbose_name = "participación institucional"
        verbose_name_plural = "participaciones institucionales"

    def __str__(self):
        return f"{self.institucion} - {self.incidente}"
