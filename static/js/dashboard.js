document.addEventListener("DOMContentLoaded", () => {
    const datosElemento = document.getElementById("datos-incidentes-dia");
    const lienzo = document.getElementById("incidentes-por-dia");
    if (!datosElemento || !lienzo) return;

    if (typeof Chart === "undefined") {
        document.getElementById("grafica-error")?.classList.remove("d-none");
        return;
    }

    const filas = JSON.parse(datosElemento.textContent);
    new Chart(lienzo, {
        type: "line",
        data: {
            labels: filas.map((fila) => fila.fecha),
            datasets: [{
                label: "Incidentes",
                data: filas.map((fila) => fila.cantidad),
                borderColor: "#23527a",
                backgroundColor: "rgba(35, 82, 122, .12)",
                fill: true,
                tension: .25,
                pointRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
    });
});
