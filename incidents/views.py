from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from accounts.navigation import obtener_navegacion

from .forms import (
    EvidenciaForm,
    FiltroIncidentesForm,
    IncidenteForm,
    SeguimientoForm,
)
from .models import (
    EvidenciaIncidente,
    Incidente,
    ParticipacionInstitucion,
    SeguimientoIncidente,
)
from .services import registrar_seguimiento


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


@login_required
def detalle_incidente(request, pk):
    incidente = get_object_or_404(
        Incidente.objects.select_related("operador_responsable").prefetch_related(
            Prefetch(
                "seguimientos",
                queryset=SeguimientoIncidente.objects.select_related("usuario")
                .order_by("fecha_hora", "pk"),
            ),
            Prefetch(
                "evidencias",
                queryset=EvidenciaIncidente.objects.select_related("usuario")
                .order_by("-fecha_hora", "-pk"),
            ),
            Prefetch(
                "participaciones_institucionales",
                queryset=ParticipacionInstitucion.objects.select_related(
                    "institucion"
                ).order_by("fecha_asignacion", "pk"),
            ),
        ),
        pk=pk,
    )
    navegacion = obtener_navegacion(request.user)
    puede_agregar = navegacion["puede_registrar_incidente"]
    cerrado = incidente.estado == Incidente.Estado.CERRADO
    formulario_seguimiento = SeguimientoForm(estado_actual=incidente.estado)
    formulario_evidencia = EvidenciaForm()

    if request.method == "POST":
        if not puede_agregar:
            raise PermissionDenied("No tiene permiso para modificar incidentes.")
        accion = request.POST.get("accion")
        if accion == "seguimiento":
            if cerrado:
                raise PermissionDenied("No se permiten seguimientos en incidentes cerrados.")
            formulario_seguimiento = SeguimientoForm(
                request.POST, estado_actual=incidente.estado
            )
            if formulario_seguimiento.is_valid():
                try:
                    registrar_seguimiento(
                        incidente=incidente,
                        usuario=request.user,
                        observacion=formulario_seguimiento.cleaned_data["observacion"],
                        estado_nuevo=formulario_seguimiento.cleaned_data["estado_nuevo"],
                    )
                except ValidationError as error:
                    formulario_seguimiento.add_error(None, error)
                else:
                    messages.success(
                        request, "Seguimiento registrado correctamente."
                    )
                    return redirect("incidents:detail", pk=pk)
        elif accion == "evidencia":
            formulario_evidencia = EvidenciaForm(request.POST, request.FILES)
            if formulario_evidencia.is_valid():
                evidencia = formulario_evidencia.save(commit=False)
                evidencia.incidente = incidente
                evidencia.usuario = request.user
                evidencia.save()
                messages.success(request, "Evidencia registrada correctamente.")
                return redirect("incidents:detail", pk=pk)
        else:
            return HttpResponseBadRequest("Acción no válida.")

    return render(
        request,
        "incidents/detail.html",
        {
            **navegacion,
            "incidente": incidente,
            "formulario_seguimiento": formulario_seguimiento,
            "formulario_evidencia": formulario_evidencia,
            "puede_agregar": puede_agregar,
            "cerrado": cerrado,
        },
    )
