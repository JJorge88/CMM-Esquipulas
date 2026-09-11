from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate

from incidents.models import Incidente, ParticipacionInstitucion


def _validar_periodo(fecha_desde=None, fecha_hasta=None):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValidationError(
            "La fecha inicial no puede ser posterior a la fecha final."
        )


def _filtrar_por_periodo(queryset, fecha_desde=None, fecha_hasta=None):
    _validar_periodo(fecha_desde, fecha_hasta)

    if fecha_desde:
        queryset = queryset.filter(
            fecha_hora_reporte__date__gte=fecha_desde
        )
    if fecha_hasta:
        queryset = queryset.filter(
            fecha_hora_reporte__date__lte=fecha_hasta
        )
    return queryset


def obtener_resumen_incidentes(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    resumen = incidentes.aggregate(
        total_incidentes=Count("id", distinct=True),
        pendientes=Count(
            "id",
            filter=Q(estado=Incidente.Estado.PENDIENTE),
            distinct=True,
        ),
        en_seguimiento=Count(
            "id",
            filter=Q(estado=Incidente.Estado.EN_SEGUIMIENTO),
            distinct=True,
        ),
        cerrados=Count(
            "id",
            filter=Q(estado=Incidente.Estado.CERRADO),
            distinct=True,
        ),
        total_seguimientos=Count("seguimientos", distinct=True),
        total_evidencias=Count("evidencias", distinct=True),
    )
    total = resumen["total_incidentes"]
    resumen["porcentaje_cerrados"] = (
        resumen["cerrados"] * 100 / total if total else 0
    )
    return resumen


def obtener_incidentes_por_estado(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    cantidades = {
        fila["estado"]: fila["cantidad"]
        for fila in incidentes.values("estado").annotate(
            cantidad=Count("id")
        )
    }
    return {
        estado: cantidades.get(estado, 0)
        for estado in Incidente.Estado.values
    }


def obtener_incidentes_por_tipo(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    return list(
        incidentes.values("tipo_incidente")
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "tipo_incidente")
    )


def obtener_incidentes_por_prioridad(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    return list(
        incidentes.values("prioridad")
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "prioridad")
    )


def obtener_incidentes_por_operador(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    return list(
        incidentes.values(
            operador_id=F("operador_responsable_id"),
            username=F("operador_responsable__username"),
            nombres=F("operador_responsable__first_name"),
            apellidos=F("operador_responsable__last_name"),
        )
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "username")
    )


def obtener_incidentes_por_institucion(
    fecha_desde=None,
    fecha_hasta=None,
):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    return list(
        ParticipacionInstitucion.objects.filter(incidente__in=incidentes)
        .values(
            "institucion_id",
            nombre=F("institucion__nombre"),
            siglas=F("institucion__siglas"),
        )
        .annotate(cantidad=Count("incidente_id", distinct=True))
        .order_by("-cantidad", "nombre")
    )


def obtener_incidentes_por_dia(fecha_desde=None, fecha_hasta=None):
    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    return list(
        incidentes.annotate(fecha=TruncDate("fecha_hora_reporte"))
        .values("fecha")
        .annotate(cantidad=Count("id"))
        .order_by("fecha")
    )


def buscar_incidentes(
    fecha_desde=None,
    fecha_hasta=None,
    estado=None,
    tipo=None,
    prioridad=None,
    operador_id=None,
    institucion_id=None,
):
    if estado is not None and estado not in Incidente.Estado.values:
        raise ValidationError("El estado indicado no es válido.")

    incidentes = _filtrar_por_periodo(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
    )
    if estado is not None:
        incidentes = incidentes.filter(estado=estado)
    if tipo is not None:
        incidentes = incidentes.filter(tipo_incidente=tipo)
    if prioridad is not None:
        incidentes = incidentes.filter(prioridad=prioridad)
    if operador_id is not None:
        incidentes = incidentes.filter(
            operador_responsable_id=operador_id
        )
    if institucion_id is not None:
        incidentes = incidentes.filter(
            participaciones_institucionales__institucion_id=institucion_id
        )

    return (
        incidentes.select_related("operador_responsable")
        .prefetch_related("participaciones_institucionales__institucion")
        .distinct()
        .order_by("-fecha_hora_reporte")
    )
