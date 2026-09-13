from incidents.models import Incidente


ESTADOS_ACTIVOS = (
    Incidente.Estado.REGISTRADO,
    Incidente.Estado.PENDIENTE,
    Incidente.Estado.EN_SEGUIMIENTO,
)


def incidentes_activos():
    """Base común para consultas operativas; excluye resueltos y cerrados."""
    return Incidente.objects.filter(estado__in=ESTADOS_ACTIVOS)


def tiempo_transcurrido(fecha_reporte, ahora):
    segundos = max(0, int((ahora - fecha_reporte).total_seconds()))
    minutos = segundos // 60
    horas, resto = divmod(minutos, 60)
    if horas:
        return f"{horas} h {resto} min"
    return f"{minutos} min"
