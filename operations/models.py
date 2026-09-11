from django.db import models


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
