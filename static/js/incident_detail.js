document.addEventListener("DOMContentLoaded", () => {
    const estado = document.getElementById("id_estado_nuevo");
    const contenedor = document.getElementById("resultado-cierre-container");
    const resultado = document.getElementById("id_resultado_cierre");
    if (!estado || !contenedor || !resultado) return;

    const actualizar = () => {
        const cerrar = estado.value === "CERRADO";
        contenedor.classList.toggle("d-none", !cerrar);
        resultado.required = cerrar;
        if (!cerrar) resultado.value = "";
    };
    estado.addEventListener("change", actualizar);
    actualizar();
});
