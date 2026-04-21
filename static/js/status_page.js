(function () {
    const ids = {
        pingValue: document.getElementById("status-ping-value"),
        pingDetail: document.getElementById("status-ping-detail"),
        constitutionValue: document.getElementById("status-constitution-value"),
        constitutionDetail: document.getElementById("status-constitution-detail"),
        runtimeValue: document.getElementById("status-runtime-value"),
        runtimeDetail: document.getElementById("status-runtime-detail"),
        incidentCount: document.getElementById("status-incident-count"),
        incidentDetail: document.getElementById("status-incident-detail"),
        metricTick: document.getElementById("metric-tick"),
        metricTickResponse: document.getElementById("metric-tick-response"),
        metricDrift: document.getElementById("metric-drift"),
        metricDriftCategory: document.getElementById("metric-drift-category"),
        metricReality: document.getElementById("metric-reality"),
        metricAgents: document.getElementById("metric-agents"),
        metricRevenue: document.getElementById("metric-revenue"),
        metricRevenueDetail: document.getElementById("metric-revenue-detail"),
        benchmarkEinstein: document.getElementById("benchmark-einstein"),
        benchmarkEinsteinDetail: document.getElementById("benchmark-einstein-detail"),
        benchmarkLifeGeneration: document.getElementById("benchmark-life-generation"),
        benchmarkLifeDetail: document.getElementById("benchmark-life-detail"),
        uptimeGrid: document.getElementById("uptime-grid"),
        incidentList: document.getElementById("incident-list"),
        incidentForm: document.getElementById("incident-form"),
        incidentResult: document.getElementById("incident-form-result"),
    };

    const chartNodes = {
        tick: document.getElementById("tick-chart"),
        drift: document.getElementById("drift-chart"),
        revenue: document.getElementById("revenue-chart"),
    };

    let charts = {};

    function fmt(value, digits = 2) {
        return Number(value || 0).toFixed(digits);
    }

    function renderIncidentList(incidents) {
        if (!ids.incidentList) return;
        if (!Array.isArray(incidents) || !incidents.length) {
            ids.incidentList.innerHTML = `
              <article class="incident-card">
                <strong>No incidents yet</strong>
                <p>The organism is operating within constitutional thresholds.</p>
              </article>
            `;
            return;
        }
        ids.incidentList.innerHTML = incidents.map((incident) => `
          <article class="incident-card" data-severity="${incident.severity || "info"}">
            <strong>${incident.title || "Untitled incident"}</strong>
            <p>${incident.message || ""}</p>
            <div class="incident-meta">
              <span>${incident.severity || "info"}</span>
              <span>${incident.status || "active"}</span>
              <span>${incident.created_at || "now"}</span>
            </div>
          </article>
        `).join("");
    }

    function renderUptime(uptime) {
        if (!ids.uptimeGrid) return;
        const windows = Array.isArray(uptime) ? uptime : [];
        ids.uptimeGrid.innerHTML = windows.map((item) => `
          <article class="uptime-card">
            <span>${item.window}</span>
            <strong>${fmt(item.pct, 2)}%</strong>
            <small class="status-note">Live-facing confidence window</small>
          </article>
        `).join("");
    }

    function ensureChart(key, node, configFactory) {
        if (!node || typeof window.Chart === "undefined") {
            return null;
        }
        if (!charts[key]) {
            charts[key] = new window.Chart(node, configFactory());
        }
        return charts[key];
    }

    function renderCharts(history) {
        const samples = Array.isArray(history) ? history : [];
        const labels = samples.map((sample) => String(sample.timestamp || "").slice(11, 19));
        const tickValues = samples.map((sample) => Number(sample.tick || 0));
        const driftValues = samples.map((sample) => Number(sample.drift || 0));
        const realityValues = samples.map((sample) => Number(sample.reality || 0));
        const revenueValues = samples.map((sample) => Number(sample.revenue || 0));

        const tickChart = ensureChart("tick", chartNodes.tick, () => ({
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Tick",
                    data: tickValues,
                    borderColor: "#00ff9d",
                    backgroundColor: "rgba(0,255,157,0.14)",
                    tension: 0.28,
                    fill: true,
                    borderWidth: 2,
                    pointRadius: 0,
                }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
        }));
        const driftChart = ensureChart("drift", chartNodes.drift, () => ({
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Drift",
                        data: driftValues,
                        borderColor: "#ff9500",
                        backgroundColor: "rgba(255,149,0,0.12)",
                        tension: 0.26,
                        fill: false,
                        borderWidth: 2,
                        pointRadius: 0,
                    },
                    {
                        label: "Reality",
                        data: realityValues,
                        borderColor: "#00ff9d",
                        backgroundColor: "rgba(0,255,157,0.10)",
                        tension: 0.26,
                        fill: false,
                        borderWidth: 2,
                        pointRadius: 0,
                    },
                ],
            },
            options: { responsive: true, maintainAspectRatio: false },
        }));
        const revenueChart = ensureChart("revenue", chartNodes.revenue, () => ({
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Revenue",
                    data: revenueValues,
                    backgroundColor: "rgba(0,255,157,0.35)",
                    borderColor: "#00ff9d",
                    borderWidth: 1,
                }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
        }));

        if (tickChart) {
            tickChart.data.labels = labels;
            tickChart.data.datasets[0].data = tickValues;
            tickChart.update();
        }
        if (driftChart) {
            driftChart.data.labels = labels;
            driftChart.data.datasets[0].data = driftValues;
            driftChart.data.datasets[1].data = realityValues;
            driftChart.update();
        }
        if (revenueChart) {
            revenueChart.data.labels = labels;
            revenueChart.data.datasets[0].data = revenueValues;
            revenueChart.update();
        }
    }

    function renderSummary(payload) {
        if (!payload || !payload.current) return;
        const current = payload.current;
        const ping = current.ping || {};
        const status = current.status || {};
        const constitution = current.constitution || {};
        const responseTimes = current.response_times_ms || {};
        const incidents = payload.active_incidents || current.incidents || [];
        const payments = current.payments || {};
        const drift = status.drift || {};
        const reality = status.reality || {};
        const benchmarks = status.benchmarks || {};
        const einstein = benchmarks.einstein_test || {};
        const gameOfLife = benchmarks.game_of_life || {};

        if (ids.pingValue) ids.pingValue.textContent = ping.status || "alive";
        if (ids.pingDetail) ids.pingDetail.textContent = `Tick ${ping.tick || 0} · ${fmt(responseTimes.ping, 1)} ms`;
        if (ids.constitutionValue) ids.constitutionValue.textContent = constitution.matches ? "verified" : "alert";
        if (ids.constitutionDetail) ids.constitutionDetail.textContent = constitution.current_hash ? `${String(constitution.current_hash).slice(0, 18)}...` : "Hash unavailable";
        if (ids.runtimeValue) ids.runtimeValue.textContent = `${fmt((drift.coefficient || 0), 3)} drift`;
        if (ids.runtimeDetail) ids.runtimeDetail.textContent = `Reality ${fmt(reality.R || 0, 3)} · ${status.agent_count || 0} agents`;
        if (ids.incidentCount) ids.incidentCount.textContent = String(incidents.length || 0);
        if (ids.incidentDetail) ids.incidentDetail.textContent = incidents.length ? "Founder attention may be required" : "No active incidents";

        if (ids.metricTick) ids.metricTick.textContent = String(ping.tick || 0);
        if (ids.metricTickResponse) ids.metricTickResponse.textContent = `Response ${fmt(responseTimes.ping, 1)} ms`;
        if (ids.metricDrift) ids.metricDrift.textContent = fmt(drift.coefficient || 0, 3);
        if (ids.metricDriftCategory) ids.metricDriftCategory.textContent = `Category ${(drift.category || "stable")}`;
        if (ids.metricReality) ids.metricReality.textContent = fmt(reality.R || 0, 3);
        if (ids.metricAgents) ids.metricAgents.textContent = `Agents ${status.agent_count || 0}`;
        if (ids.metricRevenue) ids.metricRevenue.textContent = `$${fmt(payments.confirmed_usd || 0, 2)}`;
        if (ids.metricRevenueDetail) ids.metricRevenueDetail.textContent = `${fmt(payments.pending_usd || 0, 2)} pending`;

        if (ids.benchmarkEinstein) ids.benchmarkEinstein.textContent = `${fmt(einstein.progress_score || 0, 3)} / 1.0`;
        if (ids.benchmarkEinsteinDetail) ids.benchmarkEinsteinDetail.textContent = einstein.checkpoint || "Benchmark rail warming.";
        if (ids.benchmarkLifeGeneration) ids.benchmarkLifeGeneration.textContent = `Gen ${gameOfLife.generation || 0}`;
        if (ids.benchmarkLifeDetail) ids.benchmarkLifeDetail.textContent = `${gameOfLife.live_cells || 0} live cells · density ${fmt(gameOfLife.density || 0, 3)}`;

        renderIncidentList(current.incidents || []);
        renderUptime(payload.uptime || []);
        renderCharts(payload.history || []);
    }

    async function refreshSummary() {
        const response = await fetch("/api/status-page/summary", { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Unable to load status summary.");
        }
        renderSummary(payload);
    }

    function openStream() {
        if (!window.EventSource) {
            return;
        }
        const stream = new window.EventSource("/api/status-page/stream");
        stream.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                renderSummary(payload);
            } catch (error) {
                console.error("[status/stream]", error);
            }
        };
        stream.onerror = () => {
            stream.close();
        };
    }

    if (ids.incidentForm) {
        ids.incidentForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const formData = new FormData(ids.incidentForm);
            const payload = {
                title: String(formData.get("title") || "").trim(),
                severity: String(formData.get("severity") || "info").trim(),
                message: String(formData.get("message") || "").trim(),
            };
            try {
                const response = await fetch("/api/status-page/incidents", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Unable to post incident.");
                }
                ids.incidentForm.reset();
                if (ids.incidentResult) ids.incidentResult.textContent = "Incident posted.";
                refreshSummary().catch(console.error);
            } catch (error) {
                if (ids.incidentResult) ids.incidentResult.textContent = error.message;
            }
        });
    }

    refreshSummary().catch((error) => console.error("[status/init]", error));
    openStream();
    window.setInterval(() => refreshSummary().catch((error) => console.error("[status/poll]", error)), 30000);
})();
