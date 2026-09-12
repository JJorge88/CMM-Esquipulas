from datetime import datetime, timedelta

from django.core.exceptions import ValidationError

from accounts.models import PerfilUsuario


def validar_operador(usuario):
    rol = (
        PerfilUsuario.objects.filter(usuario_id=usuario.pk)
        .values_list("rol", flat=True)
        .first()
    )
    if rol is None:
        raise ValidationError(
            {"operador": "El usuario no posee un perfil de usuario."}
        )

    if rol != PerfilUsuario.Rol.OPERADOR:
        raise ValidationError(
            {
                "operador": (
                    "Solo los usuarios con rol OPERADOR pueden recibir "
                    "asignaciones de turno."
                )
            }
        )

    if not usuario.is_active:
        raise ValidationError(
            {"operador": "El operador debe tener una cuenta activa."}
        )


def intervalo_turno(fecha, turno):
    inicio = datetime.combine(fecha, turno.hora_inicio)
    fecha_fin = fecha
    if turno.hora_fin <= turno.hora_inicio:
        fecha_fin += timedelta(days=1)
    fin = datetime.combine(fecha_fin, turno.hora_fin)
    return inicio, fin


def turnos_se_solapan(inicio, fin, otro_inicio, otro_fin):
    return inicio < otro_fin and otro_inicio < fin
