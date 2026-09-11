from django.test import TestCase

# Create your tests here.
from datetime import date, datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from incidents.models import (
    EvidenciaIncidente,
    Incidente,
    ParticipacionInstitucion,
    SeguimientoIncidente,
)
from operations.models import InstitucionApoyo

from .services import (
    buscar_incidentes,
    obtener_incidentes_por_dia,
    obtener_incidentes_por_estado,
    obtener_incidentes_por_institucion,
    obtener_incidentes_por_operador,
    obtener_incidentes_por_prioridad,
    obtener_incidentes_por_tipo,
    obtener_resumen_incidentes,
)


def fecha_hora(anio, mes, dia, hora=10):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


class ResumenVacioTests(TestCase):
    def test_resumen_sin_incidentes(self):
        resumen = obtener_resumen_incidentes()

        self.assertEqual(resumen["total_incidentes"], 0)
        self.assertEqual(resumen["porcentaje_cerrados"], 0)


class ServiciosEstadisticosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operador_uno = User.objects.create_user(
            username="operador_reporte_uno",
            first_name="Primer",
            last_name="Operador",
        )
        cls.operador_dos = User.objects.create_user(
            username="operador_reporte_dos",
            first_name="Segundo",
            last_name="Operador",
        )
        cls.institucion_uno = InstitucionApoyo.objects.create(
            nombre="Institución estadística uno",
            siglas="IEU",
        )
        cls.institucion_dos = InstitucionApoyo.objects.create(
            nombre="Institución estadística dos",
            siglas="IED",
        )
        cls.incidente_uno = cls.crear_incidente(
            fecha_hora_reporte=fecha_hora(2026, 9, 1),
            tipo_incidente="Tránsito",
            prioridad="Alta",
            operador=cls.operador_uno,
            estado=Incidente.Estado.PENDIENTE,
        )
        cls.incidente_dos = cls.crear_incidente(
            fecha_hora_reporte=fecha_hora(2026, 9, 2),
            tipo_incidente="Tránsito",
            prioridad="Media",
            operador=cls.operador_uno,
            estado=Incidente.Estado.EN_SEGUIMIENTO,
        )
        cls.incidente_tres = cls.crear_incidente(
            fecha_hora_reporte=fecha_hora(2026, 9, 3),
            tipo_incidente="Seguridad",
            prioridad="Alta",
            operador=cls.operador_dos,
            estado=Incidente.Estado.CERRADO,
        )
        cls.incidente_fuera = cls.crear_incidente(
            fecha_hora_reporte=fecha_hora(2026, 9, 10),
            tipo_incidente="Otro",
            prioridad="Baja",
            operador=cls.operador_dos,
            estado=Incidente.Estado.CERRADO,
        )

        ParticipacionInstitucion.objects.create(
            incidente=cls.incidente_uno,
            institucion=cls.institucion_uno,
        )
        ParticipacionInstitucion.objects.create(
            incidente=cls.incidente_uno,
            institucion=cls.institucion_dos,
        )
        ParticipacionInstitucion.objects.create(
            incidente=cls.incidente_dos,
            institucion=cls.institucion_uno,
        )

        SeguimientoIncidente.objects.create(
            incidente=cls.incidente_uno,
            usuario=cls.operador_uno,
            observacion="Primer seguimiento estadístico.",
            estado_anterior=Incidente.Estado.PENDIENTE,
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        SeguimientoIncidente.objects.create(
            incidente=cls.incidente_dos,
            usuario=cls.operador_uno,
            observacion="Segundo seguimiento estadístico.",
            estado_anterior=Incidente.Estado.PENDIENTE,
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        SeguimientoIncidente.objects.create(
            incidente=cls.incidente_fuera,
            usuario=cls.operador_dos,
            observacion="Seguimiento fuera del período.",
            estado_anterior=Incidente.Estado.PENDIENTE,
            estado_nuevo=Incidente.Estado.CERRADO,
        )
        EvidenciaIncidente.objects.create(
            incidente=cls.incidente_tres,
            archivo="evidencias/prueba.jpg",
            tipo=EvidenciaIncidente.Tipo.FOTO,
            usuario=cls.operador_dos,
        )
        EvidenciaIncidente.objects.create(
            incidente=cls.incidente_fuera,
            archivo="evidencias/fuera_uno.jpg",
            tipo=EvidenciaIncidente.Tipo.FOTO,
            usuario=cls.operador_dos,
        )
        EvidenciaIncidente.objects.create(
            incidente=cls.incidente_fuera,
            archivo="evidencias/fuera_dos.pdf",
            tipo=EvidenciaIncidente.Tipo.DOCUMENTO,
            usuario=cls.operador_dos,
        )

    @classmethod
    def crear_incidente(
        cls,
        fecha_hora_reporte,
        tipo_incidente,
        prioridad,
        operador,
        estado,
    ):
        return Incidente.objects.create(
            fecha_hora_reporte=fecha_hora_reporte,
            ubicacion=f"Ubicación {tipo_incidente}",
            tipo_incidente=tipo_incidente,
            prioridad=prioridad,
            descripcion=f"Descripción {tipo_incidente}",
            operador_responsable=operador,
            estado=estado,
        )

    def ids(self, queryset):
        return list(queryset.values_list("id", flat=True))

    def test_resumen_con_incidentes_en_diferentes_estados(self):
        resumen = obtener_resumen_incidentes()

        self.assertEqual(resumen["total_incidentes"], 4)
        self.assertEqual(resumen["pendientes"], 1)
        self.assertEqual(resumen["en_seguimiento"], 1)
        self.assertEqual(resumen["cerrados"], 2)
        self.assertEqual(resumen["porcentaje_cerrados"], 50)

    def test_conteo_por_estado_incluye_valores_cero(self):
        resultado = obtener_incidentes_por_estado(
            fecha_desde=date(2026, 9, 1),
            fecha_hasta=date(2026, 9, 1),
        )

        self.assertEqual(resultado[Incidente.Estado.PENDIENTE], 1)
        self.assertEqual(resultado[Incidente.Estado.EN_SEGUIMIENTO], 0)
        self.assertEqual(resultado[Incidente.Estado.CERRADO], 0)

    def test_conteo_por_tipo(self):
        resultado = obtener_incidentes_por_tipo()

        self.assertEqual(
            resultado,
            [
                {"tipo_incidente": "Tránsito", "cantidad": 2},
                {"tipo_incidente": "Otro", "cantidad": 1},
                {"tipo_incidente": "Seguridad", "cantidad": 1},
            ],
        )

    def test_conteo_por_prioridad(self):
        resultado = obtener_incidentes_por_prioridad()

        self.assertEqual(
            resultado,
            [
                {"prioridad": "Alta", "cantidad": 2},
                {"prioridad": "Baja", "cantidad": 1},
                {"prioridad": "Media", "cantidad": 1},
            ],
        )

    def test_conteo_por_operador(self):
        resultado = obtener_incidentes_por_operador()

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]["cantidad"], 2)
        self.assertEqual(resultado[0]["username"], "operador_reporte_dos")
        self.assertEqual(resultado[0]["nombres"], "Segundo")
        self.assertEqual(resultado[0]["apellidos"], "Operador")
        self.assertNotIn("email", resultado[0])
        self.assertNotIn("password", resultado[0])

    def test_conteo_por_institucion(self):
        resultado = obtener_incidentes_por_institucion()

        self.assertEqual(resultado[0]["institucion_id"], self.institucion_uno.pk)
        self.assertEqual(resultado[0]["cantidad"], 2)
        self.assertEqual(resultado[0]["nombre"], self.institucion_uno.nombre)
        self.assertEqual(resultado[0]["siglas"], "IEU")

    def test_incidente_con_varias_instituciones_cuenta_en_cada_una(self):
        resultado = {
            fila["institucion_id"]: fila["cantidad"]
            for fila in obtener_incidentes_por_institucion()
        }

        self.assertEqual(resultado[self.institucion_uno.pk], 2)
        self.assertEqual(resultado[self.institucion_dos.pk], 1)

    def test_filtro_fecha_desde(self):
        resultado = buscar_incidentes(fecha_desde=date(2026, 9, 3))

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_fuera.pk, self.incidente_tres.pk],
        )

    def test_filtro_fecha_hasta(self):
        resultado = buscar_incidentes(fecha_hasta=date(2026, 9, 2))

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_dos.pk, self.incidente_uno.pk],
        )

    def test_filtro_rango_completo(self):
        resultado = buscar_incidentes(
            fecha_desde=date(2026, 9, 2),
            fecha_hasta=date(2026, 9, 3),
        )

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_tres.pk, self.incidente_dos.pk],
        )

    def test_rechazar_rango_invalido(self):
        with self.assertRaisesMessage(
            ValidationError,
            "La fecha inicial no puede ser posterior",
        ):
            obtener_resumen_incidentes(
                fecha_desde=date(2026, 9, 3),
                fecha_hasta=date(2026, 9, 2),
            )

    def test_agrupacion_por_dia(self):
        resultado = obtener_incidentes_por_dia()

        self.assertEqual(
            resultado,
            [
                {"fecha": date(2026, 9, 1), "cantidad": 1},
                {"fecha": date(2026, 9, 2), "cantidad": 1},
                {"fecha": date(2026, 9, 3), "cantidad": 1},
                {"fecha": date(2026, 9, 10), "cantidad": 1},
            ],
        )

    def test_buscar_por_estado(self):
        resultado = buscar_incidentes(estado=Incidente.Estado.CERRADO)

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_fuera.pk, self.incidente_tres.pk],
        )

    def test_buscar_rechaza_estado_invalido(self):
        with self.assertRaisesMessage(
            ValidationError,
            "El estado indicado no es válido",
        ):
            buscar_incidentes(estado="ESTADO_INEXISTENTE")

    def test_buscar_por_tipo(self):
        resultado = buscar_incidentes(tipo="Tránsito")

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_dos.pk, self.incidente_uno.pk],
        )

    def test_buscar_por_prioridad(self):
        resultado = buscar_incidentes(prioridad="Alta")

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_tres.pk, self.incidente_uno.pk],
        )

    def test_buscar_por_operador(self):
        resultado = buscar_incidentes(operador_id=self.operador_uno.pk)

        self.assertEqual(
            self.ids(resultado),
            [self.incidente_dos.pk, self.incidente_uno.pk],
        )

    def test_buscar_por_institucion(self):
        resultado = buscar_incidentes(
            institucion_id=self.institucion_dos.pk
        )

        self.assertEqual(self.ids(resultado), [self.incidente_uno.pk])

    def test_buscar_con_varios_filtros(self):
        resultado = buscar_incidentes(
            fecha_desde=date(2026, 9, 1),
            fecha_hasta=date(2026, 9, 2),
            estado=Incidente.Estado.PENDIENTE,
            tipo="Tránsito",
            prioridad="Alta",
            operador_id=self.operador_uno.pk,
            institucion_id=self.institucion_dos.pk,
        )

        self.assertEqual(self.ids(resultado), [self.incidente_uno.pk])

    def test_totales_relacionados_respetan_periodo(self):
        resumen = obtener_resumen_incidentes(
            fecha_desde=date(2026, 9, 1),
            fecha_hasta=date(2026, 9, 3),
        )

        self.assertEqual(resumen["total_incidentes"], 3)
        self.assertEqual(resumen["total_seguimientos"], 2)
        self.assertEqual(resumen["total_evidencias"], 1)
