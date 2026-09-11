from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Incidente, SeguimientoIncidente
from .services import registrar_seguimiento


class RegistrarSeguimientoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="operador_prueba")
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=timezone.now(),
            ubicacion="Ubicación de prueba",
            tipo_incidente="Tipo de prueba",
            prioridad="Prioridad de prueba",
            descripcion="Incidente utilizado por las pruebas.",
            operador_responsable=cls.usuario,
        )

    def test_pendiente_a_en_seguimiento(self):
        seguimiento = registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Se inició la atención.",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )

        self.incidente.refresh_from_db()
        self.assertEqual(
            seguimiento.estado_anterior,
            Incidente.Estado.PENDIENTE,
        )
        self.assertEqual(
            seguimiento.estado_nuevo,
            Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.assertEqual(
            self.incidente.estado,
            Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.assertEqual(self.incidente.seguimientos.count(), 1)

    def test_en_seguimiento_a_en_seguimiento(self):
        registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Se inició la atención.",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        segundo_seguimiento = registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Continúa la atención.",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )

        self.incidente.refresh_from_db()
        self.assertEqual(
            segundo_seguimiento.estado_anterior,
            Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.assertEqual(
            segundo_seguimiento.estado_nuevo,
            Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.assertEqual(self.incidente.seguimientos.count(), 2)
        self.assertEqual(
            self.incidente.estado,
            Incidente.Estado.EN_SEGUIMIENTO,
        )

    def test_en_seguimiento_a_cerrado(self):
        registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Se inició la atención.",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        seguimiento = registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Atención finalizada.",
            estado_nuevo=Incidente.Estado.CERRADO,
        )

        self.incidente.refresh_from_db()
        self.assertEqual(
            seguimiento.estado_anterior,
            Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.assertEqual(
            seguimiento.estado_nuevo,
            Incidente.Estado.CERRADO,
        )
        self.assertEqual(
            self.incidente.estado,
            Incidente.Estado.CERRADO,
        )

    def test_cerrado_a_en_seguimiento_es_rechazado(self):
        registrar_seguimiento(
            incidente=self.incidente,
            usuario=self.usuario,
            observacion="Se cerró el incidente.",
            estado_nuevo=Incidente.Estado.CERRADO,
        )
        cantidad_inicial = self.incidente.seguimientos.count()

        with self.assertRaisesMessage(
            ValidationError,
            "No se permite cambiar el estado del incidente",
        ):
            registrar_seguimiento(
                incidente=self.incidente,
                usuario=self.usuario,
                observacion="Intento de reapertura.",
                estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
            )

        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.estado, Incidente.Estado.CERRADO)
        self.assertEqual(
            self.incidente.seguimientos.count(),
            cantidad_inicial,
        )

    def test_transaccion_revierte_seguimiento_si_falla_actualizacion(self):
        with patch.object(
            Incidente,
            "save",
            side_effect=RuntimeError("Error simulado al actualizar."),
        ):
            with self.assertRaises(RuntimeError):
                registrar_seguimiento(
                    incidente=self.incidente,
                    usuario=self.usuario,
                    observacion="Seguimiento que debe revertirse.",
                    estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
                )

        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.estado, Incidente.Estado.PENDIENTE)
        self.assertFalse(SeguimientoIncidente.objects.exists())
