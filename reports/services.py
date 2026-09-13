from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate

from incidents.models import Incidente, ParticipacionInstitucion


HORAS_DIA = tuple(f"{hora:02d}" for hora in range(24))
DIAS_SEMANA = (
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
)
ZONA_HORARIA_REPORTES = ZoneInfo("America/Guatemala")


def _validar_periodo(fecha_desde=None, fecha_hasta=None):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValidationError(
            "La fecha inicial no puede ser posterior a la fecha final."
        )


def _filtrar_por_periodo(queryset, fecha_desde=None, fecha_hasta=None):
    _validar_periodo(fecha_desde, fecha_hasta)

    if fecha_desde or fecha_hasta:
        queryset = queryset.annotate(
            _fecha_local_reporte=TruncDate(
                "fecha_hora_reporte", tzinfo=ZONA_HORARIA_REPORTES
            )
        )
    if fecha_desde:
        queryset = queryset.filter(
            _fecha_local_reporte__gte=fecha_desde
        )
    if fecha_hasta:
        queryset = queryset.filter(
            _fecha_local_reporte__lte=fecha_hasta
        )
    return queryset


def _filtrar_incidentes(
    queryset, fecha_desde=None, fecha_hasta=None, *, estado=None,
    tipo=None, prioridad=None, operador_id=None, institucion_id=None,
    camara_id=None,
):
    if estado is not None and estado not in Incidente.Estado.values:
        raise ValidationError("El estado indicado no es válido.")
    queryset = _filtrar_por_periodo(queryset, fecha_desde, fecha_hasta)
    if estado is not None:
        queryset = queryset.filter(estado=estado)
    if tipo is not None:
        queryset = queryset.filter(tipo_incidente=tipo)
    if prioridad is not None:
        queryset = queryset.filter(prioridad=prioridad)
    if operador_id is not None:
        queryset = queryset.filter(operador_responsable_id=operador_id)
    if camara_id is not None:
        queryset = queryset.filter(camara_origen_id=camara_id)
    if institucion_id is not None:
        participaciones = ParticipacionInstitucion.objects.filter(
            institucion_id=institucion_id
        ).values("incidente_id")
        queryset = queryset.filter(pk__in=participaciones)
    return queryset


def obtener_resumen_incidentes(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
    )
    resumen = incidentes.aggregate(
        total_incidentes=Count("id", distinct=True),
        registrados=Count(
            "id", filter=Q(estado=Incidente.Estado.REGISTRADO), distinct=True,
        ),
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
        resueltos=Count(
            "id", filter=Q(estado=Incidente.Estado.RESUELTO), distinct=True,
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
    resumen["tiempo_promedio_atencion"] = incidentes.filter(
        fecha_inicio_atencion__isnull=False,
    ).aggregate(promedio=Avg(F("fecha_inicio_atencion") - F("fecha_hora_reporte")))["promedio"]
    resumen["tiempo_promedio_resolucion"] = incidentes.filter(
        fecha_resolucion__isnull=False,
    ).aggregate(promedio=Avg(F("fecha_resolucion") - F("fecha_hora_reporte")))["promedio"]
    return resumen


def obtener_incidentes_por_estado(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
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


def obtener_incidentes_por_tipo(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
    )
    return list(
        incidentes.values("tipo_incidente")
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "tipo_incidente")
    )


def obtener_incidentes_por_prioridad(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
    )
    return list(
        incidentes.values("prioridad")
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "prioridad")
    )


def obtener_incidentes_por_operador(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
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
    **filtros,
):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
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


def obtener_incidentes_por_camara(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.filter(camara_origen__isnull=False),
        fecha_desde,
        fecha_hasta,
        **filtros,
    )
    filas = (
        incidentes.values(
            camara_id=F("camara_origen_id"),
            nombre=F("camara_origen__nombre"),
            ubicacion_camara=F("camara_origen__ubicacion"),
        )
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "nombre", "camara_id")
    )
    return [
        {
            "camara_id": fila["camara_id"],
            "nombre": fila["nombre"],
            "ubicacion": fila["ubicacion_camara"],
            "cantidad": fila["cantidad"],
        }
        for fila in filas
    ]


def obtener_incidentes_por_dia(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        **filtros,
    )
    return list(
        incidentes.annotate(fecha=TruncDate(
            "fecha_hora_reporte", tzinfo=ZONA_HORARIA_REPORTES
        ))
        .values("fecha")
        .annotate(cantidad=Count("id"))
        .order_by("fecha")
    )


def obtener_incidentes_por_hora(fecha_desde=None, fecha_hasta=None, **filtros):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(), fecha_desde, fecha_hasta, **filtros
    )
    cantidades = {
        fila["hora"]: fila["cantidad"]
        for fila in incidentes.order_by().annotate(
            hora=ExtractHour("fecha_hora_reporte", tzinfo=ZONA_HORARIA_REPORTES)
        ).values("hora").annotate(cantidad=Count("id"))
    }
    return {
        etiqueta: cantidades.get(hora, 0)
        for hora, etiqueta in enumerate(HORAS_DIA)
    }


def obtener_incidentes_por_dia_semana(
    fecha_desde=None, fecha_hasta=None, **filtros
):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(), fecha_desde, fecha_hasta, **filtros
    )
    cantidades = {
        fila["dia_semana"]: fila["cantidad"]
        for fila in incidentes.order_by().annotate(
            dia_semana=ExtractIsoWeekDay(
                "fecha_hora_reporte", tzinfo=ZONA_HORARIA_REPORTES
            )
        ).values("dia_semana").annotate(cantidad=Count("id"))
    }
    return {
        etiqueta: cantidades.get(numero, 0)
        for numero, etiqueta in enumerate(DIAS_SEMANA, start=1)
    }


def obtener_maximos_temporales(cantidades):
    mayor = max(cantidades.values(), default=0)
    if not mayor:
        return []
    return [etiqueta for etiqueta, cantidad in cantidades.items() if cantidad == mayor]


INDICADORES_COMPARACION = (
    ("total_incidentes", "Total de incidentes"),
    ("registrados", "Registrados"),
    ("pendientes", "Pendientes"),
    ("en_seguimiento", "En seguimiento"),
    ("resueltos", "Resueltos"),
    ("cerrados", "Cerrados"),
    ("porcentaje_cerrados", "Porcentaje de cerrados"),
    ("total_evidencias", "Total de evidencias"),
    ("total_seguimientos", "Total de seguimientos"),
    ("tiempo_promedio_atencion", "Tiempo promedio de atención"),
    ("tiempo_promedio_resolucion", "Tiempo promedio de resolución"),
)


def calcular_variacion(actual, anterior):
    """Variación neutral; None indica que falta un dato o no hay base comparable."""
    if actual is None or anterior is None:
        return {
            "variacion_absoluta": None,
            "variacion_porcentual": None,
            "tendencia": None,
        }
    diferencia = actual - anterior
    actual_num = actual.total_seconds() if hasattr(actual, "total_seconds") else actual
    anterior_num = anterior.total_seconds() if hasattr(anterior, "total_seconds") else anterior
    if anterior_num == 0:
        porcentaje = 0.0 if actual_num == 0 else None
    else:
        porcentaje = (actual_num - anterior_num) / abs(anterior_num) * 100
    return {
        "variacion_absoluta": diferencia,
        "variacion_porcentual": porcentaje,
        "tendencia": (
            "incremento" if actual_num > anterior_num
            else "disminucion" if actual_num < anterior_num else "sin_cambio"
        ),
    }


def _comparar_categorias(filas_actual, filas_anterior, *, clave, metadatos):
    actuales = {fila[clave]: fila for fila in filas_actual}
    anteriores = {fila[clave]: fila for fila in filas_anterior}
    resultado = []
    for identificador in actuales.keys() | anteriores.keys():
        fuente = actuales.get(identificador) or anteriores[identificador]
        actual = actuales.get(identificador, {}).get("cantidad", 0)
        anterior = anteriores.get(identificador, {}).get("cantidad", 0)
        variacion = calcular_variacion(actual, anterior)
        resultado.append({
            clave: identificador,
            **{salida: fuente[origen] for salida, origen in metadatos.items()},
            "actual": actual,
            "anterior": anterior,
            "diferencia": variacion["variacion_absoluta"],
            "variacion_porcentual": variacion["variacion_porcentual"],
            "tendencia": variacion["tendencia"],
        })
    etiqueta = next(iter(metadatos), clave)
    return sorted(resultado, key=lambda fila: (str(fila[etiqueta]).casefold(), str(fila[clave])))


def comparar_periodos(
    actual_desde, actual_hasta, anterior_desde, anterior_hasta, camara_id=None,
):
    _validar_periodo(actual_desde, actual_hasta)
    _validar_periodo(anterior_desde, anterior_hasta)
    filtros_actual = {
        "fecha_desde": actual_desde, "fecha_hasta": actual_hasta,
        "camara_id": camara_id,
    }
    filtros_anterior = {
        "fecha_desde": anterior_desde, "fecha_hasta": anterior_hasta,
        "camara_id": camara_id,
    }
    resumen_actual = obtener_resumen_incidentes(**filtros_actual)
    resumen_anterior = obtener_resumen_incidentes(**filtros_anterior)
    indicadores = {
        clave: {
            "etiqueta": etiqueta,
            "actual": resumen_actual[clave],
            "anterior": resumen_anterior[clave],
            **calcular_variacion(resumen_actual[clave], resumen_anterior[clave]),
        }
        for clave, etiqueta in INDICADORES_COMPARACION
    }
    return {
        "actual": resumen_actual,
        "anterior": resumen_anterior,
        "indicadores": indicadores,
        "por_tipo": _comparar_categorias(
            obtener_incidentes_por_tipo(**filtros_actual),
            obtener_incidentes_por_tipo(**filtros_anterior),
            clave="tipo_incidente", metadatos={"tipo": "tipo_incidente"},
        ),
        "por_prioridad": _comparar_categorias(
            obtener_incidentes_por_prioridad(**filtros_actual),
            obtener_incidentes_por_prioridad(**filtros_anterior),
            clave="prioridad", metadatos={"prioridad": "prioridad"},
        ),
        "por_camara": _comparar_categorias(
            obtener_incidentes_por_camara(**filtros_actual),
            obtener_incidentes_por_camara(**filtros_anterior),
            clave="camara_id", metadatos={"camara": "nombre", "ubicacion": "ubicacion"},
        ),
        "por_institucion": _comparar_categorias(
            obtener_incidentes_por_institucion(**filtros_actual),
            obtener_incidentes_por_institucion(**filtros_anterior),
            clave="institucion_id", metadatos={"institucion": "nombre", "siglas": "siglas"},
        ),
    }


def buscar_incidentes(
    fecha_desde=None,
    fecha_hasta=None,
    estado=None,
    tipo=None,
    prioridad=None,
    operador_id=None,
    institucion_id=None,
    camara_id=None,
):
    incidentes = _filtrar_incidentes(
        Incidente.objects.all(),
        fecha_desde,
        fecha_hasta,
        estado=estado, tipo=tipo, prioridad=prioridad,
        operador_id=operador_id, institucion_id=institucion_id,
        camara_id=camara_id,
    )

    return (
        incidentes.select_related("operador_responsable", "camara_origen")
        .prefetch_related("participaciones_institucionales__institucion")
        .distinct()
        .order_by("-fecha_hora_reporte")
    )
