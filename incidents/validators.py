from pathlib import Path

from django.core.exceptions import ValidationError


EXTENSIONES_POR_TIPO = {
    "FOTO": {".jpg", ".jpeg", ".png", ".webp"},
    "VIDEO": {".mp4", ".mov", ".avi", ".mkv"},
    "DOCUMENTO": {".pdf", ".doc", ".docx"},
}

EXTENSIONES_PELIGROSAS = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".php",
    ".py",
    ".js",
    ".jar",
    ".com",
    ".scr",
}


def validar_archivo_evidencia(nombre_archivo, tipo):
    extensiones = [
        extension.lower() for extension in Path(nombre_archivo).suffixes
    ]

    if any(
        extension in EXTENSIONES_PELIGROSAS for extension in extensiones
    ):
        raise ValidationError(
            "La extensión del archivo no está permitida por seguridad."
        )

    extensiones_permitidas = EXTENSIONES_POR_TIPO.get(tipo)
    extension_final = extensiones[-1] if extensiones else ""
    if (
        extensiones_permitidas is not None
        and extension_final not in extensiones_permitidas
    ):
        permitidas = ", ".join(sorted(extensiones_permitidas))
        raise ValidationError(
            f"La extensión {extension_final or 'ausente'} no corresponde "
            f"al tipo {tipo}. Extensiones permitidas: {permitidas}."
        )
