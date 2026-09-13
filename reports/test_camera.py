from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from incidents.models import Incidente
from operations.models import RecursoInstitucional, TipoRecurso

from .services import buscar_incidentes, obtener_incidentes_por_camara


class ReportesPorCamaraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="auditor_camaras")
        cls.usuario.perfil.rol = PerfilUsuario.Rol.AUDITOR
        cls.usuario.perfil.save(update_fields=("rol",))
        tipo = TipoRecurso.objects.create(nombre="Video", es_camara=True)
        cls.camara_uno = RecursoInstitucional.objects.create(
            nombre="PTZ Parque", tipo=tipo, ubicacion="Parque central"
        )
        cls.camara_dos = RecursoInstitucional.objects.create(
            nombre="PTZ Mercado", tipo=tipo, ubicacion="Mercado"
        )
        cls.fecha = timezone.make_aware(datetime(2026, 9, 12, 12, 0))
        cls.uno = cls.incidente(cls.camara_uno, cls.fecha)
        cls.dos = cls.incidente(cls.camara_uno, cls.fecha + timedelta(hours=1))
        cls.tres = cls.incidente(cls.camara_dos, cls.fecha + timedelta(days=1))
        cls.sin_camara = cls.incidente(None, cls.fecha)

    @classmethod
    def incidente(cls, camara, fecha):
        return Incidente.objects.create(
            fecha_hora_reporte=fecha, ubicacion="Sector municipal",
            tipo_incidente="Aviso", prioridad="Por evaluar",
            descripcion="Reporte", operador_responsable=cls.usuario,
            camara_origen=camara,
        )

    def test_estadistica_cuenta_por_camara_y_excluye_sin_camara(self):
        filas = obtener_incidentes_por_camara()
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0], {
            "camara_id": self.camara_uno.pk,
            "nombre": "PTZ Parque",
            "ubicacion": "Parque central",
            "cantidad": 2,
        })
        self.assertEqual(filas[1]["cantidad"], 1)
        self.assertEqual(sum(fila["cantidad"] for fila in filas), 3)

    def test_estadistica_respeta_periodo(self):
        filas = obtener_incidentes_por_camara(
            fecha_desde=date(2026, 9, 13), fecha_hasta=date(2026, 9, 13)
        )
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["camara_id"], self.camara_dos.pk)
        self.assertEqual(filas[0]["cantidad"], 1)

    def test_buscar_incidentes_filtra_por_camara(self):
        ids = set(buscar_incidentes(camara_id=self.camara_uno.pk).values_list(
            "pk", flat=True
        ))
        self.assertEqual(ids, {self.uno.pk, self.dos.pk})

    def test_consulta_historica_filtra_y_muestra_camara(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:incident_report"), {
            "camara": self.camara_uno.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        ids = {obj.pk for obj in respuesta.context["pagina"].object_list}
        self.assertEqual(ids, {self.uno.pk, self.dos.pk})
        self.assertContains(respuesta, "Cámara: PTZ Parque")

    def test_filtro_conserva_camara_historica_si_tipo_cambia(self):
        tipo = self.camara_uno.tipo
        tipo.es_camara = False
        tipo.save(update_fields=("es_camara",))
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:incident_report"), {
            "camara": self.camara_uno.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 2)

    def test_panel_incluye_grafica_por_camara(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"))
        self.assertEqual(respuesta.status_code, 200)
        grafica = respuesta.context["graficas"]["camara"]
        self.assertEqual(grafica["values"], [2, 1])
        self.assertIn("PTZ Parque — Parque central", grafica["labels"])
        self.assertContains(respuesta, "Incidentes por cámara")
        self.assertContains(respuesta, 'data-report-chart="camara"')

    def test_panel_filtrado_por_camara_no_inventa_otra_categoria(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"), {
            "camara": self.camara_dos.pk,
        })
        self.assertEqual(respuesta.context["graficas"]["camara"]["values"], [1])
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 1)
