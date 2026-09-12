from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from reports.services import (
    buscar_incidentes,
    obtener_incidentes_por_dia,
    obtener_incidentes_por_prioridad,
    obtener_incidentes_por_tipo,
    obtener_resumen_incidentes,
)

from .models import PerfilUsuario


class IniciarSesionView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class CerrarSesionView(LogoutView):
    http_method_names = ("post", "options")


def inicio(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required
def dashboard(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    rol = perfil.rol if perfil else None
    rol_mostrado = perfil.get_rol_display() if perfil else "Sin rol asignado"

    secciones_por_rol = {
        PerfilUsuario.Rol.ADMINISTRADOR: (
            "Incidentes", "Operación", "Reportes", "Usuarios"
        ),
        PerfilUsuario.Rol.COORDINADOR: (
            "Incidentes", "Operación", "Reportes"
        ),
        PerfilUsuario.Rol.OPERADOR: ("Incidentes",),
        PerfilUsuario.Rol.CONSULTA: ("Incidentes", "Reportes"),
        PerfilUsuario.Rol.AUDITOR: ("Incidentes", "Reportes"),
    }
    menu = [{"titulo": "Inicio", "url": "dashboard"}]
    menu.extend(
        {"titulo": titulo, "url": "#"}
        for titulo in secciones_por_rol.get(rol, ())
    )

    fecha_desde_texto = request.GET.get("fecha_desde", "")
    fecha_hasta_texto = request.GET.get("fecha_hasta", "")
    fecha_desde = None
    fecha_hasta = None
    error_periodo = ""

    try:
        if fecha_desde_texto:
            fecha_desde = date.fromisoformat(fecha_desde_texto)
        if fecha_hasta_texto:
            fecha_hasta = date.fromisoformat(fecha_hasta_texto)
        resumen = obtener_resumen_incidentes(fecha_desde, fecha_hasta)
    except ValueError:
        error_periodo = "Ingrese fechas válidas con el formato AAAA-MM-DD."
    except ValidationError as error:
        error_periodo = error.messages[0]

    if error_periodo:
        fecha_desde = None
        fecha_hasta = None
        resumen = obtener_resumen_incidentes()

    tipos = obtener_incidentes_por_tipo(fecha_desde, fecha_hasta)
    prioridades = obtener_incidentes_por_prioridad(fecha_desde, fecha_hasta)
    por_dia = obtener_incidentes_por_dia(fecha_desde, fecha_hasta)
    recientes = buscar_incidentes(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )[:10]
    datos_grafica = [
        {"fecha": fila["fecha"].isoformat(), "cantidad": fila["cantidad"]}
        for fila in por_dia
    ]
    mostrar_analisis = rol != PerfilUsuario.Rol.OPERADOR

    return render(
        request,
        "dashboard/index.html",
        {
            "nombre_usuario": request.user.get_full_name()
            or request.user.username,
            "rol_usuario": rol_mostrado,
            "menu": menu,
            "resumen": resumen,
            "tipos": tipos,
            "prioridades": prioridades,
            "datos_grafica": datos_grafica,
            "recientes": recientes,
            "mostrar_analisis": mostrar_analisis,
            "fecha_desde": fecha_desde_texto,
            "fecha_hasta": fecha_hasta_texto,
            "error_periodo": error_periodo,
        },
    )
