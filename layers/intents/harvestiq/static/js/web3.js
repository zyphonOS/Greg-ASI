(function bootstrapHarvestIQWeb3() {
    const ERC20_ABI = [
        "function transfer(address to, uint256 value) returns (bool)",
    ];
    const MAINNET_USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7";

    let provider = null;
    let signer = null;
    let selectedAddress = "";
    const apiBase = ((window.HARVESTIQ_BOOTSTRAP || {}).apiBase || "").replace(/\/$/, "");

    function apiUrl(path) {
        const suffix = path.startsWith("/") ? path : `/${path}`;
        return `${apiBase}${suffix}`;
    }

    function ensureEthereum() {
        if (!window.ethereum || !window.ethers) {
            throw new Error("MetaMask is required for wallet signature and USDT payment.");
        }
    }

    async function setupProvider() {
        ensureEthereum();
        provider = new window.ethers.BrowserProvider(window.ethereum);
        return provider;
    }

    async function connectWallet() {
        const activeProvider = await setupProvider();
        await activeProvider.send("eth_requestAccounts", []);
        signer = await activeProvider.getSigner();
        selectedAddress = (await signer.getAddress()).toLowerCase();
        window.dispatchEvent(new CustomEvent("harvestiq:wallet-changed", { detail: { address: selectedAddress } }));
        return { address: selectedAddress };
    }

    async function ensureConnected() {
        if (selectedAddress && signer) {
            return { address: selectedAddress };
        }
        return connectWallet();
    }

    async function requestJson(url, body) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || payload.message || "Wallet request failed.");
        }
        return payload;
    }

    async function authenticateWallet() {
        const wallet = await ensureConnected();
        const noncePayload = await requestJson(apiUrl("/auth/nonce"), { address: wallet.address });
        const signature = await signer.signMessage(noncePayload.message);
        return requestJson(apiUrl("/auth/verify"), {
            address: wallet.address,
            signature,
            nonce: noncePayload.nonce,
        });
    }

    async function assertEthereumMainnet() {
        const activeProvider = await setupProvider();
        const network = await activeProvider.getNetwork();
        if (Number(network.chainId) !== 1) {
            throw new Error("Switch MetaMask to Ethereum mainnet before sending USDT.");
        }
    }

    async function sendUsdtPayment(receiverWallet, amount) {
        const wallet = await ensureConnected();
        await assertEthereumMainnet();
        const receiverAddress = receiverWallet;
        // Ethers expects a checksummed recipient on transfer to avoid bad-address failures in wallet flows.
        const checksummedReceiver = window.ethers.getAddress(receiverAddress);
        const amountInWei = window.ethers.parseUnits(String(amount), 6);

        const contract = new window.ethers.Contract(
            window.HARVESTIQ_BOOTSTRAP.usdtContract || MAINNET_USDT_CONTRACT,
            ERC20_ABI,
            signer,
        );

        const tx = await contract.transfer(checksummedReceiver, amountInWei);

        return {
            hash: tx.hash,
            address: wallet.address,
        };
    }

    if (window.ethereum) {
        window.ethereum.on("accountsChanged", async (accounts) => {
            selectedAddress = (accounts && accounts[0] ? accounts[0] : "").toLowerCase();
            if (selectedAddress && provider) {
                signer = await provider.getSigner();
            }
            window.dispatchEvent(new CustomEvent("harvestiq:wallet-changed", { detail: { address: selectedAddress } }));
        });
    }

    window.HarvestIQWeb3 = {
        connectWallet,
        authenticateWallet,
        sendUsdtPayment,
    };
})();
