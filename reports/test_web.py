from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from incidents.models import (
    EvidenciaIncidente, Incidente, ParticipacionInstitucion,
    SeguimientoIncidente,
)
from operations.models import InstitucionApoyo


def fecha(dia):
    return timezone.make_aware(datetime(2026, 9, dia, 10, 0))


class ReportesWebTests(TestCase):
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
        cls.operador = cls.usuarios[PerfilUsuario.Rol.OPERADOR]
        cls.operador.email = "privado@example.com"
        cls.operador.save(update_fields=("email",))
        cls.otro_operador = User.objects.create_user(
            username="otro_operador", password="ClaveTemporal!123"
        )
        cls.institucion = InstitucionApoyo.objects.create(
            nombre="Bomberos", telefono="55559999"
        )
        cls.otra_institucion = InstitucionApoyo.objects.create(nombre="Policía")
        cls.i1 = cls.crear_incidente(1, "Tránsito", "Alta", Incidente.Estado.PENDIENTE, cls.operador)
        cls.i2 = cls.crear_incidente(2, "Tránsito", "Media", Incidente.Estado.EN_SEGUIMIENTO, cls.operador)
        cls.i3 = cls.crear_incidente(3, "Seguridad", "Alta", Incidente.Estado.CERRADO, cls.otro_operador)
        cls.i4 = cls.crear_incidente(10, "Otro", "Baja", Incidente.Estado.CERRADO, cls.otro_operador)
        ParticipacionInstitucion.objects.create(incidente=cls.i1, institucion=cls.institucion)
        ParticipacionInstitucion.objects.create(incidente=cls.i2, institucion=cls.institucion)
        ParticipacionInstitucion.objects.create(incidente=cls.i3, institucion=cls.otra_institucion)
        SeguimientoIncidente.objects.create(
            incidente=cls.i1, usuario=cls.operador, observacion="Seguimiento 1",
            estado_nuevo=Incidente.Estado.EN_SEGUIMIENTO,
        )
        SeguimientoIncidente.objects.create(
            incidente=cls.i2, usuario=cls.operador, observacion="Seguimiento 2",
            estado_nuevo=Incidente.Estado.CERRADO,
        )
        EvidenciaIncidente.objects.create(
            incidente=cls.i3, usuario=cls.otro_operador,
            archivo="evidencias/prueba.jpg", tipo=EvidenciaIncidente.Tipo.FOTO,
        )

    @classmethod
    def crear_incidente(cls, dia, tipo, prioridad, estado, operador):
        return Incidente.objects.create(
            fecha_hora_reporte=fecha(dia), ubicacion=f"Lugar {dia}",
            tipo_incidente=tipo, prioridad=prioridad,
            descripcion=f"Incidente {dia}", operador_responsable=operador,
            estado=estado,
        )

    def entrar(self, rol=PerfilUsuario.Rol.ADMINISTRADOR):
        self.client.force_login(self.usuarios[rol])

    def pagina(self, nombre="index", parametros=None):
        return self.client.get(reverse(f"reports:{nombre}"), parametros or {})

    def ids(self, respuesta):
        return [incidente.pk for incidente in respuesta.context["pagina"]]

    def test_a_login_obligatorio(self):
        for nombre in ("index", "incident_report"):
            self.assertEqual(self.pagina(nombre).status_code, 302)

    def test_b_c_d_e_roles_autorizados(self):
        for rol in (
            PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR,
            PerfilUsuario.Rol.CONSULTA, PerfilUsuario.Rol.AUDITOR,
        ):
            self.entrar(rol)
            for nombre in ("index", "incident_report"):
                self.assertEqual(self.pagina(nombre).status_code, 200)

    def test_f_operador_recibe_403(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        for nombre in ("index", "incident_report"):
            self.assertEqual(self.pagina(nombre).status_code, 403)

    def test_g_h_panel_vacio_indicadores_cero(self):
        Incidente.objects.all().delete()
        self.entrar()
        respuesta = self.pagina()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 0)
        self.assertEqual(respuesta.context["resumen"]["porcentaje_cerrados"], 0)
        self.assertContains(respuesta, "No hay datos disponibles para los filtros seleccionados.")
        self.assertEqual(respuesta.context["graficas"]["dia"]["values"], [])

    def test_i_indicadores_con_datos(self):
        self.entrar()
        resumen = self.pagina().context["resumen"]
        self.assertEqual(resumen["total_incidentes"], 4)
        self.assertEqual(resumen["pendientes"], 1)
        self.assertEqual(resumen["en_seguimiento"], 1)
        self.assertEqual(resumen["cerrados"], 2)
        self.assertEqual(resumen["porcentaje_cerrados"], 50)
        self.assertEqual(resumen["total_evidencias"], 1)
        self.assertEqual(resumen["total_seguimientos"], 2)

    def test_j_k_l_filtros_periodo(self):
        self.entrar()
        for parametros, total in (
            ({"fecha_desde": "2026-09-03"}, 2),
            ({"fecha_hasta": "2026-09-02"}, 2),
            ({"fecha_desde": "2026-09-02", "fecha_hasta": "2026-09-03"}, 2),
        ):
            respuesta = self.pagina(parametros=parametros)
            self.assertEqual(respuesta.context["resumen"]["total_incidentes"], total)
            self.assertEqual(respuesta.context["graficas"]["dia"]["values"], [1] * total)

    def test_m_rango_invalido_no_500(self):
        self.entrar()
        parametros = {"fecha_desde": "2026-09-10", "fecha_hasta": "2026-09-01"}
        for nombre in ("index", "incident_report"):
            respuesta = self.pagina(nombre, parametros)
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "La fecha final debe ser igual o posterior")
        self.assertEqual(self.pagina(parametros=parametros).context["resumen"]["total_incidentes"], 0)

    def test_n_o_p_graficas_estado_tipo_prioridad(self):
        self.entrar()
        graficas = self.pagina().context["graficas"]
        self.assertEqual(graficas["estado"]["values"], [0, 1, 1, 0, 2])
        self.assertEqual(dict(zip(graficas["tipo"]["labels"], graficas["tipo"]["values"]))["Tránsito"], 2)
        self.assertEqual(dict(zip(graficas["prioridad"]["labels"], graficas["prioridad"]["values"]))["Alta"], 2)

    def test_q_r_graficas_operador_institucion(self):
        self.entrar()
        graficas = self.pagina().context["graficas"]
        self.assertEqual(sorted(graficas["operador"]["values"]), [2, 2])
        self.assertEqual(dict(zip(graficas["institucion"]["labels"], graficas["institucion"]["values"]))["Bomberos"], 2)

    def test_panel_filtros_tambien_aplican_a_graficas(self):
        self.entrar()
        respuesta = self.pagina(parametros={"estado": Incidente.Estado.PENDIENTE})
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 1)
        self.assertEqual(respuesta.context["graficas"]["estado"]["values"], [0, 1, 0, 0, 0])
        self.assertEqual(respuesta.context["graficas"]["tipo"]["values"], [1])
        self.assertContains(respuesta, "Estado: Pendiente")

    def test_panel_filtro_institucion_respeta_indicadores(self):
        self.entrar()
        respuesta = self.pagina(parametros={"institucion": self.institucion.pk})
        self.assertEqual(respuesta.context["resumen"]["total_incidentes"], 2)
        self.assertEqual(respuesta.context["graficas"]["institucion"]["values"], [2])

    def test_s_consulta_historica_sin_filtros(self):
        self.entrar()
        respuesta = self.pagina("incident_report")
        self.assertEqual(self.ids(respuesta), [self.i4.pk, self.i3.pk, self.i2.pk, self.i1.pk])
        self.assertContains(respuesta, "Bomberos")

    def test_t_u_v_w_x_filtros_historicos(self):
        self.entrar()
        casos = (
            ({"estado": Incidente.Estado.PENDIENTE}, [self.i1.pk]),
            ({"tipo": "Seguridad"}, [self.i3.pk]),
            ({"prioridad": "Media"}, [self.i2.pk]),
            ({"operador": self.operador.pk}, [self.i2.pk, self.i1.pk]),
            ({"institucion": self.otra_institucion.pk}, [self.i3.pk]),
        )
        for parametros, esperados in casos:
            self.assertEqual(self.ids(self.pagina("incident_report", parametros)), esperados)

    def test_y_combinacion_filtros(self):
        self.entrar()
        parametros = {
            "fecha_desde": "2026-09-01", "fecha_hasta": "2026-09-02",
            "estado": Incidente.Estado.PENDIENTE, "tipo": "Tránsito",
            "prioridad": "Alta", "operador": self.operador.pk,
            "institucion": self.institucion.pk,
        }
        respuesta = self.pagina("incident_report", parametros)
        self.assertEqual(self.ids(respuesta), [self.i1.pk])
        self.assertEqual(len(respuesta.context["filtros_activos"]), 6)

    def test_z_paginacion_25(self):
        for dia in range(11, 38):
            Incidente.objects.create(
                fecha_hora_reporte=fecha(10), ubicacion=f"Lugar extra {dia}",
                tipo_incidente="Otro", prioridad="Baja", descripcion="Extra",
                operador_responsable=self.operador,
            )
        self.entrar()
        respuesta = self.pagina("incident_report")
        self.assertEqual(len(respuesta.context["pagina"].object_list), 25)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 31)

    def test_aa_datos_sensibles_no_aparecen(self):
        self.entrar()
        for nombre in ("index", "incident_report"):
            respuesta = self.pagina(nombre)
            self.assertNotContains(respuesta, self.operador.email)
            self.assertNotContains(respuesta, self.institucion.telefono)
            self.assertNotContains(respuesta, self.operador.password)

    def test_ab_graficas_json_seguro_sin_valores_ficticios(self):
        self.entrar()
        respuesta = self.pagina()
        self.assertContains(respuesta, 'id="datos-reportes"')
        self.assertContains(respuesta, 'type="application/json"')
        self.assertEqual(sum(respuesta.context["graficas"]["dia"]["values"]), 4)
        self.assertEqual(sum(respuesta.context["graficas"]["tipo"]["values"]), 4)

    def test_consulta_vacia(self):
        self.entrar()
        respuesta = self.pagina("incident_report", {"fecha_desde": "2035-01-01"})
        self.assertContains(respuesta, "No se encontraron incidentes.")

    def test_filtros_invalidos_y_xss_no_generan_500(self):
        self.entrar()
        for parametros in (
            {"estado": "INVENTADO"}, {"operador": "1 OR 1=1"},
            {"tipo": "<script>alert(1)</script>"},
        ):
            respuesta = self.pagina(parametros=parametros)
            self.assertEqual(respuesta.status_code, 200)
        respuesta = self.pagina(parametros={"tipo": "<script>alert(1)</script>"})
        self.assertNotContains(respuesta, "<script>alert(1)</script>")
