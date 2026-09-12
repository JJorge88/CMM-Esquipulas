from .models import PerfilUsuario


SECCIONES_POR_ROL = {
    PerfilUsuario.Rol.ADMINISTRADOR: (
        "Incidentes", "Operación", "Reportes", "Usuarios"
    ),
    PerfilUsuario.Rol.COORDINADOR: (
        "Incidentes", "Operación", "Reportes"
    ),
    PerfilUsuario.Rol.OPERADOR: ("Incidentes",),
    PerfilUsuario.Rol.CONSULTA: ("Incidentes", "Reportes"),
    PerfilUsuario.Rol.AUDITOR: ("Incidentes", "Reportes"),
}

ROLES_REGISTRO_INCIDENTES = (
    PerfilUsuario.Rol.ADMINISTRADOR,
    PerfilUsuario.Rol.COORDINADOR,
    PerfilUsuario.Rol.OPERADOR,
)


def obtener_navegacion(usuario):
    perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
    rol = perfil.rol if perfil else None
    menu = [{"titulo": "Inicio", "url": "dashboard"}]
    menu.extend(
        {
            "titulo": titulo,
            "url": "incidents:list" if titulo == "Incidentes" else "#",
        }
        for titulo in SECCIONES_POR_ROL.get(rol, ())
    )
    return {
        "menu": menu,
        "rol_usuario": perfil.get_rol_display() if perfil else "Sin rol asignado",
        "puede_registrar_incidente": rol in ROLES_REGISTRO_INCIDENTES,
    }
