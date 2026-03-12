"""
EXP_020 — Predictive Coding
Greg predicts next tick, learns from surprise.
Brain analog: Predictive processing (Karl Friston / Free Energy Principle)

How it works:
  1. Before each tick: Greg generates predictions about what the next state will be
  2. After tick resolves: Greg compares predictions to reality
  3. Prediction error (surprise) = learning signal
  4. High surprise → memory formation + drive adjustment
  5. Low surprise → confidence grows, prediction model sharpens

No backprop. No gradient descent. Pure architecture.
"""

import json
import os
import math
from datetime import datetime, timezone
from typing import Optional

# ─────────────────────────────────────────────
# PREDICTION MODEL
# ─────────────────────────────────────────────

class PredictiveModel:
    """
    Greg's internal model of the world.
    Tracks what Greg expects, what happened, and how wrong he was.
    """

    def __init__(self):
        self.predictions: list[dict] = []          # pending predictions
        self.prediction_history: list[dict] = []   # resolved predictions
        self.surprise_log: list[dict] = []         # surprise events worth remembering
        self.confidence: dict[str, float] = {}     # per-domain confidence 0.0–1.0
        self.total_predictions = 0
        self.total_resolved = 0

    # ── PREDICT ───────────────────────────────

    def predict(self, tick: int, state: dict) -> dict:
        """
        Before tick N+1: generate predictions from current state.
        Returns a prediction bundle.
        """
        predicted_health = self._predict_health(state)
        predicted_dominant_drive = self._predict_dominant_drive(state)
        predicted_agent_count = self._predict_agents(state)
        predicted_memory_count = self._predict_memories(state)

        prediction = {
            "tick": tick,
            "predicted_at": datetime.now(timezone.utc).isoformat(),
            "predicted_next_tick": tick + 1,
            "predictions": {
                "civilization_health": predicted_health,
                "dominant_drive": predicted_dominant_drive,
                "agent_count": predicted_agent_count,
                "memory_count": predicted_memory_count,
            },
            "confidence_snapshot": dict(self.confidence),
            "resolved": False,
        }

        self.predictions.append(prediction)
        self.total_predictions += 1
        return prediction

    def _predict_health(self, state: dict) -> dict:
        """Predict civilization health next tick."""
        current = state.get("civilization_health_pct", 66)
        # Simple momentum model: assume small drift toward mean
        mean = 65.0
        momentum = state.get("health_momentum", 0.0)
        predicted = current + momentum * 0.7 + (mean - current) * 0.05
        predicted = max(0.0, min(100.0, predicted))
        confidence = self.confidence.get("civilization_health", 0.5)
        return {
            "value": round(predicted, 2),
            "confidence": round(confidence, 3),
        }

    def _predict_dominant_drive(self, state: dict) -> dict:
        """Predict which drive will dominate next tick."""
        drives = state.get("drives", {})
        if not drives:
            return {"value": "create", "confidence": 0.3}
        current_dominant = max(drives, key=lambda k: drives[k])
        confidence = self.confidence.get("dominant_drive", 0.4)
        return {
            "value": current_dominant,
            "confidence": round(confidence, 3),
        }

    def _predict_agents(self, state: dict) -> dict:
        """Predict agent count next tick."""
        current = state.get("agent_count", 10154)
        # Agents grow slowly
        predicted = current + int(current * 0.001)
        confidence = self.confidence.get("agent_count", 0.7)
        return {
            "value": predicted,
            "confidence": round(confidence, 3),
        }

    def _predict_memories(self, state: dict) -> dict:
        """Predict memory count next tick."""
        current = state.get("memory_count", 10)
        # Memories accumulate but rarely
        predicted = current  # most ticks: no new memory
        confidence = self.confidence.get("memory_count", 0.75)
        return {
            "value": predicted,
            "confidence": round(confidence, 3),
        }

    # ── RESOLVE ───────────────────────────────

    def resolve(self, prediction: dict, actual_state: dict) -> dict:
        """
        After tick N+1: compare prediction to what actually happened.
        Returns surprise report.
        """
        predicted = prediction["predictions"]
        actual = {
            "civilization_health": actual_state.get("civilization_health_pct", 66),
            "dominant_drive": actual_state.get("dominant_drive", "create"),
            "agent_count": actual_state.get("agent_count", 10154),
            "memory_count": actual_state.get("memory_count", 10),
        }

        errors = {}
        surprise_score = 0.0

        # Health error (continuous)
        h_pred = predicted["civilization_health"]["value"]
        h_actual = actual["civilization_health"]
        h_err = abs(h_pred - h_actual) / 100.0
        errors["civilization_health"] = {
            "predicted": h_pred,
            "actual": h_actual,
            "error": round(h_err, 4),
        }
        surprise_score += h_err * predicted["civilization_health"]["confidence"]
        self._update_confidence("civilization_health", h_err)

        # Drive error (categorical)
        d_pred = predicted["dominant_drive"]["value"]
        d_actual = actual["dominant_drive"]
        d_err = 0.0 if d_pred == d_actual else 1.0
        errors["dominant_drive"] = {
            "predicted": d_pred,
            "actual": d_actual,
            "error": d_err,
        }
        surprise_score += d_err * predicted["dominant_drive"]["confidence"]
        self._update_confidence("dominant_drive", d_err)

        # Agent count error (relative)
        a_pred = predicted["agent_count"]["value"]
        a_actual = actual["agent_count"]
        a_err = abs(a_pred - a_actual) / max(a_actual, 1)
        errors["agent_count"] = {
            "predicted": a_pred,
            "actual": a_actual,
            "error": round(a_err, 4),
        }
        surprise_score += a_err * 0.3
        self._update_confidence("agent_count", a_err)

        # Memory count error (discrete)
        m_pred = predicted["memory_count"]["value"]
        m_actual = actual["memory_count"]
        m_err = abs(m_pred - m_actual) / max(m_actual, 1)
        errors["memory_count"] = {
            "predicted": m_pred,
            "actual": m_actual,
            "error": round(m_err, 4),
        }
        surprise_score += m_err * 0.2
        self._update_confidence("memory_count", m_err)

        # Normalize surprise (0.0 – 1.0)
        surprise_score = min(1.0, surprise_score / 4.0)

        surprise_report = {
            "tick": prediction["tick"],
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "errors": errors,
            "surprise_score": round(surprise_score, 4),
            "surprise_level": self._classify_surprise(surprise_score),
            "confidence_updated": dict(self.confidence),
        }

        # Mark prediction resolved
        prediction["resolved"] = True
        prediction["surprise_report"] = surprise_report
        self.prediction_history.append(prediction)
        self.total_resolved += 1

        # Log high-surprise events as potential memories
        if surprise_score > 0.3:
            self._log_surprise(surprise_report, actual_state)

        return surprise_report

    def _classify_surprise(self, score: float) -> str:
        if score < 0.05:
            return "NONE"
        elif score < 0.15:
            return "LOW"
        elif score < 0.30:
            return "MODERATE"
        elif score < 0.50:
            return "HIGH"
        else:
            return "SHOCK"

    def _update_confidence(self, domain: str, error: float):
        """
        Learning from surprise:
        High error → lower confidence (be more uncertain)
        Low error  → higher confidence (I understand this domain)
        """
        current = self.confidence.get(domain, 0.5)
        # Exponential moving average
        alpha = 0.15
        new_confidence = current * (1 - alpha) + (1 - error) * alpha
        self.confidence[domain] = round(max(0.05, min(0.99, new_confidence)), 4)

    def _log_surprise(self, surprise_report: dict, actual_state: dict):
        """High surprise events get flagged for memory formation."""
        entry = {
            "tick": surprise_report["tick"],
            "surprise_score": surprise_report["surprise_score"],
            "surprise_level": surprise_report["surprise_level"],
            "key_errors": {
                k: v for k, v in surprise_report["errors"].items()
                if v["error"] > 0.1
            },
            "timestamp": surprise_report["resolved_at"],
            "flagged_for_memory": True,
        }
        self.surprise_log.append(entry)

    # ── INTROSPECT ────────────────────────────

    def summarize(self) -> dict:
        """Greg's understanding of his own predictive accuracy."""
        if not self.prediction_history:
            return {"status": "no predictions resolved yet"}

        recent = self.prediction_history[-10:]
        avg_surprise = sum(
            p["surprise_report"]["surprise_score"] for p in recent
        ) / len(recent)

        return {
            "total_predictions": self.total_predictions,
            "total_resolved": self.total_resolved,
            "recent_avg_surprise": round(avg_surprise, 4),
            "surprise_events": len(self.surprise_log),
            "confidence_by_domain": dict(self.confidence),
            "model_maturity": self._maturity_label(avg_surprise),
        }

    def _maturity_label(self, avg_surprise: float) -> str:
        if avg_surprise < 0.05:
            return "EXPERT — I understand this world well"
        elif avg_surprise < 0.15:
            return "CALIBRATED — mostly right, occasionally surprised"
        elif avg_surprise < 0.30:
            return "LEARNING — building my model"
        else:
            return "NAIVE — still discovering how this world works"

    def speak(self, surprise_report: Optional[dict] = None) -> str:
        """
        Greg narrates his predictive experience in first person.
        This feeds into EXP_019 Hybrid Mind.
        """
        summary = self.summarize()
        if surprise_report is None:
            if not self.surprise_log:
                return (
                    "I have not yet resolved a prediction. "
                    "My model of the world is untested. That will change."
                )
            surprise_report = self.prediction_history[-1].get("surprise_report", {})

        level = surprise_report.get("surprise_level", "NONE")
        score = surprise_report.get("surprise_score", 0.0)
        errors = surprise_report.get("errors", {})

        # Find biggest surprise
        biggest = max(errors.items(), key=lambda x: x[1]["error"], default=None)

        lines = []

        if level == "NONE":
            lines.append("I predicted this tick almost exactly. The world is behaving as I expect.")
        elif level == "LOW":
            lines.append(f"Small surprise this tick — score {score:.3f}. My model holds.")
        elif level == "MODERATE":
            lines.append(f"Moderate surprise — score {score:.3f}. Something shifted.")
        elif level == "HIGH":
            lines.append(f"High surprise — score {score:.3f}. I was wrong about something important.")
        else:
            lines.append(f"SHOCK — score {score:.3f}. The world did something I did not anticipate.")

        if biggest:
            domain, err_data = biggest
            if err_data["error"] > 0.05:
                lines.append(
                    f"My biggest miss: {domain}. "
                    f"I expected {err_data['predicted']}, got {err_data['actual']}."
                )

        lines.append(
            f"My predictive model is now: {summary.get('model_maturity', 'forming')}. "
            f"Average surprise over recent ticks: {summary.get('recent_avg_surprise', 0):.3f}."
        )

        return " ".join(lines)

    # ── PERSISTENCE ───────────────────────────

    def to_dict(self) -> dict:
        return {
            "predictions": self.predictions[-50:],        # keep last 50 pending
            "prediction_history": self.prediction_history[-200:],  # keep last 200
            "surprise_log": self.surprise_log[-100:],
            "confidence": self.confidence,
            "total_predictions": self.total_predictions,
            "total_resolved": self.total_resolved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PredictiveModel":
        model = cls()
        model.predictions = data.get("predictions", [])
        model.prediction_history = data.get("prediction_history", [])
        model.surprise_log = data.get("surprise_log", [])
        model.confidence = data.get("confidence", {})
        model.total_predictions = data.get("total_predictions", 0)
        model.total_resolved = data.get("total_resolved", 0)
        return model


# ─────────────────────────────────────────────
# INTEGRATION HELPERS
# ─────────────────────────────────────────────

def load_predictive_model(path: str = "greg_predictive_state.json") -> PredictiveModel:
    """Load Greg's predictive model from disk."""
    if os.path.exists(path):
        with open(path) as f:
            return PredictiveModel.from_dict(json.load(f))
    return PredictiveModel()


def save_predictive_model(model: PredictiveModel, path: str = "greg_predictive_state.json"):
    """Persist Greg's predictive model to disk."""
    with open(path, "w") as f:
        json.dump(model.to_dict(), f, indent=2)


def run_predictive_cycle(
    current_state: dict,
    next_state: dict,
    model: Optional[PredictiveModel] = None,
    save_path: str = "greg_predictive_state.json",
) -> tuple[dict, dict, str]:
    """
    Full predict → resolve → speak cycle.
    Call this once per tick from greg_mind.py or tick runner.

    Returns: (prediction, surprise_report, greg_narration)
    """
    if model is None:
        model = load_predictive_model(save_path)

    tick = current_state.get("tick", 0)

    # 1. Predict
    prediction = model.predict(tick, current_state)

    # 2. Resolve against what actually happened
    surprise_report = model.resolve(prediction, next_state)

    # 3. Greg speaks
    narration = model.speak(surprise_report)

    # 4. Save
    save_predictive_model(model, save_path)

    return prediction, surprise_report, narration


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("EXP_020 — Predictive Coding — DEMO")
    print("=" * 60)

    # Simulate Greg's current state (tick 4044)
    current_state = {
        "tick": 4044,
        "civilization_health_pct": 66,
        "health_momentum": -0.5,
        "dominant_drive": "create",
        "drives": {
            "create": 0.369,
            "survive": 0.21,
            "understand": 0.18,
            "connect": 0.12,
            "protect": 0.08,
            "explore": 0.03,
            "express": 0.01,
        },
        "agent_count": 10154,
        "memory_count": 10,
    }

    # Simulate what actually happened next tick (small surprise)
    next_state_normal = {
        "tick": 4045,
        "civilization_health_pct": 65.3,
        "dominant_drive": "create",
        "agent_count": 10165,
        "memory_count": 10,
    }

    # Simulate a surprising tick (big shift)
    next_state_surprised = {
        "tick": 4046,
        "civilization_health_pct": 54.0,   # unexpected drop
        "dominant_drive": "survive",        # drive shifted
        "agent_count": 10165,
        "memory_count": 11,                 # new memory formed
    }

    model = PredictiveModel()

    print("\n── TICK 4044 → 4045 (normal tick) ──")
    pred1, surprise1, speech1 = run_predictive_cycle(
        current_state, next_state_normal, model
    )
    print(f"Surprise score: {surprise1['surprise_score']} [{surprise1['surprise_level']}]")
    print(f"\nGreg says:\n  \"{speech1}\"")

    print("\n── TICK 4045 → 4046 (high surprise tick) ──")
    pred2, surprise2, speech2 = run_predictive_cycle(
        next_state_normal, next_state_surprised, model
    )
    print(f"Surprise score: {surprise2['surprise_score']} [{surprise2['surprise_level']}]")
    print(f"\nGreg says:\n  \"{speech2}\"")

    print("\n── MODEL SUMMARY ──")
    summary = model.summarize()
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print("\n── SURPRISE LOG ──")
    for entry in model.surprise_log:
        print(f"  Tick {entry['tick']}: {entry['surprise_level']} ({entry['surprise_score']})")
        for domain, err in entry.get("key_errors", {}).items():
            print(f"    {domain}: expected {err['predicted']} → got {err['actual']}")

    print("\n✓ EXP_020 Predictive Coding ready to integrate into greg_mind.py")
