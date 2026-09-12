from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import PerfilUsuario


class AdministracionUsuariosWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = "ClaveInstitucional-7826!"
        cls.admin = User.objects.create_user(
            username="admin_visual",
            password=cls.clave,
            first_name="Ana",
            last_name="Administradora",
        )
        cls.admin.perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        cls.admin.perfil.save(update_fields=("rol",))
        cls.otro = User.objects.create_user(
            username="operador_visual",
            password=cls.clave,
            first_name="Luis",
            last_name="Mejía",
            email="luis@example.com",
        )
        cls.otro.perfil.telefono = "12345678"
        cls.otro.perfil.save(update_fields=("telefono",))

    def url_editar(self, usuario=None):
        return reverse("accounts:user_update", args=[(usuario or self.otro).pk])

    def url_estado(self, usuario=None):
        return reverse(
            "accounts:user_toggle_status", args=[(usuario or self.otro).pk]
        )

    def datos_creacion(self, **extras):
        datos = {
            "first_name": "María",
            "last_name": "Gómez",
            "username": "nueva_operadora",
            "email": "maria@example.com",
            "telefono": "87654321",
            "rol": PerfilUsuario.Rol.COORDINADOR,
            "estado_activo": "on",
            "password1": "NuevaClaveSegura-9371!",
            "password2": "NuevaClaveSegura-9371!",
        }
        datos.update(extras)
        return datos

    def datos_edicion(self, usuario=None, **extras):
        usuario = usuario or self.otro
        datos = {
            "first_name": usuario.first_name,
            "last_name": usuario.last_name,
            "username": usuario.username,
            "email": usuario.email,
            "telefono": usuario.perfil.telefono,
            "rol": usuario.perfil.rol,
            "estado_activo": "on" if usuario.is_active else "",
        }
        datos.update(extras)
        return datos

    def test_anonimo_no_accede_al_listado(self):
        respuesta = self.client.get(reverse("accounts:user_list"))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('accounts:user_list')}",
        )

    def test_administrador_accede_al_modulo(self):
        self.client.force_login(self.admin)
        for url in (
            reverse("accounts:user_list"),
            reverse("accounts:user_create"),
            self.url_editar(),
        ):
            self.assertEqual(self.client.get(url).status_code, 200)

    def verificar_rol_sin_acceso(self, rol):
        self.otro.perfil.rol = rol
        self.otro.perfil.save(update_fields=("rol",))
        self.client.force_login(self.otro)
        for url in (
            reverse("accounts:user_list"),
            reverse("accounts:user_create"),
            self.url_editar(self.admin),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(self.url_estado(self.admin)).status_code, 403
        )

    def test_coordinador_recibe_403(self):
        self.verificar_rol_sin_acceso(PerfilUsuario.Rol.COORDINADOR)

    def test_operador_recibe_403(self):
        self.verificar_rol_sin_acceso(PerfilUsuario.Rol.OPERADOR)

    def test_consulta_recibe_403(self):
        self.verificar_rol_sin_acceso(PerfilUsuario.Rol.CONSULTA)

    def test_auditor_recibe_403(self):
        self.verificar_rol_sin_acceso(PerfilUsuario.Rol.AUDITOR)

    def test_administrador_crea_usuario_perfil_rol_y_telefono(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"), self.datos_creacion(), follow=True
        )
        self.assertRedirects(respuesta, reverse("accounts:user_list"))
        self.assertContains(respuesta, "Usuario creado correctamente.")
        usuario = User.objects.get(username="nueva_operadora")
        self.assertEqual(usuario.perfil.rol, PerfilUsuario.Rol.COORDINADOR)
        self.assertEqual(usuario.perfil.telefono, "87654321")
        self.assertEqual(usuario.email, "maria@example.com")
        self.assertTrue(usuario.is_active)

    def test_contrasena_se_almacena_con_hash(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("accounts:user_create"), self.datos_creacion())
        usuario = User.objects.get(username="nueva_operadora")
        self.assertNotEqual(usuario.password, "NuevaClaveSegura-9371!")
        self.assertTrue(usuario.check_password("NuevaClaveSegura-9371!"))

    def test_contrasena_no_aparece_tras_registro(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"), self.datos_creacion(), follow=True
        )
        self.assertNotContains(respuesta, "NuevaClaveSegura-9371!")
        self.assertNotContains(respuesta, User.objects.get(
            username="nueva_operadora"
        ).password)

    def test_contrasenas_diferentes_se_rechazan(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"),
            self.datos_creacion(password2="OtraClaveSegura-7755!"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Las contraseñas no coinciden.")
        self.assertFalse(User.objects.filter(username="nueva_operadora").exists())

    def test_validador_de_contrasenas_de_django(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"),
            self.datos_creacion(password1="123", password2="123"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username="nueva_operadora").exists())

    def test_username_duplicado_se_rechaza(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"),
            self.datos_creacion(username="OPERADOR_VISUAL"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ya está en uso")
        self.assertEqual(User.objects.filter(username__iexact="operador_visual").count(), 1)

    def test_correo_invalido_se_rechaza(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"),
            self.datos_creacion(email="no-es-correo"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username="nueva_operadora").exists())

    def test_rol_invalido_se_rechaza(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("accounts:user_create"),
            self.datos_creacion(rol="ROL_INVENTADO"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username="nueva_operadora").exists())

    def test_creacion_es_atomica_si_falla_perfil(self):
        self.client.force_login(self.admin)
        with patch.object(PerfilUsuario, "save", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("accounts:user_create"), self.datos_creacion()
                )
        self.assertFalse(User.objects.filter(username="nueva_operadora").exists())

    def test_administrador_edita_datos_y_rol_de_otro_usuario(self):
        hash_anterior = self.otro.password
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            self.url_editar(),
            self.datos_edicion(
                first_name="Luis Alberto",
                email="nuevo@example.com",
                telefono="55554444",
                rol=PerfilUsuario.Rol.AUDITOR,
            ),
            follow=True,
        )
        self.assertRedirects(respuesta, reverse("accounts:user_list"))
        self.assertContains(respuesta, "Usuario actualizado correctamente.")
        self.otro.refresh_from_db()
        self.otro.perfil.refresh_from_db()
        self.assertEqual(self.otro.first_name, "Luis Alberto")
        self.assertEqual(self.otro.email, "nuevo@example.com")
        self.assertEqual(self.otro.perfil.telefono, "55554444")
        self.assertEqual(self.otro.perfil.rol, PerfilUsuario.Rol.AUDITOR)
        self.assertEqual(self.otro.password, hash_anterior)

    def test_desactivar_impide_login_y_reactivar(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(self.url_estado(), follow=True)
        self.assertContains(respuesta, "Usuario desactivado correctamente.")
        self.otro.refresh_from_db()
        self.assertFalse(self.otro.is_active)
        cliente = Client()
        self.assertFalse(cliente.login(username=self.otro.username, password=self.clave))

        respuesta = self.client.post(self.url_estado(), follow=True)
        self.assertContains(respuesta, "Usuario activado correctamente.")
        self.otro.refresh_from_db()
        self.assertTrue(self.otro.is_active)

    def test_estado_solo_acepta_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url_estado()).status_code, 405)
        self.otro.refresh_from_db()
        self.assertTrue(self.otro.is_active)

    def test_estado_requiere_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(self.url_estado()).status_code, 403)

    def test_administrador_no_puede_desactivarse(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            self.url_estado(self.admin), follow=True
        )
        self.assertContains(respuesta, "No puede desactivar su propia cuenta.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_administrador_no_puede_desactivarse_desde_edicion(self):
        self.client.force_login(self.admin)
        datos = self.datos_edicion(self.admin)
        datos.pop("estado_activo")
        respuesta = self.client.post(self.url_editar(self.admin), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No puede desactivar su propia cuenta.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_administrador_no_cambia_su_propio_rol(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            self.url_editar(self.admin),
            self.datos_edicion(self.admin, rol=PerfilUsuario.Rol.OPERADOR),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No puede cambiar su propio rol.")
        self.admin.perfil.refresh_from_db()
        self.assertEqual(self.admin.perfil.rol, PerfilUsuario.Rol.ADMINISTRADOR)

    def test_busqueda_por_username(self):
        self.verificar_filtro("busqueda", "operador_visual", self.otro)

    def test_busqueda_por_nombre(self):
        self.verificar_filtro("busqueda", "Luis", self.otro)

    def test_busqueda_por_apellido(self):
        self.verificar_filtro("busqueda", "Mejía", self.otro)

    def test_filtro_por_rol(self):
        self.verificar_filtro("rol", PerfilUsuario.Rol.OPERADOR, self.otro)

    def test_filtro_por_estado(self):
        self.otro.is_active = False
        self.otro.save(update_fields=("is_active",))
        self.verificar_filtro("estado", "inactivo", self.otro)

    def verificar_filtro(self, nombre, valor, esperado):
        self.client.force_login(self.admin)
        respuesta = self.client.get(
            reverse("accounts:user_list"), {nombre: valor}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            [usuario.pk for usuario in respuesta.context["pagina"].object_list],
            [esperado.pk],
        )

    def test_paginacion_limita_a_20(self):
        for numero in range(21):
            User.objects.create_user(username=f"pag_usuario_{numero:02}")
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 23)

    def test_html_no_muestra_password_hash(self):
        self.client.force_login(self.admin)
        for url in (
            reverse("accounts:user_list"),
            reverse("accounts:user_create"),
            self.url_editar(),
        ):
            respuesta = self.client.get(url)
            self.assertNotContains(respuesta, self.admin.password)
            self.assertNotContains(respuesta, self.otro.password)
            self.assertNotContains(respuesta, self.clave)
        respuesta_edicion = self.client.get(self.url_editar())
        self.assertNotContains(respuesta_edicion, 'name="password1"')
        self.assertNotContains(respuesta_edicion, 'name="password2"')

    def test_interfaz_no_ofrece_eliminacion_fisica(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("accounts:user_list"))
        self.assertNotContains(respuesta, "Eliminar")
        self.assertEqual(
            self.client.delete(self.url_estado()).status_code, 405
        )
        self.assertTrue(User.objects.filter(pk=self.otro.pk).exists())

    def test_menu_usuarios_solo_para_administrador(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("dashboard"))
        self.assertContains(respuesta, reverse("accounts:user_list"))
        self.client.force_login(self.otro)
        respuesta = self.client.get(reverse("dashboard"))
        self.assertNotContains(respuesta, "Usuarios")
