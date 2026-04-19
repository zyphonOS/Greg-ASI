(function () {
    const bootNode = document.getElementById("pikkaio-boot-data");
    const form = document.getElementById("pikkaio-intent-form");
    const descriptionInput = document.getElementById("intent-description");
    const declareButton = document.getElementById("declare-button");
    const acknowledgementText = document.getElementById("acknowledgement-text");
    const builderChip = document.getElementById("builder-id-chip");
    const driftScoreValue = document.getElementById("drift-score-value");
    const intentStatusText = document.getElementById("intent-status-text");
    const trajectoryNote = document.getElementById("trajectory-note");
    const interventionPanel = document.getElementById("intervention-panel");
    const characterCount = document.getElementById("intent-character-count");
    const activeIntentsList = document.getElementById("active-intents-list");

    if (!form || !descriptionInput || !declareButton || !acknowledgementText || !builderChip || !driftScoreValue || !intentStatusText || !trajectoryNote || !interventionPanel || !characterCount || !activeIntentsList) {
        return;
    }

    const gregUI = window.GregUI || {};
    let boot = {};

    try {
        boot = bootNode ? JSON.parse(bootNode.textContent || "{}") : {};
    } catch (error) {
        console.error("[greg/pikkaio]", error);
    }

    function updateCharacterCount() {
        const size = descriptionInput.value.trim().length;
        characterCount.textContent = `${size} characters`;
    }

    function driftStatus(score) {
        const value = Number(score || 0);
        if (value >= 0.95) {
            return "Fourteen days. No action.";
        }
        if (value > 0.7) {
            return "Greg is watching this.";
        }
        if (value >= 0.3) {
            return "Drift detected.";
        }
        if (value === 0) {
            return "Converging.";
        }
        return "The line is holding.";
    }

    function driftNote(hasIntent, score) {
        if (!hasIntent) {
            return "No active line declared yet. Drift cannot be measured until you speak clearly.";
        }
        if (Number(score || 0) >= 0.7) {
            return "The declared line and the lived line are separating.";
        }
        return "Greg is measuring this line against silence and follow-through.";
    }

    function colorizeDrift(score) {
        const color = gregUI.driftColor ? gregUI.driftColor(score) : "#00ff88";
        driftScoreValue.style.color = color;
    }

    function animateDrift(score) {
        const target = Number(score || 0);
        colorizeDrift(target);
        if (gregUI.animateNumber) {
            gregUI.animateNumber(driftScoreValue, target, { decimals: 2, duration: 1200 });
            return;
        }
        driftScoreValue.textContent = target.toFixed(2);
    }

    function setIntervention(intervention) {
        if (!intervention) {
            interventionPanel.innerHTML = [
                '<p class="room-label">Intervention</p>',
                '<p class="pikkaio-intervention-line"><span>Greg:</span> <span id="intervention-text">No active intervention.</span></p>',
                '<p class="pikkaio-intervention-meta">When drift crosses threshold, Greg presses on the slipping line.</p>',
            ].join("");
            return;
        }

        interventionPanel.innerHTML = [
            '<p class="room-label">Intervention</p>',
            `<p class="pikkaio-intervention-line"><span>Greg:</span> <span id="intervention-text">${intervention.message || ""}</span></p>`,
            `<p class="pikkaio-intervention-meta">Tick ${intervention.tick || ""} · Drift ${Number(intervention.drift || 0).toFixed(2)}</p>`,
        ].join("");
    }

    function renderIntents(projects, builderId) {
        const rows = Object.values(projects || {})
            .filter(function (intent) {
                return intent.creator === builderId;
            })
            .sort(function (a, b) {
                return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
            });

        if (!rows.length) {
            activeIntentsList.innerHTML = '<p class="pikkaio-empty">Nothing declared yet. The field is open.</p>';
            return;
        }

        activeIntentsList.innerHTML = rows.map(function (intent) {
            const drift = Number(intent.drift_score || 0);
            const updatedAt = intent.updated_at || intent.declared_at || "";
            const color = gregUI.driftColor ? gregUI.driftColor(drift) : "#00ff88";
            return [
                '<article class="pikkaio-intent-row">',
                `<span class="pikkaio-intent-text">${intent.description || intent.intent || intent.id}</span>`,
                `<span class="pikkaio-intent-drift" style="color:${color}">${drift.toFixed(2)}</span>`,
                `<span class="pikkaio-intent-age">${updatedAt ? updatedAt.slice(0, 10) : "now"}</span>`,
                "</article>",
            ].join("");
        }).join("");
    }

    function applyState(state, animate) {
        const score = state && state.drift_score != null ? Number(state.drift_score) : 0;
        builderChip.textContent = state && state.builder_id ? state.builder_id : "builder-unset";
        acknowledgementText.textContent = state && state.acknowledgement
            ? state.acknowledgement
            : "Declare an intent and Pikkaio will acknowledge the line in real time.";
        intentStatusText.textContent = driftStatus(score);
        trajectoryNote.textContent = driftNote(Boolean(state && state.has_intent), score);
        if (animate) {
            animateDrift(score);
        } else {
            driftScoreValue.textContent = score.toFixed(2);
            colorizeDrift(score);
        }
        setIntervention(state ? state.intervention : null);
    }

    async function fetchStatus() {
        const response = await fetch("/pikkaio/status", { cache: "no-store" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Unable to load Pikkaio status.");
        }
        return data;
    }

    async function fetchIntentLedger() {
        const response = await fetch("/pikkaio/api/intents", { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Unable to load intent ledger.");
        }
        return data;
    }

    async function refreshRoom(animate) {
        const status = await fetchStatus();
        applyState(status, animate);
        const ledger = await fetchIntentLedger();
        renderIntents(ledger.projects, status.builder_id);
        return status;
    }

    async function submitIntent(event) {
        event.preventDefault();
        const description = descriptionInput.value.trim();
        if (!description) {
            descriptionInput.focus();
            return;
        }

        declareButton.disabled = true;
        try {
            const response = await fetch("/pikkaio/intent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ description }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Unable to declare intent.");
            }
            boot = data.status || {};
            applyState(boot, true);
            acknowledgementText.textContent = data.acknowledgement || acknowledgementText.textContent;
            await refreshRoom(false);
            updateCharacterCount();
        } catch (error) {
            console.error("[greg/pikkaio]", error);
        } finally {
            declareButton.disabled = false;
        }
    }

    descriptionInput.addEventListener("input", updateCharacterCount);
    form.addEventListener("submit", submitIntent);

    updateCharacterCount();
    applyState(boot, false);
    refreshRoom(true).catch(function (error) {
        console.error("[greg/pikkaio]", error);
    });
})();
