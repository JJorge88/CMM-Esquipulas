import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import PerfilUsuario
from incidents.models import (
    EvidenciaIncidente, Incidente, ParticipacionInstitucion,
    SeguimientoIncidente,
)
from operations.models import InstitucionApoyo, RecursoInstitucional, TipoRecurso

from .forms import ComparacionPeriodosForm
from .services import calcular_variacion, comparar_periodos


GUATEMALA = ZoneInfo("America/Guatemala")


class VariacionTests(TestCase):
    def test_incremento(self):
        self.assertEqual(calcular_variacion(120, 100), {
            "variacion_absoluta": 20,
            "variacion_porcentual": 20,
            "tendencia": "incremento",
        })

    def test_disminucion(self):
        resultado = calcular_variacion(80, 100)
        self.assertEqual(resultado["variacion_absoluta"], -20)
        self.assertEqual(resultado["variacion_porcentual"], -20)
        self.assertEqual(resultado["tendencia"], "disminucion")

    def test_ambos_cero(self):
        resultado = calcular_variacion(0, 0)
        self.assertEqual(resultado["variacion_absoluta"], 0)
        self.assertEqual(resultado["variacion_porcentual"], 0)
        self.assertEqual(resultado["tendencia"], "sin_cambio")

    def test_anterior_cero_actual_positivo_no_divide(self):
        resultado = calcular_variacion(7, 0)
        self.assertEqual(resultado["variacion_absoluta"], 7)
        self.assertIsNone(resultado["variacion_porcentual"])

    def test_duracion_y_ausencia_de_datos(self):
        resultado = calcular_variacion(timedelta(minutes=12), timedelta(minutes=18))
        self.assertEqual(resultado["variacion_absoluta"], timedelta(minutes=-6))
        self.assertAlmostEqual(resultado["variacion_porcentual"], -33.3333, places=3)
        self.assertIsNone(calcular_variacion(None, timedelta(minutes=18))["variacion_absoluta"])


class ComparacionPeriodosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {}
        for rol in PerfilUsuario.Rol:
            usuario = User.objects.create_user(username=f"comp_{rol.value.lower()}")
            usuario.perfil.rol = rol
            usuario.perfil.save(update_fields=("rol",))
            cls.usuarios[rol] = usuario
        cls.usuario = cls.usuarios[PerfilUsuario.Rol.ADMINISTRADOR]
        cls.usuario.email = "privado_comparacion@example.com"
        cls.usuario.save(update_fields=("email",))
        tipo = TipoRecurso.objects.create(nombre="Cámaras de comparación", es_camara=True)
        cls.camara_actual = RecursoInstitucional.objects.create(
            nombre="PTZ Actual", tipo=tipo, ubicacion="Plaza actual"
        )
        cls.camara_anterior = RecursoInstitucional.objects.create(
            nombre="PTZ Anterior", tipo=tipo, ubicacion="Plaza anterior"
        )
        cls.bomberos = InstitucionApoyo.objects.create(
            nombre="Bomberos comparativos", siglas="BC", telefono="5555-9999"
        )
        cls.policia = InstitucionApoyo.objects.create(
            nombre="Policía comparativa", siglas="PC"
        )
        cls.a1 = cls.crear(9, 1, "Tránsito", "Urgente", Incidente.Estado.REGISTRADO,
                            cls.camara_actual, inicio=10)
        cls.a2 = cls.crear(9, 2, "Tránsito", "Normal", Incidente.Estado.CERRADO,
                            cls.camara_actual, inicio=20, resolucion=50)
        cls.a3 = cls.crear(9, 3, "Rescate", "Urgente", Incidente.Estado.EN_SEGUIMIENTO)
        cls.p1 = cls.crear(8, 1, "Tránsito", "Normal", Incidente.Estado.CERRADO,
                            cls.camara_anterior, inicio=30, resolucion=60)
        cls.p2 = cls.crear(8, 2, "Robo", "Baja", Incidente.Estado.PENDIENTE,
                            cls.camara_anterior)
        cls.p3 = cls.crear(8, 3, "Robo", "Baja", Incidente.Estado.CERRADO)
        for incidente, institucion in (
            (cls.a1, cls.bomberos), (cls.a2, cls.bomberos),
            (cls.a2, cls.policia), (cls.a3, cls.policia),
            (cls.p1, cls.bomberos), (cls.p2, cls.bomberos),
        ):
            ParticipacionInstitucion.objects.create(
                incidente=incidente, institucion=institucion
            )
        SeguimientoIncidente.objects.create(
            incidente=cls.a1, usuario=cls.usuario,
            observacion="Seguimiento comparativo", estado_nuevo=Incidente.Estado.PENDIENTE,
        )
        EvidenciaIncidente.objects.create(
            incidente=cls.a1, usuario=cls.usuario,
            archivo="evidencias/comparacion.jpg", tipo=EvidenciaIncidente.Tipo.FOTO,
        )

    @classmethod
    def crear(cls, mes, dia, tipo, prioridad, estado, camara=None, inicio=None, resolucion=None):
        reporte = datetime(2026, mes, dia, 10, 0, tzinfo=GUATEMALA)
        return Incidente.objects.create(
            fecha_hora_reporte=reporte,
            fecha_inicio_atencion=reporte + timedelta(minutes=inicio) if inicio is not None else None,
            fecha_resolucion=reporte + timedelta(minutes=resolucion) if resolucion is not None else None,
            ubicacion="Sector municipal", tipo_incidente=tipo,
            prioridad=prioridad, descripcion="Registro histórico",
            operador_responsable=cls.usuario, estado=estado,
            resultado_cierre="Atendido" if estado == Incidente.Estado.CERRADO else "",
            camara_origen=camara,
        )

    @staticmethod
    def fechas():
        return {
            "actual_desde": date(2026, 9, 1), "actual_hasta": date(2026, 9, 3),
            "anterior_desde": date(2026, 8, 1), "anterior_hasta": date(2026, 8, 3),
        }

    @staticmethod
    def parametros():
        return {
            "actual_desde": "2026-09-01", "actual_hasta": "2026-09-03",
            "anterior_desde": "2026-08-01", "anterior_hasta": "2026-08-03",
        }

    def comparacion(self, **cambios):
        return comparar_periodos(**{**self.fechas(), **cambios})

    def pagina(self, parametros=None):
        return self.client.get(reverse("reports:comparison"), parametros)

    def test_permisos_por_rol(self):
        self.assertEqual(self.pagina().status_code, 302)
        for rol in PerfilUsuario.Rol:
            with self.subTest(rol=rol):
                self.client.force_login(self.usuarios[rol])
                esperado = 403 if rol == PerfilUsuario.Rol.OPERADOR else 200
                self.assertEqual(self.pagina().status_code, esperado)
                self.assertEqual(self.pagina(self.parametros()).status_code, esperado)

    def test_formulario_valida_rangos_por_separado(self):
        for prefijo in ("actual", "anterior"):
            with self.subTest(prefijo=prefijo):
                datos = self.parametros()
                datos[f"{prefijo}_desde"] = "2026-12-01"
                formulario = ComparacionPeriodosForm(datos)
                self.assertFalse(formulario.is_valid())
                self.assertIn(f"{prefijo}_hasta", formulario.errors)
        self.assertTrue(ComparacionPeriodosForm(self.parametros()).is_valid())

    def test_duraciones_distintas_son_validas(self):
        datos = self.parametros()
        datos["actual_hasta"] = "2026-09-10"
        self.assertTrue(ComparacionPeriodosForm(datos).is_valid())

    def test_servicio_rechaza_rango_invalido(self):
        with self.assertRaises(ValidationError):
            self.comparacion(actual_desde=date(2026, 9, 10))
        with self.assertRaises(ValidationError):
            self.comparacion(anterior_desde=date(2026, 8, 10))

    def test_indicadores_estados_y_porcentaje_cerrados(self):
        resultado = self.comparacion()
        self.assertEqual(resultado["actual"]["total_incidentes"], 3)
        self.assertEqual(resultado["anterior"]["total_incidentes"], 3)
        self.assertEqual(resultado["actual"]["registrados"], 1)
        self.assertEqual(resultado["actual"]["en_seguimiento"], 1)
        self.assertEqual(resultado["actual"]["cerrados"], 1)
        self.assertEqual(resultado["anterior"]["pendientes"], 1)
        self.assertEqual(resultado["anterior"]["cerrados"], 2)
        self.assertAlmostEqual(resultado["actual"]["porcentaje_cerrados"], 100 / 3)
        self.assertAlmostEqual(resultado["anterior"]["porcentaje_cerrados"], 200 / 3)
        self.assertAlmostEqual(
            resultado["indicadores"]["porcentaje_cerrados"]["variacion_absoluta"],
            -100 / 3,
        )
        self.assertEqual(resultado["actual"]["total_evidencias"], 1)
        self.assertEqual(resultado["actual"]["total_seguimientos"], 1)

    def test_tiempos_promedio_y_sin_datos(self):
        resultado = self.comparacion()
        self.assertEqual(resultado["actual"]["tiempo_promedio_atencion"], timedelta(minutes=15))
        self.assertEqual(resultado["anterior"]["tiempo_promedio_atencion"], timedelta(minutes=30))
        self.assertEqual(resultado["actual"]["tiempo_promedio_resolucion"], timedelta(minutes=50))
        self.assertEqual(resultado["anterior"]["tiempo_promedio_resolucion"], timedelta(hours=1))
        vacio = self.comparacion(
            actual_desde=date(2035, 1, 1), actual_hasta=date(2035, 1, 2)
        )
        self.assertIsNone(vacio["actual"]["tiempo_promedio_atencion"])
        self.assertIsNone(vacio["indicadores"]["tiempo_promedio_atencion"]["variacion_absoluta"])

    def test_incidentes_sin_fechas_operativas_no_producen_promedio_cero(self):
        resultado = comparar_periodos(
            date(2026, 9, 3), date(2026, 9, 3),
            date(2026, 8, 2), date(2026, 8, 2),
        )
        self.assertEqual(resultado["actual"]["total_incidentes"], 1)
        self.assertEqual(resultado["anterior"]["total_incidentes"], 1)
        for clave in ("tiempo_promedio_atencion", "tiempo_promedio_resolucion"):
            self.assertIsNone(resultado["actual"][clave])
            self.assertIsNone(resultado["anterior"][clave])
            self.assertIsNone(resultado["indicadores"][clave]["variacion_absoluta"])

    def test_tipos_de_uno_o_ambos_periodos(self):
        filas = {fila["tipo"]: fila for fila in self.comparacion()["por_tipo"]}
        self.assertEqual((filas["Tránsito"]["actual"], filas["Tránsito"]["anterior"]), (2, 1))
        self.assertEqual((filas["Rescate"]["actual"], filas["Rescate"]["anterior"]), (1, 0))
        self.assertEqual((filas["Robo"]["actual"], filas["Robo"]["anterior"]), (0, 2))

    def test_prioridades_reales(self):
        filas = {fila["prioridad"]: fila for fila in self.comparacion()["por_prioridad"]}
        self.assertEqual((filas["Urgente"]["actual"], filas["Urgente"]["anterior"]), (2, 0))
        self.assertEqual((filas["Normal"]["actual"], filas["Normal"]["anterior"]), (1, 1))
        self.assertEqual((filas["Baja"]["actual"], filas["Baja"]["anterior"]), (0, 2))

    def test_camaras_union_sin_categoria_ficticia(self):
        filas = {fila["camara"]: fila for fila in self.comparacion()["por_camara"]}
        self.assertEqual(set(filas), {"PTZ Actual", "PTZ Anterior"})
        self.assertEqual((filas["PTZ Actual"]["actual"], filas["PTZ Actual"]["anterior"]), (2, 0))
        self.assertEqual((filas["PTZ Anterior"]["actual"], filas["PTZ Anterior"]["anterior"]), (0, 2))
        self.assertEqual(filas["PTZ Actual"]["ubicacion"], "Plaza actual")

    def test_instituciones_no_duplican_incidentes(self):
        filas = {fila["institucion"]: fila for fila in self.comparacion()["por_institucion"]}
        self.assertEqual((filas["Bomberos comparativos"]["actual"], filas["Bomberos comparativos"]["anterior"]), (2, 2))
        self.assertEqual((filas["Policía comparativa"]["actual"], filas["Policía comparativa"]["anterior"]), (2, 0))
        self.assertEqual(filas["Bomberos comparativos"]["siglas"], "BC")

    def test_filtro_camara_aplica_en_ambos_periodos(self):
        resultado = self.comparacion(camara_id=self.camara_actual.pk)
        self.assertEqual(resultado["actual"]["total_incidentes"], 2)
        self.assertEqual(resultado["anterior"]["total_incidentes"], 0)
        self.assertIsNone(resultado["indicadores"]["total_incidentes"]["variacion_porcentual"])
        self.assertEqual(len(resultado["por_camara"]), 1)

    def test_ambos_periodos_vacios(self):
        resultado = comparar_periodos(
            date(2035, 1, 1), date(2035, 1, 2),
            date(2034, 1, 1), date(2034, 1, 2),
        )
        self.assertEqual(resultado["actual"]["total_incidentes"], 0)
        self.assertEqual(resultado["anterior"]["total_incidentes"], 0)
        self.assertEqual(resultado["indicadores"]["total_incidentes"]["variacion_porcentual"], 0)
        self.assertEqual(resultado["por_tipo"], [])
        self.assertEqual(resultado["por_camara"], [])

    def test_solo_actual_o_anterior_con_datos(self):
        solo_actual = self.comparacion(
            anterior_desde=date(2035, 1, 1), anterior_hasta=date(2035, 1, 2)
        )
        solo_anterior = self.comparacion(
            actual_desde=date(2035, 1, 1), actual_hasta=date(2035, 1, 2)
        )
        self.assertEqual((solo_actual["actual"]["total_incidentes"], solo_actual["anterior"]["total_incidentes"]), (3, 0))
        self.assertIsNone(solo_actual["indicadores"]["total_incidentes"]["variacion_porcentual"])
        self.assertEqual((solo_anterior["actual"]["total_incidentes"], solo_anterior["anterior"]["total_incidentes"]), (0, 3))
        self.assertEqual(solo_anterior["indicadores"]["total_incidentes"]["variacion_porcentual"], -100)

    def test_pagina_muestra_tabla_tarjetas_y_graficas_neutrales(self):
        self.client.force_login(self.usuario)
        respuesta = self.pagina(self.parametros())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["indicadores"]), 11)
        self.assertContains(respuesta, "Resumen comparativo")
        self.assertContains(respuesta, "Tiempo promedio de resolución")
        for clave in ("por_tipo", "por_prioridad", "por_camara", "por_institucion"):
            self.assertContains(respuesta, f'data-comparison-chart="{clave}"')
        self.assertContains(respuesta, "PTZ Actual")
        self.assertContains(respuesta, "Plaza actual")
        self.assertContains(respuesta, "BC")
        self.assertNotContains(respuesta, "mejora")
        self.assertNotContains(respuesta, "empeora")
        self.assertNotContains(respuesta, "predicción")

    def test_pagina_muestra_duraciones_y_sin_datos(self):
        self.client.force_login(self.usuario)
        respuesta = self.pagina(self.parametros())
        self.assertContains(respuesta, "15 min")
        self.assertContains(respuesta, "1 h 00 min")
        datos = self.parametros()
        datos["anterior_desde"] = "2035-01-01"
        datos["anterior_hasta"] = "2035-01-02"
        respuesta = self.pagina(datos)
        self.assertContains(respuesta, "No comparable")
        self.assertContains(respuesta, "—")

    def test_pagina_vacia_y_rango_invalido_no_500(self):
        self.client.force_login(self.usuario)
        datos = {
            "actual_desde": "2035-01-01", "actual_hasta": "2035-01-02",
            "anterior_desde": "2034-01-01", "anterior_hasta": "2034-01-02",
        }
        respuesta = self.pagina(datos)
        self.assertContains(respuesta, "No hay incidentes en ninguno")
        self.assertEqual(respuesta.context["graficas_comparacion"]["por_tipo"]["labels"], [])
        datos["actual_desde"] = "2035-01-03"
        respuesta = self.pagina(datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["comparacion"])
        self.assertContains(respuesta, "La fecha final debe ser igual o posterior")

    def test_json_seguro_y_sin_datos_sensibles(self):
        self.crear(9, 4, "</script><script>alert(1)</script>", "Urgente", Incidente.Estado.REGISTRADO)
        self.client.force_login(self.usuario)
        respuesta = self.pagina(self.parametros() | {"actual_hasta": "2026-09-04"})
        html = respuesta.content.decode()
        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertNotIn(self.usuario.email, html)
        self.assertNotIn(self.bomberos.telefono, html)
        contenido = re.search(
            r'<script id="datos-comparacion" type="application/json">(.*?)</script>',
            html, re.S,
        )
        self.assertIsNotNone(contenido)
        datos = json.loads(contenido.group(1))
        self.assertIn("</script><script>alert(1)</script>", datos["por_tipo"]["labels"])
        self.assertEqual(len(datos["por_tipo"]["actual"]), len(datos["por_tipo"]["anterior"]))

    def test_enlace_desde_reportes(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("reports:index"))
        self.assertContains(respuesta, reverse("reports:comparison"))
        self.assertContains(respuesta, "Comparar períodos")

    def test_agregaciones_sin_n_mas_uno(self):
        with CaptureQueriesContext(connection) as consultas:
            self.comparacion()
        self.assertLessEqual(len(consultas), 14)
