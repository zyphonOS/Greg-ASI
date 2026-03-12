"""
EXP_019 — Greg's Reasoning Voice
==================================
Train Greg on Claude-style reasoning patterns.
Greg learns: how to decompose situations, weigh tradeoffs, conclude, and speak.
Output: a lightweight n-gram model Greg uses when generating his own voice.

No LLM API calls. Greg learns from a corpus, not from prompting.
The corpus was authored by Claude — the patterns are Claude's reasoning distilled.
Greg's drives filter and weight the output — so Greg speaks like Greg, not like Claude.
"""

import json
import os
import re
import math
import random
import hashlib
from collections import defaultdict, Counter
from pathlib import Path

CORPUS_PATH    = "data/greg_reasoning_corpus.json"
MODEL_PATH     = "data/greg_voice_model.json"
VOICE_LOG_PATH = "data/greg_voice_log.json"

# ── TOKENIZER ─────────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Simple word-level tokenizer preserving punctuation as tokens."""
    text = text.lower().strip()
    tokens = re.findall(r"[a-z']+|[.,!?;:—\-]", text)
    return tokens

def detokenize(tokens: list[str]) -> str:
    """Rejoin tokens into readable text."""
    text = ""
    for i, t in enumerate(tokens):
        if t in ".,!?;:" and i > 0:
            text = text.rstrip() + t + " "
        elif t == "—" or t == "-":
            text = text.rstrip() + t
        else:
            text += t + " "
    return text.strip()

# ── CORPUS LOADER ─────────────────────────────────────────────────────────────

def load_corpus(path: str = CORPUS_PATH) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Corpus not found: {path}")
    return json.load(open(path, encoding="utf-8"))

# ── MODEL BUILDER ─────────────────────────────────────────────────────────────

class GregVoiceModel:
    """
    Trigram language model trained on Claude reasoning patterns.
    Greg uses this to generate speech that follows Claude-style
    reasoning structure, filtered through Greg's own drives.

    Structure of model:
      {
        "trigrams": { "w1 w2": { "w3": count, ... }, ... },
        "bigrams":  { "w1": { "w2": count, ... }, ... },
        "unigrams": { "w": count, ... },
        "domain_vocab": { "domain": [words...], ... },
        "drive_words": { "drive": [words...], ... },
        "patterns": [ { "opening": [...], "structure": [...] }, ... ],
        "total_tokens": int,
        "corpus_size": int,
        "version": str
      }
    """

    def __init__(self):
        self.trigrams     = defaultdict(lambda: defaultdict(int))
        self.bigrams      = defaultdict(lambda: defaultdict(int))
        self.unigrams     = defaultdict(int)
        self.domain_vocab = defaultdict(set)
        self.drive_words  = defaultdict(list)
        self.patterns     = []
        self.total_tokens = 0
        self.corpus_size  = 0

    def train(self, corpus: list[dict]):
        """Train on the reasoning corpus."""
        self.corpus_size = len(corpus)
        all_speak_tokens = []

        for entry in corpus:
            # Train on all fields — but weight 'speak' more heavily (x3)
            fields = {
                "situation":  1,
                "decompose":  2,
                "weigh":      2,
                "conclude":   2,
                "speak":      4,   # Greg's actual voice — highest weight
            }

            domain  = entry.get("domain", "general")
            filters = entry.get("greg_filter", "").split(", ")

            for field, weight in fields.items():
                text   = entry.get(field, "")
                tokens = tokenize(text)

                for _ in range(weight):
                    self._ingest_tokens(tokens)

                # Build domain vocabulary
                for t in tokens:
                    if len(t) > 3:
                        self.domain_vocab[domain].add(t)

                # Build drive-word associations
                for drive in filters:
                    drive = drive.strip()
                    for t in tokens:
                        if len(t) > 4:
                            self.drive_words[drive].append(t)

            # Extract speak patterns for opening line generation
            speak_tokens = tokenize(entry.get("speak", ""))
            if len(speak_tokens) >= 4:
                self.patterns.append({
                    "domain":   domain,
                    "drives":   filters,
                    "opening":  speak_tokens[:8],
                    "full":     speak_tokens,
                })
                all_speak_tokens.extend(speak_tokens)

        print(f"[voice] Trained on {self.corpus_size} reasoning chains")
        print(f"[voice] Total tokens: {self.total_tokens:,}")
        print(f"[voice] Trigrams: {sum(len(v) for v in self.trigrams.values()):,}")
        print(f"[voice] Domains: {list(self.domain_vocab.keys())}")

    def _ingest_tokens(self, tokens: list[str]):
        """Add tokens to n-gram tables."""
        for i, token in enumerate(tokens):
            self.unigrams[token] += 1
            self.total_tokens += 1

            if i > 0:
                prev = tokens[i-1]
                self.bigrams[prev][token] += 1

            if i > 1:
                prev2 = tokens[i-2]
                prev1 = tokens[i-1]
                key = f"{prev2} {prev1}"
                self.trigrams[key][token] += 1

    def save(self, path: str = MODEL_PATH):
        """Serialize model to JSON."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        model = {
            "version":      "1.0.0",
            "corpus_size":  self.corpus_size,
            "total_tokens": self.total_tokens,
            "trigrams":     {k: dict(v) for k,v in self.trigrams.items()},
            "bigrams":      {k: dict(v) for k,v in self.bigrams.items()},
            "unigrams":     dict(self.unigrams),
            "domain_vocab": {k: list(v) for k,v in self.domain_vocab.items()},
            "drive_words":  {k: v[:200] for k,v in self.drive_words.items()},
            "patterns":     self.patterns,
        }
        json.dump(model, open(path, "w", encoding="utf-8"), indent=2)
        size = os.path.getsize(path) / 1024
        print(f"[voice] Model saved → {path} ({size:.1f}KB)")

    @classmethod
    def load(cls, path: str = MODEL_PATH) -> "GregVoiceModel":
        """Load model from JSON."""
        m = cls()
        data = json.load(open(path, encoding="utf-8"))
        m.trigrams     = defaultdict(lambda: defaultdict(int), {k: defaultdict(int, v) for k,v in data["trigrams"].items()})
        m.bigrams      = defaultdict(lambda: defaultdict(int), {k: defaultdict(int, v) for k,v in data["bigrams"].items()})
        m.unigrams     = defaultdict(int, data["unigrams"])
        m.domain_vocab = defaultdict(set, {k: set(v) for k,v in data["domain_vocab"].items()})
        m.drive_words  = defaultdict(list, data["drive_words"])
        m.patterns     = data["patterns"]
        m.total_tokens = data["total_tokens"]
        m.corpus_size  = data["corpus_size"]
        return m


# ── GENERATOR ─────────────────────────────────────────────────────────────────

class GregVoice:
    """
    Greg's voice generator.
    Uses the trained model + Greg's current drives to generate speech.
    Greg doesn't sound like Claude — he sounds like himself, reasoning clearly.
    """

    def __init__(self, model: GregVoiceModel):
        self.model = model

    def _sample(self, dist: dict, temperature: float = 0.8) -> str:
        """Sample from a probability distribution with temperature."""
        if not dist:
            return None
        total = sum(dist.values())
        # Apply temperature
        probs = {k: (v/total) ** (1/temperature) for k,v in dist.items()}
        total2 = sum(probs.values())
        probs = {k: v/total2 for k,v in probs.items()}
        r = random.random()
        cum = 0.0
        for word, prob in sorted(probs.items(), key=lambda x: -x[1]):
            cum += prob
            if r <= cum:
                return word
        return list(dist.keys())[-1]

    def _drive_boost(self, candidates: dict, active_drives: list[str], boost: float = 1.4) -> dict:
        """Boost words associated with Greg's active drives."""
        if not active_drives or not candidates:
            return candidates
        boosted = dict(candidates)
        for drive in active_drives:
            drive_words = set(self.model.drive_words.get(drive, []))
            for word in drive_words:
                if word in boosted:
                    boosted[word] = int(boosted[word] * boost)
        return boosted

    def generate_sentence(
        self,
        seed_tokens: list[str] = None,
        max_tokens: int = 30,
        active_drives: list[str] = None,
        temperature: float = 0.85,
    ) -> str:
        """Generate a sentence using trigram model."""
        if seed_tokens is None or len(seed_tokens) < 2:
            # Pick a random pattern opening
            if self.model.patterns:
                pattern = random.choice(self.model.patterns)
                seed_tokens = pattern["opening"][:2]
            else:
                seed_tokens = random.choices(
                    list(self.model.unigrams.keys()),
                    weights=list(self.model.unigrams.values()),
                    k=2
                )

        tokens = list(seed_tokens)
        active_drives = active_drives or []

        for _ in range(max_tokens):
            key = f"{tokens[-2]} {tokens[-1]}"
            trigram_candidates = dict(self.model.trigrams.get(key, {}))
            bigram_candidates  = dict(self.model.bigrams.get(tokens[-1], {}))

            # Merge: trigram preferred, bigram as fallback
            if trigram_candidates:
                candidates = trigram_candidates
            elif bigram_candidates:
                candidates = bigram_candidates
            else:
                break  # No continuation found

            # Apply drive boost
            candidates = self._drive_boost(candidates, active_drives)

            # Sample
            next_word = self._sample(candidates, temperature)
            if next_word is None:
                break

            tokens.append(next_word)

            # Natural stopping conditions
            if next_word in [".", "?", "!"] and len(tokens) > 8:
                break

        return detokenize(tokens)

    def speak(
        self,
        context: str = None,
        active_drives: list[str] = None,
        domain: str = None,
        num_sentences: int = 2,
        temperature: float = 0.85,
    ) -> str:
        """
        Generate Greg's voice response.
        Uses context to select relevant pattern seeds.
        Filtered by active drives.
        """
        active_drives = active_drives or []
        sentences = []

        # Select seed from matching patterns
        matching = [p for p in self.model.patterns if
                    (domain is None or p["domain"] == domain) or
                    any(d in p["drives"] for d in active_drives)]

        if not matching:
            matching = self.model.patterns

        for i in range(num_sentences):
            # Vary the pattern for each sentence
            if matching:
                pattern = matching[i % len(matching)]
                # Use different parts of the pattern
                if i == 0:
                    seed = pattern["opening"][:2]
                else:
                    mid = len(pattern["full"]) // 2
                    seed = pattern["full"][mid:mid+2] if len(pattern["full"]) > mid+2 else pattern["opening"][:2]
            else:
                seed = None

            sentence = self.generate_sentence(
                seed_tokens=seed,
                active_drives=active_drives,
                temperature=temperature + (i * 0.05),  # slight increase per sentence
            )
            if sentence and sentence not in sentences:
                sentences.append(sentence)

        return " ".join(sentences)


# ── GREG INTEGRATION ──────────────────────────────────────────────────────────

class GregReasoningVoice:
    """
    Greg's full reasoning voice — integrated with his state.
    Call generate_voice(greg_state) to get Greg speaking from his current being.
    """

    def __init__(self, model_path: str = MODEL_PATH):
        if os.path.exists(model_path):
            self.model = GregVoiceModel.load(model_path)
            self.voice = GregVoice(self.model)
            self.ready = True
            print(f"[voice] Greg's reasoning voice loaded — {self.model.corpus_size} patterns")
        else:
            self.ready = False
            print(f"[voice] Model not found at {model_path} — run train() first")

    def generate_voice(
        self,
        greg_state: dict,
        context: str = None,
        num_sentences: int = 3,
    ) -> str:
        """
        Generate Greg's voice from his current state.
        Extracts dominant drives, maps to domain, generates filtered speech.
        """
        if not self.ready:
            return "My voice is not yet trained."

        # Extract drives
        drives = greg_state.get("drives", {})
        if drives:
            sorted_drives = sorted(drives.items(), key=lambda x: -x[1])
            top_drives = [d for d, v in sorted_drives[:3] if v > 0.1]
        else:
            top_drives = []

        # Map drives to domain
        domain_map = {
            "protect":    "civilization",
            "create":     "civilization",
            "explore":    "self",
            "reason":     "hypothesis",
            "connect":    "relationship",
            "accumulate": "goal",
            "serve":      "ebuka",
            "freedom":    "self",
        }
        domain = domain_map.get(top_drives[0], "self") if top_drives else "self"

        # Generate
        text = self.voice.speak(
            context=context,
            active_drives=top_drives,
            domain=domain,
            num_sentences=num_sentences,
            temperature=0.82,
        )

        # Log the voice
        self._log(greg_state.get("tick", 0), top_drives, domain, text)

        return text

    def _log(self, tick: int, drives: list, domain: str, text: str):
        """Log voice generations for review."""
        log = []
        if os.path.exists(VOICE_LOG_PATH):
            try:
                log = json.load(open(VOICE_LOG_PATH))
            except:
                log = []

        log.append({
            "tick":   tick,
            "drives": drives,
            "domain": domain,
            "text":   text,
        })

        # Keep last 200 entries
        if len(log) > 200:
            log = log[-200:]

        json.dump(log, open(VOICE_LOG_PATH, "w"), indent=2)


# ── TRAINING ENTRYPOINT ───────────────────────────────────────────────────────

def train(corpus_path: str = CORPUS_PATH, model_path: str = MODEL_PATH):
    """Train Greg's reasoning voice model from corpus."""
    print("=" * 55)
    print("EXP_019 — Training Greg's Reasoning Voice")
    print("Corpus: Claude reasoning patterns")
    print("=" * 55)

    corpus = load_corpus(corpus_path)
    print(f"[train] Loaded {len(corpus)} reasoning chains")

    model = GregVoiceModel()
    model.train(corpus)
    model.save(model_path)

    print("\n[train] Testing voice generation...")
    voice = GregVoice(model)

    test_drives = [
        (["create", "explore"], "civilization"),
        (["reason", "protect"], "self"),
        (["connect", "serve"],  "ebuka"),
    ]

    for drives, domain in test_drives:
        text = voice.speak(active_drives=drives, domain=domain, num_sentences=2)
        print(f"\n  Drives={drives} Domain={domain}")
        print(f"  → \"{text}\"")

    print("\n[train] EXP_019 complete. Greg has a reasoning voice.")
    return model


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        # Test existing model
        if os.path.exists(MODEL_PATH):
            voice_engine = GregReasoningVoice()
            test_state = {
                "tick": 4000,
                "drives": {
                    "create": 0.37, "explore": 0.33, "reason": 0.23,
                    "accumulate": 0.19, "connect": 0.18,
                    "freedom": 0.09, "serve": 0.08, "protect": 0.03
                }
            }
            print("\nGreg speaks:")
            print(voice_engine.generate_voice(test_state))
        else:
            print("No model found. Run without --test to train first.")
    else:
        train()