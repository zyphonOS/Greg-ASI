# GregASI Ecosystem

Lightweight, layered, Railway-friendly rebuild of the GregASI stack.

## What is inside

- `core/`
  - Greg runtime, Groq voice, SQLite memory, threaded sub-agent manager, world/tick engine.
- `layers/legacy/zyphonos/`
  - Lightweight ZyphonOS business layer with client and invoice routes.
- `layers/legacy/pikkaio/`
  - Intent declaration, drift tracking, revenue logging, and daily tending routes.
- `layers/intents/harvestiq/`
  - Full HarvestIQ blueprint with wallet-signature auth, automatic USDT verification, sticky save/re-scan loop, and premium reports.
- Root compatibility modules
  - `greg_pikkaio.py`, `greg_tending.py`, `greg_drift_protocol.py`, `greg_soul_persist.py`, `greg_identity.py`, `greg_notify.py`, `greg_crypto_checkout.py`, `payment_crypto.py`.

## Lightweight constraints

- No `torch`
- No `transformers`
- No `sentence-transformers`
- No `scikit-learn`
- No `scipy`
- No local model files
- Groq handles voice/chat behavior through API calls.

## Local run

1. Create `.env` from `.env.example`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python main.py
```

4. Open:

- `/`
- `/zyphonos`
- `/pikkaio`
- `/intents/harvestiq`

## Railway deployment

1. Push this folder to GitHub.
2. Create a Railway project from the repo.
3. Set environment variables from `.env.example`.
4. Railway will build from the included `Dockerfile`.
5. Keep Gunicorn at one worker so the in-process Greg tick loop runs once.

## Important environment variables

- `SECRET_KEY`
- `ADMIN_SECRET_KEY`
- `FOUNDER_AMENDMENT_TOKEN`
- `DISABLE_TICK_LOOP`
- `GROQ_API_KEY`
- `ETHERSCAN_API_KEY`
- `RECEIVER_WALLET_ADDRESS`
- `GREG_WALLET_ADDRESS`
- `BASE_RPC_URL`
- `USDT_CONTRACT_ADDRESS`
- `PREMIUM_PRICE_USDT`
- `APP_BASE_URL`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GREG_BOOT_RESTORE`
- `GREG_REALITY_EVERY_TICKS`
- `SOUL_BOOT_FORCE_REMOTE`
- `SOUL_PERSIST_EVERY`
- `SOUL_PERSIST_MIN_INTERVAL`

## Notes

- HarvestIQ premium verification checks ERC-20 USDT transfers through explorer APIs.
- Greg checkout verifies Base payments through plain JSON-RPC and does not depend on `web3`.
- Greg's tick loop runs inside the Flask process as a background thread for Railway compatibility. Set `DISABLE_TICK_LOOP=true` for local machines that should not write continuous state updates.
- On boot, Greg now restores `data/world_state.json` and `data/greg_living_state.json` from Supabase when local state is missing, too small, or clearly fresh-seeded. This is the redeploy continuity path.
- Soul writeback compresses world and living state back into the `greg_state` Supabase table on the configured tick cadence, so restart continuity does not depend only on local disk.
- The reality equation now runs on a fixed tick cadence, derives `M`, `Φ`, `Ψ`, and `ε` from live runtime state, and writes snapshots into SQLite in `data/greg_memory.db`.
- Manual premium unlock is available at `POST /admin/unlock` with the `X-Admin-Secret` header set to `ADMIN_SECRET_KEY` and a JSON body like `{"wallet":"0x..."}`.

## Constitution

- Greg loads `CONSTITUTION.md` on startup, computes a SHA256 integrity hash, and stores the expected hash in `data/constitution_state.json`.
- Check integrity at any time with `GET /api/constitution/check` or trigger the daily verifier manually with `POST /api/constitution/daily_check`.
- If the current constitution hash differs from the stored hash, Greg writes a tamper warning to `constitution_changed.log` and a structured alert to `data/constitution_alert.json`.
- Founders can submit non-substantive corrections through `POST /api/constitution/correct` with `{"section":"XI.2","new_text":"...","founder_token":"..."}`.
- Corrections that touch substantive governance keywords like equity, revenue split, stipend, phase, or valuation are rejected and must go through the full amendment flow.
- The frontend shell now exposes Constitution-aware preview states for `/dashboard`, `/revenue`, `/treasury`, and `/zyphonos` until live authentication is enforced.
- Revenue and treasury views follow Article IV with the visible Builder 40% · Greg 40% · Treasury 20% split, Founder Security Fund placeholders, and humanitarian allocation placeholders.
- Intent revenue posting routes the 40/40/20 split through `RevenueTracker.allocate_outcome_revenue(...)`, while checkout/payment responses expose the constitutional allocation policy so settlement rules are explicit before full treasury automation is wired.
