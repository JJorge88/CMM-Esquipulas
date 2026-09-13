from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditoriaAccion, PerfilUsuario
from incidents.forms import IncidenteForm

from .models import RecursoInstitucional, TipoRecurso


class AltaCamaraWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {}
        for rol in PerfilUsuario.Rol:
            usuario = User.objects.create_user(username=f"cam_{rol.value.lower()}")
            usuario.perfil.rol = rol
            usuario.perfil.save(update_fields=("rol",))
            cls.usuarios[rol] = usuario
        cls.tipo_camara = TipoRecurso.objects.create(
            nombre="Videovigilancia", es_camara=True
        )
        cls.tipo_no_camara = TipoRecurso.objects.create(nombre="Radio")
        cls.tipo_inactivo = TipoRecurso.objects.create(
            nombre="Videovigilancia antigua", es_camara=True, activo=False
        )

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def datos(self, **cambios):
        return {
            **{
                "nombre": "PTZ Plaza", "tipo": self.tipo_camara.pk,
                "codigo_interno": "CAM-PLAZA", "ubicacion": "Plaza central",
                "estado": RecursoInstitucional.Estado.DISPONIBLE,
                "activo": "on",
            },
            **cambios,
        }

    def test_opcion_visible_solo_para_administrador(self):
        url = reverse("operations:camera_create")
        for rol in PerfilUsuario.Rol:
            with self.subTest(rol=rol):
                self.entrar(rol)
                respuesta = self.client.get(reverse("operations:resource_list"))
                if rol == PerfilUsuario.Rol.ADMINISTRADOR:
                    self.assertContains(respuesta, url)
                    self.assertContains(respuesta, "Agregar cámara")
                else:
                    self.assertNotContains(respuesta, url)

    def test_acceso_requiere_admin_tambien_en_post(self):
        url = reverse("operations:camera_create")
        self.assertEqual(self.client.get(url).status_code, 302)
        for rol in PerfilUsuario.Rol:
            if rol == PerfilUsuario.Rol.ADMINISTRADOR:
                continue
            self.entrar(rol)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.datos()).status_code, 403)
        self.assertFalse(RecursoInstitucional.objects.exists())

    def test_formulario_corto_solo_muestra_tipos_de_camara_activos(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.get(reverse("operations:camera_create"))
        self.assertEqual(respuesta.status_code, 200)
        formulario = respuesta.context["formulario"]
        self.assertEqual(
            tuple(formulario.fields),
            ("nombre", "tipo", "codigo_interno", "ubicacion", "estado", "activo"),
        )
        ids = set(formulario.fields["tipo"].queryset.values_list("pk", flat=True))
        self.assertEqual(ids, {self.tipo_camara.pk})
        self.assertContains(respuesta, "Guardar cámara")

    def test_si_no_hay_tipo_camara_indica_paso_previo(self):
        self.tipo_camara.delete()
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.get(reverse("operations:camera_create"))
        self.assertContains(respuesta, "Crear tipo de cámara")
        self.assertContains(respuesta, reverse("operations:resource_type_create"))
        self.assertContains(respuesta, "disabled")
        self.assertFalse(TipoRecurso.objects.filter(es_camara=True, activo=True).exists())

    def test_admin_crea_camara_y_queda_disponible_para_incidentes(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:camera_create"), self.datos())
        self.assertRedirects(respuesta, reverse("operations:resource_list"))
        camara = RecursoInstitucional.objects.get(nombre="PTZ Plaza")
        self.assertTrue(camara.activo)
        self.assertTrue(camara.tipo.es_camara)
        self.assertIn(
            camara.pk,
            set(IncidenteForm().fields["camara_origen"].queryset.values_list(
                "pk", flat=True
            )),
        )
        self.assertTrue(AuditoriaAccion.objects.filter(
            modulo="RECURSOS", accion="CREAR", entidad_id=str(camara.pk)
        ).exists())

    def test_post_manipulado_no_acepta_tipo_que_no_es_camara(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:camera_create"),
            self.datos(tipo=self.tipo_no_camara.pk),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("tipo", respuesta.context["formulario"].errors)
        self.assertFalse(RecursoInstitucional.objects.exists())
        self.assertFalse(AuditoriaAccion.objects.exists())

    def test_tipo_inactivo_no_se_acepta(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(
            reverse("operations:camera_create"),
            self.datos(tipo=self.tipo_inactivo.pk),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("tipo", respuesta.context["formulario"].errors)
        self.assertFalse(RecursoInstitucional.objects.exists())
