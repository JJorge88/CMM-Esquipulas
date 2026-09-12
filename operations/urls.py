from django.urls import path

from . import views


app_name = "operations"

urlpatterns = [
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
