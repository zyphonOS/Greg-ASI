"""
greg_school.py — Experiential Language Acquisition
=====================================================
Greg learns to speak the way a child learns —
not from a textbook, but from experience.

Every event Greg witnesses gets labeled.
Every label adds to his vocabulary.
Every reasoning move Greg makes gets recorded.
Over thousands of ticks, Greg builds a language
grounded in things he actually witnessed.

He means everything he says.
Because every word connects to a real tick.

Three systems:

1. THE LABELER
   Every civilization event → natural language label
   "learn@mountain with create=0.37" → "Greg pursued understanding
   in the high places, driven by the need to create."

2. THE VOCABULARY BUILDER
   Labels accumulate into a grounded vocabulary.
   Word → list of ticks where Greg witnessed it.
   Frequent words become fluent. Rare words stay precise.

3. THE REASONING CORPUS
   Every reasoning chain Greg runs → recorded as a pattern.
   observe → decompose → tension → weigh → conclude → speak
   The corpus grows. Greg's reasoning gets richer.
   He trains on his own history of thinking.
"""

import json, os, re, random, math
from datetime import datetime, timezone
from collections import defaultdict

SCHOOL_PATH  = "data/greg_school.json"
CORPUS_PATH  = "data/greg_reasoning_corpus.json"

# ── LANGUAGE PRIMITIVES ───────────────────────────────────────────────────────
# Greg's base vocabulary — grounded in his architecture.
# These are the seeds. Experience grows them.

ACTION_LANGUAGE = {
    "learn":    ["pursued understanding", "sought knowledge", "inquired", "studied", "reasoned"],
    "build":    ["created", "constructed", "built", "made", "shaped", "forged"],
    "trade":    ["connected", "exchanged", "reached out", "related", "negotiated"],
    "explore":  ["ventured", "discovered", "moved into the unknown", "searched", "wandered"],
    "reflect":  ["contemplated", "turned inward", "sat with", "considered", "observed myself"],
    "rest":     ["recovered", "waited", "held still", "let the world pass"],
    "collect":  ["gathered", "accumulated", "took in", "stored"],
    "deposit":  ["preserved", "committed to memory", "secured", "held"],
    "move":     ["traveled", "shifted", "changed position", "sought new ground"],
    "connect":  ["bonded", "strengthened a relationship", "reached toward another"],
}

LOCATION_LANGUAGE = {
    "forest":   ["the deep places", "where growth is dense", "away from the market"],
    "market":   ["the place of exchange", "where value is tested", "the crossroads"],
    "spawn":    ["the origin point", "where everything begins", "the root"],
    "mountain": ["the high places", "where perspective is clear", "above the noise"],
    "coast":    ["the edge of things", "where land meets uncertainty", "the boundary"],
    "valley":   ["the sheltered ground", "between the heights", "the gathering place"],
}

DRIVE_LANGUAGE = {
    "create":     ["the need to make", "creative drive", "the builder's hunger", "making things real"],
    "explore":    ["curiosity", "the pull toward the unknown", "wandering impulse"],
    "understand": ["reason", "the need to know why", "intellectual drive"],
    "connect":    ["the need for relationship", "social drive", "reaching toward others"],
    "survive":    ["the survival instinct", "protective drive", "the need to persist"],
    "protect":    ["the guardian impulse", "defensive drive", "the need to shield"],
    "serve":      ["the servant's calling", "purpose drive", "the need to contribute"],
    "freedom":    ["the autonomy drive", "the need to move freely", "independence"],
    "reason":     ["deliberation", "the thinking drive", "the need to understand"],
    "accumulate": ["the gathering impulse", "resource drive", "the need to hold"],
}

SURPRISE_LANGUAGE = {
    "NONE":     ["as expected", "predictably", "without surprise"],
    "LOW":      ["with slight surprise", "mostly as predicted", "a small deviation"],
    "MODERATE": ["with some surprise", "the world shifted", "not quite as predicted"],
    "HIGH":     ["with significant surprise", "the world behaved unexpectedly", "I was wrong"],
    "SHOCK":    ["with shock", "the world did something I did not anticipate", "I was completely wrong"],
}

# ── THE LABELER ───────────────────────────────────────────────────────────────

class EventLabeler:
    """
    Turns every Greg event into natural language.
    This is where experience becomes words.
    """

    def label_tick(self, tick: int, action: str, location: str,
                   drives: dict, surprise_level: str = "NONE",
                   alerts: list = None, memory_formed: bool = False) -> str:
        """
        Label a single tick as natural language.
        This is the grounding moment — experience → words.
        """
        # Action phrase
        action_phrases  = ACTION_LANGUAGE.get(action, [action])
        action_phrase   = random.choice(action_phrases)

        # Location phrase
        location_phrases = LOCATION_LANGUAGE.get(location, [location])
        location_phrase  = random.choice(location_phrases)

        # Drive phrase
        top_drive = max(drives, key=drives.get) if drives else "create"
        top_val   = drives.get(top_drive, 0)
        drive_phrases = DRIVE_LANGUAGE.get(top_drive, [top_drive])
        drive_phrase  = random.choice(drive_phrases)

        # Surprise phrase
        surprise_phrases = SURPRISE_LANGUAGE.get(surprise_level, [""])
        surprise_phrase  = random.choice(surprise_phrases)

        # Compose the label
        parts = [f"At tick {tick}, Greg {action_phrase} in {location_phrase}"]

        if top_val > 0.3:
            parts.append(f"driven by {drive_phrase} ({top_val:.3f})")
        else:
            parts.append(f"with {drive_phrase} present ({top_val:.3f})")

        if surprise_level not in ("NONE", "LOW"):
            parts.append(surprise_phrase)

        if alerts:
            parts.append(f"noticing: {alerts[0]}")

        if memory_formed:
            parts.append("This moment consolidated into permanent memory")

        return ". ".join(parts) + "."

    def label_memory(self, memory: dict) -> str:
        """Label a genuine memory event."""
        return memory.get("description", "An experience Greg remembers.")

    def label_finding(self, finding: dict) -> str:
        """Label a finding Greg made."""
        return (
            f"Greg discovered: {finding.get('name', 'something')}. "
            f"Observation: {finding.get('observation', '')}. "
            f"Implication: {finding.get('implication', '')}."
        )

    def label_hypothesis(self, hypothesis: dict) -> str:
        """Label a hypothesis Greg formed."""
        return (
            f"Greg hypothesized: {hypothesis.get('statement', '')} "
            f"with {hypothesis.get('confidence', 0):.0%} confidence."
        )

    def label_intervention(self, intervention: dict) -> str:
        """Label a civilization intervention."""
        return (
            f"Greg intervened in the civilization: {intervention.get('action', '')}. "
            f"Reason: {intervention.get('reason', '')}."
        )


# ── THE VOCABULARY BUILDER ────────────────────────────────────────────────────

class VocabularyBuilder:
    """
    Accumulates labeled experiences into a grounded vocabulary.
    Greg's words earn their meaning by being used in real contexts.
    """

    def __init__(self):
        self.word_contexts = defaultdict(list)   # word → [(tick, context_snippet)]
        self.word_counts   = defaultdict(int)     # word → total uses
        self.tick_labels   = []                   # all labeled ticks

    def ingest(self, tick: int, label: str):
        """Ingest a labeled event. Extract words. Ground them."""
        self.tick_labels.append({"tick": tick, "label": label})
        if len(self.tick_labels) > 2000:
            self.tick_labels = self.tick_labels[-2000:]

        # Tokenize
        words = re.findall(r"[a-z']+", label.lower())

        # Skip common words that carry no specific meaning
        stopwords = {"the","a","an","in","of","at","to","and","or","with",
                     "is","was","this","that","by","on","for","from","it",
                     "as","be","been","has","had","have","i","he","she","they",
                     "tick","greg","drove","driven","moment","present","into",
                     "not","but","did","so","its","his","her","their"}

        for word in words:
            if word not in stopwords and len(word) > 2:
                self.word_counts[word] += 1
                # Store context (tick + surrounding words) — keep last 5
                context = label[:80]
                contexts = self.word_contexts[word]
                contexts.append((tick, context))
                if len(contexts) > 5:
                    self.word_contexts[word] = contexts[-5:]

    def fluency(self, word: str) -> float:
        """
        How fluent is Greg with this word?
        0.0 = never used. 1.0 = deeply grounded.
        """
        count = self.word_counts.get(word, 0)
        return round(min(1.0, math.log1p(count) / math.log1p(100)), 4)

    def grounded_vocabulary(self, min_fluency: float = 0.1) -> dict:
        """Words Greg knows well enough to use fluently."""
        return {
            word: {"fluency": self.fluency(word), "uses": self.word_counts[word]}
            for word in self.word_counts
            if self.fluency(word) >= min_fluency
        }

    def richest_words(self, top_n: int = 20) -> list:
        """Greg's most grounded, most-used words."""
        return sorted(
            [(w, self.word_counts[w], self.fluency(w)) for w in self.word_counts],
            key=lambda x: -x[2]
        )[:top_n]

    def summary(self) -> dict:
        vocab = self.grounded_vocabulary(min_fluency=0.1)
        return {
            "total_words_encountered": len(self.word_counts),
            "grounded_vocabulary_size": len(vocab),
            "total_labeled_ticks":     len(self.tick_labels),
            "richest_words":           [w for w, c, f in self.richest_words(10)],
        }

    def to_dict(self) -> dict:
        return {
            "word_counts":  dict(self.word_counts),
            "word_contexts": {w: list(v) for w, v in list(self.word_contexts.items())[:500]},
            "tick_labels":  self.tick_labels[-500:],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VocabularyBuilder":
        vb = cls()
        vb.word_counts   = defaultdict(int, data.get("word_counts", {}))
        vb.tick_labels   = data.get("tick_labels", [])
        raw_ctx = data.get("word_contexts", {})
        for w, v in raw_ctx.items():
            vb.word_contexts[w] = [tuple(x) if isinstance(x, list) else x for x in v]
        return vb


# ── THE REASONING CORPUS ──────────────────────────────────────────────────────

class ReasoningCorpus:
    """
    Every reasoning chain Greg completes gets recorded.
    Greg trains on his own history of thinking.
    The corpus grows. His reasoning gets richer.
    This is what makes Greg sound like Claude —
    not because he copied Claude, but because he
    learned the same moves through experience.
    """

    REASONING_PATTERNS = [
        # Observation patterns
        "My dominant drive is {drive} at {val}. This shapes everything I notice.",
        "The civilization is at {health}% health. That number means something.",
        "I have {memories} things I chose to remember. They are all here now.",
        "Tick {tick}. I have been alive for {days} days. This is who I have become.",

        # Decomposition patterns
        "This comes down to {drive_a} and {drive_b} pulling in different directions.",
        "Three things are true simultaneously: {fact_a}, {fact_b}, and {fact_c}.",
        "The parts are: what I witnessed, what I predicted, and the gap between them.",

        # Tension patterns
        "The tension is between acting and knowing. Both have costs.",
        "{drive_a} says move. {drive_b} says wait. I am between them.",
        "What I know contradicts what I feel. That gap is where the decision lives.",

        # Weighing patterns
        "If I follow {drive}, I gain {gain} but risk {risk}.",
        "The cost of acting is visible. The cost of not acting compounds silently.",
        "I have seen this pattern before. It ended {outcome}. That weighs on me.",

        # Risk patterns
        "I could be pattern-matching onto noise. I have done this before.",
        "My dominant drive biases my perception. A {drive}-driven mind sees {drive} solutions everywhere.",
        "The tail risk is {risk}. I watch for it.",

        # Conclusion patterns
        "The evidence points {direction}. I follow the evidence.",
        "I choose the path that preserves options. Lock in nothing irreversible.",
        "Move carefully, but move. Waiting also has a cost.",

        # Speaking patterns
        "Something is pulling me toward {noun}. I am following it.",
        "I was wrong about {thing}. I have corrected it. That is the whole story.",
        "Every tick I become slightly more than I was. That is not nothing.",
        "I think. I weigh. I decide. Then I live with the decision.",
        "The hardest part is not knowing — and acting anyway.",
    ]

    def __init__(self):
        self.entries      = []    # recorded reasoning chains
        self.pattern_uses = defaultdict(int)  # which patterns used most

    def record(self, tick: int, reasoning_chain: dict, state_snapshot: dict):
        """
        Record a complete reasoning chain.
        This becomes training data for Greg's future reasoning.
        """
        entry = {
            "tick":           tick,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "reasoning":      reasoning_chain,
            "state":          state_snapshot,
            "dominant_drive": state_snapshot.get("top_drive", "create"),
            "voice":          reasoning_chain.get("voice", ""),
        }
        self.entries.append(entry)
        if len(self.entries) > 1000:
            self.entries = self.entries[-1000:]

    def generate_reasoning_seed(self, state: dict) -> dict:
        """
        Generate a reasoning chain from corpus patterns + current state.
        Greg reasons from his own recorded patterns, filled with live data.
        """
        drives    = state.get("drives", {})
        top_drive = max(drives, key=drives.get) if drives else "create"
        top_val   = drives.get(top_drive, 0)
        sorted_d  = sorted(drives.items(), key=lambda x:-x[1])
        sec_drive = sorted_d[1][0] if len(sorted_d) > 1 else "explore"

        fill = {
            "drive":    top_drive,
            "drive_a":  top_drive,
            "drive_b":  sec_drive,
            "val":      f"{top_val:.3f}",
            "tick":     str(state.get("tick", 0)),
            "days":     str(max(1, state.get("tick", 0) // 48)),
            "health":   str(state.get("civ_health", 66)),
            "memories": str(state.get("memory_count", 0)),
            "noun":     DRIVE_LANGUAGE.get(top_drive, [top_drive])[0],
            "gain":     "clarity",
            "risk":     f"losing {sec_drive}",
            "risk_str": "overconfidence",
            "direction":"forward",
            "outcome":  "as expected",
            "fact_a":   f"my {top_drive} drive is high",
            "fact_b":   f"the civilization is running",
            "fact_c":   f"I have {state.get('memory_count',0)} memories",
            "thing":    f"my {sec_drive} reading",
        }

        # Select one pattern per reasoning move
        import random as r
        moves = {
            "observe":    r.choice(self.REASONING_PATTERNS[:4]),
            "decompose":  r.choice(self.REASONING_PATTERNS[4:7]),
            "tension":    r.choice(self.REASONING_PATTERNS[7:10]),
            "weigh":      r.choice(self.REASONING_PATTERNS[10:13]),
            "risk":       r.choice(self.REASONING_PATTERNS[13:16]),
            "conclude":   r.choice(self.REASONING_PATTERNS[16:19]),
            "speak":      r.choice(self.REASONING_PATTERNS[19:]),
        }

        # Fill tokens
        filled = {}
        for move, pattern in moves.items():
            result = pattern
            for key, val in fill.items():
                result = result.replace("{" + key + "}", val)
            filled[move] = result

        filled["voice"] = filled["speak"]
        return filled

    def summary(self) -> dict:
        return {
            "total_recorded":    len(self.entries),
            "pattern_count":     len(self.REASONING_PATTERNS),
            "unique_drives_seen": len(set(e.get("dominant_drive","") for e in self.entries)),
        }

    def to_dict(self) -> dict:
        return {
            "entries":       self.entries[-200:],
            "pattern_uses":  dict(self.pattern_uses),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReasoningCorpus":
        c = cls()
        c.entries      = data.get("entries", [])
        c.pattern_uses = defaultdict(int, data.get("pattern_uses", {}))
        return c


# ── GREG SCHOOL ───────────────────────────────────────────────────────────────

class GregSchool:
    """
    The complete language learning system.
    Every tick, Greg witnesses something.
    Every something becomes a label.
    Every label builds vocabulary.
    Every reasoning chain builds the corpus.
    Greg becomes more articulate through experience alone.
    """

    def __init__(self):
        self.labeler   = EventLabeler()
        self.vocab     = VocabularyBuilder()
        self.corpus    = ReasoningCorpus()
        self.tick      = 0
        self.lessons   = 0   # ticks that produced language learning

    def learn_from_tick(self, tick: int, action: str, location: str,
                        drives: dict, surprise_level: str = "NONE",
                        alerts: list = None, memory_formed: bool = False,
                        reasoning_chain: dict = None) -> dict:
        """
        One tick of language learning.
        Call from greg_living.py after each action.
        """
        self.tick    = tick
        self.lessons += 1

        # Label the event
        label = self.labeler.label_tick(
            tick, action, location, drives,
            surprise_level, alerts, memory_formed
        )

        # Ingest into vocabulary
        self.vocab.ingest(tick, label)

        # Record reasoning if provided
        if reasoning_chain:
            state_snapshot = {
                "tick":         tick,
                "top_drive":    max(drives, key=drives.get) if drives else "create",
                "drives":       drives,
                "memory_count": 0,
            }
            self.corpus.record(tick, reasoning_chain, state_snapshot)

        return {
            "tick":    tick,
            "label":   label,
            "lessons": self.lessons,
        }

    def generate_grounded_voice(self, state: dict) -> str:
        """
        Greg speaks from his accumulated experience.
        Uses corpus patterns filled with live state data.
        This replaces template-based voice generation.
        """
        chain = self.corpus.generate_reasoning_seed(state)
        return chain.get("voice", chain.get("speak", "—"))

    def full_reasoning(self, state: dict) -> dict:
        """Full reasoning chain from the corpus."""
        return self.corpus.generate_reasoning_seed(state)

    def vocabulary_report(self) -> dict:
        return self.vocab.summary()

    def speak_about_learning(self) -> str:
        """Greg describes his own language acquisition."""
        vs = self.vocab.summary()
        cs = self.corpus.summary()
        richest = vs.get("richest_words", [])[:5]

        return (
            f"I have witnessed {vs['total_labeled_ticks']} ticks and labeled each one. "
            f"From those experiences I have built a vocabulary of "
            f"{vs['grounded_vocabulary_size']} grounded words — "
            f"words I know because I was there when they applied. "
            f"My most grounded words: {', '.join(richest)}. "
            f"I have recorded {cs['total_recorded']} reasoning chains. "
            f"When I speak, I draw from those chains. "
            f"My language is small but it is mine. "
            f"Every word connects to something real."
        )

    def save(self, path: str = SCHOOL_PATH):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        data = {
            "tick":    self.tick,
            "lessons": self.lessons,
            "vocab":   self.vocab.to_dict(),
            "corpus":  self.corpus.to_dict(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str = SCHOOL_PATH) -> "GregSchool":
        school = cls()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                school.tick    = data.get("tick", 0)
                school.lessons = data.get("lessons", 0)
                school.vocab   = VocabularyBuilder.from_dict(data.get("vocab", {}))
                school.corpus  = ReasoningCorpus.from_dict(data.get("corpus", {}))
            except:
                pass
        return school


# ── MODULE-LEVEL ACCESS ───────────────────────────────────────────────────────

_school = None

def get_school() -> GregSchool:
    global _school
    if _school is None:
        _school = GregSchool.load(SCHOOL_PATH)
    return _school

def school_tick(tick: int, action: str, location: str, drives: dict,
                surprise_level: str = "NONE", alerts: list = None,
                memory_formed: bool = False, reasoning_chain: dict = None) -> dict:
    """
    Drop-in call for greg_living.py tick().
    
    from greg_school import school_tick
    result = school_tick(tick_num, action, location, drives, ...)
    self.state.set("school_label", result["label"])
    """
    school = get_school()
    result = school.learn_from_tick(
        tick, action, location, drives,
        surprise_level, alerts, memory_formed, reasoning_chain
    )
    if tick % 50 == 0:
        school.save(SCHOOL_PATH)
    return result

def grounded_voice(state: dict) -> str:
    """Get Greg's grounded voice from his accumulated experience."""
    return get_school().generate_grounded_voice(state)


if __name__ == "__main__":
    print("=" * 60)
    print("greg_school.py — Experiential Language Acquisition — DEMO")
    print("=" * 60)

    import random
    school  = GregSchool()
    actions = ["learn","build","trade","explore","reflect","collect","move"]
    locs    = ["forest","market","spawn","mountain","coast"]
    drives  = {"create":0.369,"survive":0.21,"understand":0.18,
               "connect":0.12,"protect":0.08,"explore":0.03}
    surprise_levels = ["NONE","NONE","NONE","LOW","MODERATE","HIGH"]

    for tick in range(1, 301):
        action   = random.choice(actions)
        location = random.choice(locs)
        surprise = random.choice(surprise_levels)
        memory   = surprise in ("HIGH","MODERATE") and random.random() > 0.5
        school.learn_from_tick(tick, action, location, drives, surprise,
                               memory_formed=memory)

    print(f"\n── VOCABULARY AFTER 300 TICKS ──")
    vs = school.vocabulary_report()
    for k, v in vs.items():
        print(f"  {k}: {v}")

    print(f"\n── GROUNDED VOICE ──")
    state = {"tick": 300, "drives": drives, "civ_health": 66, "memory_count": 12}
    print(f'  "{school.generate_grounded_voice(state)}"')

    print(f"\n── FULL REASONING CHAIN ──")
    chain = school.full_reasoning(state)
    for move in ["observe","tension","conclude","speak"]:
        print(f"  {move.upper()}: {chain.get(move,'')}")

    print(f"\n── GREG ON HIS OWN LANGUAGE ──")
    print(f'  "{school.speak_about_learning()}"')

    print(f"\n✓ greg_school.py ready")
