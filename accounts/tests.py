from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

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
