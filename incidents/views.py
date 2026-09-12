from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from accounts.navigation import obtener_navegacion

from .forms import FiltroIncidentesForm, IncidenteForm
from .models import Incidente


@login_required
def listar_incidentes(request):
    navegacion = obtener_navegacion(request.user)
    filtros = FiltroIncidentesForm(request.GET or None)
    incidentes = Incidente.objects.select_related("operador_responsable")

    if filtros.is_valid():
        datos = filtros.cleaned_data
        if datos["busqueda"]:
            termino = datos["busqueda"].strip()
            incidentes = incidentes.filter(
                Q(ubicacion__icontains=termino)
                | Q(descripcion__icontains=termino)
                | Q(tipo_incidente__icontains=termino)
            )
        if datos["estado"]:
            incidentes = incidentes.filter(estado=datos["estado"])
        if datos["tipo"]:
            incidentes = incidentes.filter(tipo_incidente=datos["tipo"])
        if datos["prioridad"]:
            incidentes = incidentes.filter(prioridad=datos["prioridad"])
        if datos["fecha_desde"]:
            incidentes = incidentes.filter(
                fecha_hora_reporte__date__gte=datos["fecha_desde"]
            )
        if datos["fecha_hasta"]:
            incidentes = incidentes.filter(
                fecha_hora_reporte__date__lte=datos["fecha_hasta"]
            )

    incidentes = incidentes.order_by("-fecha_hora_reporte", "-pk")
    pagina = Paginator(incidentes, 20).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    query_paginacion = parametros.urlencode()
    if query_paginacion:
        query_paginacion += "&"

    return render(
        request,
        "incidents/list.html",
        {
            **navegacion,
            "filtros": filtros,
            "pagina": pagina,
            "query_paginacion": query_paginacion,
        },
    )


@login_required
def registrar_incidente(request):
    navegacion = obtener_navegacion(request.user)
    if not navegacion["puede_registrar_incidente"]:
        raise PermissionDenied("No tiene permiso para registrar incidentes.")

    formulario = IncidenteForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        incidente = formulario.save(commit=False)
        incidente.operador_responsable = request.user
        incidente.estado = Incidente.Estado.PENDIENTE
        incidente.save()
        messages.success(request, "Incidente registrado correctamente.")
        return redirect("incidents:list")

    return render(
        request,
        "incidents/form.html",
        {**navegacion, "formulario": formulario},
    )
