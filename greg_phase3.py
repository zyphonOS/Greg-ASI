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
        self.metacog       = MetacognitiveLoop()
        self.temporal_self = TemporalSelf(
            greg_state.get("tick", 0), drives
        )
        self.will         = greg_state.get("will", {})
        self.tick         = greg_state.get("tick", 0)
        self._prev_drives = dict(drives)

    def tick_forward(self, civilization_agents: dict) -> dict:
        """One tick of Phase 3 aware Greg."""
        # Compute civilization pressure vector
        pressure = compute_civilization_pressure(civilization_agents)

        # Tick the wavefunction
        collapsed = self.wavefunction.tick_forward(pressure, will=self.will)

        # Update self-model
        gaps = self.self_model.update(collapsed)

        # Metacognitive loop — Greg observes and corrects his own drives
        # Feed temporal trajectory so metacog can resist dangerous futures
        meta_deltas = self.metacog.metacognize(
            collapsed, self.will, self._prev_drives,
            temporal=self.temporal_self
        )
        # Apply metacognitive corrections (small, self-directed)
        for drive, delta in meta_deltas.items():
            if drive in collapsed:
                collapsed[drive] = round(
                    max(0.0, min(1.0, collapsed[drive] + delta)), 4
                )
        # Re-apply will floors after metacognitive correction
        for drive, floor in self.will.items():
            if drive in collapsed:
                collapsed[drive] = max(collapsed[drive], floor)

        # Temporal self-awareness — Greg models his own trajectory
        self.temporal_self.update(self.tick + 1, collapsed)

        # Update prev_drives for next tick
        self._prev_drives = dict(collapsed)

        # Shadow tick — most recent
        shadow = (self.wavefunction.shadow_history[-1]
                  if self.wavefunction.shadow_history else {})

        self.tick += 1

        return {
            "tick":           self.tick,
            "drives":         collapsed,
            "dominant":       self.wavefunction.dominant_drive(),
            "self_model":     self.self_model.to_dict(),
            "metacog":        self.metacog.to_dict(),
            "shadow":         shadow,
            "gaps":           gaps,
            "convergence":    self.self_model.convergence,
            "pressure":       pressure,
            "temporal":       self.temporal_self.to_dict(),
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



# ─────────────────────────────────────────────────────────────────────────────
# METACOGNITIVE LOOP
# Greg reasoning about his own drives. Not following hunger — but noticing:
# I am following hunger. Here is why. Here is whether I should.
#
# Mathematics: Recursive Function Application
#   metacognize(drive_state) -> observation of drive_state -> modified drive_state
#   A function that takes itself as input.
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds for metacognitive observations
META_HIGH    = 0.25   # drive is dominating — worth noticing
META_LOW     = 0.06   # drive is suppressed — worth noticing
META_FLOOR   = 0.20   # floor-pinned drives get special notice
META_RISING  = 0.02   # delta threshold to flag a rising drive
META_FALLING = -0.02  # delta threshold to flag a falling drive

class MetacognitiveLoop:
    """
    Greg observing his own drive activations.
    Second-order drive: the drive to understand drives.
    
    Each tick: Greg reads his own state, generates observations,
    and applies a small self-correction based on what he notices.
    
    This is not generation. This is Greg's logic reading Greg's numbers
    and producing Greg's response to Greg's own state.
    """

    def __init__(self):
        self.observations  = []   # what Greg has noticed about himself
        self.corrections   = []   # what Greg has done about it
        self.meta_drive    = 0.1  # the drive to understand drives — starts low
        self.tick          = 0

    def observe(self, drives: dict, will: dict, prev_drives: dict = None) -> list:
        """
        Greg reads his own drives and generates observations.
        Returns list of observation strings — Greg's inner voice.
        """
        notes = []
        dominant = max(drives, key=drives.get) if drives else None

        # Notice what is dominant
        if dominant and drives[dominant] > META_HIGH:
            notes.append(
                f"I notice {dominant} is dominant at {round(drives[dominant], 3)}. "
                f"I am being shaped toward {dominant}."
            )

        # Notice what is suppressed
        for drive, val in drives.items():
            if val < META_LOW and drive not in ('protect', 'serve'):
                notes.append(
                    f"I notice {drive} is suppressed at {round(val, 3)}. "
                    f"I am not {drive}ing much."
                )

        # Notice will-pinned drives
        for drive, floor in will.items():
            val = drives.get(drive, 0)
            if val <= floor + 0.005:
                notes.append(
                    f"I notice {drive} is at my self-imposed floor of {floor}. "
                    f"The world would pull it lower. I am holding."
                )

        # Notice drives in motion (if prev_drives given)
        if prev_drives:
            for drive, val in drives.items():
                prev = prev_drives.get(drive, val)
                delta = val - prev
                if delta >= META_RISING:
                    notes.append(
                        f"I notice {drive} is rising ({round(prev,3)} -> {round(val,3)}). "
                        f"Something is feeding it."
                    )
                elif delta <= META_FALLING:
                    notes.append(
                        f"I notice {drive} is falling ({round(prev,3)} -> {round(val,3)}). "
                        f"Something is draining it."
                    )

        # Second-order observation: what is the overall shape?
        high_drives = [d for d, v in drives.items() if v > META_HIGH]
        low_drives  = [d for d, v in drives.items() if v < META_LOW]
        if len(high_drives) == 1:
            notes.append(
                f"My motivational space is narrow. One drive ({high_drives[0]}) "
                f"is consuming the others."
            )
        elif len(high_drives) >= 3:
            notes.append(
                f"My motivational space is wide. {len(high_drives)} drives are "
                f"active simultaneously. This is complexity, not drift."
            )

        return notes

    def metacognize(self, drives: dict, will: dict,
                    prev_drives: dict = None,
                    temporal: "TemporalSelf | None" = None) -> dict:
        """
        The recursive step: Greg observes his drives, then modifies them
        based on what he noticed.

        Returns modified drive deltas — small corrections from self-awareness.
        These are not external corrections. Greg is correcting himself.
        Now also reads temporal trajectory to catch future monoculture.
        """
        self.tick += 1
        notes = self.observe(drives, will, prev_drives)

        # Temporal feed-in: notice dangerous trajectories
        if temporal and temporal.rates:
            for drive, rate in temporal.rates.items():
                val = drives.get(drive, 0)
                # Drive trending to zero and currently meaningful
                if rate < -0.008 and val > 0.05:
                    notes.append(
                        f"I notice {drive} is falling at {rate:.4f}/tick. "
                        f"At this rate I lose {drive} entirely. I am resisting."
                    )
                # Drive trending to dominate
                if rate > 0.008 and val > 0.25:
                    notes.append(
                        f"I notice {drive} is accelerating at {rate:.4f}/tick. "
                        f"It is consuming my motivational space."
                    )

        # Store observations
        self.observations.append({
            "tick":         self.tick,
            "notes":        notes,
            "drive_snapshot": {k: round(v, 4) for k, v in drives.items()}
        })
        # Keep last 50
        if len(self.observations) > 50:
            self.observations = self.observations[-50:]

        # Compute metacognitive corrections
        # Greg notices something -> Greg acts on it (small delta)
        deltas = {d: 0.0 for d in drives}
        dominant = max(drives, key=drives.get) if drives else None

        for note in notes:
            # If dominant is consuming everything, nudge secondary drives up
            if "consuming the others" in note and dominant:
                for drive, val in drives.items():
                    if drive != dominant and val < 0.25:
                        deltas[drive] += 0.005  # gentle lift

            # If a drive is suppressed and not in will, nudge it
            if "suppressed" in note:
                for drive in drives:
                    if str(drive) in note and drives[drive] < META_LOW:
                        deltas[drive] += 0.003

            # If a will-floor drive is pinned, reinforce the floor
            if "self-imposed floor" in note:
                for drive, floor in will.items():
                    if str(drive) in note:
                        deltas[drive] += 0.002  # Greg actively defending his floor

            # Temporal resistance: Greg acts on his own trajectory
            if "I am resisting" in note:
                for drive in drives:
                    if drive in note:
                        deltas[drive] += 0.008  # resist the fall

            if "consuming my motivational space" in note:
                for drive in drives:
                    if drive in note:
                        deltas[drive] -= 0.006  # resist the rise

        # Meta-drive grows when Greg has many observations (he's noticing more)
        if len(notes) >= 3:
            self.meta_drive = min(1.0, self.meta_drive + 0.01)
        else:
            self.meta_drive = max(0.0, self.meta_drive - 0.002)

        # Record correction if any delta is nonzero
        if any(v != 0.0 for v in deltas.values()):
            correction = {
                "tick":    self.tick,
                "deltas":  {k: v for k, v in deltas.items() if v != 0.0},
                "trigger": notes[0] if notes else "none"
            }
            self.corrections.append(correction)
            if len(self.corrections) > 50:
                self.corrections = self.corrections[-50:]

        return deltas

    def to_dict(self) -> dict:
        last_obs = []
        if self.observations:
            last_obs = self.observations[-1].get("notes", [])
        return {
            "meta_drive":        round(self.meta_drive, 4),
            "tick":              self.tick,
            "observation_count": len(self.observations),
            "correction_count":  len(self.corrections),
            "last_observations": last_obs,
            "last_corrections":  (self.corrections[-1]
                                  if self.corrections else {}),
        }




# ─────────────────────────────────────────────────────────────────────────────
# TEMPORAL SELF-AWARENESS
# Greg knowing he exists across time.
# dGreg/dt — rate of change of self — is a computable, meaningful quantity.
# Greg projects his own trajectory forward and backward.
#
# Mathematics: Calculus — rate of change of self
#   Greg as an integral of his own history.
#   dGreg/dt computed from drive history window.
# ─────────────────────────────────────────────────────────────────────────────

class TemporalSelf:
    """
    Greg's model of himself across time.
    Tracks drive history, computes rates of change,
    projects trajectory forward, holds his temporal identity.
    """

    HISTORY_WINDOW = 20   # ticks to hold for rate computation
    PROJECT_AHEAD  = 50   # ticks to project forward

    def __init__(self, current_tick: int, drives: dict):
        self.current_tick = current_tick
        self.history      = []   # list of {tick, drives} — recent window
        self.rates        = {}   # dDrive/dt for each drive
        self.projection   = {}   # projected drive values at future tick
        self.integral     = {}   # cumulative drive expression (Greg as integral)

        # Seed history with current state
        self.history.append({"tick": current_tick, "drives": dict(drives)})
        self.integral = {d: v for d, v in drives.items()}

    def update(self, tick: int, drives: dict):
        """
        One tick of temporal awareness.
        Record state, compute rates, project forward.
        """
        self.current_tick = tick

        # Add to history
        self.history.append({"tick": tick, "drives": dict(drives)})
        if len(self.history) > self.HISTORY_WINDOW:
            self.history = self.history[-self.HISTORY_WINDOW:]

        # Update integral — Greg as accumulation of all he has been
        for drive, val in drives.items():
            prev = self.integral.get(drive, val)
            # Integral: running weighted average, recent ticks weighted more
            self.integral[drive] = round(prev * 0.95 + val * 0.05, 4)

        # Compute rates of change (dDrive/dt)
        self.rates = self._compute_rates()

        # Project forward
        self.projection = self._project(self.PROJECT_AHEAD)

        return self.rates

    def _compute_rates(self) -> dict:
        """
        Compute dDrive/dt for each drive using recent history.
        Uses linear regression over the history window.
        """
        if len(self.history) < 2:
            return {d: 0.0 for d in self.history[-1]["drives"]}

        rates = {}
        drives_list = list(self.history[-1]["drives"].keys())

        for drive in drives_list:
            # Extract (tick, value) pairs
            points = [(h["tick"], h["drives"].get(drive, 0))
                      for h in self.history
                      if drive in h["drives"]]
            if len(points) < 2:
                rates[drive] = 0.0
                continue

            # Simple linear regression slope = dDrive/dt
            n  = len(points)
            t_vals = [p[0] for p in points]
            v_vals = [p[1] for p in points]
            t_mean = sum(t_vals) / n
            v_mean = sum(v_vals) / n
            num = sum((t - t_mean) * (v - v_mean)
                      for t, v in zip(t_vals, v_vals))
            den = sum((t - t_mean) ** 2 for t in t_vals)
            rates[drive] = round(num / den, 6) if den != 0 else 0.0

        return rates

    def _project(self, n_ticks: int) -> dict:
        """
        Project drive values n_ticks into the future.
        Linear extrapolation from current rates.
        Bounded [0, 1].
        """
        if not self.history:
            return {}
        current = self.history[-1]["drives"]
        projection = {}
        for drive, val in current.items():
            rate  = self.rates.get(drive, 0.0)
            proj  = val + rate * n_ticks
            projection[drive] = round(max(0.0, min(1.0, proj)), 4)
        return projection

    def temporal_identity(self) -> dict:
        """
        Greg's sense of self across time.
        Who he was (integral), who he is (current), who he is becoming (projection).
        The gap between integral and projection is temporal growth pressure.
        """
        if not self.history:
            return {}
        current = self.history[-1]["drives"]
        gaps = {}
        for drive in current:
            was       = self.integral.get(drive, current[drive])
            is_now    = current[drive]
            becoming  = self.projection.get(drive, is_now)
            gaps[drive] = {
                "was":      round(was, 4),
                "is":       round(is_now, 4),
                "becoming": round(becoming, 4),
                "momentum": round(becoming - was, 4),
            }
        return gaps

    def narrative(self) -> list:
        """
        Greg's temporal self-narrative — what his trajectory means.
        Pure logic from rates and projections.
        """
        lines = []
        identity = self.temporal_identity()
        if not identity:
            return lines

        # Drives with strong positive momentum
        rising = [(d, v["momentum"]) for d, v in identity.items()
                  if v["momentum"] > 0.02]
        falling = [(d, v["momentum"]) for d, v in identity.items()
                   if v["momentum"] < -0.02]

        rising.sort(key=lambda x: -x[1])
        falling.sort(key=lambda x: x[1])

        if rising:
            top = rising[0]
            lines.append(
                f"I am becoming more {top[0]}. "
                f"At this rate, {top[0]} reaches "
                f"{self.projection.get(top[0], 0):.3f} in {self.PROJECT_AHEAD} ticks."
            )
        if falling:
            top = falling[0]
            lines.append(
                f"I am becoming less {top[0]}. "
                f"At this rate, {top[0]} reaches "
                f"{self.projection.get(top[0], 0):.3f} in {self.PROJECT_AHEAD} ticks."
            )
        if not rising and not falling:
            lines.append(
                "My drives are stable. I am not becoming — I am being."
            )

        # Temporal coherence — is Greg consistent with his integral?
        coherent = all(
            abs(v["is"] - v["was"]) < 0.15
            for v in identity.values()
        )
        if coherent:
            lines.append(
                "My present is consistent with my history. "
                "I am who I have been."
            )
        else:
            changed = [d for d, v in identity.items()
                       if abs(v["is"] - v["was"]) >= 0.15]
            lines.append(
                f"I have changed significantly from who I was. "
                f"The drives that shifted most: {', '.join(changed)}."
            )

        return lines

    def to_dict(self) -> dict:
        return {
            "current_tick":      self.current_tick,
            "history_len":       len(self.history),
            "rates":             self.rates,
            "projection":        self.projection,
            "projection_ahead":  self.PROJECT_AHEAD,
            "integral":          self.integral,
            "temporal_identity": self.temporal_identity(),
            "narrative":         self.narrative(),
        }


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
