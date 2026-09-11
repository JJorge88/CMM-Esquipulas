from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Incidente, SeguimientoIncidente


TRANSICIONES_PERMITIDAS = {
    Incidente.Estado.PENDIENTE: {
        Incidente.Estado.EN_SEGUIMIENTO,
        Incidente.Estado.CERRADO,
    },
    Incidente.Estado.EN_SEGUIMIENTO: {
        Incidente.Estado.EN_SEGUIMIENTO,
        Incidente.Estado.CERRADO,
    },
    Incidente.Estado.CERRADO: set(),
}


def registrar_seguimiento(
    incidente,
    usuario,
    observacion,
    estado_nuevo,
    fecha_hora=None,
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

        datos_seguimiento = {
            "incidente": incidente_bloqueado,
            "usuario": usuario,
            "observacion": observacion,
            "estado_anterior": estado_anterior,
            "estado_nuevo": estado_nuevo,
        }
        if fecha_hora is not None:
            datos_seguimiento["fecha_hora"] = fecha_hora

        seguimiento = SeguimientoIncidente.objects.create(
            **datos_seguimiento
        )
        incidente_bloqueado.estado = estado_nuevo
        incidente_bloqueado.save(
            update_fields=("estado", "fecha_actualizacion")
        )

    return seguimiento
