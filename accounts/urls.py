from django.urls import include, path

from .views import (
    CerrarSesionView,
    IniciarSesionView,
    activar_desactivar_usuario,
    crear_usuario,
    editar_usuario,
    listar_auditoria,
    listar_usuarios,
)


usuarios_urlpatterns = [
    path("", listar_usuarios, name="user_list"),
    path("nuevo/", crear_usuario, name="user_create"),
    path("<int:pk>/editar/", editar_usuario, name="user_update"),
    path("<int:pk>/estado/", activar_desactivar_usuario, name="user_toggle_status"),
]

accounts_urlpatterns = [
    path("usuarios/", include(usuarios_urlpatterns)),
    path("auditoria/", listar_auditoria, name="audit_list"),
]

urlpatterns = [
    path("login/", IniciarSesionView.as_view(), name="login"),
    path("logout/", CerrarSesionView.as_view(), name="logout"),
    path("", include((accounts_urlpatterns, "accounts"), namespace="accounts")),
]
