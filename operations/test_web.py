from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import PerfilUsuario

from .forms import AsignacionForm
from .models import AsignacionTurno, Turno


class AdministracionVisualTurnosTests(TestCase):
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
        cls.otro_operador = User.objects.create_user(
            username="otro_operador", password="ClaveTemporal!123"
        )
        cls.turno = Turno.objects.create(
            nombre="Matutino", hora_inicio=time(7), hora_fin=time(15)
        )

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def asignar(self, operador=None, turno=None, fecha=date(2026, 9, 12), observacion=""):
        return AsignacionTurno.objects.create(
            operador=operador or self.usuarios[PerfilUsuario.Rol.OPERADOR],
            turno=turno or self.turno, fecha=fecha, observacion=observacion,
        )

    def datos_turno(self, **cambios):
        return {**{"nombre": "Nocturno", "hora_inicio": "22:00", "hora_fin": "06:00", "activo": "on"}, **cambios}

    def datos_asignacion(self, **cambios):
        return {**{
            "operador": self.usuarios[PerfilUsuario.Rol.OPERADOR].pk,
            "turno": self.turno.pk, "fecha": "2026-09-12", "observacion": "Prueba",
        }, **cambios}

    def test_a_login_obligatorio(self):
        for nombre in ("turn_list", "turn_create", "assignment_list", "assignment_create"):
            self.assertEqual(self.client.get(reverse(f"operations:{nombre}")).status_code, 302)

    def test_b_c_administrador_y_coordinador_ven_turnos(self):
        for rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR):
            self.entrar(rol)
            self.assertEqual(self.client.get(reverse("operations:turn_list")).status_code, 200)

    def test_d_operador_no_puede_crear_turnos(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        self.assertEqual(self.client.post(reverse("operations:turn_create"), self.datos_turno()).status_code, 403)
        self.assertFalse(Turno.objects.filter(nombre="Nocturno").exists())

    def test_e_consulta_no_tiene_acceso(self):
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        for nombre in ("turn_list", "turn_create", "assignment_list", "assignment_create"):
            self.assertEqual(self.client.get(reverse(f"operations:{nombre}")).status_code, 403)

    def test_f_auditor_solo_lectura(self):
        self.entrar(PerfilUsuario.Rol.AUDITOR)
        respuesta = self.client.get(reverse("operations:turn_list"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, reverse("operations:turn_create"))
        self.assertEqual(self.client.post(reverse("operations:turn_create"), self.datos_turno()).status_code, 403)

    def test_g_administrador_crea_turno(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:turn_create"), self.datos_turno())
        self.assertRedirects(respuesta, reverse("operations:turn_list"))
        self.assertTrue(Turno.objects.filter(nombre="Nocturno").exists())

    def test_h_coordinador_edita_turno(self):
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        respuesta = self.client.post(reverse("operations:turn_update", args=[self.turno.pk]), self.datos_turno(nombre="Mañana"))
        self.assertRedirects(respuesta, reverse("operations:turn_list"))
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.nombre, "Mañana")

    def test_i_turno_nocturno_permitido(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        self.client.post(reverse("operations:turn_create"), self.datos_turno())
        nocturno = Turno.objects.get(nombre="Nocturno")
        self.assertGreater(nocturno.hora_inicio, nocturno.hora_fin)

    def test_j_listado_muestra_turno(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        self.assertContains(self.client.get(reverse("operations:turn_list")), "Matutino")

    def test_busqueda_estado_y_paginacion_de_turnos(self):
        for indice in range(21):
            Turno.objects.create(
                nombre=f"Auxiliar {indice:02d}", hora_inicio=time(8),
                hora_fin=time(16), activo=indice != 0,
            )
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        url = reverse("operations:turn_list")
        respuesta = self.client.get(url)
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 22)
        self.assertEqual(self.client.get(url, {"nombre": "Auxiliar 00"}).context["pagina"].paginator.count, 1)
        self.assertEqual(self.client.get(url, {"activo": "no"}).context["pagina"].paginator.count, 1)

    def test_k_l_gestores_crean_asignacion(self):
        for indice, rol in enumerate((PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR)):
            self.entrar(rol)
            fecha = f"2026-09-{12 + indice:02d}"
            respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(fecha=fecha))
            self.assertRedirects(respuesta, reverse("operations:assignment_list"))
        self.assertEqual(AsignacionTurno.objects.count(), 2)

    def test_m_selector_solo_operadores_activos(self):
        inactivo = User.objects.create_user(username="inactivo", password="ClaveTemporal!123", is_active=False)
        formulario = AsignacionForm()
        ids = set(formulario.fields["operador"].queryset.values_list("pk", flat=True))
        self.assertIn(self.usuarios[PerfilUsuario.Rol.OPERADOR].pk, ids)
        self.assertIn(self.otro_operador.pk, ids)
        self.assertNotIn(inactivo.pk, ids)
        self.assertNotIn(self.usuarios[PerfilUsuario.Rol.ADMINISTRADOR].pk, ids)

    def test_n_post_manipulado_rechaza_otro_rol(self):
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(operador=self.usuarios[PerfilUsuario.Rol.COORDINADOR].pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(AsignacionTurno.objects.count(), 0)

    def test_o_rechaza_operador_inactivo(self):
        inactivo = User.objects.create_user(username="inactivo", password="ClaveTemporal!123", is_active=False)
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(operador=inactivo.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(AsignacionTurno.objects.count(), 0)

    def test_p_rechaza_duplicado(self):
        self.asignar()
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(AsignacionTurno.objects.count(), 1)
        self.assertTrue(respuesta.context["formulario"].errors)

    def test_q_rechaza_solapamiento(self):
        self.asignar()
        solapado = Turno.objects.create(nombre="Solapado", hora_inicio=time(14), hora_fin=time(20))
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(turno=solapado.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "se solapa")
        self.assertEqual(AsignacionTurno.objects.count(), 1)

    def test_r_permite_consecutivos(self):
        self.asignar()
        siguiente = Turno.objects.create(nombre="Vespertino", hora_inicio=time(15), hora_fin=time(22))
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(turno=siguiente.pk))
        self.assertRedirects(respuesta, reverse("operations:assignment_list"))

    def test_s_cruce_medianoche_rechaza_solapamiento_dia_siguiente(self):
        nocturno = Turno.objects.create(nombre="Nocturno", hora_inicio=time(22), hora_fin=time(6))
        temprano = Turno.objects.create(nombre="Temprano", hora_inicio=time(5), hora_fin=time(8))
        self.asignar(turno=nocturno)
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.post(reverse("operations:assignment_create"), self.datos_asignacion(turno=temprano.pk, fecha="2026-09-13"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "se solapa")

    def test_t_u_operador_solo_ve_sus_asignaciones(self):
        self.asignar(observacion="Propia")
        self.asignar(operador=self.otro_operador, observacion="Ajena")
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.get(reverse("operations:assignment_list"), {"operador": self.otro_operador.pk})
        self.assertEqual(respuesta.context["pagina"].paginator.count, 1)
        self.assertContains(respuesta, "Propia")
        self.assertNotContains(respuesta, "Ajena")

    def test_v_operador_no_edita_asignacion(self):
        asignacion = self.asignar()
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        self.assertEqual(self.client.post(reverse("operations:assignment_update", args=[asignacion.pk]), self.datos_asignacion()).status_code, 403)

    def test_coordinador_edita_asignacion(self):
        asignacion = self.asignar()
        self.entrar(PerfilUsuario.Rol.COORDINADOR)
        respuesta = self.client.post(
            reverse("operations:assignment_update", args=[asignacion.pk]),
            self.datos_asignacion(observacion="Actualizada"),
        )
        self.assertRedirects(respuesta, reverse("operations:assignment_list"))
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.observacion, "Actualizada")

    def test_w_auditor_ve_todo_sin_acciones(self):
        self.asignar(observacion="Una")
        self.asignar(operador=self.otro_operador, observacion="Otra")
        self.entrar(PerfilUsuario.Rol.AUDITOR)
        respuesta = self.client.get(reverse("operations:assignment_list"))
        self.assertEqual(respuesta.context["pagina"].paginator.count, 2)
        self.assertNotContains(respuesta, reverse("operations:assignment_create"))
        self.assertEqual(self.client.get(reverse("operations:assignment_update", args=[1])).status_code, 403)

    def test_x_y_z_filtros_asignaciones(self):
        otro_turno = Turno.objects.create(nombre="Tarde", hora_inicio=time(15), hora_fin=time(22))
        self.asignar()
        self.asignar(operador=self.otro_operador, turno=otro_turno, fecha=date(2026, 9, 13))
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        url = reverse("operations:assignment_list")
        for parametros in ({"fecha_desde": "2026-09-13"}, {"fecha_hasta": "2026-09-12"}, {"turno": otro_turno.pk}, {"operador": self.otro_operador.pk}):
            self.assertEqual(self.client.get(url, parametros).context["pagina"].paginator.count, 1)

    def test_aa_paginacion_20(self):
        for indice in range(21):
            self.asignar(fecha=date(2026, 8, 1 + indice))
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.get(reverse("operations:assignment_list"))
        self.assertEqual(len(respuesta.context["pagina"].object_list), 20)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 21)

    def test_ab_no_expone_hash_en_html(self):
        self.asignar()
        self.entrar(PerfilUsuario.Rol.ADMINISTRADOR)
        respuesta = self.client.get(reverse("operations:assignment_list"))
        self.assertNotContains(respuesta, self.usuarios[PerfilUsuario.Rol.OPERADOR].password)
        self.assertNotContains(respuesta, "ClaveTemporal!123")
