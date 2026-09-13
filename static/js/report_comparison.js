document.addEventListener("DOMContentLoaded", () => {
    const elemento = document.getElementById("datos-comparacion");
    if (!elemento) return;
    if (typeof Chart === "undefined") {
        document.getElementById("comparacion-graficas-error")?.classList.remove("d-none");
        return;
    }

    const datos = JSON.parse(elemento.textContent);
    document.querySelectorAll("[data-comparison-chart]").forEach((lienzo) => {
        const serie = datos[lienzo.dataset.comparisonChart];
        if (!serie || !serie.labels.length) return;
        new Chart(lienzo, {
            type: "bar",
            data: {
                labels: serie.labels,
                datasets: [
                    { label: "Período actual", data: serie.actual, backgroundColor: "#23527a" },
                    { label: "Período anterior", data: serie.anterior, backgroundColor: "#8c9bab" },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: { legend: { position: "bottom" } },
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    });
});
