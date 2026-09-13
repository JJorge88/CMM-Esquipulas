from django.urls import path

from . import views


app_name = "operations"

urlpatterns = [
    path("incidentes-activos/", views.panel_incidentes_activos, name="active_incidents"),
    path("recursos/", views.listar_recursos, name="resource_list"),
    path("recursos/nuevo/", views.crear_recurso, name="resource_create"),
    path("recursos/camaras/nueva/", views.crear_camara, name="camera_create"),
    path("recursos/<int:pk>/editar/", views.editar_recurso, name="resource_update"),
    path("recursos/<int:pk>/estado/", views.cambiar_estado_recurso, name="resource_toggle_status"),
    path("tipos-recurso/", views.listar_tipos_recurso, name="resource_type_list"),
    path("tipos-recurso/nuevo/", views.crear_tipo_recurso, name="resource_type_create"),
    path("tipos-recurso/<int:pk>/editar/", views.editar_tipo_recurso, name="resource_type_update"),
    path("instituciones/", views.listar_instituciones, name="institution_list"),
    path("instituciones/nueva/", views.crear_institucion, name="institution_create"),
    path("instituciones/<int:pk>/editar/", views.editar_institucion, name="institution_update"),
    path("instituciones/<int:pk>/estado/", views.cambiar_estado_institucion, name="institution_toggle_status"),
    path("turnos/", views.listar_turnos, name="turn_list"),
    path("turnos/nuevo/", views.crear_turno, name="turn_create"),
    path("turnos/<int:pk>/editar/", views.editar_turno, name="turn_update"),
    path("asignaciones/", views.listar_asignaciones, name="assignment_list"),
    path("asignaciones/nueva/", views.crear_asignacion, name="assignment_create"),
    path(
        "asignaciones/<int:pk>/editar/",
        views.editar_asignacion,
        name="assignment_update",
    ),
]
