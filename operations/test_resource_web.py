from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import PerfilUsuario

from .forms import RecursoForm
from .models import RecursoInstitucional, TipoRecurso


class RecursosVisualesTests(TestCase):
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
        cls.tipo = TipoRecurso.objects.create(nombre="Cámara", descripcion="Vigilancia")
        cls.tipo_inactivo = TipoRecurso.objects.create(nombre="Obsoleto", activo=False)
        cls.recurso = RecursoInstitucional.objects.create(
            nombre="Cámara Central", tipo=cls.tipo, codigo_interno="CAM-01",
            marca="Marca Uno", modelo="M1", numero_serie="SERIE-01",
            ubicacion="Parque Central",
        )

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def datos_recurso(self, **cambios):
        return {**{
            "nombre": "Cámara Norte", "tipo": self.tipo.pk,
            "codigo_interno": "CAM-02", "marca": "Marca Dos",
            "modelo": "M2", "numero_serie": "SERIE-02",
            "ubicacion": "Zona Norte", "descripcion": "Operativa",
            "estado": RecursoInstitucional.Estado.DISPONIBLE, "activo": "on",
        }, **cambios}

    def datos_tipo(self, **cambios):
        return {**{"nombre": "Radio", "descripcion": "Comunicación", "activo": "on"}, **cambios}

    def test_a_login_obligatorio(self):
        for nombre in ("resource_list", "resource_create", "resource_type_list", "resource_type_create"):
            self.assertEqual(self.client.get(reverse(f"operations:{nombre}")).status_code, 302)

    def test_b_c_d_e_f_todos_los_roles_listan_recursos(self):
        for rol in PerfilUsuario.Rol:
            self.entrar(rol)
            respuesta = self.client.get(reverse("operations:resource_list"))
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "Cámara Central")

    def test_g_h_admin_y_coordinador_crean(self):
        for indice, rol in enumerate((PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR)):
            self.entrar(rol)
            respuesta = self.client.post(
                reverse("operations:resource_create"),
                self.datos_recurso(
                    nombre=f"Cámara {indice}", codigo_interno=f"CAM-{indice + 2:02d}",
                    numero_serie=f"SERIE-{indice + 2:02d}",
                ),
            )
            self.assertRedirects(respuesta, reverse("operations:resource_list"))
        self.assertEqual(RecursoInstitucional.objects.count(), 3)

    def test_i_j_k_lectores_no_crean(self):
        for rol in (PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.entrar(rol)
            self.assertEqual(
                self.client.post(reverse("operations:resource_create"), self.datos_recurso()).status_code,
                403,
            )

    def test_l_m_gestores_editan_recurso(self):
        for rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR):
            self.entrar(rol)
            respuesta = self.client.post(
                reverse("operations:resource_update", args=[self.recurso.pk]),
                self.datos_recurso(
                    nombre=f"Editado {rol.value}", codigo_interno="CAM-01",
                    numero_serie="SERIE-01",
                ),
            )
            self.assertRedirects(respuesta, reverse("operations:resource_list"))
        self.recurso.refresh_from_db()
        self.assertEqual(self.recurso.nombre, "Editado COORDINADOR")

    def test_n_solo_admin_activa_y_desactiva(self):
        url = reverse("operations:resource_toggle_status", args=[self.recurso.pk])
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("operations:resource_list"))
        self.recurso.refresh_from_db()
        self.assertFalse(self.recurso.activo)
        self.client.post(url)
        self.recurso.refresh_from_db()
        self.assertTrue(self.recurso.activo)
        for rol in (PerfilUsuario.Rol.COORDINADOR, PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.entrar(rol)
            self.assertEqual(self.client.post(url).status_code, 403)

    def test_coordinador_no_cambia_activo_por_post_manipulado(self):
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        datos = self.datos_recurso(
            nombre=self.recurso.nombre, codigo_interno=self.recurso.codigo_interno,
            numero_serie=self.recurso.numero_serie,
        )
        datos.pop("activo")
        respuesta = self.client.post(
            reverse("operations:resource_update", args=[self.recurso.pk]), datos
        )
        self.assertRedirects(respuesta, reverse("operations:resource_list"))
        self.recurso.refresh_from_db()
        self.assertTrue(self.recurso.activo)

    def test_o_codigo_duplicado_rechazado(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:resource_create"),
            self.datos_recurso(codigo_interno="CAM-01"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este código interno ya está registrado.")
        self.assertEqual(RecursoInstitucional.objects.count(), 1)

    def test_p_serie_duplicada_rechazada(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:resource_create"),
            self.datos_recurso(numero_serie="SERIE-01"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este número de serie ya está registrado.")
        self.assertEqual(RecursoInstitucional.objects.count(), 1)

    def test_q_vacios_repetidos_permitidos(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        for indice in range(2):
            respuesta = self.client.post(
                reverse("operations:resource_create"),
                self.datos_recurso(
                    nombre=f"Sin código {indice}", codigo_interno="", numero_serie="",
                ),
            )
            self.assertRedirects(respuesta, reverse("operations:resource_list"))
        self.assertEqual(RecursoInstitucional.objects.filter(codigo_interno="").count(), 2)

    def test_r_solo_tipos_activos_en_formulario_y_post(self):
        formulario = RecursoForm()
        ids = set(formulario.fields["tipo"].queryset.values_list("pk", flat=True))
        self.assertIn(self.tipo.pk, ids)
        self.assertNotIn(self.tipo_inactivo.pk, ids)
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:resource_create"),
            self.datos_recurso(tipo=self.tipo_inactivo.pk),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(RecursoInstitucional.objects.count(), 1)

    def test_s_estado_predeterminado_modelo(self):
        recurso = RecursoInstitucional.objects.create(nombre="Sin estado explícito", tipo=self.tipo)
        self.assertEqual(recurso.estado, RecursoInstitucional.Estado.DISPONIBLE)

    def test_t_cambio_estado_operativo(self):
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        respuesta = self.client.post(
            reverse("operations:resource_update", args=[self.recurso.pk]),
            self.datos_recurso(
                nombre=self.recurso.nombre, codigo_interno=self.recurso.codigo_interno,
                numero_serie=self.recurso.numero_serie,
                estado=RecursoInstitucional.Estado.MANTENIMIENTO,
            ),
        )
        self.assertRedirects(respuesta, reverse("operations:resource_list"))
        self.recurso.refresh_from_db()
        self.assertEqual(self.recurso.estado, RecursoInstitucional.Estado.MANTENIMIENTO)

    def test_u_v_w_filtros(self):
        otro = TipoRecurso.objects.create(nombre="Vehículo")
        RecursoInstitucional.objects.create(
            nombre="Patrulla", tipo=otro,
            estado=RecursoInstitucional.Estado.MANTENIMIENTO, activo=False,
        )
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        url = reverse("operations:resource_list")
        for parametros in (
            {"tipo": otro.pk}, {"estado": RecursoInstitucional.Estado.MANTENIMIENTO},
            {"activo": "inactivo"},
        ):
            self.assertEqual(self.client.get(url, parametros).context["pagina"].paginator.count, 1)

    def test_x_y_busqueda_nombre_y_codigo(self):
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        url = reverse("operations:resource_list")
        for termino in ("Cámara Central", "CAM-01", "Marca Uno", "M1", "SERIE-01", "Parque Central"):
            self.assertEqual(self.client.get(url, {"busqueda": termino}).context["pagina"].paginator.count, 1)

    def test_z_paginacion_20(self):
        for indice in range(21):
            RecursoInstitucional.objects.create(nombre=f"Auxiliar {indice:02d}", tipo=self.tipo)
        self.entrar(PerfilUsuario.Rol.AUDITOR)
        respuesta = self.client.get(reverse("operations:resource_list"))
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 22)

    def test_aa_ab_admin_crea_y_edita_tipo(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:resource_type_create"), self.datos_tipo()
        )
        self.assertRedirects(respuesta, reverse("operations:resource_type_list"))
        tipo = TipoRecurso.objects.get(nombre="Radio")
        respuesta = self.client.post(
            reverse("operations:resource_type_update", args=[tipo.pk]),
            self.datos_tipo(nombre="Radio portátil", activo=""),
        )
        self.assertRedirects(respuesta, reverse("operations:resource_type_list"))
        tipo.refresh_from_db()
        self.assertEqual(tipo.nombre, "Radio portátil")
        self.assertFalse(tipo.activo)

    def test_ac_coordinador_consulta_pero_no_crea_tipos(self):
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        self.assertEqual(self.client.get(reverse("operations:resource_type_list")).status_code, 200)
        self.assertEqual(self.client.post(reverse("operations:resource_type_create"), self.datos_tipo()).status_code, 403)

    def test_todos_los_roles_consultan_tipos_sin_edicion(self):
        for rol in (PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR):
            self.entrar(rol)
            respuesta = self.client.get(reverse("operations:resource_type_list"))
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotContains(respuesta, reverse("operations:resource_type_create"))

    def test_ad_no_hay_eliminacion_fisica(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        for nombre in ("resource_list", "resource_type_list"):
            self.assertNotContains(self.client.get(reverse(f"operations:{nombre}")), "Eliminar")
        self.assertTrue(RecursoInstitucional.objects.filter(pk=self.recurso.pk).exists())

    def test_ae_html_no_expone_datos_sensibles(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.get(reverse("operations:resource_list"))
        self.assertNotContains(respuesta, self.recurso.numero_serie)
        self.assertNotContains(respuesta, self.usuarios[PerfilUsuario.Rol.OPERADOR].password)
        self.assertNotContains(respuesta, "ClaveTemporal!123")

    def test_csrf_en_mutaciones(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuarios[PerfilUsuario.Rol.ADMINISTRADOR])
        self.assertEqual(cliente.post(reverse("operations:resource_create"), self.datos_recurso()).status_code, 403)
        self.assertEqual(cliente.post(reverse("operations:resource_toggle_status", args=[self.recurso.pk])).status_code, 403)
