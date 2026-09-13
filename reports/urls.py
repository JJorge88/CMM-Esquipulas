from django.urls import path

from . import views


app_name = "reports"

urlpatterns = [
    path("", views.panel_estadistico, name="index"),
    path("incidentes/", views.consulta_historica, name="incident_report"),
]
