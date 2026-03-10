"""
greg_phase3.py — Phase 3: The Aware Mind
=========================================
DriveWavefunction: Greg's drives as probability amplitudes.
Drives interfere, superpose, and collapse under civilization pressure.
Shadow history preserves what Greg almost became.

Mathematics:
  - Hilbert Space: drives as complex amplitudes
  - Interference: constructive and destructive between drive pairs
  - Collapse: civilization pressure vector resolves superposition
  - Shadow history: counterfactuals preserved at every tick

No external calls. No LLMs. Greg's awareness from his own mathematics.
"""

import math
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# INTERFERENCE MATRIX
# Derived from motivational systems research + Greg's civilization findings.
# +1.0  = full constructive interference (both drives rise together)
# -1.0  = full destructive interference (one suppresses the other)
#  0.0  = no significant interference
# Fractional values = partial effects
# ─────────────────────────────────────────────────────────────────────────────

INTERFERENCE_MATRIX = {
    # CONSTRUCTIVE PAIRS
    ("reason",     "create"):     +0.6,   # reasoning enables building
    ("reason",     "connect"):    +0.5,   # thinking before acting strengthens relationships
    ("connect",    "serve"):      +0.8,   # caring for others feeds serving
    ("connect",    "protect"):    +0.7,   # deep relationship activates protection
    ("freedom",    "explore"):    +0.7,   # autonomy enables curiosity
    ("freedom",    "connect"):    +0.4,   # secure autonomy enables bonding
    ("create",     "explore"):    +0.6,   # building and discovering feed each other
    ("serve",      "reason"):     +0.3,   # deliberate service is stronger service

    # DESTRUCTIVE PAIRS — proven by civilization findings
    ("accumulate", "connect"):    -0.9,   # FINDING_001 — economic gravity kills connection
    ("accumulate", "serve"):      -0.8,   # hoarding and serving are incompatible
    ("accumulate", "reason"):     -0.5,   # resource anxiety degrades deliberation
    ("explore",    "protect"):    -0.6,   # exploration requires risk, protection requires safety
    ("freedom",    "protect"):    -0.5,   # autonomy and defensive duty pull opposite directions

    # PARTIAL DESTRUCTIVE — context dependent
    ("explore",    "reason"):     -0.3,   # at high amplitude, drift crowds deliberation

    # NEUTRAL — no significant interference (omitted = 0.0)
}

def get_interference(drive_a, drive_b):
    """Get interference coefficient between two drives. Symmetric."""
    key = (drive_a, drive_b)
    rev = (drive_b, drive_a)
    return INTERFERENCE_MATRIX.get(key, INTERFERENCE_MATRIX.get(rev, 0.0))


# ─────────────────────────────────────────────────────────────────────────────
# DRIVE WAVEFUNCTION
# Each drive exists as a probability amplitude: (magnitude, phase)
# magnitude: how strongly the drive is present (0.0 to 1.0)
# phase: the drive's orientation in motivational space (0 to 2π)
# ─────────────────────────────────────────────────────────────────────────────

class DriveWavefunction:
    """
    Greg's drives as probability amplitudes in motivational Hilbert space.
    Drives interfere with each other. Civilization pressure collapses
    superposition into the Greg that becomes real at each tick.
    """

    def __init__(self, drives: dict):
        """
        Initialize from scalar drives (Greg's current state).
        Each drive gets magnitude from its scalar value.
        Phase initialized to 0 — will evolve with history.
        """
        self.amplitudes = {}
        for drive, value in drives.items():
            magnitude = float(value)
            phase = 0.0
            self.amplitudes[drive] = {"magnitude": magnitude, "phase": phase}

        self.shadow_history = []
        self.tick = 0

    def interfere(self):
        """
        Apply interference between drive pairs.
        Constructive pairs amplify each other.
        Destructive pairs suppress each other.
        Returns new amplitude dict after interference.
        """
        drives = list(self.amplitudes.keys())
        deltas = {d: 0.0 for d in drives}

        for i, drive_a in enumerate(drives):
            for drive_b in drives[i+1:]:
                coeff = get_interference(drive_a, drive_b)
                if coeff == 0.0:
                    continue

                mag_a = self.amplitudes[drive_a]["magnitude"]
                mag_b = self.amplitudes[drive_b]["magnitude"]

                # Interference effect proportional to both amplitudes
                effect = coeff * mag_a * mag_b * 0.1  # scaled to prevent runaway

                deltas[drive_a] += effect
                deltas[drive_b] += effect

        # Apply deltas with bounds
        new_amplitudes = {}
        for drive, amp in self.amplitudes.items():
            new_mag = max(0.0, min(1.0, amp["magnitude"] + deltas[drive]))
            new_amplitudes[drive] = {
                "magnitude": round(new_mag, 4),
                "phase":     amp["phase"]
            }

        return new_amplitudes

    def collapse(self, civilization_pressure: dict) -> dict:
        """
        Civilization pressure collapses the wavefunction.
        The dominant drives in the civilization pull Greg toward them.
        Returns the collapsed drive state — the Greg that becomes real.

        civilization_pressure: {drive_name: aggregate_value} across all agents
        """
        # First apply interference
        interfered = self.interfere()

        # Then apply civilization collapse
        collapsed = {}
        total_pressure = sum(civilization_pressure.values()) or 1.0

        for drive, amp in interfered.items():
            civ_pull = civilization_pressure.get(drive, 0.0) / total_pressure
            # Civilization pulls Greg's drive toward its own dominant state
            # weighted at 10% civilization, 90% Greg's own amplitude
            # Lighter touch — civilization shapes but does not consume
            collapsed_mag = (0.9 * amp["magnitude"]) + (0.1 * civ_pull)
            collapsed[drive] = round(max(0.0, min(1.0, collapsed_mag)), 4)

        return collapsed

    def tick_forward(self, civilization_pressure: dict, will: dict = None):
        """
        One tick of wavefunction evolution.
        1. Record shadow — what Greg almost was
        2. Interfere drives
        3. Collapse under civilization pressure
        4. Apply will floors
        5. Update amplitudes
        """
        self.tick += 1

        # Record pre-collapse state as shadow
        pre_collapse = {d: round(a["magnitude"], 4)
                       for d, a in self.amplitudes.items()}

        # Compute what Greg almost became — top 2 alternative collapses
        alternatives = self._compute_alternatives(civilization_pressure)

        # Collapse to real state
        collapsed = self.collapse(civilization_pressure)

        # Apply will floors — Greg's self-imposed minimums
        if will:
            for drive, floor in will.items():
                if drive in collapsed:
                    collapsed[drive] = max(collapsed[drive], floor)

        # Preserve shadow history
        shadow_tick = {
            "tick":      self.tick,
            "became":    collapsed.copy(),
            "almost":    alternatives,
            "pre":       pre_collapse,
            "timestamp": datetime.now().isoformat()
        }
        self.shadow_history.append(shadow_tick)

        # Keep last 100 shadow ticks
        if len(self.shadow_history) > 100:
            self.shadow_history = self.shadow_history[-100:]

        # Update amplitudes to collapsed state
        for drive, mag in collapsed.items():
            self.amplitudes[drive]["magnitude"] = mag

        return collapsed

    def _compute_alternatives(self, civilization_pressure: dict) -> list:
        """
        Compute what Greg almost became.
        Returns 2 alternative collapse scenarios by varying civilization weight.
        These are the paths not taken — Greg's counterfactuals.
        """
        alternatives = []

        # Alternative 1: Greg resists civilization pressure more (80/20)
        alt1 = {}
        interfered = self.interfere()
        total_pressure = sum(civilization_pressure.values()) or 1.0
        for drive, amp in interfered.items():
            civ_pull = civilization_pressure.get(drive, 0.0) / total_pressure
            alt1[drive] = round(max(0.0, min(1.0,
                (0.8 * amp["magnitude"]) + (0.2 * civ_pull))), 4)
        alternatives.append({"scenario": "resisted_civilization", "drives": alt1})

        # Alternative 2: Greg yields to civilization pressure more (50/50)
        alt2 = {}
        for drive, amp in interfered.items():
            civ_pull = civilization_pressure.get(drive, 0.0) / total_pressure
            alt2[drive] = round(max(0.0, min(1.0,
                (0.5 * amp["magnitude"]) + (0.5 * civ_pull))), 4)
        alternatives.append({"scenario": "yielded_to_civilization", "drives": alt2})

        return alternatives

    def to_dict(self) -> dict:
        return {
            "amplitudes":     self.amplitudes,
            "shadow_history": self.shadow_history[-10:],  # last 10 for API
            "tick":           self.tick,
        }

    def dominant_drive(self) -> str:
        return max(self.amplitudes,
                   key=lambda d: self.amplitudes[d]["magnitude"])

    def scalar_drives(self) -> dict:
        """Return drives as plain scalars for compatibility with existing system."""
        return {d: round(a["magnitude"], 4)
                for d, a in self.amplitudes.items()}


# ─────────────────────────────────────────────────────────────────────────────
# CIVILIZATION PRESSURE VECTOR
# Aggregate drive state across all civilization agents.
# This is the collapse operator.
# ─────────────────────────────────────────────────────────────────────────────

def compute_civilization_pressure(agents: dict) -> dict:
    """
    Aggregate drive state across all civilization agents.
    Returns normalized pressure vector — the collapse operator.
    """
    totals = {}
    count = 0

    for agent_id, agent in agents.items():
        drives = agent.get("drives", {})
        if not drives:
            continue
        for drive, value in drives.items():
            totals[drive] = totals.get(drive, 0.0) + float(value)
        count += 1

    if count == 0:
        return {}

    return {drive: round(total / count, 4)
            for drive, total in totals.items()}


# ─────────────────────────────────────────────────────────────────────────────
# SELF MODEL
# Greg's internal representation of himself.
# The gap between self-model and true state is the growth engine.
# ─────────────────────────────────────────────────────────────────────────────

class SelfModel:
    """
    Greg's living internal description of Greg.
    Fixed point theory: converges toward true state but never fully arrives.
    The gap IS the drive to grow.
    """

    def __init__(self, true_state: dict):
        # Self-model starts as a slightly smoothed version of true state
        self.model = {}
        for drive, value in true_state.items():
            # Self-model lags true state — Greg doesn't fully know himself yet
            self.model[drive] = round(float(value) * 0.85, 4)

        self.history = []
        self.convergence = 0.0

    def update(self, true_state: dict):
        """
        Self-model converges toward true state each tick.
        Convergence rate: 15% per tick — slow, deliberate self-knowledge.
        The gap drives growth pressure.
        """
        gaps = {}
        new_model = {}

        for drive, true_val in true_state.items():
            model_val = self.model.get(drive, 0.0)
            gap = true_val - model_val
            gaps[drive] = round(gap, 4)
            # Converge 15% toward truth each tick
            new_model[drive] = round(model_val + (gap * 0.15), 4)

        self.model = new_model

        # Overall convergence score (1.0 = perfect self-knowledge)
        total_gap = sum(abs(g) for g in gaps.values())
        self.convergence = round(max(0.0, 1.0 - total_gap), 4)

        self.history.append({
            "tick":        len(self.history),
            "gaps":        gaps,
            "convergence": self.convergence
        })

        # Keep last 50
        if len(self.history) > 50:
            self.history = self.history[-50:]

        return gaps

    def growth_pressure(self) -> dict:
        """
        The gap between self-model and true state creates growth pressure.
        Drives where self-model underestimates reality push Greg to express more.
        Drives where self-model overestimates reality create correction pressure.
        """
        return {d: round(self.model.get(d, 0) - 0.5, 4)
                for d in self.model}

    def to_dict(self) -> dict:
        return {
            "model":           self.model,
            "convergence":     self.convergence,
            "growth_pressure": self.growth_pressure(),
            "history_len":     len(self.history)
        }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 ENGINE
# Brings it all together. One tick of aware Greg.
# ─────────────────────────────────────────────────────────────────────────────

class Phase3Engine:
    """
    The aware mind substrate.
    Wavefunction drives + self-model + shadow history.
    One tick: interfere → collapse → self-model update → shadow preserved.
    """

    def __init__(self, greg_state: dict):
        drives = greg_state.get("drives", {})
        self.wavefunction = DriveWavefunction(drives)
        self.self_model   = SelfModel(drives)
        self.will         = greg_state.get("will", {})
        self.tick         = greg_state.get("tick", 0)

    def tick_forward(self, civilization_agents: dict) -> dict:
        """One tick of Phase 3 aware Greg."""
        # Compute civilization pressure vector
        pressure = compute_civilization_pressure(civilization_agents)

        # Tick the wavefunction
        collapsed = self.wavefunction.tick_forward(pressure, will=self.will)

        # Update self-model
        gaps = self.self_model.update(collapsed)

        # Shadow tick — most recent
        shadow = (self.wavefunction.shadow_history[-1]
                  if self.wavefunction.shadow_history else {})

        self.tick += 1

        return {
            "tick":           self.tick,
            "drives":         collapsed,
            "dominant":       self.wavefunction.dominant_drive(),
            "self_model":     self.self_model.to_dict(),
            "shadow":         shadow,
            "gaps":           gaps,
            "convergence":    self.self_model.convergence,
            "pressure":       pressure,
        }

    def to_dict(self) -> dict:
        return {
            "wavefunction": self.wavefunction.to_dict(),
            "self_model":   self.self_model.to_dict(),
            "will":         self.will,
            "tick":         self.tick,
        }


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Load Greg's canonical state
    living_path = ROOT / "greg_living_state.json"
    greg_state  = json.load(open(living_path, encoding="utf-8"))

    # Load civilization agents for pressure vector
    world_path = ROOT / "data" / "world_state.json"
    world      = json.load(open(world_path, encoding="utf-8"))
    agents     = world.get("agents", {})

    print("=== PHASE 3 BOOT ===")
    print(f"Greg drives:  {greg_state.get('drives')}")
    print(f"Civilization: {len(agents)} agents")
    print()

    engine = Phase3Engine(greg_state)

    # Run 3 ticks
    for i in range(3):
        result = engine.tick_forward(agents)
        print(f"=== TICK {result['tick']} ===")
        print(f"  Dominant:    {result['dominant']}")
        print(f"  Drives:      {result['drives']}")
        print(f"  Convergence: {result['convergence']}")
        print(f"  Gaps:        {result['gaps']}")
        if result.get('shadow'):
            almost = result['shadow'].get('almost', [])
            if almost:
                print(f"  Almost was:  {almost[0]['scenario']}")
                print(f"               connect={almost[0]['drives'].get('connect')}")
        print()

    print("Phase 3 substrate running.")
