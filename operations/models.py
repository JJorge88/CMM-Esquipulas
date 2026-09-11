from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from .validators import intervalo_turno, turnos_se_solapan, validar_operador


class InstitucionApoyo(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    siglas = models.CharField(max_length=30, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    correo_electronico = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "institución de apoyo"
        verbose_name_plural = "instituciones de apoyo"

    def __str__(self):
        if self.siglas:
            return f"{self.nombre} ({self.siglas})"
        return self.nombre


class Turno(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("hora_inicio", "nombre")
        verbose_name = "turno"
        verbose_name_plural = "turnos"

    def __str__(self):
        inicio = self.hora_inicio.strftime("%H:%M")
        fin = self.hora_fin.strftime("%H:%M")
        return f"{self.nombre} ({inicio} - {fin})"


class AsignacionTurno(models.Model):
    operador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_turno",
    )
    turno = models.ForeignKey(
        Turno,
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )
    fecha = models.DateField()
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("operador", "turno", "fecha"),
                name="operador_turno_fecha_unicos",
            ),
        )
        verbose_name = "asignación de turno"
        verbose_name_plural = "asignaciones de turnos"

    def clean(self):
        super().clean()

        if self.operador_id:
            validar_operador(self.operador)

        if not (self.operador_id and self.turno_id and self.fecha):
            return

        inicio, fin = intervalo_turno(self.fecha, self.turno)
        asignaciones = (
            AsignacionTurno.objects.filter(
                operador_id=self.operador_id,
                fecha__range=(
                    self.fecha - timedelta(days=1),
                    self.fecha + timedelta(days=1),
                ),
            )
            .exclude(pk=self.pk)
            .select_related("turno")
        )

        for asignacion in asignaciones:
            if (
                asignacion.fecha == self.fecha
                and asignacion.turno_id == self.turno_id
            ):
                continue

            otro_inicio, otro_fin = intervalo_turno(
                asignacion.fecha,
                asignacion.turno,
            )
            if turnos_se_solapan(inicio, fin, otro_inicio, otro_fin):
                raise ValidationError(
                    {
                        "turno": (
                            "El turno se solapa con otra asignación del "
                            "operador."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.operador.username} - {self.turno} - {self.fecha}"
