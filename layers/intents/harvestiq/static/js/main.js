const bootstrap = window.HARVESTIQ_BOOTSTRAP || {};
const apiBase = (bootstrap.apiBase || "").replace(/\/$/, "");

const form = document.getElementById("analysis-form");
const submitButton = document.getElementById("submit-button");
const formStatus = document.getElementById("form-status");
const addressInput = document.getElementById("address");
const chainSelect = document.getElementById("chain");
const recentWalletsSelect = document.getElementById("recent-wallets");
const connectWalletButton = document.getElementById("connect-wallet-button");
const walletPill = document.getElementById("wallet-pill");

const resultsShell = document.getElementById("results-shell");
const resultTitle = document.getElementById("result-title");
const scoreValue = document.getElementById("score-value");
const scoreProgress = document.getElementById("score-progress");
const riskPill = document.getElementById("risk-pill");
const resultSummary = document.getElementById("result-summary");
const componentList = document.getElementById("component-list");
const recommendationList = document.getElementById("recommendation-list");
const premiumPreview = document.getElementById("premium-preview");
const upsellCopy = document.getElementById("upsell-copy");
const metricTx = document.getElementById("metric-tx");
const metricContracts = document.getElementById("metric-contracts");
const metricInbound = document.getElementById("metric-inbound");
const saveWalletButton = document.getElementById("save-wallet-button");
const shareButton = document.getElementById("share-button");
const unlockButton = document.getElementById("unlock-button");
const openReportLink = document.getElementById("open-report-link");

const savedWalletList = document.getElementById("saved-wallet-list");
const leaderboardList = document.getElementById("leaderboard-list");

const paymentModal = document.getElementById("payment-modal");
const closeModalButton = document.getElementById("close-modal-button");
const modalWallet = document.getElementById("modal-wallet");
const txHashInput = document.getElementById("tx-hash-input");
const paymentStatus = document.getElementById("payment-status");
const payUsdtButton = document.getElementById("pay-usdt-button");
const verifyPaymentButton = document.getElementById("verify-payment-button");

const circumference = 2 * Math.PI * 48;
const LOCAL_WALLETS_KEY = "harvestiq-saved-wallets";

const state = {
    authenticatedWallet: (bootstrap.authenticatedWallet || "").toLowerCase(),
    premiumAccess: Boolean(bootstrap.premiumAccess),
    walletPremiumAccess: Boolean(bootstrap.premiumAccess),
    currentReport: null,
    pollingTimer: null,
    pendingTxHash: "",
};

function apiUrl(path) {
    const suffix = path.startsWith("/") ? path : `/${path}`;
    return `${apiBase}${suffix}`;
}

function shortWallet(address) {
    if (!address) {
        return "No wallet connected";
    }
    return `${address.slice(0, 8)}...${address.slice(-4)}`;
}

function setWalletPill(address) {
    walletPill.textContent = shortWallet(address);
}

function riskToneClass(score) {
    if (score >= 70) {
        return "high";
    }
    if (score >= 40) {
        return "medium";
    }
    return "low";
}

function setGauge(score) {
    const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
    const offset = circumference - (safeScore / 100) * circumference;
    const tone = riskToneClass(safeScore);
    scoreValue.textContent = safeScore;
    scoreProgress.style.strokeDashoffset = `${offset}`;
    scoreProgress.classList.remove("risk-low", "risk-medium", "risk-high");
    scoreProgress.classList.add(`risk-${tone}`);
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options,
    });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || payload.message || "Request failed.");
    }
    return payload;
}

function dedupeWallets(list) {
    const seen = new Set();
    const deduped = [];
    for (const item of list) {
        const address = (item.address || "").toLowerCase();
        const chain = item.chain || "eth";
        const key = `${address}:${chain}`;
        if (!address || seen.has(key)) {
            continue;
        }
        seen.add(key);
        deduped.push({
            address,
            chain,
            chain_label: item.chain_label || chain.toUpperCase(),
            score: item.score,
            risk_level: item.risk_level,
        });
    }
    return deduped;
}

function localWallets() {
    try {
        const raw = window.localStorage.getItem(LOCAL_WALLETS_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (error) {
        return [];
    }
}

function persistLocalWallets(wallets) {
    window.localStorage.setItem(LOCAL_WALLETS_KEY, JSON.stringify(wallets.slice(0, 15)));
}

function mergeWalletSources() {
    return dedupeWallets([
        ...(bootstrap.savedWallets || []),
        ...(bootstrap.recentWallets || []),
        ...localWallets(),
    ]);
}

function renderRecentWallets() {
    const wallets = mergeWalletSources();
    recentWalletsSelect.innerHTML = '<option value="">Pick a saved or recent wallet</option>';
    savedWalletList.innerHTML = "";

    if (!wallets.length) {
        savedWalletList.innerHTML = '<p class="empty-state">No wallets saved yet. Run a scan, then save the ones you want to keep returning to.</p>';
        return;
    }

    wallets.forEach((wallet) => {
        const option = document.createElement("option");
        option.value = JSON.stringify(wallet);
        option.textContent = `${shortWallet(wallet.address)} | ${wallet.chain_label}`;
        recentWalletsSelect.appendChild(option);

        const card = document.createElement("button");
        card.type = "button";
        card.className = "wallet-card";
        card.innerHTML = `
            <strong>${shortWallet(wallet.address)}</strong>
            <span>${wallet.chain_label}</span>
            <small>${wallet.score !== undefined ? `${wallet.score}/100 | ${wallet.risk_level} risk` : "Saved for re-scan"}</small>
        `;
        card.addEventListener("click", () => {
            addressInput.value = wallet.address;
            chainSelect.value = wallet.chain;
        });
        savedWalletList.appendChild(card);
    });
}

function renderLeaderboard(leaders) {
    leaderboardList.innerHTML = "";
    if (!leaders.length) {
        leaderboardList.innerHTML = '<p class="empty-state">Leaderboard populates as wallets are scanned.</p>';
        return;
    }

    leaders.forEach((leader, index) => {
        const row = document.createElement("div");
        row.className = "leader-row";
        row.innerHTML = `
            <span class="leader-rank">#${index + 1}</span>
            <strong>${leader.address_masked}</strong>
            <span>${leader.chain_label}</span>
            <span>${leader.score}/100</span>
        `;
        leaderboardList.appendChild(row);
    });
}

function componentMarkup(component) {
    const percentage = Math.max(4, Math.round((component.score / component.max_score) * 100));
    return `
        <article class="component-card">
            <div class="component-title-row">
                <div>
                    <h4>${component.label}</h4>
                    <p>${component.summary}</p>
                </div>
                <span class="risk-pill risk-${component.risk.toLowerCase()}">${component.score}/${component.max_score}</span>
            </div>
            <div class="progress-shell">
                <div class="progress-bar">
                    <span class="progress-fill risk-${component.risk.toLowerCase()}" style="width:${percentage}%"></span>
                </div>
            </div>
        </article>
    `;
}

function currentCheckedWallet() {
    return (
        state.authenticatedWallet ||
        (state.currentReport ? state.currentReport.address.toLowerCase() : "") ||
        addressInput.value.trim().toLowerCase()
    );
}

function updatePremiumControls() {
    if (!state.currentReport) {
        return;
    }

    const reportWallet = (state.currentReport.address || "").toLowerCase();
    const sameWalletConnected = Boolean(state.authenticatedWallet) && state.authenticatedWallet === reportWallet;

    if (state.premiumAccess) {
        openReportLink.classList.remove("hidden");
        unlockButton.classList.add("hidden");
        return;
    }

    openReportLink.classList.add("hidden");
    unlockButton.classList.remove("hidden");

    if (sameWalletConnected && state.walletPremiumAccess) {
        unlockButton.textContent = "Verify Wallet to Open Premium";
        return;
    }

    unlockButton.textContent = "Unlock Premium";
}

function renderResult(report) {
    state.currentReport = report;
    resultsShell.classList.remove("hidden");
    resultTitle.textContent = `${report.chain_label} | ${shortWallet(report.address)}`;
    setGauge(report.score);
    const tone = riskToneClass(report.score);
    riskPill.className = `risk-pill risk-${tone}`;
    riskPill.textContent = `${report.score}/100 | ${report.risk_level} risk`;
    resultSummary.textContent = report.summary;

    metricTx.textContent = report.totals.tx_count;
    metricContracts.textContent = report.totals.contract_calls;
    metricInbound.textContent = report.totals.inbound_transfers;

    componentList.innerHTML = report.components.map(componentMarkup).join("");
    recommendationList.innerHTML = report.recommendations.map((item) => `<li>${item}</li>`).join("");
    premiumPreview.innerHTML = [
        "Exact transaction hashes tied to penalties",
        "A step-by-step optimisation checklist ranked by impact",
        "Full component scores with detailed breakdown bars",
        "One-click re-scan path after you fix the wallet",
    ].map((item) => `<li>${item}</li>`).join("");

    upsellCopy.textContent = report.upsell_copy;
    openReportLink.href = report.premium_url;
    state.walletPremiumAccess = Boolean(report.wallet_premium_access || state.walletPremiumAccess);
    updatePremiumControls();
}

async function refreshSessionState(wallet = "") {
    try {
        const checkedWallet = (wallet || currentCheckedWallet() || "").toLowerCase();
        const sessionUrl = new URL(apiUrl("/session-state"), window.location.origin);
        sessionUrl.searchParams.set("_", String(Date.now()));
        if (checkedWallet) {
            sessionUrl.searchParams.set("wallet", checkedWallet);
        }

        const data = await requestJson(sessionUrl.toString());
        const serverWallet = (data.authenticated_wallet || "").toLowerCase();
        if (serverWallet) {
            state.authenticatedWallet = serverWallet;
        }
        state.premiumAccess = Boolean(data.premium_access);
        state.walletPremiumAccess = Boolean(data.checked_wallet_premium || data.is_premium);
        bootstrap.savedWallets = data.saved_wallets || [];
        bootstrap.recentWallets = data.scan_history || [];
        bootstrap.leaderboard = data.leaderboard || [];
        setWalletPill(state.authenticatedWallet);
        renderRecentWallets();
        renderLeaderboard(bootstrap.leaderboard || []);
        updatePremiumControls();
    } catch (error) {
        console.error(error);
    }
}

async function analyseWallet(event) {
    event.preventDefault();
    formStatus.textContent = "Reading the wallet trail...";
    submitButton.disabled = true;

    try {
        const payload = await requestJson(apiUrl("/analyze"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                address: addressInput.value.trim(),
                chain: chainSelect.value,
            }),
        });

        renderResult(payload);
        await refreshSessionState(payload.address);
        const sameWalletPremium = Boolean(state.authenticatedWallet) && state.authenticatedWallet === payload.address.toLowerCase() && state.walletPremiumAccess;
        formStatus.textContent = sameWalletPremium
            ? "Premium access detected for this wallet. Verify the wallet and open the full report."
            : "Scan finished. Save the wallet or unlock premium if you want the exact damage report.";
    } catch (error) {
        formStatus.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
}

async function saveCurrentWallet() {
    if (!state.currentReport) {
        return;
    }

    try {
        await requestJson(apiUrl("/save-wallet"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                address: state.currentReport.address,
                chain: state.currentReport.chain,
            }),
        });

        const merged = dedupeWallets([
            ...localWallets(),
            {
                address: state.currentReport.address,
                chain: state.currentReport.chain,
                chain_label: state.currentReport.chain_label,
                score: state.currentReport.score,
                risk_level: state.currentReport.risk_level,
            },
        ]);
        persistLocalWallets(merged);
        await refreshSessionState();
        formStatus.textContent = "Wallet saved. Re-scan it after you apply the fixes.";
    } catch (error) {
        formStatus.textContent = error.message;
    }
}

async function shareCurrentScore() {
    if (!state.currentReport) {
        return;
    }

    try {
        const payload = await requestJson(apiUrl("/share-score"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report_id: state.currentReport.report_id }),
        });
        window.open(payload.tweet_url, "_blank", "noopener,noreferrer");
    } catch (error) {
        formStatus.textContent = error.message;
    }
}

function openPaymentModal() {
    paymentModal.classList.remove("hidden");
    paymentModal.setAttribute("aria-hidden", "false");
    modalWallet.textContent = shortWallet(state.authenticatedWallet);
    paymentStatus.textContent = "";
}

function closePaymentModal() {
    paymentModal.classList.add("hidden");
    paymentModal.setAttribute("aria-hidden", "true");
}

function stopPolling() {
    if (state.pollingTimer) {
        window.clearInterval(state.pollingTimer);
        state.pollingTimer = null;
    }
}

async function pollPaymentStatus() {
    if (!state.pendingTxHash || !state.authenticatedWallet) {
        return;
    }

    try {
        const payload = await requestJson(`${apiUrl("/payment-status")}?address=${encodeURIComponent(state.authenticatedWallet)}&tx_hash=${encodeURIComponent(state.pendingTxHash)}`);
        paymentStatus.textContent = payload.message;

        if (payload.status === "confirmed") {
            stopPolling();
            state.premiumAccess = true;
            paymentStatus.textContent = "Payment confirmed. Opening your premium report...";
            window.location.href = state.currentReport.premium_url;
        }
    } catch (error) {
        paymentStatus.textContent = error.message;
    }
}

async function verifyPayment() {
    if (!state.currentReport || !state.authenticatedWallet) {
        paymentStatus.textContent = "Connect and sign your wallet first.";
        return;
    }

    const txHash = txHashInput.value.trim();
    if (!txHash) {
        paymentStatus.textContent = "Paste or generate the USDT transaction hash first.";
        return;
    }

    paymentStatus.textContent = "Checking the payment on-chain...";
    try {
        const payload = await requestJson(apiUrl("/check-payment"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                address: state.authenticatedWallet,
                tx_hash: txHash,
                report_id: state.currentReport.report_id,
            }),
        });

        if (payload.status === "confirmed") {
            state.premiumAccess = true;
            paymentStatus.textContent = payload.message;
            window.location.href = payload.report_url || state.currentReport.premium_url;
            return;
        }

        state.pendingTxHash = txHash;
        paymentStatus.textContent = payload.message;
        stopPolling();
        state.pollingTimer = window.setInterval(pollPaymentStatus, 5000);
    } catch (error) {
        paymentStatus.textContent = error.message;
    }
}

async function runUnlockFlow() {
    if (!state.currentReport) {
        formStatus.textContent = "Run a scan first so HarvestIQ knows which report to unlock.";
        return;
    }

    if (state.premiumAccess) {
        window.location.href = state.currentReport.premium_url;
        return;
    }

    try {
        connectWalletButton.disabled = true;
        const payload = await window.HarvestIQWeb3.authenticateWallet();
        state.authenticatedWallet = payload.address.toLowerCase();
        state.premiumAccess = Boolean(payload.premium_access);
        state.walletPremiumAccess = Boolean(payload.wallet_premium_access || payload.is_premium || payload.premium_access);
        setWalletPill(state.authenticatedWallet);
        updatePremiumControls();

        if (state.premiumAccess) {
            window.location.href = state.currentReport.premium_url;
            return;
        }

        openPaymentModal();
    } catch (error) {
        formStatus.textContent = error.message;
    } finally {
        connectWalletButton.disabled = false;
    }
}

async function connectWalletOnly() {
    try {
        const wallet = await window.HarvestIQWeb3.connectWallet();
        state.authenticatedWallet = wallet.address.toLowerCase();
        setWalletPill(state.authenticatedWallet);
        await refreshSessionState(state.authenticatedWallet);
        formStatus.textContent = state.walletPremiumAccess
            ? "Wallet connected. Premium status detected from JSON; verify once to open the report."
            : "Wallet connected. Sign when you are ready to unlock premium.";
    } catch (error) {
        formStatus.textContent = error.message;
    }
}

async function sendUsdtFromWallet() {
    try {
        payUsdtButton.disabled = true;
        paymentStatus.textContent = "Opening MetaMask for the USDT transfer...";
        const payload = await window.HarvestIQWeb3.sendUsdtPayment(bootstrap.receiverWallet, bootstrap.paymentAmount);
        txHashInput.value = payload.hash;
        state.pendingTxHash = payload.hash;
        paymentStatus.textContent = "Transfer submitted. Waiting for confirmation...";
        await verifyPayment();
    } catch (error) {
        paymentStatus.textContent = error.message;
    } finally {
        payUsdtButton.disabled = false;
    }
}

function hydrateFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const address = params.get("address");
    const chain = params.get("chain");
    if (address) {
        addressInput.value = address;
    }
    if (chain && chainSelect.querySelector(`option[value="${chain}"]`)) {
        chainSelect.value = chain;
    }
}

function bindEvents() {
    form.addEventListener("submit", analyseWallet);
    saveWalletButton.addEventListener("click", saveCurrentWallet);
    shareButton.addEventListener("click", shareCurrentScore);
    unlockButton.addEventListener("click", runUnlockFlow);
    connectWalletButton.addEventListener("click", connectWalletOnly);
    payUsdtButton.addEventListener("click", sendUsdtFromWallet);
    verifyPaymentButton.addEventListener("click", verifyPayment);
    closeModalButton.addEventListener("click", closePaymentModal);
    paymentModal.addEventListener("click", (event) => {
        if (event.target.dataset.closeModal === "true") {
            closePaymentModal();
        }
    });

    recentWalletsSelect.addEventListener("change", (event) => {
        if (!event.target.value) {
            return;
        }
        const wallet = JSON.parse(event.target.value);
        addressInput.value = wallet.address;
        chainSelect.value = wallet.chain;
    });

    window.addEventListener("harvestiq:wallet-changed", (event) => {
        state.authenticatedWallet = (event.detail.address || "").toLowerCase();
        setWalletPill(state.authenticatedWallet);
        if (state.authenticatedWallet) {
            refreshSessionState(state.authenticatedWallet);
            return;
        }
        state.walletPremiumAccess = false;
        updatePremiumControls();
    });
}

async function init() {
    bindEvents();
    hydrateFromQuery();
    setWalletPill(state.authenticatedWallet);
    renderRecentWallets();
    renderLeaderboard(bootstrap.leaderboard || []);
    setGauge(0);
    await refreshSessionState();
}

init();
