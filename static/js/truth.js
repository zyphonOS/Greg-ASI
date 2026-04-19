(function () {
    const room = document.querySelector(".truth-room");

    if (!room) {
        return;
    }

    const gregUI = window.GregUI || {};
    const refreshUrl = room.getAttribute("data-refresh-url") || window.location.pathname;

    function animateValue(id, decimals) {
        const node = document.getElementById(id);
        if (!node) {
            return;
        }
        const target = Number(node.getAttribute("data-value") || node.textContent || "0");
        if (gregUI.animateNumber) {
            gregUI.animateNumber(node, target, { decimals: decimals || 0, duration: 1200 });
        }
    }

    function colorizeDriftCells() {
        document.querySelectorAll(".truth-drift").forEach(function (cell) {
            const drift = Number(cell.getAttribute("data-drift") || cell.textContent || "0");
            if (gregUI.driftColor) {
                cell.style.color = gregUI.driftColor(drift);
            }
        });
    }

    function animateCurrentValues() {
        animateValue("truth-r-score", 6);
        animateValue("truth-term-m", 4);
        animateValue("truth-term-phi", 4);
        animateValue("truth-term-psi", 4);
        animateValue("truth-term-epsilon", 4);
        colorizeDriftCells();
    }

    async function refreshTruthRoom() {
        try {
            const response = await fetch(refreshUrl, { cache: "no-store" });
            const html = await response.text();
            if (!response.ok) {
                throw new Error("Unable to refresh truth room.");
            }
            const doc = gregUI.parseHTML ? gregUI.parseHTML(html) : new DOMParser().parseFromString(html, "text/html");
            const nextR = doc.getElementById("truth-r-score");
            const nextTick = doc.getElementById("truth-tick");
            const nextTerms = doc.getElementById("truth-terms");
            const nextComponents = doc.getElementById("truth-components");
            const nextIntents = doc.getElementById("truth-intents-body");
            const nextEvents = doc.getElementById("truth-events-list");
            const nextIntervention = doc.getElementById("truth-last-intervention");

            if (nextTick) {
                document.getElementById("truth-tick").textContent = nextTick.textContent;
            }
            if (nextTerms) {
                document.getElementById("truth-terms").innerHTML = nextTerms.innerHTML;
            }
            if (nextComponents) {
                document.getElementById("truth-components").innerHTML = nextComponents.innerHTML;
            }
            if (nextIntents) {
                document.getElementById("truth-intents-body").innerHTML = nextIntents.innerHTML;
            }
            if (nextEvents) {
                document.getElementById("truth-events-list").innerHTML = nextEvents.innerHTML;
            }
            if (nextIntervention) {
                document.getElementById("truth-last-intervention").innerHTML = nextIntervention.innerHTML;
            }
            if (nextR) {
                document.getElementById("truth-r-score").setAttribute("data-value", nextR.getAttribute("data-value") || nextR.textContent || "0");
            }
            ["truth-term-m", "truth-term-phi", "truth-term-psi", "truth-term-epsilon"].forEach(function (id) {
                const nextNode = doc.getElementById(id);
                const currentNode = document.getElementById(id);
                if (nextNode && currentNode) {
                    currentNode.setAttribute("data-value", nextNode.getAttribute("data-value") || nextNode.textContent || "0");
                }
            });
            animateCurrentValues();
        } catch (error) {
            console.error("[greg/truth]", error);
        }
    }

    animateCurrentValues();
    window.setInterval(refreshTruthRoom, 5000);
})();
