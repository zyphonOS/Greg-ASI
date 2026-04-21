# For Users

GregASI is a Constitution-bound operating organism. You are not navigating a generic app. You are entering a governed system that keeps the mission, economics, and execution path visible.

## Sign Up

1. Open `/signup`.
2. Create an account with an email and password.
3. Log in to unlock chat, profile, and protected builder surfaces.

## Connect A Wallet

1. Open `/connect-wallet`.
2. Connect a Base-compatible wallet such as MetaMask or Coinbase Wallet.
3. Switch to Base Sepolia when prompted.
4. Your address is then available for payments and attribution.

## Chat With Greg

1. Open `/chat`.
2. Choose a room: `general`, `tech`, or `random`.
3. Ask Greg a direct question.
4. Greg responds through the same think path that powers the wider organism.

## Generate Images

Use `/api/greg/image` or the public checkout at `/pay`.

### `curl`

```bash
curl -X POST http://localhost:5000/api/greg/image \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"A sovereign GregASI sigil in a dark chamber\"}"
```

### PowerShell

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/greg/image" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"prompt":"A sovereign GregASI sigil in a dark chamber"}'
```

### JavaScript

```javascript
const response = await fetch("/api/greg/image", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ prompt: "A sovereign GregASI sigil in a dark chamber" }),
});
const payload = await response.json();
console.log(payload.image_url);
```

## Pay With USDC

Use `/pay` for the guided flow or call `/api/payment/create-intent` directly.

### Price Reference

- Image generation: `$5 USDC`
- Code page: `$10 USDC`
- Business task: `$2 USDC`

## View Intent History

Users can review personal state and wallet posture from `/profile`. Founders can inspect the full queue from `/founder-office`.
