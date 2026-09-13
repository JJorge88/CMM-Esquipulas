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
    PerfilUsuario.Rol.AUDITOR: ("Incidentes", "Operación", "Reportes"),
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
            "url": (
                "incidents:list" if titulo == "Incidentes"
                else "accounts:user_list" if titulo == "Usuarios"
                else "operations:turn_list" if titulo == "Operación"
                else "#"
            ),
            "subopciones": (
                (
                    {"titulo": "Turnos", "url": "operations:turn_list"},
                    {"titulo": "Asignaciones", "url": "operations:assignment_list"},
                    {"titulo": "Instituciones", "url": "operations:institution_list"},
                    {"titulo": "Recursos", "url": "operations:resource_list"},
                    *(({"titulo": "Tipos de recurso", "url": "operations:resource_type_list"},)
                      if rol in (PerfilUsuario.Rol.ADMINISTRADOR, PerfilUsuario.Rol.COORDINADOR)
                      else ()),
                )
                if titulo == "Operación" else ()
            ),
        }
        for titulo in SECCIONES_POR_ROL.get(rol, ())
    )
    return {
        "menu": menu,
        "rol_usuario": perfil.get_rol_display() if perfil else "Sin rol asignado",
        "puede_registrar_incidente": rol in ROLES_REGISTRO_INCIDENTES,
        "mostrar_mis_turnos": rol == PerfilUsuario.Rol.OPERADOR,
        "mostrar_instituciones": rol in (
            PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA,
        ),
        "mostrar_recursos": rol in (
            PerfilUsuario.Rol.OPERADOR, PerfilUsuario.Rol.CONSULTA,
        ),
    }
