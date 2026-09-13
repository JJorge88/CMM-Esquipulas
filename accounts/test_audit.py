import tempfile
from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from incidents.models import EvidenciaIncidente, Incidente
from operations.models import (
    AsignacionTurno, InstitucionApoyo, RecursoInstitucional, TipoRecurso, Turno,
)

from .audit import registrar_auditoria
from .models import AuditoriaAccion, PerfilUsuario


class AuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {}
        for rol in PerfilUsuario.Rol:
            usuario = User.objects.create_user(
                username=f"aud_{rol.value.lower()}", password="ClavePrivada-9831!"
            )
            usuario.perfil.rol = rol
            usuario.perfil.save(update_fields=("rol",))
            cls.usuarios[rol] = usuario
        cls.operador = cls.usuarios[PerfilUsuario.Rol.OPERADOR]
        cls.admin = cls.usuarios[PerfilUsuario.Rol.ADMINISTRADOR]
        cls.institucion = InstitucionApoyo.objects.create(nombre="Bomberos")
        cls.turno = Turno.objects.create(
            nombre="Matutino", hora_inicio=time(7), hora_fin=time(15)
        )
        cls.tipo = TipoRecurso.objects.create(nombre="Cámara")
        cls.incidente = Incidente.objects.create(
            fecha_hora_reporte=timezone.now(), ubicacion="Centro",
            tipo_incidente="Accidente", prioridad="Alta",
            descripcion="Reporte", operador_responsable=cls.operador,
            estado=Incidente.Estado.PENDIENTE,
        )

    def entrar(self, rol=PerfilUsuario.Rol.ADMINISTRADOR):
        self.client.force_login(self.usuarios[rol])

    def registro(self, **campos):
        return registrar_auditoria(
            usuario=campos.pop("usuario", self.admin),
            accion=campos.pop("accion", "CREAR"),
            modulo=campos.pop("modulo", "INCIDENTES"),
            entidad=campos.pop("entidad", "Incidente"),
            entidad_id=campos.pop("entidad_id", str(self.incidente.pk)),
            descripcion=campos.pop("descripcion", "Registro de prueba"),
            **campos,
        )

    def test_servicio_guarda_metadatos_y_solo_remote_addr(self):
        request = RequestFactory().post("/prueba/", HTTP_X_FORWARDED_FOR="10.1.2.3")
        request.META["REMOTE_ADDR"] = "127.0.0.4"
        registro = self.registro(request=request)
        self.assertEqual((registro.ip, registro.metodo_http, registro.ruta),
                         ("127.0.0.4", "POST", "/prueba/"))
        self.assertIsNotNone(registro.fecha_hora)

    def test_usuario_eliminado_queda_nulo(self):
        temporal = User.objects.create_user(username="aud_temporal")
        registro = self.registro(usuario=temporal)
        temporal.delete()
        registro.refresh_from_db()
        self.assertIsNone(registro.usuario)

    def test_no_guarda_password_hash_ni_datos_de_request(self):
        request = RequestFactory().post(
            "/prueba/", {"password": "SECRETO-PRUEBA"},
            HTTP_AUTHORIZATION="Bearer TOKEN-PRUEBA", HTTP_COOKIE="sessionid=SECRETO",
        )
        registro = self.registro(request=request)
        self.assertNotIn("SECRETO", str(vars(registro)))
        self.assertNotIn(self.admin.password, str(vars(registro)))
        self.assertNotIn("TOKEN-PRUEBA", str(vars(registro)))

    def test_admin_es_de_consulta(self):
        configuracion = admin.site._registry[AuditoriaAccion]
        request = RequestFactory().get("/admin/accounts/auditoriaaccion/")
        self.assertFalse(configuracion.has_add_permission(request))
        self.assertFalse(configuracion.has_change_permission(request))
        self.assertFalse(configuracion.has_delete_permission(request))
        self.assertIn("descripcion", configuracion.readonly_fields)

    def test_crear_editar_y_desactivar_usuario(self):
        self.entrar()
        datos = {
            "username": "aud_nuevo", "first_name": "Nuevo", "last_name": "Usuario",
            "email": "nuevo@example.com", "telefono": "12345678",
            "rol": PerfilUsuario.Rol.OPERADOR, "estado_activo": "on",
            "password1": "NuevaClaveSegura-9371!", "password2": "NuevaClaveSegura-9371!",
        }
        self.assertEqual(self.client.post(reverse("accounts:user_create"), datos).status_code, 302)
        nuevo = User.objects.get(username="aud_nuevo")
        self.assertTrue(AuditoriaAccion.objects.filter(modulo="USUARIOS", accion="CREAR", entidad_id=str(nuevo.pk)).exists())
        datos.pop("password1")
        datos.pop("password2")
        datos["first_name"] = "Editado"
        self.assertEqual(self.client.post(reverse("accounts:user_update", args=[nuevo.pk]), datos).status_code, 302)
        self.assertTrue(AuditoriaAccion.objects.filter(modulo="USUARIOS", accion="EDITAR", entidad_id=str(nuevo.pk)).exists())
        self.assertEqual(self.client.post(reverse("accounts:user_toggle_status", args=[nuevo.pk])).status_code, 302)
        self.assertTrue(AuditoriaAccion.objects.filter(modulo="USUARIOS", accion="DESACTIVAR", entidad_id=str(nuevo.pk)).exists())
        self.assertFalse(AuditoriaAccion.objects.filter(descripcion__icontains="NuevaClaveSegura").exists())

    def test_crear_incidente(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        datos = {
            "fecha_hora_reporte": "2026-09-12T14:30", "ubicacion": "Norte",
            "tipo_incidente": "Aviso", "prioridad": "Pendiente de evaluar",
            "descripcion": "Aviso ciudadano",
        }
        self.assertEqual(self.client.post(reverse("incidents:create"), datos).status_code, 302)
        nuevo = Incidente.objects.get(ubicacion="Norte")
        self.assertTrue(AuditoriaAccion.objects.filter(modulo="INCIDENTES", accion="CREAR", entidad_id=str(nuevo.pk)).exists())

    def test_seguimiento_y_cambio_de_estado(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.post(reverse("incidents:detail", args=[self.incidente.pk]), {
            "accion": "seguimiento", "observacion": "Se inició atención",
            "estado_nuevo": Incidente.Estado.EN_SEGUIMIENTO,
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(AuditoriaAccion.objects.filter(accion="AGREGAR_SEGUIMIENTO").exists())
        cambio = AuditoriaAccion.objects.get(accion="CAMBIAR_ESTADO")
        self.assertIn("PENDIENTE", cambio.descripcion)
        self.assertIn("EN_SEGUIMIENTO", cambio.descripcion)

    def test_cargar_evidencia(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        with tempfile.TemporaryDirectory() as directorio, override_settings(MEDIA_ROOT=directorio):
            respuesta = self.client.post(reverse("incidents:detail", args=[self.incidente.pk]), {
                "accion": "evidencia", "tipo": EvidenciaIncidente.Tipo.FOTO,
                "archivo": SimpleUploadedFile("auditoria.jpg", b"contenido privado"),
                "descripcion": "Foto", "fecha_hora": "2026-09-12T14:30",
            })
        self.assertEqual(respuesta.status_code, 302)
        registro = AuditoriaAccion.objects.get(accion="CARGAR_EVIDENCIA")
        self.assertNotIn("contenido privado", registro.descripcion)
        self.assertNotIn("auditoria.jpg", registro.descripcion)

    def test_asignar_institucion(self):
        self.entrar(PerfilUsuario.Rol.OPERADOR)
        respuesta = self.client.post(reverse("incidents:detail", args=[self.incidente.pk]), {
            "accion": "institucion", "institucion": self.institucion.pk,
            "observacion": "Apoyo", "fecha_asignacion": "2026-09-12T14:30",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(AuditoriaAccion.objects.filter(accion="ASIGNAR_INSTITUCION").exists())

    def test_operaciones_crean_auditoria(self):
        self.entrar()
        solicitudes = (
            ("turn_create", {"nombre": "Nocturno", "hora_inicio": "22:00", "hora_fin": "06:00", "activo": "on"}, "TURNOS"),
            ("assignment_create", {"operador": self.operador.pk, "turno": self.turno.pk, "fecha": "2026-09-12", "observacion": "Prueba"}, "ASIGNACIONES"),
            ("institution_create", {"nombre": "Policía Municipal", "siglas": "PM", "telefono": "55550000", "correo_electronico": "", "direccion": "", "activa": "on"}, "INSTITUCIONES"),
            ("resource_type_create", {"nombre": "Radio", "descripcion": "Comunicación", "activo": "on"}, "RECURSOS"),
            ("resource_create", {"nombre": "Cámara Norte", "tipo": self.tipo.pk, "codigo_interno": "CAM-02", "marca": "M", "modelo": "X", "numero_serie": "SERIE-02", "ubicacion": "Norte", "descripcion": "Operativa", "estado": "DISPONIBLE", "activo": "on"}, "RECURSOS"),
        )
        for nombre, datos, modulo in solicitudes:
            with self.subTest(nombre=nombre):
                respuesta = self.client.post(reverse(f"operations:{nombre}"), datos)
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(AuditoriaAccion.objects.filter(modulo=modulo, accion="CREAR").exists())

    def test_ediciones_y_cambios_de_estado_operativos(self):
        self.entrar()
        asignacion = AsignacionTurno.objects.create(
            operador=self.operador, turno=self.turno, fecha=date(2026, 9, 12)
        )
        recurso = RecursoInstitucional.objects.create(
            nombre="Cámara Central", tipo=self.tipo, codigo_interno="CAM-01",
            estado=RecursoInstitucional.Estado.DISPONIBLE,
        )
        solicitudes = (
            ("turn_update", self.turno.pk, {"nombre": "Mañana", "hora_inicio": "07:00", "hora_fin": "15:00", "activo": "on"}, "TURNOS", "EDITAR"),
            ("assignment_update", asignacion.pk, {"operador": self.operador.pk, "turno": self.turno.pk, "fecha": "2026-09-12", "observacion": "Cambio"}, "ASIGNACIONES", "EDITAR"),
            ("institution_update", self.institucion.pk, {"nombre": "Bomberos", "siglas": "BV", "telefono": "12345678", "correo_electronico": "", "direccion": "", "activa": "on"}, "INSTITUCIONES", "EDITAR"),
            ("institution_toggle_status", self.institucion.pk, {}, "INSTITUCIONES", "DESACTIVAR"),
            ("resource_update", recurso.pk, {"nombre": "Cámara Central", "tipo": self.tipo.pk, "codigo_interno": "CAM-01", "marca": "", "modelo": "", "numero_serie": "", "ubicacion": "Norte", "descripcion": "", "estado": RecursoInstitucional.Estado.DISPONIBLE, "activo": "on"}, "RECURSOS", "EDITAR"),
            ("resource_toggle_status", recurso.pk, {}, "RECURSOS", "DESACTIVAR"),
            ("resource_type_update", self.tipo.pk, {"nombre": "Cámara", "descripcion": "Vigilancia", "activo": "on"}, "RECURSOS", "EDITAR"),
        )
        for nombre, pk, datos, modulo, accion in solicitudes:
            with self.subTest(nombre=nombre):
                respuesta = self.client.post(reverse(f"operations:{nombre}", args=[pk]), datos)
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(AuditoriaAccion.objects.filter(
                    modulo=modulo, accion=accion, entidad_id=str(pk)
                ).exists())

    def test_formulario_invalido_y_permiso_denegado_no_auditan(self):
        self.entrar()
        self.assertEqual(self.client.post(reverse("operations:turn_create"), {}).status_code, 200)
        self.assertEqual(AuditoriaAccion.objects.count(), 0)
        self.entrar(PerfilUsuario.Rol.CONSULTA)
        self.assertEqual(self.client.post(reverse("operations:turn_create"), {}).status_code, 403)
        self.assertEqual(AuditoriaAccion.objects.count(), 0)

    def test_fallo_de_auditoria_revierte_creacion(self):
        self.entrar()
        with patch("operations.views.registrar_auditoria", side_effect=RuntimeError("prueba")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("operations:turn_create"), {
                    "nombre": "Temporal", "hora_inicio": "08:00", "hora_fin": "16:00", "activo": "on",
                })
        self.assertFalse(Turno.objects.filter(nombre="Temporal").exists())

    def test_acceso_por_rol(self):
        url = reverse("accounts:audit_list")
        self.assertEqual(url, "/auditoria/")
        self.assertEqual(self.client.get(url).status_code, 302)
        for rol in PerfilUsuario.Rol:
            with self.subTest(rol=rol):
                self.entrar(rol)
                esperado = 200 if rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.AUDITOR) else 403
                self.assertEqual(self.client.get(url).status_code, esperado)

    def test_navegacion_y_get_no_crean_auditoria(self):
        url = reverse("accounts:audit_list")
        for rol in PerfilUsuario.Rol:
            self.entrar(rol)
            respuesta = self.client.get(reverse("dashboard"))
            if rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.AUDITOR):
                self.assertContains(respuesta, url)
                self.client.get(url)
            else:
                self.assertNotContains(respuesta, url)
        self.assertEqual(AuditoriaAccion.objects.count(), 0)

    def test_filtros_busqueda_y_paginacion(self):
        self.entrar()
        primero = self.registro(modulo="INCIDENTES", descripcion="Colisión central")
        otro = self.registro(usuario=self.operador, modulo="TURNOS", accion="EDITAR", descripcion="Turno vespertino")
        url = reverse("accounts:audit_list")
        for filtro, esperado in (
            ({"modulo": "TURNOS"}, otro),
            ({"usuario": self.operador.pk}, otro),
            ({"accion": "EDITAR"}, otro),
            ({"busqueda": "Colisión"}, primero),
            ({"fecha_desde": timezone.localdate().isoformat()}, primero),
            ({"fecha_hasta": timezone.localdate().isoformat()}, primero),
        ):
            with self.subTest(filtro=filtro):
                respuesta = self.client.get(url, filtro)
                self.assertEqual(respuesta.status_code, 200)
                ids = {obj.pk for obj in respuesta.context["pagina"].object_list}
                self.assertIn(esperado.pk, ids)
                if "fecha_" not in str(filtro):
                    self.assertEqual(len(ids), 1)
        for indice in range(31):
            self.registro(descripcion=f"Extra {indice}")
        respuesta = self.client.get(url)
        self.assertEqual(len(respuesta.context["pagina"].object_list), 30)
        self.assertEqual(respuesta.context["pagina"].paginator.count, 33)

    def test_filtro_fecha_excluye_registros_fuera_de_rango(self):
        self.entrar()
        antiguo = self.registro(descripcion="Antiguo")
        reciente = self.registro(descripcion="Reciente")
        AuditoriaAccion.objects.filter(pk=antiguo.pk).update(
            fecha_hora=timezone.now() - timedelta(days=3)
        )
        respuesta = self.client.get(reverse("accounts:audit_list"), {
            "fecha_desde": timezone.localdate().isoformat(),
            "fecha_hasta": timezone.localdate().isoformat(),
        })
        ids = {obj.pk for obj in respuesta.context["pagina"].object_list}
        self.assertEqual(ids, {reciente.pk})

    def test_html_no_expone_secretos(self):
        self.entrar()
        request = RequestFactory().post("/prueba/", {"password": "NO-MOSTRAR"})
        self.registro(request=request)
        contenido = self.client.get(reverse("accounts:audit_list")).content.decode()
        for secreto in (self.admin.password, "ClavePrivada-9831!", "NO-MOSTRAR", "sessionid", "DB_PASSWORD", "SECRET_KEY"):
            self.assertNotIn(secreto, contenido)
