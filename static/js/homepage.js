(function () {
    const form = document.getElementById("intent-form");
    const input = document.getElementById("intent-input");
    const submit = document.getElementById("intent-submit");
    const responseLine = document.getElementById("intent-response");
    const navTrigger = document.getElementById("nav-trigger");
    const navMenu = document.getElementById("nav-menu");
    const navBackdrop = document.getElementById("nav-backdrop");
    const terminal = document.getElementById("wordcode-terminal");
    const terminalOutput = document.getElementById("wordcode-output");
    const terminalForm = document.getElementById("wordcode-form");
    const terminalInput = document.getElementById("wordcode-input");
    const aliveNode = document.getElementById("homepage-alive");
    const tickNode = document.getElementById("homepage-tick");
    const driftNode = document.getElementById("homepage-drift");
    const realityNode = document.getElementById("homepage-reality");

    if (!form || !input || !submit || !responseLine || !terminal || !terminalOutput || !terminalForm || !terminalInput) {
        return;
    }

    const gregUI = window.GregUI || {};
    const commandHistory = [];
    let historyIndex = -1;

    function terminalOpen() {
        return !terminal.hidden;
    }

    function setSubmitVisibility() {
        const hasContent = input.value.trim().length > 0;
        submit.hidden = !hasContent;
    }

    function homepageReply(score) {
        const drift = Number(score || 0);
        if (drift === 0) {
            return "Intent logged. Greg is tracing the line now.";
        }
        if (drift > 0.7) {
            return "Intent declared. Greg has opened a high-energy execution line.";
        }
        return "Intent recorded. The line is open and ready for the next move.";
    }

    function setResponse(message, isError) {
        responseLine.textContent = message || "";
        responseLine.classList.toggle("is-error", Boolean(isError));
    }

    function renderHomepageState(state) {
        if (!state) {
            return;
        }
        if (aliveNode) {
            aliveNode.textContent = state.alive === false ? "offline" : "Greg is alive";
        }
        if (tickNode) {
            tickNode.textContent = String(Number(state.tick || 0));
        }
        if (driftNode) {
            const drift = Number((state.drift && state.drift.coefficient) || 0);
            const category = (state.drift && state.drift.category) || "stable";
            driftNode.textContent = `${category} ${drift.toFixed(3)}`;
        }
        if (realityNode) {
            const reality = Number(state.reality_score || (state.reality && state.reality.R) || 0);
            realityNode.textContent = reality.toFixed(3);
        }
    }

    function closeMenu() {
        if (gregUI.closeNav) {
            gregUI.closeNav();
            return;
        }
        if (navMenu) {
            navMenu.hidden = true;
        }
        if (navBackdrop) {
            navBackdrop.hidden = true;
        }
        if (navTrigger) {
            navTrigger.setAttribute("aria-expanded", "false");
        }
    }

    async function pollState() {
        if (gregUI.pollState) {
            const state = await gregUI.pollState();
            if (state) {
                return state;
            }
        }

        const res = await fetch("/api/state", { cache: "no-store" });
        const data = await res.json();
        if (!res.ok || !data.ok) {
            throw new Error(data.error || "Unable to read Greg state.");
        }
        return data;
    }

    async function declareIntent(description) {
        const res = await fetch("/pikkaio/intent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ description }),
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Unable to declare intent.");
        }
        return data;
    }

    async function submitIntent(event) {
        event.preventDefault();
        const description = input.value.trim();
        if (!description) {
            setSubmitVisibility();
            return;
        }

        try {
            const data = await declareIntent(description);
            const driftScore = data && data.status ? Number(data.status.drift_score || 0) : 0;
            input.value = "";
            setSubmitVisibility();
            setResponse(homepageReply(driftScore), false);
        } catch (error) {
            console.error("[greg/homepage]", error);
            setResponse(error.message || "Unable to declare intent.", true);
        }
    }

    function focusIntentField() {
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
    }

    function blurIntentField() {
        input.blur();
    }

    function appendTerminalLine(message, tone) {
        const line = document.createElement("p");
        const variant = tone || "standard";
        line.className = `wordcode-line${variant === "error" ? " wordcode-line-error" : ""}${variant === "greg" ? " wordcode-line-greg" : ""}`;
        line.textContent = message;
        terminalOutput.appendChild(line);
        while (terminalOutput.childElementCount > 20) {
            terminalOutput.removeChild(terminalOutput.firstElementChild);
        }
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }

    function openTerminal() {
        terminal.hidden = false;
        terminal.setAttribute("aria-hidden", "false");
        if (!terminalOutput.childElementCount) {
            appendTerminalLine("help  declare [intent text]  status  drift  exit", "greg");
        }
        terminalInput.focus();
    }

    function closeTerminal() {
        terminal.hidden = true;
        terminal.setAttribute("aria-hidden", "true");
        terminalInput.value = "";
        historyIndex = -1;
    }

    async function runWordcode(command) {
        const trimmed = command.trim();
        if (!trimmed) {
            return;
        }

        appendTerminalLine(`greg > ${trimmed}`);

        if (trimmed === "help") {
            appendTerminalLine("declare [intent text] | status | drift | help | exit", "greg");
            return;
        }

        if (trimmed === "exit") {
            closeTerminal();
            return;
        }

        if (trimmed === "status") {
            const state = await pollState();
            appendTerminalLine(
                `tick ${state.tick} | R ${Number(state.reality_score || 0).toFixed(6)} | ε ${Number(state.epsilon || 0).toFixed(4)}`,
                "greg",
            );
            return;
        }

        if (trimmed === "drift") {
            const res = await fetch("/pikkaio/status", { cache: "no-store" });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || "Unable to read drift.");
            }
            const driftScore = data.drift_score == null ? 0 : Number(data.drift_score);
            appendTerminalLine(`drift ${driftScore.toFixed(4)}`, "greg");
            return;
        }

        if (trimmed.startsWith("declare ")) {
            const intentText = trimmed.slice(8).trim();
            if (!intentText) {
                throw new Error("declare requires intent text.");
            }
            const data = await declareIntent(intentText);
            const driftScore = data && data.status ? Number(data.status.drift_score || 0) : 0;
            setResponse(homepageReply(driftScore), false);
            appendTerminalLine(homepageReply(driftScore), "greg");
            return;
        }

        throw new Error("Unknown command. Type help.");
    }

    async function submitTerminal(event) {
        event.preventDefault();
        const command = terminalInput.value.trim();
        if (!command) {
            return;
        }
        commandHistory.push(command);
        historyIndex = commandHistory.length;
        terminalInput.value = "";
        try {
            await runWordcode(command);
        } catch (error) {
            console.error("[greg/terminal]", error);
            appendTerminalLine(error.message || "Command failed.", "error");
        }
    }

    input.addEventListener("input", setSubmitVisibility);
    form.addEventListener("submit", submitIntent);
    terminalForm.addEventListener("submit", submitTerminal);

    if (!gregUI.closeNav) {
        if (navTrigger) {
            navTrigger.addEventListener("click", function () {
                if (navMenu && navMenu.hidden) {
                    navMenu.hidden = false;
                    if (navBackdrop) {
                        navBackdrop.hidden = false;
                    }
                    navTrigger.setAttribute("aria-expanded", "true");
                } else {
                    closeMenu();
                }
            });
        }

        if (navBackdrop) {
            navBackdrop.addEventListener("click", closeMenu);
        }
    }

    terminalInput.addEventListener("keydown", function (event) {
        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (!commandHistory.length) {
                return;
            }
            historyIndex = Math.max(0, historyIndex - 1);
            terminalInput.value = commandHistory[historyIndex] || "";
            terminalInput.setSelectionRange(terminalInput.value.length, terminalInput.value.length);
        }
    });

    document.addEventListener("keydown", function (event) {
        const target = event.target;
        const inEditable =
            target instanceof HTMLInputElement ||
            target instanceof HTMLTextAreaElement ||
            target.isContentEditable;

        if ((event.ctrlKey && event.key === "`") || (!event.ctrlKey && !event.metaKey && !event.altKey && event.key === "`")) {
            event.preventDefault();
            if (!terminalOpen()) {
                openTerminal();
            }
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            if (terminalOpen()) {
                closeTerminal();
                return;
            }
            closeMenu();
            blurIntentField();
            return;
        }

        if (terminalOpen()) {
            return;
        }

        if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key === "/" && !inEditable) {
            event.preventDefault();
            focusIntentField();
            return;
        }

        if (event.ctrlKey && event.key === "Enter") {
            if (input.value.trim()) {
                event.preventDefault();
                form.requestSubmit();
            }
        }
    });

    setSubmitVisibility();
    document.addEventListener("greg:state", function (event) {
        renderHomepageState(event.detail);
    });
    pollState().then(renderHomepageState).catch(function (error) {
        console.error("[greg/homepage]", error);
    });
    window.setInterval(pollState, 3000);
})();
