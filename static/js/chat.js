(function () {
    const bootstrap = window.CHAT_BOOTSTRAP || {};
    const rooms = Array.isArray(bootstrap.rooms) ? bootstrap.rooms : ["general", "tech", "random"];
    let currentRoom = bootstrap.currentRoom || "general";
    let lastId = 0;
    let eventSource = null;

    const feed = document.getElementById("chat-feed");
    const form = document.getElementById("chat-form");
    const messageInput = document.getElementById("chat-message");
    const sendButton = document.getElementById("chat-send");
    const roomTitle = document.getElementById("chat-room-title");
    const tickNode = document.getElementById("chat-tick");
    const driftNode = document.getElementById("chat-drift");

    if (!feed || !form || !messageInput || !sendButton) {
        return;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderEntry(entry) {
        const wrapper = document.createElement("article");
        wrapper.className = "chat-entry";
        wrapper.dataset.entryId = String(entry.id || "");
        wrapper.innerHTML = `
            <div class="chat-bubble chat-bubble-user">
                <span class="bubble-meta">${escapeHtml(entry.user_email || "builder")} · ${escapeHtml(entry.room || currentRoom)}</span>
                <p>${escapeHtml(entry.message || "")}</p>
            </div>
            <div class="chat-bubble chat-bubble-greg">
                <span class="bubble-meta">Greg · ${escapeHtml(entry.timestamp || "now")}</span>
                <p>${escapeHtml(entry.response || "")}</p>
            </div>
        `;
        feed.appendChild(wrapper);
        feed.scrollTop = feed.scrollHeight;
        lastId = Math.max(lastId, Number(entry.id || 0));
    }

    function resetFeed() {
        feed.innerHTML = "";
        lastId = 0;
    }

    async function loadHistory() {
        resetFeed();
        const response = await fetch(`/api/chat/history?room=${encodeURIComponent(currentRoom)}`, { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Unable to load chat history.");
        }
        (payload.messages || []).forEach((entry) => renderEntry(entry));
    }

    function openStream() {
        if (eventSource) {
            eventSource.close();
        }
        eventSource = new EventSource(`/api/chat/stream?room=${encodeURIComponent(currentRoom)}&last_id=${lastId}`);
        eventSource.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (!payload || Number(payload.id || 0) <= lastId) {
                    return;
                }
                renderEntry(payload);
            } catch (error) {
                console.error("[greg/chat/stream]", error);
            }
        };
        eventSource.onerror = () => {
            if (eventSource) {
                eventSource.close();
            }
            window.setTimeout(openStream, 1200);
        };
    }

    async function switchRoom(room) {
        if (!rooms.includes(room)) {
            return;
        }
        currentRoom = room;
        document.querySelectorAll(".room-tab").forEach((button) => {
            button.classList.toggle("is-active", button.dataset.room === currentRoom);
        });
        if (roomTitle) {
            roomTitle.textContent = currentRoom;
        }
        await loadHistory();
        openStream();
    }

    async function sendMessage(message) {
        const response = await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room: currentRoom, message }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Greg did not respond.");
        }
        renderEntry(payload.entry);
        if (tickNode) {
            tickNode.textContent = `tick ${Number(payload.tick || 0)}`;
        }
    }

    document.querySelectorAll(".room-tab").forEach((button) => {
        button.addEventListener("click", () => {
            switchRoom(button.dataset.room).catch((error) => {
                console.error("[greg/chat]", error);
            });
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = messageInput.value.trim();
        if (!message) {
            return;
        }
        sendButton.disabled = true;
        try {
            await sendMessage(message);
            messageInput.value = "";
        } catch (error) {
            console.error("[greg/chat]", error);
        } finally {
            sendButton.disabled = false;
            messageInput.focus();
        }
    });

    document.addEventListener("greg:state", (event) => {
        const state = event.detail || {};
        const drift = Number((state.drift && state.drift.coefficient) || 0);
        const category = (state.drift && state.drift.category) || "stable";
        if (tickNode) {
            tickNode.textContent = `tick ${Number(state.tick || 0)}`;
        }
        if (driftNode) {
            driftNode.textContent = `${category} ${drift.toFixed(3)}`;
        }
    });

    switchRoom(currentRoom).catch((error) => {
        console.error("[greg/chat]", error);
    });
})();
