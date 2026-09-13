from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.models import PerfilUsuario
from accounts.navigation import obtener_navegacion
from accounts.permissions import roles_permitidos
from incidents.models import Incidente

from .forms import FiltrosReportesForm
from .services import (
    buscar_incidentes,
    obtener_incidentes_por_dia,
    obtener_incidentes_por_estado,
    obtener_incidentes_por_institucion,
    obtener_incidentes_por_operador,
    obtener_incidentes_por_prioridad,
    obtener_incidentes_por_tipo,
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
        for nombre in ("dia", "estado", "tipo", "prioridad", "operador", "institucion")
    }
    if criterios is not None:
        resumen = obtener_resumen_incidentes(**criterios)
        por_dia = obtener_incidentes_por_dia(**criterios)
        por_estado = obtener_incidentes_por_estado(**criterios)
        por_tipo = obtener_incidentes_por_tipo(**criterios)
        por_prioridad = obtener_incidentes_por_prioridad(**criterios)
        por_operador = obtener_incidentes_por_operador(**criterios)
        por_institucion = obtener_incidentes_por_institucion(**criterios)
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
        }
    return render(request, "reports/index.html", {
        **obtener_navegacion(request.user), "filtros": filtros,
        "filtros_activos": filtros_activos, "resumen": resumen,
        "graficas": graficas,
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
