from django.urls import path

from .views import CerrarSesionView, IniciarSesionView


urlpatterns = [
    path("login/", IniciarSesionView.as_view(), name="login"),
    path("logout/", CerrarSesionView.as_view(), name="logout"),
]
