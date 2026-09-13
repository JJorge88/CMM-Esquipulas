from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditoriaAccion, PerfilUsuario
from operations.models import RecursoInstitucional, TipoRecurso

from .forms import IncidenteForm
from .models import Incidente
from .services import registrar_seguimiento


class CamaraOrigenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin_camaras", password="Temporal-Camaras2026!"
        )
        cls.admin.perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        cls.admin.perfil.save(update_fields=("rol",))
        cls.tipo_camara = TipoRecurso.objects.create(
            nombre="Videovigilancia", es_camara=True
        )
        cls.tipo_otro = TipoRecurso.objects.create(nombre="Radio")
        cls.tipo_inactivo = TipoRecurso.objects.create(
            nombre="Videovigilancia inactiva", es_camara=True, activo=False
        )
        cls.disponible = cls.recurso("PTZ Parque", cls.tipo_camara, "CAM-01")
        cls.en_uso = cls.recurso(
            "PTZ Mercado", cls.tipo_camara, "CAM-02",
            estado=RecursoInstitucional.Estado.EN_USO,
        )
        cls.no_camara = cls.recurso("Radio central", cls.tipo_otro, "RAD-01")
        cls.inactiva = cls.recurso(
            "PTZ apagada", cls.tipo_camara, "CAM-03", activo=False
        )
        cls.tipo_desactivado = cls.recurso(
            "PTZ anterior", cls.tipo_inactivo, "CAM-04"
        )
        cls.mantenimiento = cls.recurso(
            "PTZ reparación", cls.tipo_camara, "CAM-05",
            estado=RecursoInstitucional.Estado.MANTENIMIENTO,
        )
        cls.fuera_servicio = cls.recurso(
            "PTZ averiada", cls.tipo_camara, "CAM-06",
            estado=RecursoInstitucional.Estado.FUERA_DE_SERVICIO,
        )

    @classmethod
    def recurso(cls, nombre, tipo, codigo, **extras):
        return RecursoInstitucional.objects.create(
            nombre=nombre, tipo=tipo, codigo_interno=codigo,
            ubicacion="Sector municipal", **extras,
        )

    def datos_incidente(self, **extras):
        datos = {
            "fecha_hora_reporte": "2026-09-12T14:30",
            "ubicacion": "Parque central",
            "tipo_incidente": "Aviso",
            "prioridad": "Por evaluar",
            "descripcion": "Reporte recibido.",
        }
        datos.update(extras)
        return datos

    def crear_incidente(self, camara=None):
        return Incidente.objects.create(
            fecha_hora_reporte=timezone.make_aware(datetime(2026, 9, 12, 14, 30)),
            ubicacion="Parque central", tipo_incidente="Aviso",
            prioridad="Por evaluar", descripcion="Reporte recibido.",
            operador_responsable=self.admin, camara_origen=camara,
        )

    def test_tipo_no_es_camara_por_defecto(self):
        tipo = TipoRecurso.objects.create(nombre="Nuevo tipo")
        self.assertFalse(tipo.es_camara)

    def test_administrador_marca_tipo_y_crea_recurso_de_camara(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("operations:resource_type_create"), {
            "nombre": "Videovigilancia móvil", "descripcion": "", "activo": "on",
            "es_camara": "on",
        })
        self.assertEqual(respuesta.status_code, 302)
        tipo = TipoRecurso.objects.get(nombre="Videovigilancia móvil")
        self.assertTrue(tipo.es_camara)
        respuesta = self.client.post(reverse("operations:resource_create"), {
            "nombre": "PTZ móvil", "tipo": tipo.pk,
            "codigo_interno": "CAM-MOV", "marca": "", "modelo": "",
            "numero_serie": "", "ubicacion": "Unidad móvil",
            "descripcion": "", "estado": RecursoInstitucional.Estado.DISPONIBLE,
            "activo": "on",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(RecursoInstitucional.objects.filter(
            nombre="PTZ móvil", tipo=tipo
        ).exists())

    def test_formulario_solo_ofrece_camaras_operativas(self):
        formulario = IncidenteForm()
        ids = set(formulario.fields["camara_origen"].queryset.values_list(
            "pk", flat=True
        ))
        self.assertEqual(ids, {self.disponible.pk, self.en_uso.pk})
        self.assertFalse(formulario.fields["camara_origen"].required)
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("incidents:create"))
        self.assertContains(respuesta, "Cámara de origen (opcional)")
        self.assertContains(respuesta, "PTZ Parque")
        self.assertContains(respuesta, "PTZ Mercado")
        for nombre in (
            "Radio central", "PTZ apagada", "PTZ anterior",
            "PTZ reparación", "PTZ averiada",
        ):
            self.assertNotContains(respuesta, nombre)

    def test_creacion_sin_camara_sigue_valida(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("incidents:create"), self.datos_incidente()
        )
        incidente = Incidente.objects.get(ubicacion="Parque central")
        self.assertRedirects(respuesta, reverse("incidents:detail", args=[incidente.pk]))
        self.assertIsNone(incidente.camara_origen)

    def test_creacion_con_camara_guarda_relacion_y_auditoria(self):
        self.client.force_login(self.admin)
        self.disponible.numero_serie = "SERIE-PRIVADA-123"
        self.disponible.save(update_fields=("numero_serie",))
        respuesta = self.client.post(
            reverse("incidents:create"),
            self.datos_incidente(camara_origen=self.disponible.pk),
        )
        incidente = Incidente.objects.get(ubicacion="Parque central")
        self.assertRedirects(respuesta, reverse("incidents:detail", args=[incidente.pk]))
        self.assertEqual(incidente.camara_origen, self.disponible)
        auditoria = AuditoriaAccion.objects.get(
            modulo="INCIDENTES", accion="CREAR", entidad_id=str(incidente.pk)
        )
        self.assertIn("PTZ Parque", auditoria.descripcion)
        self.assertNotIn("SERIE-PRIVADA-123", auditoria.descripcion)
        detalle = self.client.get(reverse("incidents:detail", args=[incidente.pk]))
        self.assertNotContains(detalle, "SERIE-PRIVADA-123")

    def test_post_manipulado_rechaza_recursos_no_permitidos(self):
        self.client.force_login(self.admin)
        for recurso in (
            self.no_camara, self.inactiva, self.tipo_desactivado,
            self.mantenimiento, self.fuera_servicio,
        ):
            with self.subTest(recurso=recurso.nombre):
                respuesta = self.client.post(
                    reverse("incidents:create"),
                    self.datos_incidente(camara_origen=recurso.pk),
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("camara_origen", respuesta.context["formulario"].errors)
                self.assertEqual(Incidente.objects.count(), 0)
                self.assertEqual(AuditoriaAccion.objects.count(), 0)

    def test_modelo_rechaza_camara_no_valida_directamente(self):
        for recurso in (
            self.no_camara, self.inactiva, self.tipo_desactivado,
            self.mantenimiento, self.fuera_servicio,
        ):
            with self.subTest(recurso=recurso.nombre):
                with self.assertRaises(ValidationError):
                    self.crear_incidente(recurso)

    def test_camara_historica_no_impide_seguimiento(self):
        incidente = self.crear_incidente(self.disponible)
        self.disponible.estado = RecursoInstitucional.Estado.FUERA_DE_SERVICIO
        self.disponible.activo = False
        self.disponible.save(update_fields=("estado", "activo"))
        incidente.full_clean()
        seguimiento = registrar_seguimiento(
            incidente=incidente, usuario=self.admin, observacion="Atención iniciada",
            estado_nuevo=Incidente.Estado.PENDIENTE,
        )
        self.assertEqual(seguimiento.incidente.camara_origen_id, self.disponible.pk)

    def test_protect_impide_eliminar_camara_relacionada(self):
        self.crear_incidente(self.disponible)
        with self.assertRaises(ProtectedError):
            self.disponible.delete()

    def test_detalle_muestra_camara_y_estado_actual(self):
        incidente = self.crear_incidente(self.disponible)
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("incidents:detail", args=[incidente.pk]))
        for texto in (
            "PTZ Parque", "CAM-01", "Sector municipal", "Estado actual",
            "El estado actual puede diferir",
        ):
            self.assertContains(respuesta, texto)

    def test_detalle_sin_camara_lo_indica(self):
        incidente = self.crear_incidente()
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("incidents:detail", args=[incidente.pk]))
        self.assertContains(respuesta, "Sin cámara asociada")

    def test_listado_filtra_camara_y_la_muestra_bajo_ubicacion(self):
        con_camara = self.crear_incidente(self.disponible)
        self.crear_incidente(self.en_uso)
        self.crear_incidente()
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("incidents:list"), {
            "camara": self.disponible.pk,
        })
        self.assertEqual(
            [obj.pk for obj in respuesta.context["pagina"].object_list],
            [con_camara.pk],
        )
        self.assertContains(respuesta, "Cámara: PTZ Parque")
