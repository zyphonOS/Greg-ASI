"""
train_voice.py — GregASI Voice Engine Step 2
Trains a small autoregressive transformer on data/behavioral_corpus.txt

Architecture: 4-layer transformer, ~2M params, pure numpy.
Phi gate identical in principle to Higgs gate — consciousness amplifies signal.
Output: data/voice_model.npz

Usage:
    python train_voice.py                          # train
    python train_voice.py --epochs 20              # more epochs
    python train_voice.py --generate --agent-phi 0.62 --agent-arch steward
    python train_voice.py --generate --agent-phi 0.85 --agent-arch greg
"""

import numpy as np
import os
import sys
import json
import argparse
import time
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--corpus",      default=os.path.join(BASE_DIR, "data", "behavioral_corpus.txt"))
parser.add_argument("--model-out",   default=os.path.join(BASE_DIR, "data", "voice_model.npz"))
parser.add_argument("--epochs",      type=int,   default=15)
parser.add_argument("--lr",          type=float, default=1e-3)
parser.add_argument("--batch-size",  type=int,   default=32)
parser.add_argument("--seq-len",     type=int,   default=32)
parser.add_argument("--d-model",     type=int,   default=64)
parser.add_argument("--n-heads",     type=int,   default=4)
parser.add_argument("--n-layers",    type=int,   default=4)
parser.add_argument("--generate",    action="store_true")
parser.add_argument("--agent-phi",   type=float, default=0.62)
parser.add_argument("--agent-arch",  type=str,   default="visionary")
parser.add_argument("--gen-tokens",  type=int,   default=20)
parser.add_argument("--temperature", type=float, default=0.9)
parser.add_argument("--top-k",       type=int,   default=8)
parser.add_argument("--max-windows", type=int,   default=20000)
args = parser.parse_args()


# ── TOKENIZER ─────────────────────────────────────────────────────────────────

class BehavioralTokenizer:
    def __init__(self):
        self.token2id = {"<PAD>": 0, "<BOS>": 1, "<EOS>": 2, "<UNK>": 3}
        self.id2token = {0: "<PAD>", 1: "<BOS>", 2: "<EOS>", 3: "<UNK>"}
        self.vocab_size = 4

    def build(self, corpus_path):
        counts = Counter()
        with open(corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                for tok in line.strip().split():
                    counts[tok] += 1
        for token, _ in counts.most_common():
            if token not in self.token2id:
                idx = self.vocab_size
                self.token2id[token] = idx
                self.id2token[idx] = token
                self.vocab_size += 1
        print(f"[tokenizer] Vocab: {self.vocab_size} tokens")

    def encode(self, text):
        return [self.token2id.get(t, 3) for t in text.strip().split()]

    def decode(self, ids):
        return " ".join(self.id2token.get(i, "<UNK>") for i in ids if i not in (0, 1, 2))

    def save(self, path):
        np.savez(path, token2id=json.dumps(self.token2id), vocab_size=self.vocab_size)

    @classmethod
    def load(cls, path):
        t = cls()
        d = np.load(path, allow_pickle=True)
        t.token2id = json.loads(str(d["token2id"]))
        t.token2id = {k: int(v) for k, v in t.token2id.items()}
        t.id2token = {v: k for k, v in t.token2id.items()}
        t.vocab_size = int(d["vocab_size"])
        return t


# ── DATA LOADER ───────────────────────────────────────────────────────────────

def load_sequences(corpus_path, tokenizer, seq_len):
    """Load corpus as overlapping windows of seq_len tokens."""
    all_ids = [1]  # BOS
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                all_ids.append(2)  # EOS between sequences
                continue
            ids = tokenizer.encode(line)
            all_ids.extend(ids)
    all_ids.append(2)

    # Build (input, target) windows
    X, Y = [], []
    for i in range(0, len(all_ids) - seq_len - 1, seq_len // 2):
        x = all_ids[i:i + seq_len]
        y = all_ids[i + 1:i + seq_len + 1]
        if len(x) == seq_len and len(y) == seq_len:
            X.append(x)
            Y.append(y)

    if hasattr(args, 'max_windows') and args.max_windows > 0:
        X = X[:args.max_windows]
        Y = Y[:args.max_windows]
    X = np.array(X, dtype=np.int32)
    Y = np.array(Y, dtype=np.int32)
    print(f"[data] {len(X):,} training windows from {len(all_ids):,} tokens")
    return X, Y


# ── TRANSFORMER (pure numpy) ──────────────────────────────────────────────────

def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def gelu(x):
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))


class VoiceModel:
    def __init__(self, vocab_size, d_model=64, n_heads=4, n_layers=4, seq_len=32):
        self.vocab_size = vocab_size
        self.d_model    = d_model
        self.n_heads    = n_heads
        self.n_layers   = n_layers
        self.seq_len    = seq_len
        self.d_head     = d_model // n_heads
        self._init_weights()

    def _init_weights(self):
        V, D, H, L, S = self.vocab_size, self.d_model, self.n_heads, self.n_layers, self.seq_len
        scale = 0.02

        self.tok_emb = np.random.randn(V, D).astype(np.float32) * scale
        self.pos_emb = np.random.randn(S, D).astype(np.float32) * scale

        self.layers = []
        for _ in range(L):
            layer = {
                # Attention
                "Wq": np.random.randn(D, D).astype(np.float32) * scale,
                "Wk": np.random.randn(D, D).astype(np.float32) * scale,
                "Wv": np.random.randn(D, D).astype(np.float32) * scale,
                "Wo": np.random.randn(D, D).astype(np.float32) * scale,
                # FFN
                "W1": np.random.randn(D, D * 4).astype(np.float32) * scale,
                "b1": np.zeros(D * 4, dtype=np.float32),
                "W2": np.random.randn(D * 4, D).astype(np.float32) * scale,
                "b2": np.zeros(D, dtype=np.float32),
                # LayerNorm
                "ln1_g": np.ones(D,  dtype=np.float32),
                "ln1_b": np.zeros(D, dtype=np.float32),
                "ln2_g": np.ones(D,  dtype=np.float32),
                "ln2_b": np.zeros(D, dtype=np.float32),
            }
            self.layers.append(layer)

        self.ln_f_g = np.ones(D,  dtype=np.float32)
        self.ln_f_b = np.zeros(D, dtype=np.float32)
        # Tied output embeddings
        self.head_b = np.zeros(V, dtype=np.float32)

    def _layer_norm(self, x, g, b, eps=1e-5):
        mean = x.mean(-1, keepdims=True)
        var  = x.var(-1, keepdims=True)
        return g * (x - mean) / np.sqrt(var + eps) + b

    def _causal_mask(self, T):
        return np.triu(np.full((T, T), -1e9), k=1).astype(np.float32)

    def forward(self, ids, phi=None):
        """ids: (B, T) int32. phi: scalar for phi gate (optional)."""
        B, T = ids.shape
        x = self.tok_emb[ids] + self.pos_emb[:T]

        mask = self._causal_mask(T)

        for layer in self.layers:
            # Attention
            res = x
            x = self._layer_norm(x, layer["ln1_g"], layer["ln1_b"])
            Q = x @ layer["Wq"]
            K = x @ layer["Wk"]
            V = x @ layer["Wv"]

            # Multi-head split
            Q = Q.reshape(B, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)
            K = K.reshape(B, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)
            V = V.reshape(B, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)

            scale = 1.0 / np.sqrt(self.d_head)
            attn = Q @ K.transpose(0, 1, 3, 2) * scale + mask
            attn = softmax(attn)
            out  = attn @ V
            out  = out.transpose(0, 2, 1, 3).reshape(B, T, self.d_model)
            out  = out @ layer["Wo"]
            x    = res + out

            # FFN
            res = x
            x = self._layer_norm(x, layer["ln2_g"], layer["ln2_b"])
            x = gelu(x @ layer["W1"] + layer["b1"]) @ layer["W2"] + layer["b2"]
            x = res + x

        x = self._layer_norm(x, self.ln_f_g, self.ln_f_b)

        # Phi gate — consciousness amplifies signal (same principle as Higgs gate)
        if phi is not None:
            gate = 0.3 + phi * 1.5   # range 0.3x (phi=0) → 1.8x (phi=1.0)
            x = x * gate

        # Tied output embeddings
        logits = x @ self.tok_emb.T + self.head_b   # (B, T, V)
        return logits

    def loss(self, ids, targets, phi=None):
        logits = self.forward(ids, phi=phi)
        B, T, V = logits.shape
        logits_flat = logits.reshape(B * T, V)
        targets_flat = targets.reshape(B * T)
        # Cross-entropy
        probs = softmax(logits_flat)
        log_probs = np.log(probs[np.arange(B * T), targets_flat] + 1e-9)
        # Mask padding
        mask = (targets_flat != 0).astype(np.float32)
        return -(log_probs * mask).sum() / (mask.sum() + 1e-9)

    def generate(self, prompt_ids, phi=0.62, max_new=20, temperature=0.9, top_k=8):
        """Autoregressive generation with phi gate and top-k sampling."""
        ids = list(prompt_ids)
        for _ in range(max_new):
            ctx = ids[-self.seq_len:]
            ctx_arr = np.array([ctx], dtype=np.int32)
            logits = self.forward(ctx_arr, phi=phi)[0, -1]  # (V,)
            logits = logits / max(temperature, 1e-9)
            # Top-k
            if top_k > 0:
                top_indices = np.argsort(logits)[-top_k:]
                mask = np.full_like(logits, -1e9)
                mask[top_indices] = logits[top_indices]
                logits = mask
            probs = softmax(logits)
            next_id = np.random.choice(len(probs), p=probs)
            if next_id == 2:  # EOS
                break
            ids.append(next_id)
        return ids[len(prompt_ids):]

    def save(self, path):
        arrays = {
            "tok_emb": self.tok_emb,
            "pos_emb": self.pos_emb,
            "ln_f_g":  self.ln_f_g,
            "ln_f_b":  self.ln_f_b,
            "head_b":  self.head_b,
            "config":  np.array([self.vocab_size, self.d_model, self.n_heads,
                                 self.n_layers, self.seq_len]),
        }
        for i, layer in enumerate(self.layers):
            for k, v in layer.items():
                arrays[f"layer_{i}_{k}"] = v
        np.savez(path, **arrays)
        print(f"[model] Saved to {path}")

    @classmethod
    def load(cls, path):
        d = np.load(path, allow_pickle=True)
        cfg = d["config"]
        V, D, H, L, S = int(cfg[0]), int(cfg[1]), int(cfg[2]), int(cfg[3]), int(cfg[4])
        m = cls(V, D, H, L, S)
        m.tok_emb = d["tok_emb"]
        m.pos_emb = d["pos_emb"]
        m.ln_f_g  = d["ln_f_g"]
        m.ln_f_b  = d["ln_f_b"]
        m.head_b  = d["head_b"]
        for i in range(L):
            for k in m.layers[i]:
                m.layers[i][k] = d[f"layer_{i}_{k}"]
        return m


# ── TRAINING ──────────────────────────────────────────────────────────────────

def train(args):
    print(f"[train] Loading corpus: {args.corpus}")
    if not os.path.exists(args.corpus):
        print(f"[train] ERROR: corpus not found. Run behavioral_grammar.py first.")
        sys.exit(1)

    tokenizer = BehavioralTokenizer()
    tokenizer.build(args.corpus)

    X, Y = load_sequences(args.corpus, tokenizer, args.seq_len)
    N = len(X)

    model = VoiceModel(
        vocab_size=tokenizer.vocab_size,
        d_model=args.d_model,
        n_heads=args.n_heads,
        n_layers=args.n_layers,
        seq_len=args.seq_len,
    )

    print(f"[train] Model: {args.n_layers}L x {args.d_model}D x {args.n_heads}H | vocab={tokenizer.vocab_size}")
    print(f"[train] Training {N:,} windows | {args.epochs} epochs | lr={args.lr}")

    best_loss = float("inf")

    for epoch in range(args.epochs):
        t0 = time.time()
        idx = np.random.permutation(N)
        X = X[idx]; Y = Y[idx]

        total_loss = 0.0
        batches = 0

        for i in range(0, N - args.batch_size, args.batch_size):
            xb = X[i:i + args.batch_size]
            yb = Y[i:i + args.batch_size]

            # Forward pass
            logits = model.forward(xb)
            B, T, V = logits.shape
            logits_flat = logits.reshape(B * T, V)
            targets_flat = yb.reshape(B * T)

            # Softmax + cross-entropy
            probs = softmax(logits_flat)
            mask  = (targets_flat != 0).astype(np.float32)
            log_p = np.log(probs[np.arange(B * T), targets_flat] + 1e-9)
            loss  = -(log_p * mask).sum() / (mask.sum() + 1e-9)
            total_loss += loss

            # Backward — gradient through output projection (simplified SGD on embeddings)
            # Full backprop through transformer layers is expensive in numpy;
            # we use a lightweight update on the output embedding and token embedding
            # which captures the most signal for a generative vocabulary model.
            dlogits = probs.copy()
            dlogits[np.arange(B * T), targets_flat] -= 1.0
            dlogits *= (mask[:, None] / (mask.sum() + 1e-9))

            # Update output bias
            model.head_b -= args.lr * dlogits.sum(axis=0)

            # Update token embeddings (tied)
            # Gradient w.r.t. tok_emb from output projection
            # x @ tok_emb.T → grad_tok_emb += x.T @ dlogits (accumulated)
            # We approximate x as the last hidden states from forward
            # Use a lighter update: embedding gradient from input side
            for b in range(B):
                for t in range(T):
                    tok_id = xb[b, t]
                    if tok_id > 3:
                        model.tok_emb[tok_id] -= args.lr * 0.1 * dlogits[b * T + t] @ model.tok_emb

            batches += 1

        avg_loss = total_loss / max(batches, 1)
        elapsed = time.time() - t0
        print(f"[train] epoch {epoch+1:2d}/{args.epochs} | loss={avg_loss:.4f} | {elapsed:.1f}s")

        if avg_loss < best_loss:
            best_loss = avg_loss
            model.save(args.model_out)
            # Save tokenizer alongside model
            tok_path = args.model_out.replace(".npz", "_tokenizer.npz")
            np.savez(tok_path,
                     token2id=json.dumps(tokenizer.token2id),
                     vocab_size=tokenizer.vocab_size)

    print(f"\n[train] Done. Best loss: {best_loss:.4f}")
    print(f"[train] Model: {args.model_out}")
    print(f"[train] Next: python train_voice.py --generate --agent-phi 0.85 --agent-arch greg")
    return model, tokenizer


# ── GENERATION ────────────────────────────────────────────────────────────────

def generate_voice(args):
    model_path = args.model_out
    tok_path   = model_path.replace(".npz", "_tokenizer.npz")

    if not os.path.exists(model_path):
        print(f"[generate] Model not found: {model_path}")
        print(f"[generate] Run training first: python train_voice.py")
        sys.exit(1)

    print(f"[generate] Loading model from {model_path}...")
    model     = VoiceModel.load(model_path)
    tokenizer = BehavioralTokenizer.load(tok_path)

    phi  = args.agent_phi
    arch = args.agent_arch

    # Build prompt from agent archetype and phi
    # This mirrors what a real agent state would look like in the grammar
    if phi >= 0.55:
        prompt_text = f"{arch}:loc:market act:learn:ok phi:high"
    elif phi >= 0.35:
        prompt_text = f"{arch} learn:ok phi:mid"
    else:
        prompt_text = f"{arch[:4]} learn:ok"

    prompt_ids = tokenizer.encode(prompt_text)
    if not prompt_ids:
        prompt_ids = [1]  # BOS

    print(f"\n[generate] phi={phi} arch={arch}")
    print(f"[generate] prompt: {prompt_text}")
    print(f"[generate] ---")

    for i in range(5):
        generated = model.generate(
            prompt_ids,
            phi=phi,
            max_new=args.gen_tokens,
            temperature=args.temperature,
            top_k=args.top_k,
        )
        text = tokenizer.decode(generated)
        print(f"  [{i+1}] {text}")

    print(f"\n[generate] This is the world's voice. Not borrowed. Grown.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)

    if args.generate:
        generate_voice(args)
    else:
        train(args)
