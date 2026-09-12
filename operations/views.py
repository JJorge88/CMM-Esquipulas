from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import PerfilUsuario
from accounts.navigation import obtener_navegacion
from accounts.permissions import roles_permitidos

from .forms import AsignacionForm, FiltroAsignacionesForm, FiltroTurnosForm, TurnoForm
from .models import AsignacionTurno, Turno


GESTORES = (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR)
LECTORES = (*GESTORES, PerfilUsuario.Rol.AUDITOR)
LECTORES_ASIGNACIONES = (*LECTORES, PerfilUsuario.Rol.OPERADOR)


def _paginacion(request, objetos):
    pagina = Paginator(objetos, 20).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    query = parametros.urlencode()
    return pagina, f"{query}&" if query else ""


def _puede_gestionar(request):
    return PerfilUsuario.objects.filter(
        usuario=request.user, rol__in=GESTORES
    ).exists()


@roles_permitidos(*LECTORES)
def listar_turnos(request):
    filtros = FiltroTurnosForm(request.GET or None)
    turnos = Turno.objects.all()
    if filtros.is_valid():
        if filtros.cleaned_data["nombre"]:
            turnos = turnos.filter(nombre__icontains=filtros.cleaned_data["nombre"])
        if filtros.cleaned_data["activo"]:
            turnos = turnos.filter(activo=filtros.cleaned_data["activo"] == "si")
    pagina, query_paginacion = _paginacion(
        request, turnos.order_by("hora_inicio", "nombre", "pk")
    )
    return render(request, "operations/turn_list.html", {
        **obtener_navegacion(request.user), "filtros": filtros, "pagina": pagina,
        "query_paginacion": query_paginacion,
        "puede_gestionar": _puede_gestionar(request),
    })


@roles_permitidos(*GESTORES)
def crear_turno(request):
    formulario = TurnoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Turno creado correctamente.")
        return redirect("operations:turn_list")
    return render(request, "operations/turn_form.html", {
        **obtener_navegacion(request.user), "formulario": formulario, "creacion": True,
    })


@roles_permitidos(*GESTORES)
def editar_turno(request, pk):
    turno = get_object_or_404(Turno, pk=pk)
    formulario = TurnoForm(request.POST or None, instance=turno)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Turno actualizado correctamente.")
        return redirect("operations:turn_list")
    return render(request, "operations/turn_form.html", {
        **obtener_navegacion(request.user), "formulario": formulario,
        "creacion": False, "turno": turno,
    })


@roles_permitidos(*LECTORES_ASIGNACIONES)
def listar_asignaciones(request):
    es_operador = PerfilUsuario.objects.filter(
        usuario=request.user, rol=PerfilUsuario.Rol.OPERADOR
    ).exists()
    asignaciones = AsignacionTurno.objects.select_related("operador", "turno")
    if es_operador:
        asignaciones = asignaciones.filter(operador=request.user)
    filtros = FiltroAsignacionesForm(request.GET or None, mostrar_operador=not es_operador)
    if filtros.is_valid():
        datos = filtros.cleaned_data
        if datos["fecha_desde"]:
            asignaciones = asignaciones.filter(fecha__gte=datos["fecha_desde"])
        if datos["fecha_hasta"]:
            asignaciones = asignaciones.filter(fecha__lte=datos["fecha_hasta"])
        if datos["turno"]:
            asignaciones = asignaciones.filter(turno=datos["turno"])
        if not es_operador and datos["operador"]:
            asignaciones = asignaciones.filter(operador=datos["operador"])
    pagina, query_paginacion = _paginacion(
        request, asignaciones.order_by("-fecha", "turno__hora_inicio", "pk")
    )
    return render(request, "operations/assignment_list.html", {
        **obtener_navegacion(request.user), "filtros": filtros, "pagina": pagina,
        "query_paginacion": query_paginacion,
        "puede_gestionar": not es_operador and _puede_gestionar(request),
        "es_operador": es_operador,
    })


def _guardar_asignacion(request, formulario, mensaje):
    if request.method == "POST" and formulario.is_valid():
        try:
            formulario.save()
        except ValidationError as error:
            for campo, errores in error.message_dict.items():
                for texto in errores:
                    formulario.add_error(campo if campo in formulario.fields else None, texto)
        else:
            messages.success(request, mensaje)
            return redirect("operations:assignment_list")
    return None


@roles_permitidos(*GESTORES)
def crear_asignacion(request):
    formulario = AsignacionForm(request.POST or None)
    respuesta = _guardar_asignacion(request, formulario, "Asignación creada correctamente.")
    if respuesta:
        return respuesta
    return render(request, "operations/assignment_form.html", {
        **obtener_navegacion(request.user), "formulario": formulario, "creacion": True,
    })


@roles_permitidos(*GESTORES)
def editar_asignacion(request, pk):
    asignacion = get_object_or_404(AsignacionTurno, pk=pk)
    formulario = AsignacionForm(request.POST or None, instance=asignacion)
    respuesta = _guardar_asignacion(request, formulario, "Asignación actualizada correctamente.")
    if respuesta:
        return respuesta
    return render(request, "operations/assignment_form.html", {
        **obtener_navegacion(request.user), "formulario": formulario,
        "creacion": False, "asignacion": asignacion,
    })
