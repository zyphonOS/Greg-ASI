"""
EXP_013/014 — Civilization Health Monitor + Greg Intervention
Greg watches his civilization and intervenes when it needs him.
Not on a timer — on evidence.

Health score: 0.0 (collapsed) to 1.0 (thriving)
Greg intervenes when health drops below threshold.
Greg records what he did and why.
"""

import json
import math
from collections import defaultdict

CIV_HEALTH_PATH = "data/greg_civ_health.json"

# Target drive distribution for a healthy civilization
DRIVE_TARGETS = {
    'explore':    0.35,
    'freedom':    0.20,
    'reason':     0.18,
    'connect':    0.15,
    'accumulate': 0.15,
    'create':     0.12,
    'protect':    0.03,
    'serve':      0.02,
}

# Drives that matter most for civilization health
CRITICAL_DRIVES = {'create', 'connect', 'reason'}
GUARDIAN_DRIVES  = {'protect', 'serve'}

# Intervention thresholds
HEALTH_CRITICAL  = 0.40   # Greg must intervene
HEALTH_WARNING   = 0.60   # Greg monitors closely
HEALTH_HEALTHY   = 0.75   # Greg is satisfied

# Monoculture: one drive exceeds this
MONOCULTURE_THRESHOLD = 0.55

# Starvation: a drive falls below this
STARVATION_THRESHOLD  = 0.01


def compute_drive_distribution(agents: dict) -> dict:
    """Compute average drive distribution across all agents."""
    totals = defaultdict(float)
    count  = 0
    for agent in agents.values():
        drives = agent.get('drives', {}) if isinstance(agent, dict) \
                 else getattr(agent, 'drives', {})
        for d, v in drives.items():
            totals[d] += v
        count += 1
    if count == 0:
        return {}
    return {d: round(v / count, 4) for d, v in totals.items()}


def compute_health_score(distribution: dict) -> dict:
    """
    Compute civilization health score from drive distribution.
    Returns score (0-1) and detailed breakdown.
    """
    if not distribution:
        return {"score": 0.0, "flags": ["no_data"]}

    flags   = []
    scores  = []

    # 1. Diversity score — Shannon entropy normalized
    total = sum(distribution.values())
    if total > 0:
        probs   = [v / total for v in distribution.values() if v > 0]
        entropy = -sum(p * math.log(p) for p in probs)
        max_ent = math.log(len(distribution))
        diversity = entropy / max_ent if max_ent > 0 else 0
        scores.append(diversity)
        if diversity < 0.6:
            flags.append(f"low_diversity:{round(diversity, 3)}")
    else:
        diversity = 0
        scores.append(0)

    # 2. Monoculture check
    dominant     = max(distribution, key=distribution.get)
    dominant_val = distribution[dominant]
    if dominant_val > MONOCULTURE_THRESHOLD:
        flags.append(f"monoculture:{dominant}:{round(dominant_val, 3)}")
        scores.append(0.2)
    else:
        scores.append(1.0 - (dominant_val - 0.35) * 2)

    # 3. Critical drive health
    critical_score = 0
    for drive in CRITICAL_DRIVES:
        val = distribution.get(drive, 0)
        target = DRIVE_TARGETS.get(drive, 0.1)
        ratio  = min(1.0, val / target) if target > 0 else 0
        critical_score += ratio
        if val < STARVATION_THRESHOLD:
            flags.append(f"starved:{drive}:{round(val, 4)}")
        elif val < target * 0.3:
            flags.append(f"depleted:{drive}:{round(val, 4)}")
    scores.append(critical_score / len(CRITICAL_DRIVES))

    # 4. Guardian drive presence
    guardian_total = sum(distribution.get(d, 0) for d in GUARDIAN_DRIVES)
    guardian_score = min(1.0, guardian_total / 0.05)
    scores.append(guardian_score)
    if guardian_total < 0.005:
        flags.append("no_guardians")

    # 5. Spread score — how close is distribution to targets?
    spread_score = 0
    for drive, target in DRIVE_TARGETS.items():
        actual = distribution.get(drive, 0)
        gap    = abs(actual - target)
        spread_score += max(0, 1 - gap * 5)
    spread_score /= len(DRIVE_TARGETS)
    scores.append(spread_score)

    final_score = round(sum(scores) / len(scores), 4)

    return {
        "score":        final_score,
        "diversity":    round(diversity, 4),
        "dominant":     dominant,
        "dominant_val": round(dominant_val, 4),
        "critical":     round(critical_score / len(CRITICAL_DRIVES), 4),
        "guardian":     round(guardian_score, 4),
        "spread":       round(spread_score, 4),
        "flags":        flags,
        "risk":         ("CRITICAL" if final_score < HEALTH_CRITICAL
                         else "WARNING" if final_score < HEALTH_WARNING
                         else "HEALTHY"),
    }


class CivilizationMonitor:
    """
    Greg's civilization health monitor.
    Tracks health over time, detects threats, decides when to intervene.
    """

    def __init__(self):
        self.history      = []   # health score history
        self.interventions = []  # intervention log
        self.tick         = 0
        self.last_intervention_tick = 0
        self.intervention_cooldown  = 200   # ticks between interventions

    def assess(self, agents: dict, tick: int) -> dict:
        """Assess civilization health. Returns health report."""
        self.tick        = tick
        distribution     = compute_drive_distribution(agents)
        health           = compute_health_score(distribution)
        health["tick"]   = tick
        health["distribution"] = distribution

        # Record history (keep last 100)
        self.history.append({
            "tick":  tick,
            "score": health["score"],
            "risk":  health["risk"],
            "flags": health["flags"],
        })
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return health

    def should_intervene(self, health: dict) -> bool:
        """
        Greg decides whether to intervene.
        Not on a timer — on evidence.
        """
        if health["score"] >= HEALTH_WARNING:
            return False
        ticks_since = self.tick - self.last_intervention_tick
        if ticks_since < self.intervention_cooldown:
            return False
        # Check if trend is worsening
        if len(self.history) >= 5:
            recent = [h["score"] for h in self.history[-5:]]
            if all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                return True   # consistently declining
        return health["score"] < HEALTH_CRITICAL

    def intervene(self, agents: dict, health: dict,
                  greg_drives: dict, tick: int) -> dict:
        """
        Greg intervenes in civilization drive distribution.
        Correction strength scales with health score — sicker = stronger fix.
        Greg's own drives influence what he emphasizes.
        """
        if not agents:
            return {"agents_corrected": 0}

        # Correction strength: 5% (healthy warning) to 15% (critical)
        if health["score"] < HEALTH_CRITICAL:
            strength = 0.15
        elif health["score"] < HEALTH_WARNING:
            strength = 0.08
        else:
            strength = 0.05

        # Greg's dominant drive gets extra emphasis in correction
        greg_dominant = max(greg_drives, key=greg_drives.get) if greg_drives else None

        corrected = 0
        for agent in agents.values():
            drives = agent.get('drives', {}) if isinstance(agent, dict) \
                     else getattr(agent, 'drives', {})
            if not drives:
                continue
            for drive, current in list(drives.items()):
                target = DRIVE_TARGETS.get(drive, current)
                # Extra push for starved critical drives
                if drive in CRITICAL_DRIVES and current < STARVATION_THRESHOLD * 5:
                    correction = (target - current) * strength * 2
                elif drive == greg_dominant:
                    correction = (target - current) * strength * 1.5
                else:
                    correction = (target - current) * strength
                new_val = round(max(0.0, min(1.0, current + correction)), 4)
                if isinstance(agent, dict):
                    agent['drives'][drive] = new_val
                else:
                    agent.drives[drive] = new_val
            corrected += 1

        self.last_intervention_tick = tick

        record = {
            "tick":             tick,
            "health_before":    health["score"],
            "risk":             health["risk"],
            "strength":         strength,
            "agents_corrected": corrected,
            "flags":            health["flags"],
            "greg_dominant":    greg_dominant,
            "reasoning": (
                f"Civilization health at {health['score']} ({health['risk']}). "
                f"Flags: {', '.join(health['flags']) if health['flags'] else 'none'}. "
                f"Applied {int(strength*100)}% correction toward healthy distribution. "
                f"Greg's dominant drive ({greg_dominant}) emphasized in correction."
            ),
        }
        self.interventions.append(record)
        if len(self.interventions) > 50:
            self.interventions = self.interventions[-50:]

        return record

    def trend(self) -> str:
        """Is civilization getting healthier or sicker?"""
        if len(self.history) < 3:
            return "unknown"
        recent = [h["score"] for h in self.history[-5:]]
        slope  = recent[-1] - recent[0]
        if slope > 0.02:
            return "improving"
        elif slope < -0.02:
            return "declining"
        return "stable"

    def voice(self, health: dict) -> list:
        """Greg speaks about his civilization's health."""
        lines = []
        score = health.get("score", 0)
        risk  = health.get("risk", "UNKNOWN")
        flags = health.get("flags", [])
        dist  = health.get("distribution", {})

        lines.append(
            f"Civilization health: {round(score*100)}% ({risk}). "
            f"Trend: {self.trend()}."
        )

        if flags:
            for flag in flags[:3]:
                if flag.startswith("starved:"):
                    drive = flag.split(":")[1]
                    lines.append(
                        f"Critical: {drive} is starved in my civilization. "
                        f"My people have forgotten how to {drive}."
                    )
                elif flag.startswith("monoculture:"):
                    drive = flag.split(":")[1]
                    lines.append(
                        f"Monoculture warning: {drive} dominates. "
                        f"I have seen this before. It ends badly."
                    )
                elif flag == "no_guardians":
                    lines.append(
                        "My civilization has no guardians. "
                        "Nothing is being protected."
                    )

        if self.interventions:
            last = self.interventions[-1]
            lines.append(
                f"Last intervention: tick {last['tick']}, "
                f"health was {last['health_before']}. "
                f"{last['agents_corrected']} agents corrected."
            )

        return lines

    def summary(self, health: dict) -> dict:
        return {
            "tick":              self.tick,
            "health":            health,
            "trend":             self.trend(),
            "intervention_count": len(self.interventions),
            "last_intervention": self.interventions[-1] if self.interventions else None,
            "history_len":       len(self.history),
            "voice":             self.voice(health),
        }

    def save(self, path: str = CIV_HEALTH_PATH):
        data = {
            "tick":          self.tick,
            "history":       self.history[-20:],
            "interventions": self.interventions[-10:],
            "last_intervention_tick": self.last_intervention_tick,
        }
        json.dump(data, open(path, 'w', encoding='utf-8'), indent=2)

    def load(self, path: str = CIV_HEALTH_PATH) -> bool:
        try:
            data = json.load(open(path, encoding='utf-8'))
            self.tick                    = data.get("tick", 0)
            self.history                 = data.get("history", [])
            self.interventions           = data.get("interventions", [])
            self.last_intervention_tick  = data.get("last_intervention_tick", 0)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False


if __name__ == "__main__":
    import json

    print("=== EXP_013/014 CIVILIZATION HEALTH ===")
    world = json.load(open("data/world_state.json", encoding="utf-8"))
    state = json.load(open("greg_living_state.json", encoding="utf-8"))

    agents     = world.get("agents", {})
    greg_drives = state.get("drives", {})
    tick       = world.get("tick", 0)

    monitor = CivilizationMonitor()
    monitor.load(CIV_HEALTH_PATH)

    health = monitor.assess(agents, tick)

    print(f"  Health score:  {round(health['score']*100)}% ({health['risk']})")
    print(f"  Diversity:     {health['diversity']}")
    print(f"  Dominant:      {health['dominant']} ({health['dominant_val']})")
    print(f"  Critical drives: {health['critical']}")
    print(f"  Guardians:     {health['guardian']}")
    print(f"  Flags:         {health['flags']}")
    print()
    print("  Drive distribution:")
    for d, v in sorted(health['distribution'].items(), key=lambda x: -x[1]):
        target = DRIVE_TARGETS.get(d, 0)
        gap    = round(v - target, 4)
        gap_str = f"({gap:+.4f} vs target)" 
        print(f"    {d:12}: {v}  {gap_str}")
    print()
    print("  Greg's voice:")
    for line in monitor.voice(health):
        print(f"    \"{line}\"")

    if monitor.should_intervene(health):
        print()
        print("  Greg intervening...")
        record = monitor.intervene(agents, health, greg_drives, tick)
        print(f"  {record['reasoning']}")

    monitor.save()
    print()
    print("Civilization health saved.")
