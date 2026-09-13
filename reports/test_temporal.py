import json
import re
from datetime import date, datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from incidents.models import Incidente
from operations.models import RecursoInstitucional, TipoRecurso

from .services import (
    DIAS_SEMANA, HORAS_DIA, obtener_incidentes_por_dia_semana,
    obtener_incidentes_por_hora, obtener_maximos_temporales,
)


GUATEMALA = ZoneInfo("America/Guatemala")


class TemporalVacioTests(TestCase):
    def test_horas_vacias_en_orden(self):
        resultado = obtener_incidentes_por_hora()
        self.assertEqual(tuple(resultado), HORAS_DIA)
        self.assertEqual(len(resultado), 24)
        self.assertTrue(all(cantidad == 0 for cantidad in resultado.values()))

    def test_dias_vacios_en_orden(self):
        resultado = obtener_incidentes_por_dia_semana()
        self.assertEqual(tuple(resultado), DIAS_SEMANA)
        self.assertEqual(len(resultado), 7)
        self.assertTrue(all(cantidad == 0 for cantidad in resultado.values()))

    def test_sin_datos_no_inventa_maximo(self):
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_hora()), [])
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_dia_semana()), [])


class TemporalConDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="temporal_auditor")
        cls.usuario.perfil.rol = PerfilUsuario.Rol.AUDITOR
        cls.usuario.perfil.save(update_fields=("rol",))
        cls.usuario.email = "privado_temporal@example.com"
        cls.usuario.save(update_fields=("email",))
        tipo = TipoRecurso.objects.create(nombre="Cámara temporal", es_camara=True)
        cls.camara = RecursoInstitucional.objects.create(
            nombre="PTZ temporal", tipo=tipo, ubicacion="Plaza"
        )
        cls.lunes_8_a = cls.crear(datetime(2026, 9, 7, 8, 5, tzinfo=GUATEMALA), cls.camara)
        cls.lunes_8_b = cls.crear(datetime(2026, 9, 7, 8, 55, tzinfo=GUATEMALA), cls.camara)
        cls.martes_9 = cls.crear(datetime(2026, 9, 8, 9, 0, tzinfo=GUATEMALA))
        cls.sabado_8 = cls.crear(datetime(2026, 9, 12, 8, 0, tzinfo=GUATEMALA))

    @classmethod
    def crear(cls, fecha_reporte, camara=None, tipo="Aviso temporal"):
        return Incidente.objects.create(
            fecha_hora_reporte=fecha_reporte,
            ubicacion="Plaza municipal", tipo_incidente=tipo,
            prioridad="Por evaluar", descripcion="Dato histórico",
            operador_responsable=cls.usuario, camara_origen=camara,
        )

    def test_agrupa_horas_y_dias_reales(self):
        horas = obtener_incidentes_por_hora()
        dias = obtener_incidentes_por_dia_semana()
        self.assertEqual(horas["08"], 3)
        self.assertEqual(horas["09"], 1)
        self.assertEqual(horas["00"], 0)
        self.assertEqual(dias["Lunes"], 2)
        self.assertEqual(dias["Martes"], 1)
        self.assertEqual(dias["Sábado"], 1)
        self.assertEqual(dias["Domingo"], 0)
        self.assertEqual(sum(horas.values()), 4)
        self.assertEqual(sum(dias.values()), 4)

    def test_fecha_desde_hasta_y_rango_en_ambas_series(self):
        casos = (
            ({"fecha_desde": date(2026, 9, 8)}, 2),
            ({"fecha_hasta": date(2026, 9, 7)}, 2),
            ({"fecha_desde": date(2026, 9, 8), "fecha_hasta": date(2026, 9, 8)}, 1),
        )
        for filtros, esperado in casos:
            with self.subTest(filtros=filtros):
                self.assertEqual(sum(obtener_incidentes_por_hora(**filtros).values()), esperado)
                self.assertEqual(sum(obtener_incidentes_por_dia_semana(**filtros).values()), esperado)

    def test_rango_invalido_usa_validacion_existente(self):
        filtros = {"fecha_desde": date(2026, 9, 9), "fecha_hasta": date(2026, 9, 8)}
        with self.assertRaises(ValidationError):
            obtener_incidentes_por_hora(**filtros)
        with self.assertRaises(ValidationError):
            obtener_incidentes_por_dia_semana(**filtros)

    def test_zona_guatemala_aunque_timezone_activa_sea_utc(self):
        self.crear(datetime(2026, 9, 8, 2, 30, tzinfo=datetime_timezone.utc))
        with timezone.override("UTC"):
            horas = obtener_incidentes_por_hora()
            dias = obtener_incidentes_por_dia_semana()
            horas_lunes = obtener_incidentes_por_hora(
                fecha_desde=date(2026, 9, 7), fecha_hasta=date(2026, 9, 7)
            )
        self.assertEqual(horas["20"], 1)
        self.assertEqual(horas["02"], 0)
        self.assertEqual(horas_lunes["20"], 1)
        self.assertEqual(sum(horas_lunes.values()), 3)
        self.assertEqual(dias["Lunes"], 3)
        self.assertEqual(dias["Martes"], 1)

    def test_maximos_y_empates(self):
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_hora()), ["08"])
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_dia_semana()), ["Lunes"])
        self.crear(datetime(2026, 9, 12, 9, 10, tzinfo=GUATEMALA))
        self.crear(datetime(2026, 9, 12, 9, 20, tzinfo=GUATEMALA))
        self.crear(datetime(2026, 9, 7, 10, 0, tzinfo=GUATEMALA))
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_hora()), ["08", "09"])
        self.assertEqual(obtener_maximos_temporales(obtener_incidentes_por_dia_semana()), ["Lunes", "Sábado"])

    def test_filtro_camara_aplica_a_ambas_series(self):
        filtros = {"camara_id": self.camara.pk}
        self.assertEqual(obtener_incidentes_por_hora(**filtros)["08"], 2)
        self.assertEqual(obtener_incidentes_por_dia_semana(**filtros)["Lunes"], 2)
        self.assertEqual(sum(obtener_incidentes_por_hora(**filtros).values()), 2)

    def test_agregacion_se_hace_en_base_de_datos(self):
        with self.assertNumQueries(1):
            obtener_incidentes_por_hora()
        with self.assertNumQueries(1):
            obtener_incidentes_por_dia_semana()

    def test_panel_muestra_graficas_y_resumen(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"))
        self.assertContains(respuesta, "Incidentes por hora del día")
        self.assertContains(respuesta, "Incidentes por día de la semana")
        self.assertContains(respuesta, 'data-report-chart="hora"')
        self.assertContains(respuesta, 'data-report-chart="dia_semana"')
        self.assertEqual(respuesta.context["graficas"]["hora"]["labels"][0], "00:00")
        self.assertEqual(respuesta.context["graficas"]["hora"]["labels"][-1], "23:00")
        self.assertEqual(respuesta.context["graficas"]["hora"]["values"][8], 3)
        self.assertEqual(respuesta.context["graficas"]["dia_semana"]["labels"], list(DIAS_SEMANA))
        self.assertEqual(respuesta.context["hora_mayor_incidencia"], ["08:00 - 09:00"])
        self.assertEqual(respuesta.context["dia_mayor_incidencia"], ["Lunes"])
        self.assertNotContains(respuesta, self.usuario.email)

    def test_panel_empates_no_afirma_unico_maximo(self):
        self.crear(datetime(2026, 9, 12, 9, 10, tzinfo=GUATEMALA))
        self.crear(datetime(2026, 9, 12, 9, 20, tzinfo=GUATEMALA))
        self.crear(datetime(2026, 9, 7, 10, 0, tzinfo=GUATEMALA))
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"))
        self.assertEqual(respuesta.context["hora_mayor_incidencia"], [
            "08:00 - 09:00", "09:00 - 10:00",
        ])
        self.assertEqual(respuesta.context["dia_mayor_incidencia"], ["Lunes", "Sábado"])
        self.assertContains(respuesta, "Empate entre franjas horarias")
        self.assertContains(respuesta, "Empate entre días")

    def test_panel_filtra_camara_y_periodo(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"), {
            "fecha_desde": "2026-09-07", "fecha_hasta": "2026-09-07",
            "camara": self.camara.pk,
        })
        self.assertEqual(sum(respuesta.context["graficas"]["hora"]["values"]), 2)
        self.assertEqual(sum(respuesta.context["graficas"]["dia_semana"]["values"]), 2)

    def test_json_script_escapa_texto_y_no_expone_datos_sensibles(self):
        self.crear(
            datetime(2026, 9, 13, 12, 0, tzinfo=GUATEMALA),
            tipo="</script><script>alert(1)</script>",
        )
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"))
        html = respuesta.content.decode()
        self.assertIn('type="application/json"', html)
        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertNotIn(self.usuario.email, html)
        contenido = re.search(
            r'<script id="datos-reportes" type="application/json">(.*?)</script>',
            html, re.S,
        )
        self.assertIsNotNone(contenido)
        datos = json.loads(contenido.group(1))
        self.assertEqual(len(datos["hora"]["values"]), 24)
        self.assertEqual(len(datos["dia_semana"]["values"]), 7)

    def test_panel_vacio_muestra_ceros_y_mensaje(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"), {
            "fecha_desde": "2035-01-01"
        })
        self.assertEqual(respuesta.context["graficas"]["hora"]["values"], [0] * 24)
        self.assertEqual(respuesta.context["graficas"]["dia_semana"]["values"], [0] * 7)
        self.assertEqual(respuesta.context["hora_mayor_incidencia"], [])
        self.assertEqual(respuesta.context["dia_mayor_incidencia"], [])
        self.assertContains(respuesta, "No hay datos disponibles en el período seleccionado.")
        self.assertContains(respuesta, "Sin datos suficientes.", count=2)
