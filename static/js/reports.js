document.addEventListener("DOMContentLoaded", () => {
    const elemento = document.getElementById("datos-reportes");
    if (!elemento) return;
    if (typeof Chart === "undefined") {
        document.getElementById("graficas-error")?.classList.remove("d-none");
        return;
    }

    const datos = JSON.parse(elemento.textContent);
    const colores = ["#23527a", "#176b94", "#2f83a2", "#5b9bb1", "#86b1c1", "#aacbd4"];
    const configuraciones = {
        dia: { tipo: "line", horizontal: false },
        estado: { tipo: "doughnut", horizontal: false },
        tipo: { tipo: "bar", horizontal: true },
        prioridad: { tipo: "bar", horizontal: false },
        operador: { tipo: "bar", horizontal: true },
        institucion: { tipo: "bar", horizontal: true },
        camara: { tipo: "bar", horizontal: true },
    };

    document.querySelectorAll("[data-report-chart]").forEach((lienzo) => {
        const clave = lienzo.dataset.reportChart;
        const serie = datos[clave];
        if (!serie || !serie.values.some((valor) => valor > 0)) return;
        const config = configuraciones[clave];
        new Chart(lienzo, {
            type: config.tipo,
            data: {
                labels: serie.labels,
                datasets: [{
                    label: "Incidentes",
                    data: serie.values,
                    backgroundColor: config.tipo === "doughnut" ? colores : "#23527a",
                    borderColor: "#23527a",
                    borderWidth: config.tipo === "line" ? 2 : 0,
                    fill: config.tipo === "line",
                    tension: .25,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: config.horizontal ? "y" : "x",
                plugins: { legend: { display: config.tipo === "doughnut" } },
                scales: config.tipo === "doughnut" ? {} : {
                    [config.horizontal ? "x" : "y"]: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                    },
                },
            },
        });
    });
});
