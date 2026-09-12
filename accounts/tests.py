from datetime import date, datetime
import json
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from incidents.models import Incidente

from .models import PerfilUsuario


class AutenticacionWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password_prueba = "ClaveSeguraPrueba-2026!"
        cls.usuario = User.objects.create_user(
            username="operador_web_prueba",
            password=cls.password_prueba,
            first_name="Jorge",
            last_name="Prueba",
        )

    def test_dashboard_exige_autenticacion(self):
        respuesta = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_usuario_valido_inicia_sesion(self):
        respuesta = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.username,
                "password": self.password_prueba,
            },
        )

        self.assertRedirects(respuesta, reverse("dashboard"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.usuario.pk,
        )

    def test_credenciales_incorrectas_no_autentican(self):
        respuesta = self.client.post(
            reverse("login"),
            {"username": self.usuario.username, "password": "incorrecta"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Usuario o contraseña incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_inactivo_no_inicia_sesion(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=("is_active",))

        respuesta = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.username,
                "password": self.password_prueba,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "cuenta inactiva")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_autenticado_ve_dashboard_y_rol(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Bienvenido, Jorge Prueba")
        self.assertContains(respuesta, "Rol: ")
        self.assertContains(respuesta, "Operador")

    def test_logout_post_elimina_sesion_y_redirige(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(reverse("logout"))

        self.assertRedirects(respuesta, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_get_no_cierra_sesion(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("logout"))

        self.assertEqual(respuesta.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_requiere_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)

        respuesta = cliente.post(reverse("logout"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("_auth_user_id", cliente.session)

    def test_login_redirige_si_ya_esta_autenticado(self):
        self.client.force_login(self.usuario)

        self.assertRedirects(
            self.client.get(reverse("login")),
            reverse("dashboard"),
        )

    def test_raiz_redirige_segun_autenticacion(self):
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("login"))

        self.client.force_login(self.usuario)
        self.assertRedirects(
            self.client.get(reverse("inicio")),
            reverse("dashboard"),
        )

    def test_menu_operador_muestra_solo_opciones_correspondientes(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("dashboard"))
        titulos = [opcion["titulo"] for opcion in respuesta.context["menu"]]

        self.assertEqual(titulos, ["Inicio", "Incidentes"])
        self.assertContains(respuesta, "Incidentes")
        self.assertNotContains(respuesta, "Operación")
        self.assertNotContains(respuesta, "Reportes")
        self.assertNotContains(respuesta, "Usuarios")

    def test_menu_administrador_muestra_opciones_correspondientes(self):
        perfil = self.usuario.perfil
        perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        perfil.save(update_fields=("rol",))
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("dashboard"))
        titulos = [opcion["titulo"] for opcion in respuesta.context["menu"]]

        self.assertEqual(
            titulos,
            ["Inicio", "Incidentes", "Operación", "Reportes", "Usuarios"],
        )
        for titulo in titulos:
            self.assertContains(respuesta, titulo)

    def test_password_no_aparece_en_html(self):
        respuesta_login = self.client.get(reverse("login"))
        self.assertNotContains(respuesta_login, self.password_prueba)

        self.client.force_login(self.usuario)
        respuesta_dashboard = self.client.get(reverse("dashboard"))
        self.assertNotContains(respuesta_dashboard, self.password_prueba)


class DashboardVacioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="dashboard_vacio")

    def test_dashboard_vacio_y_protegido(self):
        self.assertRedirects(
            self.client.get(reverse("dashboard")),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 0)
        self.assertEqual(respuesta.context["resumen"]["porcentaje_cerrados"], 0)
        self.assertContains(respuesta, "0%")
        self.assertContains(respuesta, "No hay datos disponibles")
        self.assertNotContains(respuesta, 'id="datos-incidentes-dia"')


class DashboardConDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="dashboard_datos",
            password="ClavePruebaDashboard!",
            first_name="Ana",
            last_name="Prueba",
            email="correo-privado@example.invalid",
        )
        cls.usuario.perfil.telefono = "5555-1234"
        cls.usuario.perfil.save(update_fields=("telefono",))
        cls.usuario.perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        cls.usuario.perfil.save(update_fields=("rol",))
        cls.incidentes = [
            cls.crear_incidente(
                dia=1,
                tipo="Tipo Uno",
                prioridad="Prioridad Uno",
                estado=Incidente.Estado.PENDIENTE,
            ),
            cls.crear_incidente(
                dia=2,
                tipo="Tipo Uno",
                prioridad="Prioridad Dos",
                estado=Incidente.Estado.EN_SEGUIMIENTO,
            ),
            cls.crear_incidente(
                dia=3,
                tipo="Tipo Dos",
                prioridad="Prioridad Uno",
                estado=Incidente.Estado.CERRADO,
            ),
        ]

    @classmethod
    def crear_incidente(cls, dia, tipo, prioridad, estado):
        return Incidente.objects.create(
            fecha_hora_reporte=timezone.make_aware(
                datetime(2026, 9, dia, 10, 0)
            ),
            ubicacion=f"Ubicación {dia}",
            tipo_incidente=tipo,
            prioridad=prioridad,
            descripcion="Descripción de prueba.",
            operador_responsable=cls.usuario,
            estado=estado,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_indicadores_usados_en_html_son_datos_reales(self):
        respuesta = self.client.get(reverse("dashboard"))
        resumen = respuesta.context["resumen"]

        self.assertEqual(resumen["total_incidentes"], 3)
        self.assertEqual(resumen["pendientes"], 1)
        self.assertEqual(resumen["en_seguimiento"], 1)
        self.assertEqual(resumen["cerrados"], 1)
        self.assertAlmostEqual(resumen["porcentaje_cerrados"], 100 / 3)
        self.assertContains(respuesta, "Total de incidentes")
        self.assertContains(respuesta, "33,3%")

    def test_indicadores_cambian_si_cambian_los_datos(self):
        anterior = self.client.get(reverse("dashboard"))
        self.crear_incidente(
            dia=4,
            tipo="Tipo Dos",
            prioridad="Prioridad Dos",
            estado=Incidente.Estado.CERRADO,
        )
        posterior = self.client.get(reverse("dashboard"))

        self.assertEqual(anterior.context["resumen"]["total_incidentes"], 3)
        self.assertEqual(posterior.context["resumen"]["total_incidentes"], 4)
        self.assertEqual(posterior.context["resumen"]["cerrados"], 2)

    def test_filtro_fecha_desde(self):
        respuesta = self.client.get(
            reverse("dashboard"), {"fecha_desde": "2026-09-02"}
        )

        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 2)
        self.assertEqual(len(respuesta.context["recientes"]), 2)
        self.assertEqual(len(respuesta.context["datos_grafica"]), 2)

    def test_filtro_fecha_hasta(self):
        respuesta = self.client.get(
            reverse("dashboard"), {"fecha_hasta": "2026-09-02"}
        )

        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 2)
        self.assertEqual(len(respuesta.context["recientes"]), 2)

    def test_filtro_rango_completo(self):
        respuesta = self.client.get(
            reverse("dashboard"),
            {"fecha_desde": "2026-09-02", "fecha_hasta": "2026-09-02"},
        )

        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 1)
        self.assertEqual(respuesta.context["tipos"][0]["tipo_incidente"], "Tipo Uno")
        self.assertEqual(respuesta.context["datos_grafica"][0]["fecha"], "2026-09-02")

    def test_rango_invalido_no_genera_error_500(self):
        respuesta = self.client.get(
            reverse("dashboard"),
            {"fecha_desde": "2026-09-03", "fecha_hasta": "2026-09-01"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La fecha inicial no puede ser posterior")
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 3)

    def test_fecha_malformada_no_genera_error_500(self):
        respuesta = self.client.get(
            reverse("dashboard"), {"fecha_desde": "no-es-fecha"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingrese fechas válidas")

    def test_recientes_tienen_maximo_diez_y_orden_descendente(self):
        for numero in range(4, 16):
            self.crear_incidente(
                dia=numero,
                tipo="Tipo Adicional",
                prioridad="Prioridad Adicional",
                estado=Incidente.Estado.PENDIENTE,
            )

        respuesta = self.client.get(reverse("dashboard"))
        recientes = list(respuesta.context["recientes"])

        self.assertEqual(len(recientes), 10)
        self.assertEqual(recientes[0].fecha_hora_reporte.date(), date(2026, 9, 15))
        self.assertEqual(recientes[-1].fecha_hora_reporte.date(), date(2026, 9, 6))
        self.assertEqual(
            [fila.fecha_hora_reporte for fila in recientes],
            sorted(
                (fila.fecha_hora_reporte for fila in recientes),
                reverse=True,
            ),
        )

    def test_resumen_por_tipo_y_prioridad(self):
        respuesta = self.client.get(reverse("dashboard"))

        self.assertEqual(respuesta.context["tipos"][0], {
            "tipo_incidente": "Tipo Uno", "cantidad": 2
        })
        self.assertEqual(respuesta.context["prioridades"][0], {
            "prioridad": "Prioridad Uno", "cantidad": 2
        })
        self.assertContains(respuesta, "Tipo Uno")
        self.assertContains(respuesta, "Prioridad Uno")

    def test_datos_diarios_se_serializan_para_grafica(self):
        respuesta = self.client.get(reverse("dashboard"))
        html = respuesta.content.decode()
        contenido_json = re.search(
            r'<script id="datos-incidentes-dia" type="application/json">(.*?)</script>',
            html,
        )

        self.assertIsNotNone(contenido_json)
        self.assertEqual(
            json.loads(contenido_json.group(1)),
            [
                {"fecha": "2026-09-01", "cantidad": 1},
                {"fecha": "2026-09-02", "cantidad": 1},
                {"fecha": "2026-09-03", "cantidad": 1},
            ],
        )

    def test_html_no_expone_informacion_sensible(self):
        respuesta = self.client.get(reverse("dashboard"))

        self.assertNotContains(respuesta, "ClavePruebaDashboard!")
        self.assertNotContains(respuesta, "correo-privado@example.invalid")
        self.assertNotContains(respuesta, "5555-1234")

    def test_operador_ve_resumen_y_recientes_sin_analisis(self):
        perfil = self.usuario.perfil
        perfil.rol = PerfilUsuario.Rol.OPERADOR
        perfil.save(update_fields=("rol",))

        respuesta = self.client.get(reverse("dashboard"))

        self.assertContains(respuesta, "Total de incidentes")
        self.assertContains(respuesta, "Incidentes recientes")
        self.assertNotContains(respuesta, 'id="incidentes-por-dia"')
