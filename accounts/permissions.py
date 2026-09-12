from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import PerfilUsuario


def roles_permitidos(*roles):
    """Restringe una vista autenticada a los roles indicados."""

    def decorador(vista):
        @login_required
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            permitido = PerfilUsuario.objects.filter(
                usuario=request.user, rol__in=roles
            ).exists()
            if not permitido:
                raise PermissionDenied("No tiene permiso para acceder a este módulo.")
            return vista(request, *args, **kwargs)

        return protegida

    return decorador
