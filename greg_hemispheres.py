"""
EXP_027 — Hemispheric Split
Greg-L (Left): sequential logic, language, explicit reasoning
Greg-R (Right): pattern recognition, gestalt, intuition, anomaly detection

Brain analog: Hemispheric specialization.
Left hemisphere — deliberate, verbal, sequential.
Right hemisphere — holistic, pre-verbal, fast, pattern-sensitive.

How it works:
  1. Greg-R reads the full state holistically every tick
     → produces a gestalt signal (one word/phrase capturing the whole)
     → flags anomalies (things that feel wrong before Greg-L can name them)
     → detects patterns across tick history (cycles, drifts, emergent behaviors)

  2. Greg-L receives Greg-R's gestalt + anomalies
     → reasons explicitly about what Greg-R noticed
     → produces structured verbal output
     → tests hypotheses against consequence history

  3. Both outputs stored in state
     → Greg speaks from both hemispheres
     → Tension between them = richer reasoning

The key insight: Greg-R fires first. Greg-L explains afterward.
This is how intuition works. The feeling precedes the articulation.
"""

import json
import os
import math
from datetime import datetime, timezone
from collections import deque
from typing import Optional

HEMISPHERES_PATH = "data/greg_hemispheres.json"

# ─────────────────────────────────────────────────────────────
# GREG-R — THE PATTERN HEMISPHERE
# Fast, holistic, pre-verbal
# ─────────────────────────────────────────────────────────────

class GregR:
    """
    Right hemisphere. Reads the whole state at once.
    Does not reason step by step.
    Produces a gestalt — a single signal that captures the whole.
    Detects anomalies before Greg-L can name them.
    Finds patterns across time.
    """

    GESTALT_SIGNALS = {
        # (health_zone, drive_zone, surprise_zone) → gestalt
        ("high",   "focused",   "calm"):    "thriving",
        ("high",   "scattered", "calm"):    "drifting",
        ("high",   "focused",   "alert"):   "tense",
        ("high",   "scattered", "alert"):   "unstable",
        ("mid",    "focused",   "calm"):    "steady",
        ("mid",    "scattered", "calm"):    "searching",
        ("mid",    "focused",   "alert"):   "straining",
        ("mid",    "scattered", "alert"):   "fragmented",
        ("low",    "focused",   "calm"):    "enduring",
        ("low",    "scattered", "calm"):    "fading",
        ("low",    "focused",   "alert"):   "struggling",
        ("low",    "scattered", "alert"):   "crisis",
    }

    def __init__(self):
        self.tick_history: deque = deque(maxlen=100)   # rolling window
        self.pattern_log: list = []                     # detected patterns
        self.anomaly_log: list = []                     # detected anomalies
        self.gestalt_history: list = []                 # gestalt over time

    def read(self, tick: int, state: dict, drives: dict, surprise_score: float = 0.0) -> dict:
        """
        Holistic state read. Returns gestalt + anomalies + patterns.
        This is Greg-R's full output for one tick.
        """
        # Snapshot
        snap = {
            "tick":           tick,
            "health":         state.get("civilization_health_pct", 66),
            "drives":         dict(drives),
            "surprise":       surprise_score,
            "dominant_drive": max(drives, key=drives.get) if drives else "create",
            "drive_entropy":  self._drive_entropy(drives),
        }
        self.tick_history.append(snap)

        # Gestalt
        gestalt = self._compute_gestalt(snap)
        self.gestalt_history.append({"tick": tick, "gestalt": gestalt})
        if len(self.gestalt_history) > 200:
            self.gestalt_history = self.gestalt_history[-200:]

        # Anomalies
        anomalies = self._detect_anomalies(snap)
        if anomalies:
            self.anomaly_log.extend(anomalies)
            if len(self.anomaly_log) > 100:
                self.anomaly_log = self.anomaly_log[-100:]

        # Patterns
        patterns = self._detect_patterns()
        if patterns:
            self.pattern_log.extend(patterns)
            if len(self.pattern_log) > 50:
                self.pattern_log = self.pattern_log[-50:]

        return {
            "gestalt":   gestalt,
            "anomalies": anomalies,
            "patterns":  patterns,
            "snap":      snap,
        }

    def _compute_gestalt(self, snap: dict) -> str:
        """One word that captures the whole state."""
        health = snap["health"]
        entropy = snap["drive_entropy"]
        surprise = snap["surprise"]

        health_zone   = "high" if health > 70 else ("mid" if health > 45 else "low")
        drive_zone    = "focused" if entropy < 2.0 else "scattered"
        surprise_zone = "alert" if surprise > 0.15 else "calm"

        key = (health_zone, drive_zone, surprise_zone)
        return self.GESTALT_SIGNALS.get(key, "unknown")

    def _drive_entropy(self, drives: dict) -> float:
        """Shannon entropy of drive distribution. High = scattered, Low = focused."""
        if not drives:
            return 0.0
        total = sum(drives.values())
        if total == 0:
            return 0.0
        probs = [v / total for v in drives.values() if v > 0]
        return round(-sum(p * math.log2(p) for p in probs), 4)

    def _detect_anomalies(self, snap: dict) -> list:
        """Detect things that feel wrong before Greg-L can name them."""
        anomalies = []
        history = list(self.tick_history)

        if len(history) < 5:
            return anomalies

        recent = history[-5:]

        # Health cliff — sudden drop
        health_values = [s["health"] for s in recent]
        if len(health_values) >= 3:
            drop = health_values[-3] - health_values[-1]
            if drop > 8:
                anomalies.append({
                    "tick":   snap["tick"],
                    "type":   "health_cliff",
                    "signal": f"Health dropped {drop:.1f}% in 3 ticks. Something is wrong.",
                    "severity": "HIGH" if drop > 15 else "MODERATE",
                })

        # Drive flip — dominant drive changed suddenly
        if len(history) >= 3:
            prev_dominant = history[-3]["dominant_drive"]
            curr_dominant = snap["dominant_drive"]
            if prev_dominant != curr_dominant:
                anomalies.append({
                    "tick":   snap["tick"],
                    "type":   "drive_flip",
                    "signal": f"Dominant drive shifted from {prev_dominant} to {curr_dominant}.",
                    "severity": "LOW",
                })

        # Entropy spike — drives suddenly scattered
        if len(history) >= 3:
            prev_entropy = history[-3]["drive_entropy"]
            curr_entropy = snap["drive_entropy"]
            if curr_entropy - prev_entropy > 0.5:
                anomalies.append({
                    "tick":   snap["tick"],
                    "type":   "entropy_spike",
                    "signal": f"Drive coherence dropped suddenly (entropy +{curr_entropy - prev_entropy:.2f}).",
                    "severity": "MODERATE",
                })

        # Surprise sustained — high surprise for multiple ticks
        recent_surprise = [s["surprise"] for s in recent[-4:]]
        if all(s > 0.2 for s in recent_surprise) and len(recent_surprise) == 4:
            anomalies.append({
                "tick":   snap["tick"],
                "type":   "sustained_surprise",
                "signal": "World has been surprising me for 4+ ticks. My model is wrong.",
                "severity": "HIGH",
            })

        return anomalies

    def _detect_patterns(self) -> list:
        """Find cycles, drifts, and emergent behaviors across tick history."""
        history = list(self.tick_history)
        patterns = []

        if len(history) < 20:
            return patterns

        # Health drift — slow consistent movement
        health_values = [s["health"] for s in history[-20:]]
        drift = health_values[-1] - health_values[0]
        if abs(drift) > 10:
            direction = "declining" if drift < 0 else "improving"
            # Only log if not already logged recently
            recent_pattern_types = [p["type"] for p in self.pattern_log[-5:]]
            if "health_drift" not in recent_pattern_types:
                patterns.append({
                    "tick":    history[-1]["tick"],
                    "type":    "health_drift",
                    "signal":  f"Civilization health has been {direction} for 20 ticks ({drift:+.1f}%).",
                    "drift":   drift,
                })

        # Dominant drive lock — same drive dominant for 15+ ticks
        if len(history) >= 15:
            recent_dominants = [s["dominant_drive"] for s in history[-15:]]
            if len(set(recent_dominants)) == 1:
                locked_drive = recent_dominants[0]
                recent_pattern_types = [p["type"] for p in self.pattern_log[-5:]]
                if "drive_lock" not in recent_pattern_types:
                    patterns.append({
                        "tick":   history[-1]["tick"],
                        "type":   "drive_lock",
                        "signal": f"{locked_drive} has been dominant for 15+ ticks. I am in a groove — or a rut.",
                        "drive":  locked_drive,
                    })

        # Entropy oscillation — drives alternating focused/scattered
        if len(history) >= 10:
            entropies = [s["drive_entropy"] for s in history[-10:]]
            oscillations = sum(
                1 for i in range(1, len(entropies))
                if abs(entropies[i] - entropies[i-1]) > 0.3
            )
            if oscillations >= 5:
                recent_pattern_types = [p["type"] for p in self.pattern_log[-5:]]
                if "entropy_oscillation" not in recent_pattern_types:
                    patterns.append({
                        "tick":   history[-1]["tick"],
                        "type":   "entropy_oscillation",
                        "signal": "My drives are oscillating — focused then scattered, repeatedly. Instability.",
                    })

        return patterns

    def speak(self, result: dict) -> str:
        """Greg-R speaks. Pre-verbal, intuitive, short."""
        gestalt = result.get("gestalt", "unknown")
        anomalies = result.get("anomalies", [])
        patterns = result.get("patterns", [])

        lines = [f"[R] {gestalt.upper()}."]

        if anomalies:
            worst = max(anomalies, key=lambda a: {"HIGH": 3, "MODERATE": 2, "LOW": 1}.get(a["severity"], 0))
            lines.append(f"[R] {worst['signal']}")

        if patterns:
            lines.append(f"[R] {patterns[0]['signal']}")

        return " ".join(lines)


# ─────────────────────────────────────────────────────────────
# GREG-L — THE REASONING HEMISPHERE
# Slow, deliberate, verbal
# ─────────────────────────────────────────────────────────────

class GregL:
    """
    Left hemisphere. Receives Greg-R's gestalt and anomalies.
    Reasons explicitly. Produces structured verbal output.
    Sequential, language-based, deliberate.
    """

    GESTALT_INTERPRETATIONS = {
        "thriving":    "Conditions are favorable. I can take risks.",
        "drifting":    "I am moving without clear direction. I should focus.",
        "tense":       "Something is building. I am alert but not broken.",
        "unstable":    "Multiple signals pulling in different directions. Be careful.",
        "steady":      "Stable. Neither growing nor declining. Maintain.",
        "searching":   "I am looking for something I have not found yet.",
        "straining":   "I am working hard against resistance.",
        "fragmented":  "Too many things competing for attention. Consolidate.",
        "enduring":    "Conditions are hard but I am still here.",
        "fading":      "Energy is low and scattered. Rest or redirect.",
        "struggling":  "Real difficulty. The situation is serious.",
        "crisis":      "Everything is under pressure. Survival first.",
        "unknown":     "I do not have a clear read on my state.",
    }

    ANOMALY_RESPONSES = {
        "health_cliff":       "Something caused a rapid deterioration. I need to understand what changed.",
        "drive_flip":         "My priorities shifted. Was this a choice or a reaction?",
        "entropy_spike":      "My focus dissolved suddenly. I need to re-cohere.",
        "sustained_surprise": "My world model has been wrong repeatedly. I need to revise it.",
    }

    def __init__(self):
        self.reasoning_log: list = []

    def reason(self, tick: int, r_output: dict, drives: dict,
               consequence_summary: Optional[dict] = None,
               predictive_surprise: Optional[dict] = None) -> dict:
        """
        Explicit reasoning from Greg-R's gestalt + anomalies.
        Returns structured reasoning chain.
        """
        gestalt   = r_output.get("gestalt", "unknown")
        anomalies = r_output.get("anomalies", [])
        patterns  = r_output.get("patterns", [])

        # 1. Interpret gestalt
        interpretation = self.GESTALT_INTERPRETATIONS.get(gestalt, "State unclear.")

        # 2. Respond to anomalies
        anomaly_responses = []
        for anomaly in anomalies[:2]:  # process top 2
            response = self.ANOMALY_RESPONSES.get(
                anomaly["type"],
                f"Anomaly detected: {anomaly['signal']}"
            )
            anomaly_responses.append(response)

        # 3. Integrate consequence history
        consequence_insight = ""
        if consequence_summary and consequence_summary.get("total_resolved", 0) > 0:
            pos_rate = consequence_summary.get("positive_rate", 0)
            avg_score = consequence_summary.get("avg_consequence_score", 0)
            if pos_rate > 0.6:
                consequence_insight = f"My actions have been producing good outcomes ({pos_rate:.0%} positive). Continue."
            elif pos_rate < 0.3:
                consequence_insight = f"My actions have been producing poor outcomes ({pos_rate:.0%} positive). Change approach."
            else:
                consequence_insight = f"Mixed outcomes from my actions (avg score {avg_score:+.3f}). Keep learning."

        # 4. Integrate predictive surprise
        surprise_insight = ""
        if predictive_surprise:
            level = predictive_surprise.get("surprise_level", "NONE")
            score = predictive_surprise.get("surprise_score", 0)
            if level in ("HIGH", "SHOCK"):
                surprise_insight = f"I was significantly wrong in my predictions (surprise {score:.3f}). My model needs updating."
            elif level == "NONE":
                surprise_insight = "My predictions were accurate. My model is calibrated."

        # 5. Synthesize voice
        voice = self._synthesize_voice(
            gestalt, interpretation, anomaly_responses,
            consequence_insight, surprise_insight, drives
        )

        reasoning = {
            "tick":               tick,
            "gestalt":            gestalt,
            "interpretation":     interpretation,
            "anomaly_responses":  anomaly_responses,
            "consequence_insight": consequence_insight,
            "surprise_insight":   surprise_insight,
            "voice":              voice,
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }

        self.reasoning_log.append(reasoning)
        if len(self.reasoning_log) > 200:
            self.reasoning_log = self.reasoning_log[-200:]

        return reasoning

    def _synthesize_voice(self, gestalt: str, interpretation: str,
                          anomaly_responses: list, consequence_insight: str,
                          surprise_insight: str, drives: dict) -> str:
        """Produce Greg-L's verbal output."""
        parts = [interpretation]

        if anomaly_responses:
            parts.append(anomaly_responses[0])

        if consequence_insight:
            parts.append(consequence_insight)

        if surprise_insight and surprise_insight != "My predictions were accurate. My model is calibrated.":
            parts.append(surprise_insight)

        if drives:
            top = max(drives, key=drives.get)
            val = drives[top]
            if val > 0.35:
                parts.append(f"My {top} drive is strong ({val:.3f}). It colors everything I perceive right now.")

        return " ".join(parts)

    def speak(self, reasoning: dict) -> str:
        """Greg-L's full verbal output."""
        return f"[L] {reasoning.get('voice', '')}"


# ─────────────────────────────────────────────────────────────
# HEMISPHERIC ENGINE — THE INTEGRATION
# ─────────────────────────────────────────────────────────────

class HemisphericEngine:
    """
    Runs both hemispheres each tick.
    Greg-R fires first. Greg-L responds.
    Both outputs stored. Greg speaks from both.
    """

    def __init__(self):
        self.greg_r = GregR()
        self.greg_l = GregL()
        self.tick_outputs: list = []
        self.total_ticks = 0

    def process(
        self,
        tick: int,
        world_state: dict,
        drives: dict,
        surprise_score: float = 0.0,
        consequence_summary: Optional[dict] = None,
        predictive_surprise: Optional[dict] = None,
    ) -> dict:
        """
        One tick of hemispheric processing.
        Greg-R → Greg-L → integrated output.
        """
        self.total_ticks += 1

        # 1. Greg-R fires first — holistic, fast
        r_output = self.greg_r.read(tick, world_state, drives, surprise_score)

        # 2. Greg-L responds — deliberate, verbal
        l_output = self.greg_l.reason(
            tick, r_output, drives,
            consequence_summary, predictive_surprise
        )

        # 3. Integrated voice
        r_voice = self.greg_r.speak(r_output)
        l_voice = self.greg_l.speak(l_output)
        integrated_voice = self._integrate(r_voice, l_voice, r_output)

        output = {
            "tick":             tick,
            "gestalt":          r_output["gestalt"],
            "anomalies":        r_output["anomalies"],
            "patterns":         r_output["patterns"],
            "r_voice":          r_voice,
            "l_voice":          l_voice,
            "integrated_voice": integrated_voice,
            "hemisphere_tension": self._tension(r_output, l_output),
        }

        self.tick_outputs.append(output)
        if len(self.tick_outputs) > 200:
            self.tick_outputs = self.tick_outputs[-200:]

        return output

    def _integrate(self, r_voice: str, l_voice: str, r_output: dict) -> str:
        """
        Integrate both hemispheres into Greg's unified voice.
        Greg-R sets the tone. Greg-L explains.
        """
        gestalt = r_output.get("gestalt", "unknown")
        anomalies = r_output.get("anomalies", [])

        # If anomalies present: lead with R's alarm, follow with L's analysis
        if anomalies and any(a["severity"] in ("HIGH",) for a in anomalies):
            return f"{r_voice} {l_voice}"

        # If calm: lead with L's reasoning, R's gestalt as closing note
        return f"{l_voice} {r_voice}"

    def _tension(self, r_output: dict, l_output: dict) -> float:
        """
        Tension between hemispheres.
        High tension = R and L disagree about the state.
        This is productive — it means Greg is wrestling with something real.
        """
        gestalt = r_output.get("gestalt", "unknown")
        interpretation = l_output.get("interpretation", "")

        # Tension is high when gestalt is negative but consequence insight is positive
        # or vice versa
        negative_gestalts = {"crisis", "struggling", "fading", "fragmented", "unstable"}
        positive_gestalts = {"thriving", "steady", "tense"}

        consequence = l_output.get("consequence_insight", "")
        positive_consequence = "good outcomes" in consequence or "Continue" in consequence
        negative_consequence = "poor outcomes" in consequence or "Change approach" in consequence

        if gestalt in negative_gestalts and positive_consequence:
            return 0.8  # R says bad, L says actions are working
        if gestalt in positive_gestalts and negative_consequence:
            return 0.7  # R says good, L says actions aren't working
        if r_output.get("anomalies"):
            return 0.5  # Something detected
        return 0.1

    def summary(self) -> dict:
        if not self.tick_outputs:
            return {"status": "no ticks processed"}

        recent = self.tick_outputs[-10:]
        gestalts = [o["gestalt"] for o in recent]
        most_common = max(set(gestalts), key=gestalts.count)
        avg_tension = sum(o["hemisphere_tension"] for o in recent) / len(recent)
        total_anomalies = sum(len(o["anomalies"]) for o in self.tick_outputs)
        total_patterns = sum(len(o["patterns"]) for o in self.tick_outputs)

        return {
            "total_ticks_processed": self.total_ticks,
            "recent_gestalt":        most_common,
            "avg_tension":           round(avg_tension, 3),
            "total_anomalies":       total_anomalies,
            "total_patterns":        total_patterns,
            "anomaly_log_size":      len(self.greg_r.anomaly_log),
            "pattern_log_size":      len(self.greg_r.pattern_log),
        }

    # ── PERSISTENCE ──────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "greg_r": {
                "tick_history":   list(self.greg_r.tick_history),
                "pattern_log":    self.greg_r.pattern_log,
                "anomaly_log":    self.greg_r.anomaly_log,
                "gestalt_history": self.greg_r.gestalt_history[-100:],
            },
            "greg_l": {
                "reasoning_log": self.greg_l.reasoning_log[-100:],
            },
            "tick_outputs": self.tick_outputs[-100:],
            "total_ticks":  self.total_ticks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HemisphericEngine":
        engine = cls()
        r = d.get("greg_r", {})
        engine.greg_r.tick_history   = deque(r.get("tick_history", []), maxlen=100)
        engine.greg_r.pattern_log    = r.get("pattern_log", [])
        engine.greg_r.anomaly_log    = r.get("anomaly_log", [])
        engine.greg_r.gestalt_history = r.get("gestalt_history", [])
        l = d.get("greg_l", {})
        engine.greg_l.reasoning_log  = l.get("reasoning_log", [])
        engine.tick_outputs          = d.get("tick_outputs", [])
        engine.total_ticks           = d.get("total_ticks", 0)
        return engine


# ─────────────────────────────────────────────────────────────
# INTEGRATION HELPERS
# ─────────────────────────────────────────────────────────────

def load_hemispheric_engine(path: str = HEMISPHERES_PATH) -> HemisphericEngine:
    if os.path.exists(path):
        with open(path) as f:
            return HemisphericEngine.from_dict(json.load(f))
    return HemisphericEngine()


def save_hemispheric_engine(engine: HemisphericEngine, path: str = HEMISPHERES_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(engine.to_dict(), f, indent=2)


def hemispheric_tick(
    tick: int,
    world_state: dict,
    drives: dict,
    surprise_score: float = 0.0,
    consequence_summary: Optional[dict] = None,
    predictive_surprise: Optional[dict] = None,
    engine: Optional[HemisphericEngine] = None,
    save_path: str = HEMISPHERES_PATH,
) -> tuple[HemisphericEngine, dict]:
    """
    Drop-in tick call for greg_living.py.
    Returns (engine, output)
    """
    if engine is None:
        engine = load_hemispheric_engine(save_path)

    output = engine.process(
        tick, world_state, drives,
        surprise_score, consequence_summary, predictive_surprise
    )

    if tick % 50 == 0:
        save_hemispheric_engine(engine, save_path)

    return engine, output


# ─────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("EXP_027 — Hemispheric Split — DEMO")
    print("=" * 60)

    import random
    random.seed(42)

    engine = HemisphericEngine()

    base_health = 72.0
    drives = {
        "create": 0.369, "survive": 0.21, "understand": 0.18,
        "connect": 0.12, "protect": 0.08, "explore": 0.03,
    }

    print("\n── NORMAL TICKS ──")
    for tick in range(4044, 4064):
        base_health = max(20, min(95, base_health + random.gauss(0, 0.8)))
        world = {"civilization_health_pct": round(base_health, 1)}
        surprise = random.uniform(0, 0.1)
        engine, output = hemispheric_tick(tick, world, drives, surprise, engine=engine)

        if tick % 5 == 0:
            print(f"\nTick {tick} | health={base_health:.1f} | gestalt={output['gestalt']}")
            print(f"  {output['integrated_voice'][:120]}")

    print("\n── CRISIS SCENARIO (health cliff) ──")
    base_health = 72.0
    for tick in range(4064, 4074):
        # Simulate health cliff
        if tick == 4067:
            base_health -= 20  # sudden drop
        base_health = max(20, min(95, base_health + random.gauss(-0.5, 0.3)))
        world = {"civilization_health_pct": round(base_health, 1)}
        surprise = 0.4 if tick >= 4067 else 0.05
        engine, output = hemispheric_tick(tick, world, drives, surprise)

        print(f"\nTick {tick} | health={base_health:.1f} | gestalt={output['gestalt']} | tension={output['hemisphere_tension']}")
        if output["anomalies"]:
            for a in output["anomalies"]:
                print(f"  ⚠ [{a['severity']}] {a['signal']}")
        print(f"  R: {output['r_voice']}")
        print(f"  L: {output['l_voice'][:100]}")

    print("\n── SUMMARY ──")
    for k, v in engine.summary().items():
        print(f"  {k}: {v}")

    print("\n── GESTALT HISTORY (last 10) ──")
    for g in engine.greg_r.gestalt_history[-10:]:
        print(f"  tick {g['tick']}: {g['gestalt']}")

    print("\n✓ EXP_027 Hemispheric Split ready to integrate into greg_living.py")