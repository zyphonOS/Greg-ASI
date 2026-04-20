(function () {
    const bootstrap = window.GREG_CHECKOUT || {};
    const services = Array.isArray(bootstrap.services) ? bootstrap.services : [];
    const chainId = Number(bootstrap.chainId || 84532);

    const form = document.getElementById("pay-form");
    const serviceSelect = document.getElementById("pay-service");
    const descriptionInput = document.getElementById("pay-description");
    const connectButton = document.getElementById("connect-wallet");
    const payButton = document.getElementById("start-payment");
    const walletStatus = document.getElementById("wallet-status");
    const priceNode = document.getElementById("service-price");
    const resultPanel = document.getElementById("checkout-result");

    let walletAddress = "";

    if (!form || !serviceSelect || !descriptionInput || !connectButton || !payButton || !walletStatus || !priceNode || !resultPanel) {
        return;
    }

    function serviceConfig() {
        return services.find((item) => item.service === serviceSelect.value) || services[0] || { service: "image", price: 5 };
    }

    function renderPrice() {
        const item = serviceConfig();
        priceNode.textContent = `$${Number(item.price || 0).toFixed(0)} USDC`;
    }

    async function ensureBaseSepolia() {
        if (!window.ethereum) {
            throw new Error("No injected wallet found. Install MetaMask or Coinbase Wallet.");
        }
        const chainHex = `0x${chainId.toString(16)}`;
        try {
            await window.ethereum.request({
                method: "wallet_switchEthereumChain",
                params: [{ chainId: chainHex }],
            });
        } catch (error) {
            await window.ethereum.request({
                method: "wallet_addEthereumChain",
                params: [{
                    chainId: chainHex,
                    chainName: "Base Sepolia",
                    nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
                    rpcUrls: ["https://sepolia.base.org"],
                    blockExplorerUrls: ["https://sepolia.basescan.org"],
                }],
            });
        }
    }

    async function connectWallet() {
        await ensureBaseSepolia();
        const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
        walletAddress = (accounts && accounts[0]) || "";
        if (!walletAddress) {
            throw new Error("Wallet connection failed.");
        }
        walletStatus.textContent = walletAddress;
        return walletAddress;
    }

    function renderResult(payload) {
        const result = payload.service_result || {};
        if (result.service === "image" && result.image_url) {
            resultPanel.innerHTML = `
              <span class="commerce-label">Image Complete</span>
              <img src="${result.image_url}" alt="Generated image">
              <a class="commerce-link" href="${result.image_url}" target="_blank" rel="noreferrer">Open image</a>
            `;
            return;
        }
        if (result.service === "code" && result.full_url) {
            resultPanel.innerHTML = `
              <span class="commerce-label">Code Page Complete</span>
              <p>${result.status || "done"}</p>
              <a class="commerce-link" href="${result.full_url}" target="_blank" rel="noreferrer">Open deployed page</a>
            `;
            return;
        }
        resultPanel.innerHTML = `
          <span class="commerce-label">Task Complete</span>
          <p>${result.response || result.message || payload.credit_message || "Completed."}</p>
        `;
    }

    async function createPaymentIntent() {
        const item = serviceConfig();
        const response = await fetch("/api/payment/create-intent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                service: item.service,
                description: descriptionInput.value.trim(),
                wallet_address: walletAddress,
            }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Unable to create payment intent.");
        }
        return payload;
    }

    async function sendUsdcTransaction(transactionRequest) {
        const txHash = await window.ethereum.request({
            method: "eth_sendTransaction",
            params: [{
                from: walletAddress,
                to: transactionRequest.to,
                data: transactionRequest.data,
                value: transactionRequest.value || "0x0",
            }],
        });
        return txHash;
    }

    async function confirmPayment(paymentId, txHash) {
        const response = await fetch("/api/payment/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                payment_id: paymentId,
                tx_hash: txHash,
                wallet_address: walletAddress,
            }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Payment confirmation failed.");
        }
        return payload;
    }

    connectButton.addEventListener("click", async () => {
        try {
            await connectWallet();
        } catch (error) {
            walletStatus.textContent = error.message;
        }
    });

    serviceSelect.addEventListener("change", renderPrice);
    renderPrice();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!descriptionInput.value.trim()) {
            resultPanel.innerHTML = "<p>Description is required.</p>";
            return;
        }
        payButton.disabled = true;
        try {
            if (!walletAddress) {
                await connectWallet();
            }
            resultPanel.innerHTML = "<p>Creating payment intent...</p>";
            const payment = await createPaymentIntent();
            resultPanel.innerHTML = "<p>Requesting USDC transaction from wallet...</p>";
            const txHash = await sendUsdcTransaction(payment.transaction_request);
            resultPanel.innerHTML = "<p>Confirming on Base Sepolia...</p>";
            const confirmed = await confirmPayment(payment.payment_id, txHash);
            renderResult(confirmed);
        } catch (error) {
            resultPanel.innerHTML = `<p>${error.message}</p>`;
        } finally {
            payButton.disabled = false;
        }
    });
})();
