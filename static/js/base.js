(function () {
    const navTrigger = document.getElementById("nav-trigger");
    const navMenu = document.getElementById("nav-menu");
    const navBackdrop = document.getElementById("nav-backdrop");
    const pulse = document.getElementById("tick-pulse");

    let lastAliveAt = Date.now();
    let lastState = null;

    function setPulse(isAlive) {
        if (!pulse) {
            return;
        }
        pulse.classList.toggle("is-alive", Boolean(isAlive));
        pulse.classList.toggle("is-flatline", !isAlive);
    }

    function openNav() {
        if (!navMenu || !navBackdrop || !navTrigger) {
            return;
        }
        navMenu.hidden = false;
        navBackdrop.hidden = false;
        navMenu.setAttribute("aria-hidden", "false");
        navTrigger.setAttribute("aria-expanded", "true");
    }

    function closeNav() {
        if (!navMenu || !navBackdrop || !navTrigger) {
            return;
        }
        navMenu.hidden = true;
        navBackdrop.hidden = true;
        navMenu.setAttribute("aria-hidden", "true");
        navTrigger.setAttribute("aria-expanded", "false");
    }

    async function fetchStateDirect() {
        const response = await fetch("/api/state", { cache: "no-store" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Unable to read /api/state.");
        }
        return data;
    }

    async function pollState() {
        try {
            const data = await fetchStateDirect();
            lastState = data;
            if (data.alive !== false) {
                lastAliveAt = Date.now();
            }
            setPulse((Date.now() - lastAliveAt) <= 10000);
            document.dispatchEvent(new CustomEvent("greg:state", { detail: data }));
            return data;
        } catch (error) {
            if ((Date.now() - lastAliveAt) > 10000) {
                setPulse(false);
            }
            console.error("[greg/pulse]", error);
            return lastState;
        }
    }

    function animateNumber(node, target, options) {
        if (!node) {
            return;
        }
        const settings = options || {};
        const duration = settings.duration || 1200;
        const decimals = settings.decimals || 0;
        const prefix = settings.prefix || "";
        const suffix = settings.suffix || "";
        const formatter = settings.formatter;
        const endValue = Number(target || 0);
        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        if (reduced) {
            node.textContent = formatter ? formatter(endValue) : `${prefix}${endValue.toFixed(decimals)}${suffix}`;
            return;
        }

        const start = performance.now();

        function frame(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = endValue * eased;
            node.textContent = formatter ? formatter(value) : `${prefix}${value.toFixed(decimals)}${suffix}`;
            if (progress < 1) {
                requestAnimationFrame(frame);
            } else {
                node.textContent = formatter ? formatter(endValue) : `${prefix}${endValue.toFixed(decimals)}${suffix}`;
            }
        }

        requestAnimationFrame(frame);
    }

    function driftColor(score) {
        const value = Number(score || 0);
        if (value > 0.7) {
            return "var(--danger)";
        }
        if (value >= 0.3) {
            return "var(--warn)";
        }
        return "var(--accent)";
    }

    function showToast(message, isError = false) {
      const toast = document.createElement('div');
      toast.className = 'toast' + (isError ? ' error' : '');
      toast.innerText = message;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
      }, 3000);
    }

    function parseHTML(html) {
        return new DOMParser().parseFromString(html, "text/html");
    }

    window.GregUI = {
        animateNumber,
        closeNav,
        driftColor,
        getState: function () {
            return lastState;
        },
        openNav,
        parseHTML,
        pollState,
    };

    if (navTrigger) {
        navTrigger.addEventListener("click", function () {
            if (navMenu && navMenu.hidden) {
                openNav();
            } else {
                closeNav();
            }
        });
    }

    if (navBackdrop) {
        navBackdrop.addEventListener("click", closeNav);
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && navMenu && !navMenu.hidden) {
            closeNav();
        }
    });

    setPulse(true);
    pollState();
    window.setInterval(pollState, 3000);
})();


