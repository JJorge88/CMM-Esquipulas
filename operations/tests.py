from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from accounts.models import PerfilUsuario

from .models import (
    AsignacionTurno,
    InstitucionApoyo,
    RecursoInstitucional,
    TipoRecurso,
    Turno,
)


class InstitucionApoyoTests(TestCase):
    def test_crear_institucion_de_apoyo(self):
        institucion = InstitucionApoyo.objects.create(
            nombre="Institución de prueba",
            siglas="IDP",
            telefono="0000-0000",
            correo_electronico="prueba@example.com",
            direccion="Dirección de prueba",
        )

        institucion.refresh_from_db()
        self.assertEqual(institucion.nombre, "Institución de prueba")
        self.assertEqual(institucion.siglas, "IDP")
        self.assertTrue(institucion.activa)
        self.assertIsNotNone(institucion.fecha_creacion)
        self.assertIsNotNone(institucion.fecha_actualizacion)


class TurnoTests(TestCase):
    def test_crear_turno_correctamente(self):
        turno = Turno.objects.create(
            nombre="Turno de prueba",
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0),
        )

        turno.refresh_from_db()
        self.assertEqual(turno.nombre, "Turno de prueba")
        self.assertEqual(turno.hora_inicio, time(8, 0))
        self.assertEqual(turno.hora_fin, time(16, 0))
        self.assertTrue(turno.activo)


class AsignacionTurnoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fecha = date(2026, 9, 11)
        cls.operador = User.objects.create_user(
            username="operador_turno_prueba"
        )
        cls.otro_operador = User.objects.create_user(
            username="otro_operador_turno_prueba"
        )
        cls.turno_manana = Turno.objects.create(
            nombre="Turno mañana de prueba",
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0),
        )
        cls.turno_tarde = Turno.objects.create(
            nombre="Turno tarde de prueba",
            hora_inicio=time(12, 0),
            hora_fin=time(16, 0),
        )

    def test_crear_asignacion_para_operador(self):
        asignacion = AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        self.assertEqual(asignacion.operador, self.operador)
        self.assertEqual(asignacion.turno, self.turno_manana)
        self.assertEqual(asignacion.fecha, self.fecha)

    def test_rechazar_usuario_administrador(self):
        administrador = User.objects.create_user(
            username="administrador_turno_prueba"
        )
        administrador.perfil.rol = PerfilUsuario.Rol.ADMINISTRADOR
        administrador.perfil.save(update_fields=("rol",))

        with self.assertRaisesMessage(
            ValidationError,
            "Solo los usuarios con rol OPERADOR",
        ):
            AsignacionTurno.objects.create(
                operador=administrador,
                turno=self.turno_manana,
                fecha=self.fecha,
            )

    def test_rechazar_usuario_sin_perfil(self):
        usuario_sin_perfil = User.objects.create_user(
            username="usuario_sin_perfil_turno_prueba"
        )
        usuario_sin_perfil.perfil.delete()

        with self.assertRaisesMessage(
            ValidationError,
            "El usuario no posee un perfil de usuario",
        ):
            AsignacionTurno.objects.create(
                operador=usuario_sin_perfil,
                turno=self.turno_manana,
                fecha=self.fecha,
            )

    def test_rechazar_asignacion_duplicada(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        with self.assertRaises(ValidationError):
            AsignacionTurno.objects.create(
                operador=self.operador,
                turno=self.turno_manana,
                fecha=self.fecha,
            )

        self.assertEqual(AsignacionTurno.objects.count(), 1)

    def test_operador_puede_tener_asignaciones_en_fechas_distintas(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha + timedelta(days=1),
        )

        self.assertEqual(self.operador.asignaciones_turno.count(), 2)

    def test_operadores_diferentes_pueden_compartir_turno_y_fecha(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )
        AsignacionTurno.objects.create(
            operador=self.otro_operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        self.assertEqual(AsignacionTurno.objects.count(), 2)

    def test_rechazar_turnos_solapados(self):
        turno_solapado = Turno.objects.create(
            nombre="Turno solapado de prueba",
            hora_inicio=time(11, 0),
            hora_fin=time(15, 0),
        )
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "El turno se solapa con otra asignación",
        ):
            AsignacionTurno.objects.create(
                operador=self.operador,
                turno=turno_solapado,
                fecha=self.fecha,
            )

    def test_permitir_turnos_sin_solapamiento(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_tarde,
            fecha=self.fecha,
        )

        self.assertEqual(self.operador.asignaciones_turno.count(), 2)

    def test_validar_turno_que_cruza_medianoche(self):
        turno_nocturno = Turno.objects.create(
            nombre="Turno nocturno de prueba",
            hora_inicio=time(22, 0),
            hora_fin=time(6, 0),
        )
        turno_madrugada = Turno.objects.create(
            nombre="Turno madrugada de prueba",
            hora_inicio=time(5, 0),
            hora_fin=time(8, 0),
        )
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=turno_nocturno,
            fecha=self.fecha,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "El turno se solapa con otra asignación",
        ):
            AsignacionTurno.objects.create(
                operador=self.operador,
                turno=turno_madrugada,
                fecha=self.fecha + timedelta(days=1),
            )

    def test_protect_impide_eliminar_operador_asignado(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        with self.assertRaises(ProtectedError):
            self.operador.delete()

    def test_protect_impide_eliminar_turno_asignado(self):
        AsignacionTurno.objects.create(
            operador=self.operador,
            turno=self.turno_manana,
            fecha=self.fecha,
        )

        with self.assertRaises(ProtectedError):
            self.turno_manana.delete()


class TipoRecursoTests(TestCase):
    def test_crear_tipo_recurso(self):
        tipo = TipoRecurso.objects.create(
            nombre="Tipo de recurso de prueba",
            descripcion="Descripción de prueba.",
        )

        tipo.refresh_from_db()
        self.assertEqual(tipo.nombre, "Tipo de recurso de prueba")
        self.assertTrue(tipo.activo)
        self.assertIsNotNone(tipo.fecha_creacion)
        self.assertIsNotNone(tipo.fecha_actualizacion)


class RecursoInstitucionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tipo = TipoRecurso.objects.create(
            nombre="Tipo para recursos de prueba"
        )

    def crear_recurso(self, **datos):
        valores = {
            "nombre": "Recurso institucional de prueba",
            "tipo": self.tipo,
        }
        valores.update(datos)
        return RecursoInstitucional.objects.create(**valores)

    def test_crear_recurso_institucional(self):
        recurso = self.crear_recurso(
            codigo_interno="COD-PRUEBA-001",
            marca="Marca de prueba",
            modelo="Modelo de prueba",
            numero_serie="SERIE-PRUEBA-001",
            ubicacion="Ubicación de prueba",
            descripcion="Descripción de prueba.",
        )

        recurso.refresh_from_db()
        self.assertEqual(recurso.nombre, "Recurso institucional de prueba")
        self.assertEqual(recurso.tipo, self.tipo)
        self.assertTrue(recurso.activo)

    def test_estado_predeterminado_es_disponible(self):
        recurso = self.crear_recurso()

        self.assertEqual(
            recurso.estado,
            RecursoInstitucional.Estado.DISPONIBLE,
        )

    def test_relacion_inversa_tipo_recursos(self):
        recurso = self.crear_recurso()

        self.assertQuerySetEqual(self.tipo.recursos.all(), [recurso])

    def test_rechazar_codigo_interno_duplicado(self):
        self.crear_recurso(codigo_interno="CODIGO-DUPLICADO")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_recurso(
                    nombre="Segundo recurso de prueba",
                    codigo_interno="CODIGO-DUPLICADO",
                )

    def test_permitir_codigo_interno_vacio_en_multiples_recursos(self):
        self.crear_recurso(codigo_interno="")
        self.crear_recurso(
            nombre="Segundo recurso sin código",
            codigo_interno="",
        )

        self.assertEqual(RecursoInstitucional.objects.count(), 2)

    def test_rechazar_numero_serie_duplicado(self):
        self.crear_recurso(numero_serie="SERIE-DUPLICADA")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_recurso(
                    nombre="Segundo recurso de prueba",
                    numero_serie="SERIE-DUPLICADA",
                )

    def test_permitir_numero_serie_vacio_en_multiples_recursos(self):
        self.crear_recurso(numero_serie="")
        self.crear_recurso(
            nombre="Segundo recurso sin serie",
            numero_serie="",
        )

        self.assertEqual(RecursoInstitucional.objects.count(), 2)

    def test_protect_impide_eliminar_tipo_con_recursos(self):
        self.crear_recurso()

        with self.assertRaises(ProtectedError):
            self.tipo.delete()

    def test_permitir_cambios_de_estado(self):
        recurso = self.crear_recurso()

        recurso.estado = RecursoInstitucional.Estado.EN_USO
        recurso.save(update_fields=("estado", "fecha_actualizacion"))
        recurso.refresh_from_db()
        self.assertEqual(recurso.estado, RecursoInstitucional.Estado.EN_USO)

        recurso.estado = RecursoInstitucional.Estado.MANTENIMIENTO
        recurso.save(update_fields=("estado", "fecha_actualizacion"))
        recurso.refresh_from_db()
        self.assertEqual(
            recurso.estado,
            RecursoInstitucional.Estado.MANTENIMIENTO,
        )

        recurso.estado = RecursoInstitucional.Estado.DISPONIBLE
        recurso.save(update_fields=("estado", "fecha_actualizacion"))
        recurso.refresh_from_db()
        self.assertEqual(
            recurso.estado,
            RecursoInstitucional.Estado.DISPONIBLE,
        )
