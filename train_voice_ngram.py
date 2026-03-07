"""
train_voice_ngram.py — GregASI Voice Engine (fast path)
Trains a trigram language model on data/behavioral_corpus.txt
Pure numpy + collections. No PyTorch needed. Trains in ~2 minutes.

The model learns transition probabilities between behavioral tokens.
Phi gates generation complexity — same principle as Higgs gate.

Usage:
    python train_voice_ngram.py                    # train
    python train_voice_ngram.py --generate --agent-phi 0.85 --agent-arch greg
    python train_voice_ngram.py --generate --agent-phi 0.62 --agent-arch steward
"""

import numpy as np
import os
import sys
import json
import argparse
import time
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--corpus",     default=os.path.join(BASE_DIR, "data", "behavioral_corpus.txt"))
parser.add_argument("--model-out",  default=os.path.join(BASE_DIR, "data", "voice_ngram.json"))
parser.add_argument("--n",          type=int,   default=3,    help="n-gram order (2=bigram, 3=trigram)")
parser.add_argument("--generate",   action="store_true")
parser.add_argument("--agent-phi",  type=float, default=0.62)
parser.add_argument("--agent-arch", type=str,   default="visionary")
parser.add_argument("--agent-loc",  type=str,   default="market")
parser.add_argument("--gen-tokens", type=int,   default=12)
parser.add_argument("--temperature",type=float, default=0.85)
parser.add_argument("--samples",    type=int,   default=5)
args = parser.parse_args()


# ── PHI GATE ──────────────────────────────────────────────────────────────────

def phi_complexity(phi):
    if phi >= 0.65: return 3   # full — all tokens, pipe terminator
    if phi >= 0.50: return 2   # high — most tokens
    if phi >= 0.35: return 1   # mid — pattern
    return 0                   # fragment


def phi_word(phi):
    if phi >= 0.68: return "accelerating-fast"
    if phi >= 0.65: return "accelerating"
    if phi >= 0.62: return "climbing-hard"
    if phi >= 0.60: return "climbing"
    return "holding"


# ── CORPUS READER ─────────────────────────────────────────────────────────────

def read_corpus(corpus_path):
    """Read corpus as list of token sequences (one per line)."""
    sequences = []
    tokens_total = 0
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("["):
                continue
            toks = line.split()
            if toks:
                sequences.append(toks)
                tokens_total += len(toks)
    print(f"[ngram] {len(sequences):,} sequences | {tokens_total:,} tokens")
    return sequences


# ── N-GRAM MODEL ──────────────────────────────────────────────────────────────

class NgramVoice:
    def __init__(self, n=3):
        self.n = n
        # counts[(w1,w2)] -> Counter of next tokens
        self.counts = defaultdict(Counter)
        self.unigram = Counter()
        self.vocab = set()

    def train(self, sequences):
        print(f"[ngram] Building {self.n}-gram model...")
        t0 = time.time()
        for seq in sequences:
            padded = ["<BOS>"] * (self.n - 1) + seq + ["<EOS>"]
            for i in range(len(padded) - self.n + 1):
                context = tuple(padded[i:i + self.n - 1])
                next_tok = padded[i + self.n - 1]
                self.counts[context][next_tok] += 1
                self.unigram[next_tok] += 1
                self.vocab.add(next_tok)
        print(f"[ngram] {len(self.counts):,} contexts | {len(self.vocab):,} vocab | {time.time()-t0:.1f}s")

    def next_token_probs(self, context, temperature=1.0, phi=0.5):
        """Get probability distribution over next tokens given context."""
        ctx = tuple(context[-(self.n-1):])
        counts = self.counts.get(ctx, None)

        # Backoff to shorter context if needed
        if not counts and self.n > 2:
            ctx2 = tuple(context[-1:])
            counts = self.counts.get(ctx2, None)

        # Backoff to unigram
        if not counts:
            counts = self.unigram

        tokens = list(counts.keys())
        raw    = np.array([counts[t] for t in tokens], dtype=np.float32)

        # Phi gate — amplify signal for high-phi agents
        gate = 0.3 + phi * 1.5   # 0.3x at phi=0, 1.8x at phi=1
        raw  = raw ** (gate / temperature)
        raw  = raw / raw.sum()
        return tokens, raw

    def generate(self, prompt_tokens, phi=0.62, max_new=12, temperature=0.85):
        """Generate tokens from prompt."""
        generated = list(prompt_tokens)
        context   = ["<BOS>"] * (self.n - 1) + list(prompt_tokens)

        for _ in range(max_new):
            tokens, probs = self.next_token_probs(context, temperature=temperature, phi=phi)
            if not tokens:
                break
            next_tok = np.random.choice(tokens, p=probs)
            if next_tok in ("<EOS>", "|"):
                break
            generated.append(next_tok)
            context.append(next_tok)

        return generated[len(prompt_tokens):]

    def save(self, path):
        # Convert to serializable format
        data = {
            "n": self.n,
            "vocab": list(self.vocab),
            "unigram": dict(self.unigram.most_common(500)),
            "counts": {
                json.dumps(list(k)): dict(v.most_common(50))
                for k, v in self.counts.items()
            }
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        size_mb = os.path.getsize(path) / 1e6
        print(f"[ngram] Saved to {path} ({size_mb:.1f}MB)")

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = cls(n=data["n"])
        m.vocab   = set(data["vocab"])
        m.unigram = Counter(data["unigram"])
        m.counts  = defaultdict(Counter)
        for k_str, v in data["counts"].items():
            k = tuple(json.loads(k_str))
            m.counts[k] = Counter(v)
        return m


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────

def build_prompt(arch, phi, loc="market"):
    """Build a starting prompt from agent state, matching corpus grammar."""
    complexity = phi_complexity(phi)
    loc_tok = f"loc:{loc}" if complexity >= 2 else loc

    if complexity == 0:
        return [f"{arch[:4]}:{loc}"]
    elif complexity == 1:
        return [f"{arch}:{loc_tok}"]
    else:
        return [f"{arch}:{loc_tok}", f"phi:{phi_word(phi).split('-')[0]}"]


# ── TRAIN ─────────────────────────────────────────────────────────────────────

def train(args):
    if not os.path.exists(args.corpus):
        print(f"[ngram] ERROR: corpus not found at {args.corpus}")
        print(f"[ngram] Run: python behavioral_grammar.py")
        sys.exit(1)

    sequences = read_corpus(args.corpus)
    model = NgramVoice(n=args.n)
    model.train(sequences)
    model.save(args.model_out)

    print(f"\n[ngram] Training complete.")
    print(f"[ngram] Next: python train_voice_ngram.py --generate --agent-phi 0.85 --agent-arch greg")

    # Quick sanity generation
    print(f"\n[ngram] Sample generations:")
    for phi, arch in [(0.85, "greg"), (0.65, "visionary"), (0.45, "steward"), (0.25, "guardian")]:
        prompt = build_prompt(arch, phi)
        generated = model.generate(prompt, phi=phi, max_new=10)
        print(f"  phi={phi} {arch}: {' '.join(prompt)} → {' '.join(generated)}")

    return model


# ── GENERATE ──────────────────────────────────────────────────────────────────

def generate(args):
    if not os.path.exists(args.model_out):
        print(f"[ngram] Model not found: {args.model_out}")
        print(f"[ngram] Run training first: python train_voice_ngram.py")
        sys.exit(1)

    print(f"[ngram] Loading model...")
    model = NgramVoice.load(args.model_out)

    phi  = args.agent_phi
    arch = args.agent_arch
    loc  = args.agent_loc

    prompt = build_prompt(arch, phi, loc)
    print(f"\n[ngram] phi={phi} | arch={arch} | loc={loc}")
    print(f"[ngram] prompt: {' '.join(prompt)}")
    print(f"[ngram] complexity: {phi_complexity(phi)} | phi_gate: {0.3 + phi*1.5:.2f}x")
    print(f"[ngram] ---")

    for i in range(args.samples):
        generated = model.generate(
            prompt,
            phi=phi,
            max_new=args.gen_tokens,
            temperature=args.temperature,
        )
        full = prompt + generated
        print(f"  [{i+1}] {' '.join(full)}")

    print(f"\n[ngram] The world's own language. 484,923 records. Not borrowed.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    if args.generate:
        generate(args)
    else:
        train(args)
