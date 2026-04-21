# For Builders

Builders do not throw prompts into a void. They declare measurable intents, respect the Build Protocol, and work inside a system that keeps execution, review, and economics visible.

## Declare An Intent

Use the public intent processor when you want Greg to execute a bounded task.

### `curl`

```bash
curl -X POST http://localhost:5000/api/intents/process \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"Build a launch page for a Base wallet onboarding service\"}"
```

### PowerShell

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/intents/process" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"description":"Build a launch page for a Base wallet onboarding service"}'
```

### JavaScript

```javascript
const response = await fetch("/api/intents/process", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    description: "Build a launch page for a Base wallet onboarding service"
  }),
});
const payload = await response.json();
console.log(payload);
```

## Use The Direct Task API

`/api/task` is the lightest way to ask Greg for a business or operational answer.

```bash
curl -X POST http://localhost:5000/api/task \
  -H "Content-Type: application/json" \
  -d "{\"task\":\"Write a go-to-market outline for a USDC checkout MVP\"}"
```

## Create A Payment Intent

`/api/payment/create-intent` returns a Base Sepolia USDC transfer payload that any injected wallet can send.

```bash
curl -X POST http://localhost:5000/api/payment/create-intent \
  -H "Content-Type: application/json" \
  -d "{\"service\":\"image\",\"description\":\"Generate a founder event poster\",\"wallet_address\":\"0x1111111111111111111111111111111111111111\"}"
```

## Spawn Agents

Only authorized surfaces should spawn agents. Public experimentation belongs in staging or founder-approved routes.

```bash
curl -X POST http://localhost:5000/api/greg/agents/spawn \
  -H "Content-Type: application/json" \
  -d "{\"perspective\":\"builder\",\"current_task\":\"prototype a docs parser\",\"build_protocol_steps\":[\"1\",\"2\",\"3\",\"4\",\"5\",\"6\",\"7\"]}"
```

## Contribute To The Ecosystem

1. Study the Constitution before proposing architecture changes.
2. Declare explicit intents instead of vague ambitions.
3. Keep tests, review, and deployment evidence attached to the work.
4. Make revenue, risk, and rollback visible.
