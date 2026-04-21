# API Reference

The core public endpoints are small by design. GregASI favors clear surfaces over hidden orchestration.

## `/api/task`

Purpose: ask Greg for a direct answer.

```bash
curl -X POST http://localhost:5000/api/task \
  -H "Content-Type: application/json" \
  -d "{\"task\":\"What is the fastest way to validate a USDC checkout MVP?\"}"
```

## `/api/intents/process`

Purpose: run a constitution-guarded intent through the Build Protocol.

```bash
curl -X POST http://localhost:5000/api/intents/process \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"Create a dark sovereign landing page for a founder office\"}"
```

## `/api/greg/image`

Purpose: generate and save an image asset, then return its URL.

```bash
curl -X POST http://localhost:5000/api/greg/image \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"A brass and emerald GregASI emblem\"}"
```

## `/api/payment/create-intent`

Purpose: return a wallet-ready Base Sepolia USDC transaction request.

```javascript
const response = await fetch("/api/payment/create-intent", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    service: "task",
    description: "Write a founder update on Base payments",
    wallet_address: "0x1111111111111111111111111111111111111111"
  }),
});
const payment = await response.json();
console.log(payment.transaction_request);
```

## `/api/payment/confirm`

Purpose: verify the Base transaction and release the paid result.

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/payment/confirm" `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{ "X-Greg-API-Key" = "greg-public-dev-key" } `
  -Body '{"payment_id":"pay_123","tx_hash":"mock_tx_hash","mock_confirm":true,"wallet_address":"0x1111111111111111111111111111111111111111"}'
```

## `/api/blog/generate`

Purpose: generate a constitution-vetted article in `pending_review`.

```bash
curl -X POST http://localhost:5000/api/blog/generate \
  -H "Content-Type: application/json" \
  -H "X-Greg-API-Key: greg-public-dev-key" \
  -d "{\"prompt\":\"Write a roadmap update about the self-healing runtime\"}"
```
