from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from incidents.models import Incidente, ParticipacionInstitucion

from .models import InstitucionApoyo


class InstitucionesVisualesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {}
        for rol in PerfilUsuario.Rol:
            usuario = User.objects.create_user(
                username=rol.value.lower(), password="ClaveTemporal!123"
            )
            usuario.perfil.rol = rol
            usuario.perfil.save(update_fields=("rol",))
            cls.usuarios[rol] = usuario
        cls.institucion = InstitucionApoyo.objects.create(
            nombre="Bomberos Voluntarios", siglas="BV", telefono="12345678"
        )
        cls.inactiva = InstitucionApoyo.objects.create(
            nombre="Institución inactiva", activa=False
        )
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=timezone.now(), ubicacion="Centro",
            tipo_incidente="Emergencia", prioridad="Alta",
            descripcion="Descripción", operador_responsable=cls.usuarios[PerfilUsuario.Rol.OPERADOR],
        )
        cls.otro_incidente = Incidente.objects.create(
            fecha_hora_reporte=timezone.now(), ubicacion="Norte",
            tipo_incidente="Emergencia", prioridad="Alta",
            descripcion="Otro", operador_responsable=cls.usuarios[PerfilUsuario.Rol.OPERADOR],
        )

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def datos_institucion(self, **cambios):
        return {**{
            "nombre": "Policía Municipal", "siglas": "PM",
            "telefono": "55550000", "correo_electronico": "apoyo@example.com",
            "direccion": "Centro", "activa": "on",
        }, **cambios}

    def datos_participacion(self, **cambios):
        return {**{
            "accion": "institucion", "institucion": self.institucion.pk,
            "observacion": "Acudió al lugar",
            "fecha_asignacion": "2026-09-12T14:30",
        }, **cambios}

    def detalle(self, incidente=None):
        return reverse("incidents:detail", args=[(incidente or self.incidente).pk])

    def test_a_login_obligatorio(self):
        for nombre in ("institution_list", "institution_create"):
            self.assertEqual(self.client.get(reverse(f"operations:{nombre}")).status_code, 302)
        self.assertEqual(self.client.post(self.detalle(), self.datos_participacion()).status_code, 302)

    def test_b_c_d_e_f_todos_los_roles_consultan(self):
        for rol in PerfilUsuario.Rol:
            self.entrar(rol)
            respuesta = self.client.get(reverse("operations:institution_list"))
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "Bomberos Voluntarios")

    def test_g_h_administrador_y_coordinador_crean(self):
        for indice, rol in enumerate((PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR)):
            self.entrar(rol)
            respuesta = self.client.post(
                reverse("operations:institution_create"),
                self.datos_institucion(nombre=f"Institución {indice}"),
            )
            self.assertRedirects(respuesta, reverse("operations:institution_list"))
        self.assertEqual(InstitucionApoyo.objects.count(), 4)

    def test_i_j_k_roles_lectura_no_crean(self):
        for rol in (PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.entrar(rol)
            self.assertEqual(
                self.client.post(reverse("operations:institution_create"), self.datos_institucion()).status_code,
                403,
            )

    def test_l_nombre_duplicado_rechazado(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:institution_create"),
            self.datos_institucion(nombre=self.institucion.nombre),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["formulario"].errors)
        self.assertEqual(InstitucionApoyo.objects.count(), 2)

    def test_correo_invalido_y_campos_opcionales(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        url = reverse("operations:institution_create")
        respuesta = self.client.post(url, self.datos_institucion(correo_electronico="incorrecto"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("correo_electronico", respuesta.context["formulario"].errors)
        respuesta = self.client.post(url, self.datos_institucion(
            nombre="Sin contacto", siglas="", telefono="", correo_electronico="", direccion=""
        ))
        self.assertRedirects(respuesta, reverse("operations:institution_list"))

    def test_m_n_gestores_editan(self):
        for rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR):
            self.entrar(rol)
            respuesta = self.client.post(
                reverse("operations:institution_update", args=[self.institucion.pk]),
                self.datos_institucion(nombre=f"Editada {rol.value}"),
            )
            self.assertRedirects(respuesta, reverse("operations:institution_list"))
        self.institucion.refresh_from_db()
        self.assertEqual(self.institucion.nombre, "Editada COORDINADOR")

    def test_o_estado_solo_administrador_y_post(self):
        url = reverse("operations:institution_toggle_status", args=[self.institucion.pk])
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("operations:institution_list"))
        self.institucion.refresh_from_db()
        self.assertFalse(self.institucion.activa)
        self.client.post(url)
        self.institucion.refresh_from_db()
        self.assertTrue(self.institucion.activa)
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_coordinador_no_cambia_estado_con_post_manipulado(self):
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        datos = self.datos_institucion(nombre=self.institucion.nombre)
        datos.pop("activa")
        respuesta = self.client.post(
            reverse("operations:institution_update", args=[self.institucion.pk]), datos
        )
        self.assertRedirects(respuesta, reverse("operations:institution_list"))
        self.institucion.refresh_from_db()
        self.assertTrue(self.institucion.activa)

    def test_p_no_hay_ruta_de_eliminacion(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.get(reverse("operations:institution_list"))
        self.assertNotContains(respuesta, "Eliminar")
        self.assertTrue(InstitucionApoyo.objects.filter(pk=self.institucion.pk).exists())

    def test_q_r_s_gestores_y_operador_asignan(self):
        instituciones = (
            self.institucion,
            InstitucionApoyo.objects.create(nombre="Policía"),
            InstitucionApoyo.objects.create(nombre="Bomberos Municipales"),
        )
        for rol, institucion in zip(
            (PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.COORDINADOR, PerfilUsuario.Rol.ADMINISTRADOR),
            instituciones,
        ):
            self.entrar(rol)
            respuesta = self.client.post(
                self.detalle(), self.datos_participacion(institucion=institucion.pk)
            )
            self.assertRedirects(respuesta, self.detalle())
        self.assertEqual(ParticipacionInstitucion.objects.count(), 3)

    def test_t_u_lectores_no_asignan(self):
        for rol in (PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.entrar(rol)
            self.assertEqual(self.client.post(self.detalle(), self.datos_participacion()).status_code, 403)

    def test_v_inactiva_no_asignable(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.post(
            self.detalle(), self.datos_participacion(institucion=self.inactiva.pk)
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(ParticipacionInstitucion.objects.count(), 0)

    def test_w_duplicado_muestra_error(self):
        ParticipacionInstitucion.objects.create(
            incidente=self.incidente, institucion=self.institucion
        )
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.post(self.detalle(), self.datos_participacion())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ya está asociada")
        self.assertEqual(ParticipacionInstitucion.objects.count(), 1)

    def test_x_incidente_viene_de_url(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.post(
            self.detalle(), self.datos_participacion(incidente=self.otro_incidente.pk)
        )
        self.assertRedirects(respuesta, self.detalle())
        self.assertEqual(ParticipacionInstitucion.objects.get().incidente, self.incidente)

    def test_y_z_detalle_muestra_datos_conservados(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        self.client.post(self.detalle(), self.datos_participacion())
        participacion = ParticipacionInstitucion.objects.get()
        self.assertEqual(participacion.observacion, "Acudió al lugar")
        self.assertEqual(timezone.localtime(participacion.fecha_asignacion).strftime("%Y-%m-%dT%H:%M"), "2026-09-12T14:30")
        respuesta = self.client.get(self.detalle())
        self.assertContains(respuesta, "Bomberos Voluntarios")
        self.assertContains(respuesta, "Acudió al lugar")

    def test_aa_paginacion_20(self):
        for indice in range(21):
            InstitucionApoyo.objects.create(nombre=f"Auxiliar {indice:02d}")
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        respuesta = self.client.get(reverse("operations:institution_list"))
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 23)

    def test_ab_busqueda_nombre_siglas_telefono(self):
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        url = reverse("operations:institution_list")
        for termino in ("Bomberos", "BV", "12345678"):
            self.assertEqual(
                self.client.get(url, {"busqueda": termino}).context["pagina"].paginator.count,
                1,
            )

    def test_ac_filtro_estado(self):
        self.entrar(PerfilUsuario.Rol.AUDITOR)
        url = reverse("operations:institution_list")
        self.assertEqual(self.client.get(url, {"estado": "activa"}).context["pagina"].paginator.count, 1)
        self.assertEqual(self.client.get(url, {"estado": "inactiva"}).context["pagina"].paginator.count, 1)

    def test_csrf_obligatorio_en_mutaciones(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuarios[PerfilUsuario.Rol.ADMINISTRADOR])
        self.assertEqual(cliente.post(reverse("operations:institution_create"), self.datos_institucion()).status_code, 403)
        self.assertEqual(cliente.post(self.detalle(), self.datos_participacion()).status_code, 403)
