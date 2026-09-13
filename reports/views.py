from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.models import PerfilUsuario
from accounts.navigation import obtener_navegacion
from accounts.permissions import roles_permitidos
from incidents.models import Incidente

from .forms import ComparacionPeriodosForm, FiltrosReportesForm
from .services import (
    DIAS_SEMANA,
    HORAS_DIA,
    buscar_incidentes,
    comparar_periodos,
    INDICADORES_COMPARACION,
    obtener_incidentes_por_camara,
    obtener_incidentes_por_dia,
    obtener_incidentes_por_dia_semana,
    obtener_incidentes_por_estado,
    obtener_incidentes_por_hora,
    obtener_incidentes_por_institucion,
    obtener_incidentes_por_operador,
    obtener_incidentes_por_prioridad,
    obtener_incidentes_por_tipo,
    obtener_maximos_temporales,
    obtener_resumen_incidentes,
)


ROLES_REPORTES = (
    PerfilUsuario.Rol.ADMINISTRADOR,
    PerfilUsuario.Rol.COORDINADOR,
    PerfilUsuario.Rol.CONSULTA,
    PerfilUsuario.Rol.AUDITOR,
)


def _filtros(request):
    formulario = FiltrosReportesForm(request.GET)
    if formulario.is_valid():
        return formulario, formulario.criterios(), formulario.resumen_activos()
    return formulario, None, []


def _valores(filas, etiqueta):
    return {
        "labels": [fila[etiqueta] for fila in filas],
        "values": [fila["cantidad"] for fila in filas],
    }


def _duracion_humana(valor, *, con_signo=False):
    if valor is None:
        return "—"
    segundos = round(abs(valor.total_seconds()))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        texto = f"{horas} h {minutos:02d} min"
    elif minutos:
        texto = f"{minutos} min"
    else:
        texto = f"{segundos} s" if segundos else "0 min"
    if con_signo and valor.total_seconds() != 0:
        return ("+" if valor.total_seconds() > 0 else "−") + texto
    return texto


def _indicadores_para_plantilla(comparacion):
    filas = []
    for clave, etiqueta in INDICADORES_COMPARACION:
        dato = comparacion["indicadores"][clave]
        duracion = clave.startswith("tiempo_promedio_")
        porcentaje = clave == "porcentaje_cerrados"

        def mostrar(valor, *, diferencia=False):
            if valor is None:
                return "—"
            if duracion:
                return _duracion_humana(valor, con_signo=diferencia)
            if porcentaje:
                return f"{valor:+.1f} p.p." if diferencia else f"{valor:.1f} %"
            return f"{valor:+d}" if diferencia and valor else str(valor)

        variacion_porcentual = dato["variacion_porcentual"]
        filas.append({
            "clave": clave, "etiqueta": etiqueta,
            "actual": mostrar(dato["actual"]),
            "anterior": mostrar(dato["anterior"]),
            "diferencia": mostrar(dato["variacion_absoluta"], diferencia=True),
            "variacion_porcentual": (
                f"{variacion_porcentual:+.2f} %"
                if variacion_porcentual is not None else "No comparable"
            ),
            "tendencia": dato["tendencia"],
        })
    return filas


@roles_permitidos(*ROLES_REPORTES)
def comparacion_periodos(request):
    formulario = ComparacionPeriodosForm(request.GET or None)
    comparacion = None
    indicadores = []
    graficas = {}
    if request.GET and formulario.is_valid():
        datos = formulario.cleaned_data
        comparacion = comparar_periodos(
            datos["actual_desde"], datos["actual_hasta"],
            datos["anterior_desde"], datos["anterior_hasta"],
            camara_id=datos["camara"].pk if datos["camara"] else None,
        )
        indicadores = _indicadores_para_plantilla(comparacion)
        for clave, etiqueta in (
            ("por_tipo", "tipo"), ("por_prioridad", "prioridad"),
            ("por_camara", "camara"), ("por_institucion", "institucion"),
        ):
            filas = comparacion[clave]
            graficas[clave] = {
                "labels": [
                    f"{fila[etiqueta]} — {fila['ubicacion']}"
                    if clave == "por_camara" and fila["ubicacion"]
                    else fila[etiqueta] for fila in filas
                ],
                "actual": [fila["actual"] for fila in filas],
                "anterior": [fila["anterior"] for fila in filas],
            }
    return render(request, "reports/comparison.html", {
        **obtener_navegacion(request.user),
        "formulario": formulario, "comparacion": comparacion,
        "indicadores": indicadores, "tarjetas": indicadores[:4],
        "graficas_comparacion": graficas,
    })


@roles_permitidos(*ROLES_REPORTES)
def panel_estadistico(request):
    filtros, criterios, filtros_activos = _filtros(request)
    resumen = {
        "total_incidentes": 0, "registrados": 0, "pendientes": 0,
        "en_seguimiento": 0, "resueltos": 0, "cerrados": 0,
        "porcentaje_cerrados": 0,
        "total_evidencias": 0, "total_seguimientos": 0,
        "tiempo_promedio_atencion": None,
        "tiempo_promedio_resolucion": None,
    }
    graficas = {
        nombre: {"labels": [], "values": []}
        for nombre in (
            "dia", "estado", "tipo", "prioridad", "operador",
            "institucion", "camara",
        )
    }
    graficas["hora"] = {
        "labels": [f"{hora}:00" for hora in HORAS_DIA],
        "values": [0] * 24,
    }
    graficas["dia_semana"] = {
        "labels": list(DIAS_SEMANA),
        "values": [0] * 7,
    }
    hora_mayor_incidencia = []
    dia_mayor_incidencia = []
    if criterios is not None:
        resumen = obtener_resumen_incidentes(**criterios)
        por_dia = obtener_incidentes_por_dia(**criterios)
        por_estado = obtener_incidentes_por_estado(**criterios)
        por_tipo = obtener_incidentes_por_tipo(**criterios)
        por_prioridad = obtener_incidentes_por_prioridad(**criterios)
        por_operador = obtener_incidentes_por_operador(**criterios)
        por_institucion = obtener_incidentes_por_institucion(**criterios)
        por_camara = obtener_incidentes_por_camara(**criterios)
        por_hora = obtener_incidentes_por_hora(**criterios)
        por_dia_semana = obtener_incidentes_por_dia_semana(**criterios)
        hora_mayor_incidencia = [
            f"{hora}:00 - {(int(hora) + 1) % 24:02d}:00"
            for hora in obtener_maximos_temporales(por_hora)
        ]
        dia_mayor_incidencia = obtener_maximos_temporales(por_dia_semana)
        graficas = {
            "dia": {
                "labels": [fila["fecha"].isoformat() for fila in por_dia],
                "values": [fila["cantidad"] for fila in por_dia],
            },
            "estado": {
                "labels": [dict(Incidente.Estado.choices)[clave] for clave in por_estado],
                "values": list(por_estado.values()),
            },
            "tipo": _valores(por_tipo, "tipo_incidente"),
            "prioridad": _valores(por_prioridad, "prioridad"),
            "operador": {
                "labels": [
                    f"{fila['nombres']} {fila['apellidos']}".strip()
                    or fila["username"] for fila in por_operador
                ],
                "values": [fila["cantidad"] for fila in por_operador],
            },
            "institucion": _valores(por_institucion, "nombre"),
            "camara": {
                "labels": [
                    f"{fila['nombre']} — {fila['ubicacion']}"
                    if fila["ubicacion"] else fila["nombre"]
                    for fila in por_camara
                ],
                "values": [fila["cantidad"] for fila in por_camara],
            },
            "hora": {
                "labels": [f"{hora}:00" for hora in por_hora],
                "values": list(por_hora.values()),
            },
            "dia_semana": {
                "labels": list(por_dia_semana),
                "values": list(por_dia_semana.values()),
            },
        }
    return render(request, "reports/index.html", {
        **obtener_navegacion(request.user), "filtros": filtros,
        "filtros_activos": filtros_activos, "resumen": resumen,
        "graficas": graficas,
        "hora_mayor_incidencia": hora_mayor_incidencia,
        "dia_mayor_incidencia": dia_mayor_incidencia,
    })


@roles_permitidos(*ROLES_REPORTES)
def consulta_historica(request):
    filtros, criterios, filtros_activos = _filtros(request)
    incidentes = buscar_incidentes(**criterios) if criterios is not None else Incidente.objects.none()
    incidentes = incidentes.order_by("-fecha_hora_reporte", "-pk")
    pagina = Paginator(incidentes, 25).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    query = parametros.urlencode()
    return render(request, "reports/incident_report.html", {
        **obtener_navegacion(request.user), "filtros": filtros,
        "filtros_activos": filtros_activos, "pagina": pagina,
        "query_paginacion": f"{query}&" if query else "",
    })
