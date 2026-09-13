from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from incidents.models import Incidente, ParticipacionInstitucion

from .models import InstitucionApoyo, RecursoInstitucional, TipoRecurso
from .services import incidentes_activos, tiempo_transcurrido


class PanelIncidentesActivosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("operations:active_incidents")
        cls.usuarios = {}
        for rol in PerfilUsuario.Rol:
            usuario = User.objects.create_user(username=f"panel_{rol.value.lower()}")
            usuario.perfil.rol = rol
            usuario.perfil.save(update_fields=("rol",))
            cls.usuarios[rol] = usuario
        cls.operador = cls.usuarios[PerfilUsuario.Rol.OPERADOR]
        cls.otro_operador = User.objects.create_user(username="panel_otro")
        cls.tipo_camara = TipoRecurso.objects.create(
            nombre="Videovigilancia panel", es_camara=True
        )
        cls.camara = RecursoInstitucional.objects.create(
            nombre="PTZ Central", tipo=cls.tipo_camara,
            ubicacion="Azotea municipal",
        )
        cls.institucion = InstitucionApoyo.objects.create(
            nombre="Bomberos panel", telefono="5555-5555",
            correo_electronico="privado@example.com",
        )
        cls.otra_institucion = InstitucionApoyo.objects.create(
            nombre="Tránsito panel"
        )
        base = timezone.now().replace(second=0, microsecond=0)
        cls.registrado_viejo = cls.crear(
            estado=Incidente.Estado.REGISTRADO,
            fecha_hora_reporte=base - timedelta(hours=3),
            tipo_incidente="Choque", prioridad="Urgente",
            ubicacion="Parque Central", descripcion="Vehículo detenido",
            camara_origen=cls.camara,
        )
        cls.registrado_nuevo = cls.crear(
            estado=Incidente.Estado.REGISTRADO,
            fecha_hora_reporte=base - timedelta(minutes=5),
            tipo_incidente="Alerta", prioridad="Normal",
            ubicacion="Mercado", descripcion="Aviso de prueba",
        )
        cls.pendiente = cls.crear(
            estado=Incidente.Estado.PENDIENTE,
            fecha_hora_reporte=base - timedelta(hours=2),
            tipo_incidente="Incendio", prioridad="Urgente",
            ubicacion="Barrio Norte", descripcion="Humo visible",
            operador_responsable=cls.otro_operador,
        )
        cls.seguimiento = cls.crear(
            estado=Incidente.Estado.EN_SEGUIMIENTO,
            fecha_hora_reporte=base - timedelta(hours=1),
            tipo_incidente="Caída", prioridad="Normal",
            ubicacion="Colonia Sur", descripcion="Persona asistida",
        )
        cls.resuelto = cls.crear(
            estado=Incidente.Estado.RESUELTO,
            fecha_hora_reporte=base - timedelta(days=1),
            tipo_incidente="Resuelto", prioridad="Urgente",
            ubicacion="Sitio resuelto", descripcion="Finalizado",
        )
        cls.cerrado = cls.crear(
            estado=Incidente.Estado.CERRADO,
            fecha_hora_reporte=base - timedelta(days=2),
            tipo_incidente="Cerrado", prioridad="Normal",
            ubicacion="Sitio cerrado", descripcion="Archivado",
            resultado_cierre="Atendido",
        )
        ParticipacionInstitucion.objects.create(
            incidente=cls.registrado_viejo, institucion=cls.institucion
        )
        ParticipacionInstitucion.objects.create(
            incidente=cls.pendiente, institucion=cls.otra_institucion
        )

    @classmethod
    def crear(cls, **cambios):
        datos = {
            "fecha_hora_reporte": timezone.now(),
            "tipo_incidente": "Aviso", "prioridad": "Normal",
            "ubicacion": "Punto de prueba", "descripcion": "Descripción",
            "operador_responsable": cls.operador,
        }
        return Incidente.objects.create(**{**datos, **cambios})

    def entrar(self, rol=PerfilUsuario.Rol.OPERADOR):
        self.client.force_login(self.usuarios[rol])

    def ids(self, parametros=None):
        respuesta = self.client.get(self.url, parametros or {})
        return respuesta, [incidente.pk for incidente in respuesta.context["pagina"]]

    def test_anonimo_no_accede(self):
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_roles_autorizados_pueden_consultar(self):
        for rol in PerfilUsuario.Rol:
            with self.subTest(rol=rol):
                self.entrar(rol)
                self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_usuario_sin_perfil_no_accede(self):
        usuario = User.objects.create_user(username="panel_sin_perfil")
        usuario.perfil.delete()
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_solo_estados_activos_y_total(self):
        self.entrar()
        respuesta, ids = self.ids()
        self.assertEqual(set(ids), {
            self.registrado_viejo.pk, self.registrado_nuevo.pk,
            self.pendiente.pk, self.seguimiento.pk,
        })
        self.assertNotIn(self.resuelto.pk, ids)
        self.assertNotIn(self.cerrado.pk, ids)
        self.assertEqual(respuesta.context["conteos"], {
            "total": 4, "registrados": 2, "pendientes": 1,
            "en_seguimiento": 1,
        })
        self.assertEqual(incidentes_activos().count(), 4)

    def test_orden_por_estado_y_antiguedad(self):
        self.entrar()
        _, ids = self.ids()
        self.assertEqual(ids, [
            self.registrado_viejo.pk, self.registrado_nuevo.pk,
            self.pendiente.pk, self.seguimiento.pk,
        ])

    def test_tiempo_transcurrido_humano(self):
        ahora = timezone.now()
        self.assertEqual(tiempo_transcurrido(ahora - timedelta(minutes=5), ahora), "5 min")
        self.assertEqual(tiempo_transcurrido(ahora - timedelta(hours=1, minutes=12), ahora), "1 h 12 min")
        self.entrar()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Tiempo transcurrido")
        self.assertContains(respuesta, "h 0 min")

    def test_camara_opcional_y_ubicacion(self):
        self.entrar()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "PTZ Central")
        self.assertContains(respuesta, "Azotea municipal")
        self.assertContains(respuesta, "Parque Central")
        self.assertContains(respuesta, "Mercado")
        self.assertEqual(
            respuesta.context["pagina"].object_list[1].camara_origen_id, None
        )

    def test_instituciones_y_enlace_al_detalle(self):
        self.entrar()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Bomberos panel")
        self.assertContains(respuesta, reverse("incidents:detail", args=[self.registrado_viejo.pk]))
        self.assertContains(respuesta, "Ver incidente")

    def test_filtro_estado(self):
        self.entrar()
        _, ids = self.ids({"estado": Incidente.Estado.PENDIENTE})
        self.assertEqual(ids, [self.pendiente.pk])

    def test_estado_no_activo_es_invalido(self):
        self.entrar()
        respuesta = self.client.get(self.url, {"estado": Incidente.Estado.CERRADO})
        self.assertIn("estado", respuesta.context["filtros"].errors)

    def test_filtro_tipo(self):
        self.entrar()
        _, ids = self.ids({"tipo": "Incendio"})
        self.assertEqual(ids, [self.pendiente.pk])

    def test_filtro_prioridad(self):
        self.entrar()
        _, ids = self.ids({"prioridad": "Urgente"})
        self.assertEqual(ids, [self.registrado_viejo.pk, self.pendiente.pk])

    def test_filtro_operador(self):
        self.entrar()
        _, ids = self.ids({"operador": self.otro_operador.pk})
        self.assertEqual(ids, [self.pendiente.pk])

    def test_filtro_institucion(self):
        self.entrar()
        _, ids = self.ids({"institucion": self.institucion.pk})
        self.assertEqual(ids, [self.registrado_viejo.pk])

    def test_filtro_camara(self):
        self.entrar()
        _, ids = self.ids({"camara": self.camara.pk})
        self.assertEqual(ids, [self.registrado_viejo.pk])

    def test_busqueda_ubicacion_descripcion_e_id(self):
        self.entrar()
        for termino, esperado in (
            ("Parque Central", self.registrado_viejo.pk),
            ("Humo visible", self.pendiente.pk),
            (str(self.seguimiento.pk), self.seguimiento.pk),
        ):
            with self.subTest(termino=termino):
                _, ids = self.ids({"busqueda": termino})
                self.assertEqual(ids, [esperado])

    def test_filtros_solo_contienen_datos_activos(self):
        self.entrar()
        formulario = self.client.get(self.url).context["filtros"]
        self.assertNotIn("Resuelto", [valor for valor, _ in formulario.fields["tipo"].choices])
        self.assertNotIn("Cerrado", [valor for valor, _ in formulario.fields["tipo"].choices])

    def test_no_muestra_datos_sensibles_ni_acciones_nuevas(self):
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, "privado@example.com")
        self.assertNotContains(respuesta, "5555-5555")
        self.assertNotContains(respuesta, "Guardar seguimiento")
        self.assertNotContains(respuesta, "Asignar institución")

    def test_navegacion_en_escritorio_y_movil(self):
        self.entrar()
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, self.url, count=2)

    def test_consultas_acotadas_sin_n_mas_uno(self):
        self.entrar()
        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url)
        self.assertLessEqual(len(consultas), 16)
        self.assertEqual(sum(
            'FROM "incidents_participacioninstitucion"' in consulta["sql"]
            for consulta in consultas
        ), 1)
