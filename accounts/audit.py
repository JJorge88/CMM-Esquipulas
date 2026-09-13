from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address

from .models import AuditoriaAccion


def registrar_auditoria(
    *, usuario, accion, modulo, entidad="", entidad_id="",
    descripcion="", request=None,
):
    """Registra metadatos mínimos de una acción confirmada, sin copiar el request."""
    ip = None
    metodo_http = ""
    ruta = ""
    if request is not None:
        candidata = request.META.get("REMOTE_ADDR")
        if candidata:
            try:
                validate_ipv46_address(candidata)
            except ValidationError:
                pass
            else:
                ip = candidata
        metodo_http = request.method[:10]
        ruta = request.path[:255]

    return AuditoriaAccion.objects.create(
        usuario=usuario,
        accion=accion,
        modulo=modulo,
        entidad=entidad or "",
        entidad_id=str(entidad_id) if entidad_id is not None else "",
        descripcion=descripcion or "",
        ip=ip,
        metodo_http=metodo_http,
        ruta=ruta,
    )
