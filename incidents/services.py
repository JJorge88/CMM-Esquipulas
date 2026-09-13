from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Incidente, SeguimientoIncidente


TRANSICIONES_PERMITIDAS = {
    Incidente.Estado.REGISTRADO: {
        Incidente.Estado.PENDIENTE,
        Incidente.Estado.EN_SEGUIMIENTO,
    },
    Incidente.Estado.PENDIENTE: {
        Incidente.Estado.EN_SEGUIMIENTO,
        Incidente.Estado.RESUELTO,
    },
    Incidente.Estado.EN_SEGUIMIENTO: {
        Incidente.Estado.EN_SEGUIMIENTO,
        Incidente.Estado.RESUELTO,
    },
    Incidente.Estado.RESUELTO: {Incidente.Estado.CERRADO},
    Incidente.Estado.CERRADO: set(),
}


def registrar_seguimiento(
    incidente,
    usuario,
    observacion,
    estado_nuevo,
    fecha_hora=None,
    resultado_cierre=None,
):
    with transaction.atomic():
        incidente_bloqueado = Incidente.objects.select_for_update().get(
            pk=incidente.pk
        )
        estado_anterior = incidente_bloqueado.estado

        if estado_nuevo not in TRANSICIONES_PERMITIDAS.get(
            estado_anterior, set()
        ):
            raise ValidationError(
                "No se permite cambiar el estado del incidente "
                f"de {estado_anterior} a {estado_nuevo}."
            )

        if estado_nuevo == Incidente.Estado.CERRADO:
            if not resultado_cierre or not resultado_cierre.strip():
                raise ValidationError(
                    "Debe registrar el resultado para cerrar el incidente."
                )

        momento = fecha_hora if fecha_hora is not None else timezone.now()

        datos_seguimiento = {
            "incidente": incidente_bloqueado,
            "usuario": usuario,
            "observacion": observacion,
            "estado_anterior": estado_anterior,
            "estado_nuevo": estado_nuevo,
            "fecha_hora": momento,
        }

        seguimiento = SeguimientoIncidente.objects.create(
            **datos_seguimiento
        )
        incidente_bloqueado.estado = estado_nuevo
        campos_actualizados = ["estado", "fecha_actualizacion"]
        if (
            estado_nuevo == Incidente.Estado.EN_SEGUIMIENTO
            and estado_anterior != Incidente.Estado.EN_SEGUIMIENTO
            and incidente_bloqueado.fecha_inicio_atencion is None
        ):
            incidente_bloqueado.fecha_inicio_atencion = momento
            campos_actualizados.append("fecha_inicio_atencion")
        if (
            estado_nuevo == Incidente.Estado.RESUELTO
            and incidente_bloqueado.fecha_resolucion is None
        ):
            incidente_bloqueado.fecha_resolucion = momento
            campos_actualizados.append("fecha_resolucion")
        if estado_nuevo == Incidente.Estado.CERRADO:
            if incidente_bloqueado.fecha_cierre is None:
                incidente_bloqueado.fecha_cierre = momento
                campos_actualizados.append("fecha_cierre")
            incidente_bloqueado.resultado_cierre = resultado_cierre.strip()
            campos_actualizados.append("resultado_cierre")
        incidente_bloqueado.full_clean()
        incidente_bloqueado.save(
            update_fields=campos_actualizados
        )

    return seguimiento
