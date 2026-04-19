// treasury.js – Base Mainnet reads via viem (CDN ESM)
// No API key required. Basescan free tier used for tx history.

import {
  createPublicClient,
  http,
  formatEther,
  formatUnits,
} from "https://esm.sh/viem@2.21.19";
import { base } from "https://esm.sh/viem@2.21.19/chains";

const WALLET   = window.TREASURY_WALLET || "";
const USDC_ADDR = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const BASE_RPC  = "https://mainnet.base.org";
const BASESCAN  = "https://api.basescan.org/api";

// ── viem client ────────────────────────────────────────────────
const client = createPublicClient({
  chain: base,
  transport: http(BASE_RPC),
});

// ── ERC-20 balanceOf ABI fragment ──────────────────────────────
const ERC20_ABI = [
  {
    inputs: [{ name: "account", type: "address" }],
    name: "balanceOf",
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
    type: "function",
  },
];

// ── Helpers ────────────────────────────────────────────────────

function shortAddr(addr) {
  if (!addr || addr.length < 10) return addr;
  return addr.slice(0, 6) + "…" + addr.slice(-4);
}

function relativeTime(ts) {
  const diff = Math.floor(Date.now() / 1000) - parseInt(ts, 10);
  if (diff < 60)     return `${diff}s ago`;
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function setBalance(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = text;
}

// ── Fetch ETH balance ──────────────────────────────────────────
async function fetchETHBalance() {
  try {
    const raw = await client.getBalance({ address: WALLET });
    const val = parseFloat(formatEther(raw)).toFixed(6);
    setBalance("eth-balance", val);
  } catch (e) {
    setBalance("eth-balance", `<span class="tbc-loading">ERROR</span>`);
    console.error("ETH balance error:", e);
  }
}

// ── Fetch USDC balance ─────────────────────────────────────────
async function fetchUSDCBalance() {
  try {
    const raw = await client.readContract({
      address: USDC_ADDR,
      abi: ERC20_ABI,
      functionName: "balanceOf",
      args: [WALLET],
    });
    // USDC has 6 decimals on Base
    const val = parseFloat(formatUnits(raw, 6)).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    setBalance("usdc-balance", val);
  } catch (e) {
    setBalance("usdc-balance", `<span class="tbc-loading">ERROR</span>`);
    console.error("USDC balance error:", e);
  }
}

// ── Fetch recent transactions (Basescan free, no key) ──────────
async function fetchTransactions() {
  const tbody  = document.getElementById("txn-tbody");
  const errDiv = document.getElementById("txn-error");
  const url    = `${BASESCAN}?module=account&action=txlist&address=${WALLET}&startblock=0&endblock=99999999&sort=desc&offset=10&page=1`;

  try {
    const resp = await fetch(url);
    const data = await resp.json();

    if (data.status !== "1" || !Array.isArray(data.result) || data.result.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding:2rem 1rem;text-align:center;color:var(--muted);font-size:0.7rem;letter-spacing:.1em;">NO TRANSACTIONS FOUND</td></tr>`;
      return;
    }

    const walletLower = WALLET.toLowerCase();
    const rows = data.result.map((tx) => {
      const fromLower = tx.from.toLowerCase();
      const toLower   = (tx.to || "").toLowerCase();
      const fromClass = fromLower === walletLower ? "txn-addr self" : "txn-addr";
      const toClass   = toLower   === walletLower ? "txn-addr self" : "txn-addr";
      const val       = parseFloat(formatEther(BigInt(tx.value))).toFixed(6);

      return `<tr>
        <td><a class="txn-hash-link" href="https://basescan.org/tx/${tx.hash}" target="_blank" rel="noopener noreferrer">${shortAddr(tx.hash)}</a></td>
        <td>${parseInt(tx.blockNumber, 10).toLocaleString()}</td>
        <td><span class="${fromClass}">${shortAddr(tx.from)}</span></td>
        <td><span class="${toClass}">${tx.to ? shortAddr(tx.to) : "CONTRACT CREATE"}</span></td>
        <td>${val}</td>
        <td>${relativeTime(tx.timeStamp)}</td>
      </tr>`;
    });

    tbody.innerHTML = rows.join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding:2rem 1rem;text-align:center;color:var(--muted);font-size:0.7rem;letter-spacing:.1em;">FETCH ERROR</td></tr>`;
    errDiv.textContent = "Basescan API unavailable. Check network or try again later.";
    errDiv.style.display = "block";
    console.error("TX fetch error:", e);
  }
}

// ── Copy address ───────────────────────────────────────────────
function initCopyBtn() {
  const btn   = document.getElementById("copy-addr-btn");
  const toast = document.getElementById("copy-toast");
  if (!btn || !toast) return;

  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(WALLET);
      toast.classList.add("visible");
      setTimeout(() => toast.classList.remove("visible"), 1800);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = WALLET;
      ta.style.position = "fixed";
      ta.style.opacity  = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      toast.classList.add("visible");
      setTimeout(() => toast.classList.remove("visible"), 1800);
    }
  });
}

// ── Timestamp ─────────────────────────────────────────────────
function setTimestamp() {
  const el = document.getElementById("fetch-timestamp");
  if (el) {
    const now = new Date();
    el.textContent = now.toUTCString();
  }
}

// ── Init ───────────────────────────────────────────────────────
(async () => {
  if (!WALLET || WALLET === "0x0000000000000000000000000000000000000000") {
    setBalance("eth-balance", `<span class="tbc-loading">NO WALLET SET</span>`);
    setBalance("usdc-balance", `<span class="tbc-loading">NO WALLET SET</span>`);
    document.getElementById("txn-tbody").innerHTML =
      `<tr><td colspan="6" style="padding:2rem 1rem;text-align:center;color:var(--muted);font-size:0.7rem;letter-spacing:.1em;">TREASURY_WALLET_ADDRESS NOT CONFIGURED</td></tr>`;
    setTimestamp();
    initCopyBtn();
    return;
  }

  initCopyBtn();
  await Promise.all([fetchETHBalance(), fetchUSDCBalance(), fetchTransactions()]);
  setTimestamp();
})();