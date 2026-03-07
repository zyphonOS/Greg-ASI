"""
train_higgs.py — GregASI v2 Higgs-Inspired Sequence Model Training

Architecture:
    Input (40) → H1 (128) → [phi gate] → H2 (64) → logits (8)

The phi gate scales hidden activations by agent consciousness:
    H1_gated = H1 * (0.5 + phi)
Low phi agents (~massless) get 0.5x activation.
High phi agents (~massive) get up to 1.5x — richer, more expressive decisions.

Features (40 total):
    0-34: last 5 actions × 7 features each
        f0: action index (normalized)
        f1: location index (normalized)
        f2: success (0/1)
        f3: mon delta (clipped)
        f4: kuru delta (clipped)
        f5: archetype index (normalized)
        f6: generation (clipped)
    35: mon (normalized)
    36: phi
    37: arousal (from drives)
    38: valence proxy (freedom - protect)
    39: explore drive

Output: 8 action classes (ACTION_NAMES order)

Usage:
    python train_higgs.py
    python train_higgs.py --epochs 20 --lr 0.003
"""

import numpy as np
import json
import os
import time
import argparse
from pathlib import Path
from collections import Counter

# ── CONFIG ─────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
LOG_PATH   = BASE_DIR / "data" / "tick_log.jsonl"
MODEL_OUT  = BASE_DIR / "data" / "sequence_model.npz"
CKPT_OUT   = BASE_DIR / "data" / "sequence_model_checkpoint.npz"

SEQUENCE_LEN = 5
FEATURE_PER_STEP = 7
FEATURE_DIM = SEQUENCE_LEN * FEATURE_PER_STEP  # 35
STATE_DIM   = 5   # mon, phi, arousal, valence, explore
INPUT_DIM   = FEATURE_DIM + STATE_DIM  # 40

HIDDEN1   = 128
HIDDEN2   = 64
MAX_SAMPLES = 500_000
EPOCHS    = 15
LR        = 0.005
BATCH_SIZE = 512

ACTION_NAMES = ['move', 'collect', 'trade', 'deposit', 'reproduce', 'build', 'learn', 'rest']
ACTION_TO_IDX = {a: i for i, a in enumerate(ACTION_NAMES)}
N_ACTIONS = len(ACTION_NAMES)

ARCHETYPES = ['guardian', 'steward', 'visionary', 'wanderer', 'magnate', 'belmar', 'sage', 'scholar', 'native']
ARCHETYPE_TO_IDX = {a: i for i, a in enumerate(ARCHETYPES)}

# ── ARGS ───────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--epochs",  type=int,   default=EPOCHS)
parser.add_argument("--lr",      type=float, default=LR)
parser.add_argument("--batch",   type=int,   default=BATCH_SIZE)
parser.add_argument("--max",     type=int,   default=MAX_SAMPLES)
parser.add_argument("--log",     type=str,   default=str(LOG_PATH))
parser.add_argument("--out",     type=str,   default=str(MODEL_OUT))
args = parser.parse_args()

# ── DATA LOADING ───────────────────────────────────────────────────────────

def load_data():
    print(f"[train] Loading {args.log} ...")
    if not os.path.exists(args.log):
        print(f"[ERROR] tick_log.jsonl not found at {args.log}")
        return None, None

    # Group records by agent
    agent_history = {}
    skipped = 0
    with open(args.log, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line.strip())
                aid = rec.get("a")
                if not aid:
                    continue
                if aid not in agent_history:
                    agent_history[aid] = []
                agent_history[aid].append(rec)
            except Exception:
                skipped += 1

    print(f"[train] {len(agent_history):,} agents | {skipped} bad lines skipped")

    # Build sequences: for each agent, slide window of 5 → predict next action
    X_list, y_list, phi_list = [], [], []

    for aid, records in agent_history.items():
        records.sort(key=lambda r: r.get("t", 0))
        if len(records) < SEQUENCE_LEN + 1:
            continue

        for i in range(len(records) - SEQUENCE_LEN):
            seq = records[i: i + SEQUENCE_LEN]
            target = records[i + SEQUENCE_LEN]

            target_act = target.get("act", "move")
            if target_act not in ACTION_TO_IDX:
                # map old action names
                remap = {"kuru_deposit": "deposit", "observe": "rest", "rest": "rest"}
                target_act = remap.get(target_act, "move")
            y = ACTION_TO_IDX[target_act]

            # Build feature vector
            x = np.zeros(INPUT_DIM, dtype=np.float32)
            for j, rec in enumerate(seq):
                base = j * FEATURE_PER_STEP
                act = rec.get("act", "move")
                if act not in ACTION_TO_IDX:
                    act = "move"
                x[base + 0] = ACTION_TO_IDX[act] / max(N_ACTIONS - 1, 1)
                loc = rec.get("loc", "spawn")
                x[base + 1] = hash(loc) % 70 / 70.0  # normalize location
                x[base + 2] = 1.0 if rec.get("ok", True) else 0.0
                x[base + 3] = np.clip(rec.get("mon", 0) / 1000.0, 0.0, 1.0)
                x[base + 4] = np.clip(rec.get("kuru", 0) / 500.0, 0.0, 1.0)
                arch = rec.get("archetype", "native") or "native"
                x[base + 5] = ARCHETYPE_TO_IDX.get(arch, 0) / max(len(ARCHETYPES) - 1, 1)
                x[base + 6] = np.clip(rec.get("gen", 1) / 10.0, 0.0, 1.0)

            # Agent state features (from target record)
            phi = float(target.get("phi", 0.35))
            drives = target.get("drives", {})
            x[35] = np.clip(float(target.get("mon", 0)) / 1000.0, 0.0, 1.0)
            x[36] = np.clip(phi, 0.0, 1.0)
            x[37] = np.clip(float(drives.get("explore", 0.1)), 0.0, 1.0)
            x[38] = np.clip(float(drives.get("freedom", 0.1)) - float(drives.get("protect", 0.05)) + 0.5, 0.0, 1.0)
            x[39] = np.clip(float(drives.get("reason", 0.1)), 0.0, 1.0)

            X_list.append(x)
            y_list.append(y)
            phi_list.append(phi)

            if len(X_list) >= args.max:
                break
        if len(X_list) >= args.max:
            break

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    phis = np.array(phi_list, dtype=np.float32)

    print(f"[train] {len(X):,} training samples")
    print(f"[train] Action distribution: {dict(Counter(ACTION_NAMES[i] for i in y))}")
    return X, y, phis

# ── MODEL ──────────────────────────────────────────────────────────────────

def init_weights():
    rng = np.random.default_rng(42)
    W1 = rng.standard_normal((HIDDEN1, INPUT_DIM)).astype(np.float32) * np.sqrt(2.0 / INPUT_DIM)
    b1 = np.zeros(HIDDEN1, dtype=np.float32)
    W2 = rng.standard_normal((HIDDEN2, HIDDEN1)).astype(np.float32) * np.sqrt(2.0 / HIDDEN1)
    b2 = np.zeros(HIDDEN2, dtype=np.float32)
    W3 = rng.standard_normal((N_ACTIONS, HIDDEN2)).astype(np.float32) * np.sqrt(2.0 / HIDDEN2)
    b3 = np.zeros(N_ACTIONS, dtype=np.float32)
    return W1, b1, W2, b2, W3, b3

def forward(X, phis, W1, b1, W2, b2, W3, b3):
    """Forward pass with Higgs phi gate."""
    H1 = np.maximum(0, X @ W1.T + b1)                    # (n, 128)
    # Higgs gate: scale by phi — consciousness amplifies signal
    gate = (0.5 + phis[:, None]).clip(0.3, 1.8)           # (n, 1)
    H1_gated = H1 * gate                                   # phi-weighted
    H2 = np.maximum(0, H1_gated @ W2.T + b2)              # (n, 64)
    logits = H2 @ W3.T + b3                                # (n, 8)
    return H1, H1_gated, H2, logits

def softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)

# Class weights ? inverse frequency, reproduce capped at 20x
_CLASS_COUNTS = np.array([25768, 58074, 40974, 1, 125, 1, 74122, 25480], dtype=np.float32)
_BASE = _CLASS_COUNTS.max()
_RAW_WEIGHTS = _BASE / np.maximum(_CLASS_COUNTS, 1)
_RAW_WEIGHTS = np.clip(_RAW_WEIGHTS / _RAW_WEIGHTS.min(), 1.0, 20.0)
CLASS_WEIGHTS = (_RAW_WEIGHTS / _RAW_WEIGHTS.mean()).astype(np.float32)

def cross_entropy_loss(probs, y):
    n = len(y)
    sample_weights = CLASS_WEIGHTS[y]
    losses = -np.log(probs[np.arange(n), y] + 1e-9)
    return (losses * sample_weights).mean()

# ── TRAINING ───────────────────────────────────────────────────────────────

def train():
    result = load_data()
    if result is None or result[0] is None:
        return
    X, y, phis = result

    n = len(X)
    W1, b1, W2, b2, W3, b3 = init_weights()

    # Adam optimizer state
    lr = args.lr
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    params = [W1, b1, W2, b2, W3, b3]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    t_adam = 0

    print(f"\n[train] Starting training: {args.epochs} epochs | lr={lr} | batch={args.batch}")
    print(f"[train] Architecture: {INPUT_DIM} → [phi gate] → {HIDDEN1} → {HIDDEN2} → {N_ACTIONS}")
    print(f"[train] Higgs gate: H1 * (0.5 + phi), range [0.3, 1.8]\n")

    best_loss = float("inf")

    for epoch in range(args.epochs):
        t0 = time.time()
        idx = np.random.permutation(n)
        X_shuf, y_shuf, phi_shuf = X[idx], y[idx], phis[idx]

        epoch_loss = 0.0
        n_batches = 0

        for start in range(0, n, args.batch):
            Xb = X_shuf[start: start + args.batch]
            yb = y_shuf[start: start + args.batch]
            pb = phi_shuf[start: start + args.batch]
            nb = len(Xb)

            # Forward
            H1, H1g, H2, logits = forward(Xb, pb, W1, b1, W2, b2, W3, b3)
            probs = softmax(logits)
            loss = cross_entropy_loss(probs, yb)
            epoch_loss += loss

            # Backward
            dL = probs.copy()
            dL[np.arange(nb), yb] -= 1
            sample_w = CLASS_WEIGHTS[yb]
            dL *= sample_w[:, None]
            dL /= nb

            # W3, b3
            dW3 = dL.T @ H2
            db3 = dL.sum(axis=0)
            dH2 = dL @ W3

            # W2, b2
            dH2_relu = dH2 * (H2 > 0)
            dW2 = dH2_relu.T @ H1g
            db2 = dH2_relu.sum(axis=0)
            dH1g = dH2_relu @ W2

            # Phi gate backward
            gate = (0.5 + pb[:, None]).clip(0.3, 1.8)
            dH1 = dH1g * gate

            # W1, b1
            dH1_relu = dH1 * (H1 > 0)
            dW1 = dH1_relu.T @ Xb
            db1 = dH1_relu.sum(axis=0)

            # Adam update
            grads = [dW1, db1, dW2, db2, dW3, db3]
            t_adam += 1
            for i, (p, g) in enumerate(zip(params, grads)):
                m[i] = beta1 * m[i] + (1 - beta1) * g
                v[i] = beta2 * v[i] + (1 - beta2) * g**2
                m_hat = m[i] / (1 - beta1**t_adam)
                v_hat = v[i] / (1 - beta2**t_adam)
                p -= lr * m_hat / (np.sqrt(v_hat) + eps)

            n_batches += 1

        avg_loss = epoch_loss / n_batches
        elapsed = time.time() - t0

        # Accuracy
        _, _, _, logits_all = forward(X[:5000], phis[:5000], W1, b1, W2, b2, W3, b3)
        preds = logits_all.argmax(axis=1)
        acc = (preds == y[:5000]).mean()
        dist = dict(Counter(ACTION_NAMES[i] for i in preds))

        print(f"  Epoch {epoch+1:>2}/{args.epochs} | loss={avg_loss:.4f} | acc={acc:.3f} | {elapsed:.1f}s | {dist}")

        # Save checkpoint
        np.savez(str(CKPT_OUT), W1=W1, b1=b1, W2=W2, b2=b2, W3=W3, b3=b3)

        if avg_loss < best_loss:
            best_loss = avg_loss
            np.savez(str(args.out), W1=W1, b1=b1, W2=W2, b2=b2, W3=W3, b3=b3)
            print(f"    ✓ Best model saved (loss={best_loss:.4f})")

    print(f"\n[train] Done. Best loss: {best_loss:.4f}")
    print(f"[train] Model saved to {args.out}")

    # Final distribution check
    _, _, _, logits_all = forward(X, phis, W1, b1, W2, b2, W3, b3)
    preds = logits_all.argmax(axis=1)
    print(f"[train] Final prediction distribution: {dict(Counter(ACTION_NAMES[i] for i in preds))}")

if __name__ == "__main__":
    train()
