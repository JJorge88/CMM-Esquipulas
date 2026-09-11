import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import EvidenciaIncidente, Incidente, SeguimientoIncidente
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


class EvidenciaIncidenteTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directorio_media = tempfile.mkdtemp()
        cls.configuracion_media = override_settings(
            MEDIA_ROOT=cls.directorio_media
        )
        cls.configuracion_media.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.configuracion_media.disable()
        shutil.rmtree(cls.directorio_media, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="usuario_evidencia_prueba"
        )
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=timezone.now(),
            ubicacion="Ubicación de evidencia de prueba",
            tipo_incidente="Tipo de prueba",
            prioridad="Prioridad de prueba",
            descripcion="Incidente utilizado para probar evidencias.",
            operador_responsable=cls.usuario,
        )

    def crear_evidencia(self, tipo, nombre_archivo):
        return EvidenciaIncidente.objects.create(
            incidente=self.incidente,
            archivo=SimpleUploadedFile(
                nombre_archivo,
                b"contenido temporal de prueba",
            ),
            tipo=tipo,
            usuario=self.usuario,
        )

    def test_crear_fotografia_jpg_valida(self):
        evidencia = self.crear_evidencia(
            EvidenciaIncidente.Tipo.FOTO,
            "fotografia.jpg",
        )

        self.assertTrue(evidencia.archivo.storage.exists(evidencia.archivo.name))
        self.assertTrue(
            evidencia.archivo.name.startswith(
                f"evidencias/incidentes/{self.incidente.pk}/"
            )
        )
        self.assertTrue(evidencia.archivo.name.endswith(".jpg"))

    def test_crear_video_mp4_valido(self):
        evidencia = self.crear_evidencia(
            EvidenciaIncidente.Tipo.VIDEO,
            "video.mp4",
        )

        self.assertEqual(evidencia.tipo, EvidenciaIncidente.Tipo.VIDEO)
        self.assertTrue(evidencia.archivo.storage.exists(evidencia.archivo.name))

    def test_rechazar_fotografia_con_extension_ejecutable(self):
        with self.assertRaisesMessage(
            ValidationError,
            "no está permitida por seguridad",
        ):
            self.crear_evidencia(
                EvidenciaIncidente.Tipo.FOTO,
                "archivo.exe",
            )

        self.assertFalse(EvidenciaIncidente.objects.exists())

    def test_rechazar_video_con_extension_de_fotografia(self):
        with self.assertRaisesMessage(
            ValidationError,
            "no corresponde al tipo VIDEO",
        ):
            self.crear_evidencia(
                EvidenciaIncidente.Tipo.VIDEO,
                "fotografia.jpg",
            )

        self.assertFalse(EvidenciaIncidente.objects.exists())

    def test_relacion_inversa_del_incidente(self):
        evidencia = self.crear_evidencia(
            EvidenciaIncidente.Tipo.DOCUMENTO,
            "documento.pdf",
        )

        self.assertQuerySetEqual(
            self.incidente.evidencias.all(),
            [evidencia],
        )

    def test_asociacion_del_usuario(self):
        evidencia = self.crear_evidencia(
            EvidenciaIncidente.Tipo.OTRO,
            "registro.txt",
        )

        self.assertEqual(evidencia.usuario, self.usuario)

    def test_eliminar_incidente_elimina_registro_de_evidencia(self):
        evidencia = self.crear_evidencia(
            EvidenciaIncidente.Tipo.FOTO,
            "fotografia.jpg",
        )
        evidencia_id = evidencia.pk

        self.incidente.delete()

        self.assertFalse(
            EvidenciaIncidente.objects.filter(pk=evidencia_id).exists()
        )
