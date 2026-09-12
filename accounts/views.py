from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from reports.services import (
    buscar_incidentes,
    obtener_incidentes_por_dia,
    obtener_incidentes_por_prioridad,
    obtener_incidentes_por_tipo,
    obtener_resumen_incidentes,
)

from .forms import CrearUsuarioForm, EditarUsuarioForm, FiltroUsuariosForm
from .models import PerfilUsuario
from .navigation import obtener_navegacion
from .permissions import roles_permitidos


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
    navegacion = obtener_navegacion(request.user)
    rol = PerfilUsuario.objects.filter(usuario=request.user).values_list(
        "rol", flat=True
    ).first()

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
            **navegacion,
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


@roles_permitidos(PerfilUsuario.Rol.ADMINISTRADOR)
def listar_usuarios(request):
    filtros = FiltroUsuariosForm(request.GET or None)
    usuarios = User.objects.select_related("perfil")
    if filtros.is_valid():
        datos = filtros.cleaned_data
        if datos["busqueda"]:
            termino = datos["busqueda"].strip()
            usuarios = usuarios.filter(
                Q(username__icontains=termino)
                | Q(first_name__icontains=termino)
                | Q(last_name__icontains=termino)
            )
        if datos["rol"]:
            usuarios = usuarios.filter(perfil__rol=datos["rol"])
        if datos["estado"]:
            usuarios = usuarios.filter(is_active=datos["estado"] == "activo")

    usuarios = usuarios.order_by("first_name", "last_name", "username", "pk")
    pagina = Paginator(usuarios, 20).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    query_paginacion = parametros.urlencode()
    if query_paginacion:
        query_paginacion += "&"
    return render(
        request,
        "accounts/user_list.html",
        {
            **obtener_navegacion(request.user),
            "filtros": filtros,
            "pagina": pagina,
            "query_paginacion": query_paginacion,
        },
    )


@roles_permitidos(PerfilUsuario.Rol.ADMINISTRADOR)
def crear_usuario(request):
    formulario = CrearUsuarioForm(
        request.POST or None, initial={"estado_activo": True}
    )
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        with transaction.atomic():
            usuario = User.objects.create_user(
                username=datos["username"],
                email=datos["email"],
                password=datos["password1"],
                first_name=datos["first_name"],
                last_name=datos["last_name"],
                is_active=datos["estado_activo"],
            )
            perfil = usuario.perfil
            perfil.rol = datos["rol"]
            perfil.telefono = datos["telefono"]
            perfil.save(update_fields=("rol", "telefono"))
        messages.success(request, "Usuario creado correctamente.")
        return redirect("accounts:user_list")

    return render(
        request,
        "accounts/user_form.html",
        {
            **obtener_navegacion(request.user),
            "formulario": formulario,
            "creacion": True,
        },
    )


@roles_permitidos(PerfilUsuario.Rol.ADMINISTRADOR)
def editar_usuario(request, pk):
    usuario = get_object_or_404(User.objects.select_related("perfil"), pk=pk)
    perfil = get_object_or_404(PerfilUsuario, usuario=usuario)
    inicial = {
        "first_name": usuario.first_name,
        "last_name": usuario.last_name,
        "username": usuario.username,
        "email": usuario.email,
        "telefono": perfil.telefono,
        "rol": perfil.rol,
        "estado_activo": usuario.is_active,
    }
    formulario = EditarUsuarioForm(
        request.POST or None,
        initial=inicial,
        usuario=usuario,
        actor=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        with transaction.atomic():
            usuario.first_name = datos["first_name"]
            usuario.last_name = datos["last_name"]
            usuario.username = datos["username"]
            usuario.email = datos["email"]
            usuario.is_active = datos["estado_activo"]
            usuario.save(
                update_fields=(
                    "first_name", "last_name", "username", "email", "is_active"
                )
            )
            perfil.telefono = datos["telefono"]
            perfil.rol = datos["rol"]
            perfil.save(update_fields=("telefono", "rol"))
        messages.success(request, "Usuario actualizado correctamente.")
        return redirect("accounts:user_list")

    return render(
        request,
        "accounts/user_form.html",
        {
            **obtener_navegacion(request.user),
            "formulario": formulario,
            "creacion": False,
            "usuario_editado": usuario,
        },
    )


@roles_permitidos(PerfilUsuario.Rol.ADMINISTRADOR)
@require_POST
def activar_desactivar_usuario(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.pk == request.user.pk and usuario.is_active:
        messages.warning(request, "No puede desactivar su propia cuenta.")
        return redirect("accounts:user_list")

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=("is_active",))
    mensaje = (
        "Usuario activado correctamente."
        if usuario.is_active else "Usuario desactivado correctamente."
    )
    messages.success(request, mensaje)
    return redirect("accounts:user_list")
