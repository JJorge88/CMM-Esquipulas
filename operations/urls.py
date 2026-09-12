from django.urls import path

from . import views


app_name = "operations"

urlpatterns = [
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
