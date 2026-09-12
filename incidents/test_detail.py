import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from operations.models import InstitucionApoyo

from .models import (
    EvidenciaIncidente,
    Incidente,
    ParticipacionInstitucion,
    SeguimientoIncidente,
)
from .services import registrar_seguimiento


class DetalleIncidenteWebTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directorio_media = tempfile.mkdtemp()
        cls.configuracion_media = override_settings(MEDIA_ROOT=cls.directorio_media)
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
            username="operador_detalle",
            password="ClaveTemporal-Detalle2026!",
        )
        cls.otro_usuario = User.objects.create_user(username="otro_detalle")
        cls.fecha = timezone.make_aware(datetime(2026, 5, 10, 10, 0))
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=cls.fecha,
            ubicacion="Parque central",
            tipo_incidente="Accidente",
            prioridad="Urgente",
            descripcion="Descripción detallada del reporte.",
            operador_responsable=cls.usuario,
        )
        cls.otro_incidente = Incidente.objects.create(
            fecha_hora_reporte=cls.fecha,
            ubicacion="Otra ubicación",
            tipo_incidente="Otro tipo",
            prioridad="Normal",
            descripcion="Otro incidente.",
            operador_responsable=cls.otro_usuario,
        )

    def url(self, incidente=None):
        return reverse("incidents:detail", args=[
            (incidente or self.incidente).pk
        ])

    def cambiar_rol(self, rol):
        perfil = self.usuario.perfil
        perfil.rol = rol
        perfil.save(update_fields=("rol",))

    def datos_seguimiento(self, **extras):
        datos = {
            "accion": "seguimiento",
            "observacion": "Se inició la atención.",
            "estado_nuevo": Incidente.Estado.EN_SEGUIMIENTO,
        }
        datos.update(extras)
        return datos

    def datos_evidencia(self, nombre="foto.jpg", **extras):
        datos = {
            "accion": "evidencia",
            "archivo": SimpleUploadedFile(nombre, b"archivo de prueba"),
            "tipo": EvidenciaIncidente.Tipo.FOTO,
            "descripcion": "Fotografía del lugar",
            "fecha_hora": "2026-05-10T11:30",
        }
        datos.update(extras)
        return datos

    def test_detalle_requiere_autenticacion(self):
        respuesta = self.client.get(self.url())
        self.assertRedirects(
            respuesta, f"{reverse('login')}?next={self.url()}"
        )

    def test_incidente_inexistente_devuelve_404(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:detail", args=[999999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_autenticado_consulta_detalle_e_informacion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        self.assertEqual(respuesta.status_code, 200)
        for texto in (
            f"Incidente #{self.incidente.pk}",
            "Parque central",
            "Accidente",
            "Urgente",
            "Pendiente",
            "operador_detalle",
            "Descripción detallada del reporte.",
            "Fecha de creación",
            "Última actualización",
        ):
            self.assertContains(respuesta, texto)

    def test_todos_los_roles_consultan_detalle(self):
        self.client.force_login(self.usuario)
        for rol in PerfilUsuario.Rol.values:
            self.cambiar_rol(rol)
            self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_historial_muestra_seguimientos_en_orden_cronologico(self):
        SeguimientoIncidente.objects.create(
            incidente=self.incidente,
            usuario=self.usuario,
            fecha_hora=self.fecha + timedelta(hours=2),
            observacion="Segunda observación",
            estado_anterior=Incidente.Estado.EN_SEGUIMIENTO,
            estado_nuevo=Incidente.Estado.CERRADO,
        )
        SeguimientoIncidente.objects.create(
            incidente=self.incidente,
            usuario=self.otro_usuario,
            fecha_hora=self.fecha + timedelta(hours=1),
            observacion="Primera observación",
            estado_anterior=Incidente.Estado.PENDIENTE,
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        contenido = respuesta.content.decode()
        self.assertLess(
            contenido.index("Primera observación"),
            contenido.index("Segunda observación"),
        )
        self.assertContains(respuesta, "otro_detalle")
        self.assertContains(respuesta, "En seguimiento")

    def test_sin_seguimientos_muestra_estado_vacio(self):
        self.client.force_login(self.usuario)
        self.assertContains(
            self.client.get(self.url()), "No hay seguimientos registrados."
        )

    def test_operador_agrega_seguimiento_con_servicio(self):
        self.client.force_login(self.usuario)
        with patch(
            "incidents.views.registrar_seguimiento", wraps=registrar_seguimiento
        ) as servicio:
            respuesta = self.client.post(
                self.url(), self.datos_seguimiento(), follow=True
            )
        self.assertTrue(servicio.called)
        self.assertRedirects(respuesta, self.url())
        self.assertContains(
            respuesta, "Seguimiento registrado correctamente."
        )
        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.estado, Incidente.Estado.EN_SEGUIMIENTO)
        seguimiento = self.incidente.seguimientos.get()
        self.assertEqual(seguimiento.usuario, self.usuario)
        self.assertEqual(seguimiento.estado_anterior, Incidente.Estado.PENDIENTE)

    def test_coordinador_agrega_seguimiento(self):
        self.cambiar_rol(PerfilUsuario.Rol.COORDINADOR)
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.post(self.url(), self.datos_seguimiento()).status_code,
            302,
        )

    def test_administrador_agrega_seguimiento(self):
        self.cambiar_rol(PerfilUsuario.Rol.ADMINISTRADOR)
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.post(self.url(), self.datos_seguimiento()).status_code,
            302,
        )

    def test_consulta_y_auditor_no_agregan_seguimiento(self):
        self.client.force_login(self.usuario)
        for rol in (PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.cambiar_rol(rol)
            self.assertEqual(
                self.client.post(self.url(), self.datos_seguimiento()).status_code,
                403,
            )
            self.assertNotContains(self.client.get(self.url()), "Agregar seguimiento")
        self.assertFalse(SeguimientoIncidente.objects.exists())

    def test_post_no_falsifica_usuario_ni_incidente(self):
        self.client.force_login(self.usuario)
        self.client.post(
            self.url(),
            self.datos_seguimiento(
                usuario=self.otro_usuario.pk,
                incidente=self.otro_incidente.pk,
                estado_anterior=Incidente.Estado.CERRADO,
            ),
        )
        seguimiento = SeguimientoIncidente.objects.get()
        self.assertEqual(seguimiento.usuario, self.usuario)
        self.assertEqual(seguimiento.incidente, self.incidente)
        self.assertEqual(seguimiento.estado_anterior, Incidente.Estado.PENDIENTE)

    def test_formulario_ofrece_solo_transiciones_validas(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        opciones = dict(respuesta.context["formulario_seguimiento"].fields[
            "estado_nuevo"
        ].choices)
        self.assertEqual(
            set(opciones),
            {Incidente.Estado.EN_SEGUIMIENTO, Incidente.Estado.CERRADO},
        )

    def test_servicio_rechaza_transicion_y_muestra_error(self):
        self.client.force_login(self.usuario)
        with patch(
            "incidents.views.registrar_seguimiento",
            side_effect=ValidationError("Transición no permitida."),
        ):
            respuesta = self.client.post(self.url(), self.datos_seguimiento())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Transición no permitida.")
        self.assertFalse(SeguimientoIncidente.objects.exists())

    def test_incidente_cerrado_no_acepta_seguimiento(self):
        self.incidente.estado = Incidente.Estado.CERRADO
        self.incidente.save(update_fields=("estado",))
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, "Este incidente está cerrado")
        self.assertNotContains(respuesta, "Agregar seguimiento")
        self.assertEqual(
            self.client.post(self.url(), self.datos_seguimiento()).status_code,
            403,
        )
        self.assertFalse(SeguimientoIncidente.objects.exists())

    def test_evidencia_existente_aparece_en_detalle(self):
        evidencia = EvidenciaIncidente.objects.create(
            incidente=self.incidente,
            usuario=self.otro_usuario,
            archivo=SimpleUploadedFile("documento.pdf", b"archivo de prueba"),
            tipo=EvidenciaIncidente.Tipo.DOCUMENTO,
            descripcion="Documento de respaldo",
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, "Documento de respaldo")
        self.assertContains(respuesta, "otro_detalle")
        self.assertContains(respuesta, evidencia.archivo.url)

    def test_operador_carga_evidencia_y_asigna_relaciones(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            self.url(), self.datos_evidencia(), follow=True
        )
        self.assertRedirects(respuesta, self.url())
        self.assertContains(respuesta, "Evidencia registrada correctamente.")
        evidencia = EvidenciaIncidente.objects.get()
        self.assertEqual(evidencia.usuario, self.usuario)
        self.assertEqual(evidencia.incidente, self.incidente)
        self.assertTrue(evidencia.archivo.storage.exists(evidencia.archivo.name))

    def test_consulta_no_carga_evidencia(self):
        self.cambiar_rol(PerfilUsuario.Rol.CONSULTA)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(self.url(), self.datos_evidencia())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(EvidenciaIncidente.objects.exists())

    def test_post_evidencia_no_falsifica_usuario_ni_incidente(self):
        self.client.force_login(self.usuario)
        self.client.post(
            self.url(),
            self.datos_evidencia(
                usuario=self.otro_usuario.pk,
                incidente=self.otro_incidente.pk,
            ),
        )
        evidencia = EvidenciaIncidente.objects.get()
        self.assertEqual(evidencia.usuario, self.usuario)
        self.assertEqual(evidencia.incidente, self.incidente)

    def test_archivo_prohibido_se_rechaza_sin_error_500(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            self.url(), self.datos_evidencia("programa.exe")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no está permitida por seguridad")
        self.assertFalse(EvidenciaIncidente.objects.exists())

    def test_instituciones_participantes_aparecen(self):
        institucion = InstitucionApoyo.objects.create(
            nombre="Bomberos Municipales", siglas="BM"
        )
        ParticipacionInstitucion.objects.create(
            incidente=self.incidente,
            institucion=institucion,
            fecha_asignacion=self.fecha + timedelta(hours=1),
            observacion="Se solicitó apoyo.",
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, "Bomberos Municipales")
        self.assertContains(respuesta, "BM")
        self.assertContains(respuesta, "Se solicitó apoyo.")

    def test_enlace_desde_listado_abre_detalle_correcto(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertContains(respuesta, self.url())
        self.assertEqual(self.client.get(self.url()).context["incidente"], self.incidente)

    def test_html_no_expone_password_ni_ruta_fisica(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url())
        self.assertNotContains(respuesta, "ClaveTemporal-Detalle2026!")
        self.assertNotContains(respuesta, self.directorio_media)
        self.assertNotContains(respuesta, 'name="usuario"')
        self.assertNotContains(respuesta, 'name="incidente"')

    def test_post_requiere_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(
            cliente.post(self.url(), self.datos_seguimiento()).status_code,
            403,
        )
