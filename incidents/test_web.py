from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario

from .models import Incidente


class IncidentesWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="operador_web_incidentes",
            password="TemporalPrueba-2026!",
        )
        cls.otro_usuario = User.objects.create_user(username="otro_operador")
        cls.fecha_base = timezone.make_aware(datetime(2026, 5, 10, 10, 0))
        cls.antiguo = cls.crear_incidente(
            fecha_hora_reporte=cls.fecha_base,
            ubicacion="Parque central",
            tipo_incidente="Accidente",
            prioridad="Urgente",
            descripcion="Colisión en la vía.",
            estado=Incidente.Estado.CERRADO,
        )
        cls.reciente = cls.crear_incidente(
            fecha_hora_reporte=cls.fecha_base + timedelta(days=2),
            ubicacion="Barrio El Centro",
            tipo_incidente="Incendio",
            prioridad="Normal",
            descripcion="Humo en una vivienda.",
            estado=Incidente.Estado.PENDIENTE,
        )

    @classmethod
    def crear_incidente(cls, **campos):
        datos = {
            "fecha_hora_reporte": cls.fecha_base,
            "ubicacion": "Ubicación de prueba",
            "tipo_incidente": "Tipo de prueba",
            "prioridad": "Prioridad de prueba",
            "descripcion": "Descripción de prueba",
            "operador_responsable": cls.usuario,
        }
        datos.update(campos)
        return Incidente.objects.create(**datos)

    def cambiar_rol(self, rol):
        perfil = self.usuario.perfil
        perfil.rol = rol
        perfil.save(update_fields=("rol",))

    def datos_registro(self, **extras):
        datos = {
            "fecha_hora_reporte": "2026-05-15T14:30",
            "ubicacion": "Zona municipal",
            "tipo_incidente": "Aviso ciudadano",
            "prioridad": "Por evaluar",
            "descripcion": "Reporte recibido por operador.",
        }
        datos.update(extras)
        return datos

    def test_anonimo_no_accede_al_listado(self):
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('incidents:list')}",
        )

    def test_anonimo_no_accede_al_registro(self):
        respuesta = self.client.get(reverse("incidents:create"))
        self.assertEqual(respuesta.status_code, 302)

    def test_autenticado_accede_al_listado(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Parque central")

    def test_operador_abre_formulario(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:create"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Información general")
        self.assertContains(respuesta, "Asignación")
        self.assertNotContains(respuesta, 'name="operador_responsable"')
        self.assertNotContains(respuesta, 'name="estado"')

    def test_administrador_registra(self):
        self.cambiar_rol(PerfilUsuario.Rol.ADMINISTRADOR)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("incidents:create"), self.datos_registro(), follow=True
        )
        self.assertRedirects(respuesta, reverse("incidents:list"))
        self.assertContains(respuesta, "Incidente registrado correctamente.")

    def test_coordinador_registra(self):
        self.cambiar_rol(PerfilUsuario.Rol.COORDINADOR)
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("incidents:create"), self.datos_registro()
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Incidente.objects.filter(ubicacion="Zona municipal").exists())

    def test_consulta_recibe_403_en_get_y_post(self):
        self.cambiar_rol(PerfilUsuario.Rol.CONSULTA)
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.get(reverse("incidents:create")).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("incidents:create"), self.datos_registro()
            ).status_code,
            403,
        )
        self.assertFalse(Incidente.objects.filter(ubicacion="Zona municipal").exists())

    def test_auditor_recibe_403(self):
        self.cambiar_rol(PerfilUsuario.Rol.AUDITOR)
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.get(reverse("incidents:create")).status_code, 403
        )

    def test_creacion_asigna_usuario_y_estado_pendiente(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("incidents:create"), self.datos_registro())
        incidente = Incidente.objects.get(ubicacion="Zona municipal")
        self.assertEqual(incidente.operador_responsable, self.usuario)
        self.assertEqual(incidente.estado, Incidente.Estado.PENDIENTE)
        self.assertIsNotNone(incidente.fecha_creacion)

    def test_post_manipulado_no_cambia_operador_ni_estado(self):
        self.client.force_login(self.usuario)
        self.client.post(
            reverse("incidents:create"),
            self.datos_registro(
                operador_responsable=self.otro_usuario.pk,
                estado=Incidente.Estado.CERRADO,
            ),
        )
        incidente = Incidente.objects.get(ubicacion="Zona municipal")
        self.assertEqual(incidente.operador_responsable, self.usuario)
        self.assertEqual(incidente.estado, Incidente.Estado.PENDIENTE)

    def test_registro_requiere_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(
            reverse("incidents:create"), self.datos_registro()
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_listado_ordenado_del_mas_reciente(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertEqual(
            [obj.pk for obj in respuesta.context["pagina"].object_list],
            [self.reciente.pk, self.antiguo.pk],
        )

    def test_busqueda_por_ubicacion(self):
        self.verificar_filtro("busqueda", "Parque", self.antiguo)

    def test_busqueda_por_descripcion(self):
        self.verificar_filtro("busqueda", "Humo", self.reciente)

    def test_busqueda_por_tipo(self):
        self.verificar_filtro("busqueda", "Incendio", self.reciente)

    def test_filtro_por_estado(self):
        self.verificar_filtro("estado", Incidente.Estado.CERRADO, self.antiguo)

    def test_filtro_por_tipo(self):
        self.verificar_filtro("tipo", "Incendio", self.reciente)

    def test_filtro_por_prioridad(self):
        self.verificar_filtro("prioridad", "Urgente", self.antiguo)

    def test_filtro_fecha_desde(self):
        self.verificar_filtro("fecha_desde", "2026-05-11", self.reciente)

    def test_filtro_fecha_hasta(self):
        self.verificar_filtro("fecha_hasta", "2026-05-11", self.antiguo)

    def verificar_filtro(self, nombre, valor, esperado):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"), {nombre: valor})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            [obj.pk for obj in respuesta.context["pagina"].object_list],
            [esperado.pk],
        )

    def test_rango_invalido_no_falla(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("incidents:list"),
            {"fecha_desde": "2026-05-20", "fecha_hasta": "2026-05-01"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta, "La fecha inicial no puede ser posterior a la fecha final."
        )

    def test_paginacion_limitada_a_20_y_conserva_filtros(self):
        for numero in range(21):
            self.crear_incidente(
                fecha_hora_reporte=self.fecha_base + timedelta(minutes=numero),
                tipo_incidente="Accidente",
            )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(
            reverse("incidents:list"), {"tipo": "Accidente"}
        )
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertContains(respuesta, "tipo=Accidente&amp;page=2")

    def test_boton_registro_no_aparece_para_consulta(self):
        self.cambiar_rol(PerfilUsuario.Rol.CONSULTA)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertNotContains(respuesta, "Registrar incidente")

    def test_html_no_expone_password_ni_datos_sensibles(self):
        self.client.force_login(self.usuario)
        for url in (reverse("incidents:list"), reverse("incidents:create")):
            respuesta = self.client.get(url)
            self.assertNotContains(respuesta, "TemporalPrueba-2026!")
            self.assertNotContains(respuesta, 'name="password"')

    def test_listado_vacio(self):
        Incidente.objects.all().delete()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("incidents:list"))
        self.assertContains(respuesta, "No hay incidentes registrados.")
