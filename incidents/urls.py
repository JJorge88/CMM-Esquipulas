from django.urls import path

from . import views


app_name = "incidents"

urlpatterns = [
    path("", views.listar_incidentes, name="list"),
    path("nuevo/", views.registrar_incidente, name="create"),
    path("<int:pk>/", views.detalle_incidente, name="detail"),
]
