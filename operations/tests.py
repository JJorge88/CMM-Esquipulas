from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from accounts.models import PerfilUsuario

from .models import AsignacionTurno, InstitucionApoyo, Turno


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
