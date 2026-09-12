from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

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

    return render(
        request,
        "dashboard/index.html",
        {
            "nombre_usuario": request.user.get_full_name()
            or request.user.username,
            "rol_usuario": rol_mostrado,
            "menu": menu,
        },
    )
