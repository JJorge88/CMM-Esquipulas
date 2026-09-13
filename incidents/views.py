from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from accounts.audit import registrar_auditoria
from accounts.navigation import obtener_navegacion

from .forms import (
    EvidenciaForm,
    FiltroIncidentesForm,
    IncidenteForm,
    ParticipacionInstitucionForm,
    SeguimientoForm,
)
from .models import (
    EvidenciaIncidente,
    Incidente,
    ParticipacionInstitucion,
    SeguimientoIncidente,
)
from .services import registrar_seguimiento
from django.utils import timezone


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
        incidente.estado = Incidente.Estado.REGISTRADO
        with transaction.atomic():
            incidente.save()
            registrar_auditoria(usuario=request.user, accion="CREAR", modulo="INCIDENTES", entidad="Incidente", entidad_id=incidente.pk, descripcion=f"Incidente {incidente.pk} registrado.", request=request)
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
    formulario_participacion = ParticipacionInstitucionForm(
        incidente=incidente, initial={"fecha_asignacion": timezone.localtime()}
    )

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
                    with transaction.atomic():
                        seguimiento = registrar_seguimiento(
                            incidente=incidente,
                            usuario=request.user,
                            observacion=formulario_seguimiento.cleaned_data["observacion"],
                            estado_nuevo=formulario_seguimiento.cleaned_data["estado_nuevo"],
                            resultado_cierre=formulario_seguimiento.cleaned_data["resultado_cierre"],
                        )
                        registrar_auditoria(usuario=request.user, accion="AGREGAR_SEGUIMIENTO", modulo="INCIDENTES", entidad="SeguimientoIncidente", entidad_id=seguimiento.pk, descripcion=f"Seguimiento agregado al incidente {incidente.pk}.", request=request)
                        if seguimiento.estado_nuevo != seguimiento.estado_anterior:
                            registrar_auditoria(usuario=request.user, accion="CAMBIAR_ESTADO", modulo="INCIDENTES", entidad="Incidente", entidad_id=incidente.pk, descripcion=f"Estado del incidente {incidente.pk}: {seguimiento.estado_anterior} → {seguimiento.estado_nuevo}.", request=request)
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
                with transaction.atomic():
                    evidencia.save()
                    registrar_auditoria(usuario=request.user, accion="CARGAR_EVIDENCIA", modulo="INCIDENTES", entidad="EvidenciaIncidente", entidad_id=evidencia.pk, descripcion=f"Evidencia tipo {evidencia.tipo} agregada al incidente {incidente.pk}.", request=request)
                messages.success(request, "Evidencia registrada correctamente.")
                return redirect("incidents:detail", pk=pk)
        elif accion == "institucion":
            formulario_participacion = ParticipacionInstitucionForm(
                request.POST, incidente=incidente
            )
            if formulario_participacion.is_valid():
                participacion = formulario_participacion.save(commit=False)
                participacion.incidente = incidente
                try:
                    with transaction.atomic():
                        participacion.save()
                        registrar_auditoria(usuario=request.user, accion="ASIGNAR_INSTITUCION", modulo="INCIDENTES", entidad="ParticipacionInstitucion", entidad_id=participacion.pk, descripcion=f"Institución {participacion.institucion.nombre} asociada al incidente {incidente.pk}.", request=request)
                except IntegrityError:
                    formulario_participacion.add_error(
                        "institucion", "Esta institución ya está asociada al incidente."
                    )
                else:
                    messages.success(request, "Institución asignada correctamente.")
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
            "formulario_participacion": formulario_participacion,
            "puede_agregar": puede_agregar,
            "cerrado": cerrado,
        },
    )
