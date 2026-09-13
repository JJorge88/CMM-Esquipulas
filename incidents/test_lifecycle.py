from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from reports.services import obtener_incidentes_por_estado, obtener_resumen_incidentes

from .forms import SeguimientoForm
from .models import Incidente, SeguimientoIncidente
from .services import registrar_seguimiento


def momento(hora):
    return timezone.make_aware(datetime(2026, 9, 1, hora, 0))


class CicloVidaIncidenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="operador_ciclo", password="ClaveTemporal!123"
        )
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=momento(10), ubicacion="Centro",
            tipo_incidente="Tránsito", prioridad="Alta",
            descripcion="Incidente del ciclo", operador_responsable=cls.usuario,
        )

    def seguir(self, estado, hora, **extras):
        return registrar_seguimiento(
            incidente=self.incidente, usuario=self.usuario,
            observacion="Avance del incidente", estado_nuevo=estado,
            fecha_hora=momento(hora), **extras,
        )

    def test_estado_inicial_registrado(self):
        self.assertEqual(self.incidente.estado, Incidente.Estado.REGISTRADO)
        self.assertIsNone(self.incidente.fecha_inicio_atencion)
        self.assertIsNone(self.incidente.fecha_resolucion)
        self.assertIsNone(self.incidente.fecha_cierre)

    def test_registrado_pasa_a_pendiente(self):
        seguimiento = self.seguir(Incidente.Estado.PENDIENTE, 11)
        self.incidente.refresh_from_db()
        self.assertEqual(seguimiento.estado_anterior, Incidente.Estado.REGISTRADO)
        self.assertEqual(self.incidente.estado, Incidente.Estado.PENDIENTE)
        self.assertIsNone(self.incidente.fecha_inicio_atencion)

    def test_registrado_pasa_directo_a_seguimiento(self):
        seguimiento = self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.incidente.refresh_from_db()
        self.assertEqual(seguimiento.estado_anterior, Incidente.Estado.REGISTRADO)
        self.assertEqual(self.incidente.fecha_inicio_atencion, momento(11))

    def test_pendiente_pasa_directo_a_resuelto_sin_inventar_atencion(self):
        self.seguir(Incidente.Estado.PENDIENTE, 11)
        self.seguir(Incidente.Estado.RESUELTO, 12)
        self.incidente.refresh_from_db()
        self.assertIsNone(self.incidente.fecha_inicio_atencion)
        self.assertEqual(self.incidente.fecha_resolucion, momento(12))

    def test_seguimiento_repetido_no_sobrescribe_inicio(self):
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 12)
        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.fecha_inicio_atencion, momento(11))
        self.assertEqual(self.incidente.seguimientos.count(), 2)

    def test_resuelto_y_cerrado_conservan_fechas_y_resultado(self):
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.seguir(Incidente.Estado.RESUELTO, 12)
        seguimiento = self.seguir(
            Incidente.Estado.CERRADO, 13,
            resultado_cierre="Atención finalizada sin daños personales.",
        )
        self.incidente.refresh_from_db()
        self.assertEqual(seguimiento.estado_anterior, Incidente.Estado.RESUELTO)
        self.assertEqual(self.incidente.fecha_inicio_atencion, momento(11))
        self.assertEqual(self.incidente.fecha_resolucion, momento(12))
        self.assertEqual(self.incidente.fecha_cierre, momento(13))
        self.assertEqual(
            self.incidente.resultado_cierre,
            "Atención finalizada sin daños personales.",
        )

    def test_rechaza_transiciones_arbitrarias(self):
        casos = (
            (Incidente.Estado.REGISTRADO, Incidente.Estado.RESUELTO),
            (Incidente.Estado.REGISTRADO, Incidente.Estado.CERRADO),
            (Incidente.Estado.PENDIENTE, Incidente.Estado.CERRADO),
            (Incidente.Estado.EN_SEGUIMIENTO, Incidente.Estado.PENDIENTE),
            (Incidente.Estado.RESUELTO, Incidente.Estado.EN_SEGUIMIENTO),
            (Incidente.Estado.CERRADO, Incidente.Estado.REGISTRADO),
        )
        for anterior, nuevo in casos:
            with self.subTest(anterior=anterior, nuevo=nuevo):
                incidente = Incidente.objects.create(
                    fecha_hora_reporte=momento(10), ubicacion="Otro",
                    tipo_incidente="Tránsito", prioridad="Alta",
                    descripcion="Caso inválido", operador_responsable=self.usuario,
                    estado=anterior,
                )
                with self.assertRaises(ValidationError):
                    registrar_seguimiento(
                        incidente=incidente, usuario=self.usuario,
                        observacion="Intento inválido", estado_nuevo=nuevo,
                    )
                incidente.refresh_from_db()
                self.assertEqual(incidente.estado, anterior)
                self.assertFalse(incidente.seguimientos.exists())

    def test_rechaza_cierre_sin_resultado_en_servicio_y_formulario(self):
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.seguir(Incidente.Estado.RESUELTO, 12)
        for resultado in (None, "", "   "):
            with self.subTest(resultado=resultado):
                with self.assertRaisesMessage(ValidationError, "Debe registrar el resultado"):
                    self.seguir(Incidente.Estado.CERRADO, 13, resultado_cierre=resultado)
        formulario = SeguimientoForm(
            {"observacion": "Cierre", "estado_nuevo": "CERRADO", "resultado_cierre": " "},
            estado_actual=Incidente.Estado.RESUELTO,
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("resultado_cierre", formulario.errors)
        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.estado, Incidente.Estado.RESUELTO)
        self.assertEqual(self.incidente.seguimientos.count(), 2)

    def test_cierre_web_muestra_y_guarda_resultado(self):
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.seguir(Incidente.Estado.RESUELTO, 12)
        self.client.force_login(self.usuario)
        url = reverse("incidents:detail", args=[self.incidente.pk])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'id="resultado-cierre-container"')
        self.assertContains(respuesta, "incident_detail.js")
        sin_resultado = self.client.post(url, {
            "accion": "seguimiento", "observacion": "Cerrar",
            "estado_nuevo": Incidente.Estado.CERRADO,
        })
        self.assertEqual(sin_resultado.status_code, 200)
        self.assertContains(sin_resultado, "Debe registrar el resultado")
        respuesta = self.client.post(url, {
            "accion": "seguimiento", "observacion": "Cerrar",
            "estado_nuevo": Incidente.Estado.CERRADO,
            "resultado_cierre": "Se restableció la circulación.",
        })
        self.assertRedirects(respuesta, url)
        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.resultado_cierre, "Se restableció la circulación.")
        self.assertContains(self.client.get(url), "Se restableció la circulación.")

    def test_legacy_cerrado_sin_resultado_o_fechas_permanece_usable(self):
        historico = Incidente.objects.create(
            fecha_hora_reporte=momento(10), ubicacion="Histórico",
            tipo_incidente="Otro", prioridad="Alta", descripcion="Anterior",
            operador_responsable=self.usuario, estado=Incidente.Estado.CERRADO,
        )
        historico.full_clean()
        self.assertIsNone(historico.fecha_inicio_atencion)
        self.assertIsNone(historico.fecha_resolucion)
        self.assertIsNone(historico.fecha_cierre)
        self.assertEqual(historico.resultado_cierre, "")
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.get(reverse("incidents:detail", args=[historico.pk])).status_code,
            200,
        )

    def test_modelo_exige_resultado_al_entrar_a_cerrado(self):
        self.incidente.estado = Incidente.Estado.CERRADO
        with self.assertRaisesMessage(ValidationError, "Debe registrar el resultado"):
            self.incidente.full_clean()

    def test_registro_historico_en_seguimiento_no_recibe_fecha_falsa(self):
        historico = Incidente.objects.create(
            fecha_hora_reporte=momento(10), ubicacion="Histórico en curso",
            tipo_incidente="Otro", prioridad="Alta", descripcion="Anterior",
            operador_responsable=self.usuario,
            estado=Incidente.Estado.EN_SEGUIMIENTO,
        )
        registrar_seguimiento(
            incidente=historico, usuario=self.usuario, observacion="Continúa",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO, fecha_hora=momento(13),
        )
        historico.refresh_from_db()
        self.assertIsNone(historico.fecha_inicio_atencion)

    def test_promedios_omiten_historicos_sin_fechas(self):
        self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.seguir(Incidente.Estado.RESUELTO, 12)
        self.seguir(
            Incidente.Estado.CERRADO, 13, resultado_cierre="Finalizado",
        )
        Incidente.objects.create(
            fecha_hora_reporte=momento(10), ubicacion="Histórico",
            tipo_incidente="Otro", prioridad="Alta", descripcion="Anterior",
            operador_responsable=self.usuario, estado=Incidente.Estado.CERRADO,
        )
        resumen = obtener_resumen_incidentes()
        self.assertEqual(resumen["registrados"], 0)
        self.assertEqual(resumen["cerrados"], 2)
        self.assertEqual(resumen["porcentaje_cerrados"], 100)
        self.assertEqual(resumen["tiempo_promedio_atencion"], timedelta(hours=1))
        self.assertEqual(resumen["tiempo_promedio_resolucion"], timedelta(hours=2))

    def test_dashboard_reportes_y_filtros_reconocen_estados(self):
        resuelto = Incidente.objects.create(
            fecha_hora_reporte=momento(10), ubicacion="Resuelto",
            tipo_incidente="Otro", prioridad="Media", descripcion="Resuelto",
            operador_responsable=self.usuario, estado=Incidente.Estado.RESUELTO,
        )
        self.assertEqual(
            obtener_incidentes_por_estado()[Incidente.Estado.RESUELTO], 1
        )
        self.client.force_login(self.usuario)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.context["resumen"]["registrados"], 1)
        self.assertEqual(dashboard.context["resumen"]["resueltos"], 1)
        listado = self.client.get(reverse("incidents:list"), {
            "estado": Incidente.Estado.RESUELTO,
        })
        self.assertEqual([obj.pk for obj in listado.context["pagina"]], [resuelto.pk])
        perfil = self.usuario.perfil
        perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        perfil.save(update_fields=("rol",))
        reporte = self.client.get(reverse("reports:index"))
        self.assertEqual(reporte.context["resumen"]["registrados"], 1)
        self.assertEqual(reporte.context["resumen"]["resueltos"], 1)
        self.assertEqual(
            reporte.context["graficas"]["estado"]["values"],
            [1, 0, 0, 1, 0],
        )
        historico = self.client.get(reverse("reports:incident_report"), {
            "estado": Incidente.Estado.RESUELTO,
        })
        self.assertEqual([obj.pk for obj in historico.context["pagina"]], [resuelto.pk])

    def test_seguimiento_guarda_timestamp_igual_a_fecha_operativa(self):
        seguimiento = self.seguir(Incidente.Estado.EN_SEGUIMIENTO, 11)
        self.incidente.refresh_from_db()
        self.assertEqual(seguimiento.fecha_hora, momento(11))
        self.assertEqual(self.incidente.fecha_inicio_atencion, seguimiento.fecha_hora)

    def test_transicion_cierre_no_sobrescribe_fecha_preexistente(self):
        self.incidente.estado = Incidente.Estado.RESUELTO
        self.incidente.fecha_cierre = momento(12)
        self.incidente.save(update_fields=("estado", "fecha_cierre"))
        self.seguir(
            Incidente.Estado.CERRADO, 13,
            resultado_cierre="Resultado documentado",
        )
        self.incidente.refresh_from_db()
        self.assertEqual(self.incidente.fecha_cierre, momento(12))
        self.assertEqual(self.incidente.resultado_cierre, "Resultado documentado")


class MigracionHistoricaTests(TransactionTestCase):
    def test_conserva_estados_y_no_inventa_fechas(self):
        anterior = ("incidents", "0004_participacioninstitucion_and_more")
        actual = ("incidents", "0005_incidente_fecha_cierre_and_more")
        try:
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate([anterior])
            modelos_anteriores = ejecutor.loader.project_state([anterior]).apps
            UsuarioAnterior = modelos_anteriores.get_model("auth", "User")
            IncidenteAnterior = modelos_anteriores.get_model("incidents", "Incidente")
            usuario = UsuarioAnterior.objects.create(username="usuario_historico")
            ids = []
            for estado in ("PENDIENTE", "EN_SEGUIMIENTO", "CERRADO"):
                incidente = IncidenteAnterior.objects.create(
                    fecha_hora_reporte=momento(10), ubicacion="Archivo histórico",
                    tipo_incidente="Otro", prioridad="Alta", descripcion="Anterior",
                    operador_responsable_id=usuario.pk, estado=estado,
                )
                ids.append(incidente.pk)
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate([actual])
            modelos_actuales = ejecutor.loader.project_state([actual]).apps
            IncidenteActual = modelos_actuales.get_model("incidents", "Incidente")
            incidentes = list(IncidenteActual.objects.filter(pk__in=ids).order_by("pk"))
            self.assertEqual(
                [incidente.estado for incidente in incidentes],
                ["PENDIENTE", "EN_SEGUIMIENTO", "CERRADO"],
            )
            for incidente in incidentes:
                self.assertIsNone(incidente.fecha_inicio_atencion)
                self.assertIsNone(incidente.fecha_resolucion)
                self.assertIsNone(incidente.fecha_cierre)
                self.assertEqual(incidente.resultado_cierre, "")
        finally:
            MigrationExecutor(connection).migrate([actual])
