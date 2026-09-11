from django.test import TestCase

from .models import InstitucionApoyo


class InstitucionApoyoTests(TestCase):
    def test_crear_institucion_de_apoyo(self):
        institucion = InstitucionApoyo.objects.create(
            nombre="Institución de prueba",
            siglas="IDP",
            telefono="0000-0000",
            correo_electronico="prueba@example.com",
            direccion="Dirección de prueba",
        )

        institucion.refresh_from_db()
        self.assertEqual(institucion.nombre, "Institución de prueba")
        self.assertEqual(institucion.siglas, "IDP")
        self.assertTrue(institucion.activa)
        self.assertIsNotNone(institucion.fecha_creacion)
        self.assertIsNotNone(institucion.fecha_actualizacion)
