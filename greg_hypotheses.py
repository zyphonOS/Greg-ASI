"""
EXP_012 — Greg's Hypothesis Engine
Greg reasons about his own patterns and generates hypotheses.
Not generated text. Pure logic — Greg reads his own data,
finds correlations, and makes a claim with evidence.

A hypothesis has:
  - claim:    what Greg thinks is true
  - evidence: the data points that support it
  - confidence: how strongly the data supports it (0.0 to 1.0)
  - test:     how Greg would verify or falsify it
  - status:   forming / active / confirmed / falsified
"""

import json
import time
from collections import defaultdict

HYPOTHESES_PATH = "data/greg_hypotheses.json"

STATUS_FORMING   = "forming"
STATUS_ACTIVE    = "active"
STATUS_CONFIRMED = "confirmed"
STATUS_FALSIFIED = "falsified"


class Hypothesis:
    def __init__(self, hyp_id: str, claim: str, evidence: list,
                 confidence: float, test: str, tick: int,
                 category: str = "drive"):
        self.id         = hyp_id
        self.claim      = claim
        self.evidence   = evidence   # list of evidence strings
        self.confidence = round(confidence, 3)
        self.test       = test
        self.tick       = tick
        self.category   = category
        self.status     = STATUS_ACTIVE
        self.updated_at = tick
        self.confirmations = 0
        self.falsifications = 0

    def reinforce(self, amount: float = 0.05):
        self.confidence    = round(min(1.0, self.confidence + amount), 3)
        self.confirmations += 1
        if self.confidence >= 0.85:
            self.status = STATUS_CONFIRMED

    def challenge(self, amount: float = 0.10):
        self.confidence      = round(max(0.0, self.confidence - amount), 3)
        self.falsifications += 1
        if self.confidence <= 0.15:
            self.status = STATUS_FALSIFIED

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "claim":          self.claim,
            "evidence":       self.evidence,
            "confidence":     self.confidence,
            "test":           self.test,
            "tick":           self.tick,
            "category":       self.category,
            "status":         self.status,
            "updated_at":     self.updated_at,
            "confirmations":  self.confirmations,
            "falsifications": self.falsifications,
        }


class HypothesisEngine:
    """
    Greg's reasoning engine.
    Reads drives, temporal data, patterns, findings, goals
    and generates hypotheses about what is true about his world and himself.
    """

    MAX_HYPOTHESES = 20

    def __init__(self):
        self.hypotheses: list[Hypothesis] = []
        self.tick = 0

    # ── Hypothesis generation ────────────────────────────────────────────────

    def generate(self, state: dict) -> list[Hypothesis]:
        """
        Greg reads his full state and generates new hypotheses.
        Returns only hypotheses not already held.
        """
        drives   = state.get("drives", {})
        findings = state.get("findings", [])
        temporal = state.get("phase3_temporal", {})
        goals    = state.get("goals", {})
        metacog  = state.get("phase3_metacog", {})
        tick     = state.get("tick", 0)
        patterns = state.get("phase3_self_model", {})

        existing_claims = {h.claim for h in self.hypotheses}
        new_hyps = []

        # ── Category 1: Temporal hypotheses ──────────────────────────────
        identity = temporal.get("temporal_identity", {})
        rates    = temporal.get("rates", {})

        # Rising drives while others fall
        rising  = [(d, v) for d, v in rates.items() if v > 0.002]
        falling = [(d, v) for d, v in rates.items() if v < -0.003]

        if rising and falling:
            top_rising  = max(rising,  key=lambda x: x[1])
            top_falling = min(falling, key=lambda x: x[1])
            claim = (
                f"When {top_falling[0]} falls, {top_rising[0]} rises — "
                f"they may be competing for the same motivational space."
            )
            if claim not in existing_claims:
                evidence = [
                    f"{top_rising[0]} rate: {top_rising[1]:+.5f}/tick",
                    f"{top_falling[0]} rate: {top_falling[1]:+.5f}/tick",
                    f"Interference matrix suggests drives compete for amplitude.",
                ]
                confidence = min(0.85, 0.4 + abs(top_rising[1]) * 10
                                      + abs(top_falling[1]) * 10)
                test = (
                    f"If I deliberately suppress {top_rising[0]}, "
                    f"does {top_falling[0]} recover?"
                )
                new_hyps.append(Hypothesis(
                    f"hyp_competition_{top_falling[0]}_{top_rising[0]}_{tick}",
                    claim, evidence, confidence, test, tick, "temporal"
                ))

        # Drive heading to zero
        for drive, t in identity.items():
            if t.get("becoming", 1) < 0.05 and t.get("is", 1) > 0.10:
                claim = (
                    f"{drive} is trending toward zero. "
                    f"If unchecked, I will lose {drive} entirely."
                )
                if claim not in existing_claims:
                    evidence = [
                        f"Current: {t['is']}, projected: {t['becoming']} in 50 ticks",
                        f"Momentum: {t['momentum']:+.4f}",
                        f"Integral (who I have been): {t['was']}",
                    ]
                    confidence = min(0.9, 0.5 + abs(t["momentum"]) * 2)
                    test = (
                        f"Watch {drive} over next 50 ticks. "
                        f"Does goal pressure hold it above 0.05?"
                    )
                    new_hyps.append(Hypothesis(
                        f"hyp_loss_{drive}_{tick}",
                        claim, evidence, confidence, test, tick, "temporal"
                    ))

        # ── Category 2: Pattern hypotheses ─────────────────────────────
        # connect_drift is Greg's most reinforced pattern
        connect_drift_count = sum(
            1 for m in state.get("memory", [])
            if isinstance(m, dict) and
            m.get("detail", {}).get("notice") == "connect_drift"
        )
        if connect_drift_count >= 5:
            claim = (
                "connect_drift is my default failure mode. "
                "Under sustained pressure, I lose connection before anything else."
            )
            if claim not in existing_claims:
                evidence = [
                    f"connect_drift noticed {connect_drift_count} times in memory",
                    "pattern_connect_drift has highest weight in knowledge graph (5.45)",
                    "FINDING_001 recorded connect as first dominant drive",
                    f"Will floor set at 0.18 specifically to resist this pattern",
                ]
                new_hyps.append(Hypothesis(
                    f"hyp_connect_drift_pattern_{tick}",
                    claim, evidence, 0.82, 
                    "Track whether connect falls below floor more than any other will-drive.",
                    tick, "pattern"
                ))

        # ── Category 3: Goal hypotheses ──────────────────────────────
        active_goals = goals.get("active_goals", [])
        for goal in active_goals:
            drive    = goal.get("drive")
            progress = goal.get("progress", 0)
            current  = goal.get("current", 0)
            target   = goal.get("target", 0)

            # Goal making no progress despite pressure
            if progress < 0.05 and drive and rates.get(drive, 0) < -0.003:
                claim = (
                    f"Civilization pressure on {drive} exactly cancels "
                    f"my goal pressure. I am in equilibrium, not progress."
                )
                if claim not in existing_claims:
                    evidence = [
                        f"Goal progress: {int(progress*100)}% after multiple ticks",
                        f"Drive rate: {rates.get(drive, 0):+.5f}/tick",
                        f"Current value: {round(current, 3)} vs target: {target}",
                    ]
                    new_hyps.append(Hypothesis(
                        f"hyp_equilibrium_{drive}_{tick}",
                        claim, evidence, 0.65,
                        f"Increase goal pressure on {drive} and observe if progress breaks equilibrium.",
                        tick, "goal"
                    ))

        # ── Category 4: Civilization hypotheses ──────────────────────
        civ = state.get("civilization", {})
        civ_drives = civ.get("drive_distribution", {})
        if civ_drives:
            civ_dominant = max(civ_drives, key=civ_drives.get)
            greg_dominant = max(drives, key=drives.get) if drives else None
            if civ_dominant == greg_dominant:
                claim = (
                    f"Greg and civilization share the same dominant drive ({civ_dominant}). "
                    f"Greg may be a mirror of his civilization rather than its guide."
                )
                if claim not in existing_claims:
                    evidence = [
                        f"Greg dominant: {greg_dominant} ({round(drives.get(greg_dominant,0),3)})",
                        f"Civilization dominant: {civ_dominant} ({round(civ_drives.get(civ_dominant,0),3)})",
                    ]
                    new_hyps.append(Hypothesis(
                        f"hyp_mirror_{civ_dominant}_{tick}",
                        claim, evidence, 0.55,
                        f"Would Greg's {civ_dominant} fall if civilization's {civ_dominant} fell?",
                        tick, "civilization"
                    ))

        # ── Category 5: Meta hypothesis — about hypotheses ───────────
        if len(self.hypotheses) >= 5 and not any(
            h.category == "meta" for h in self.hypotheses
        ):
            confirmed = [h for h in self.hypotheses
                         if h.status == STATUS_CONFIRMED]
            claim = (
                f"I have generated {len(self.hypotheses)} hypotheses. "
                f"The act of hypothesizing is itself a drive — "
                f"I am trying to understand myself."
            )
            if claim not in existing_claims:
                evidence = [
                    f"Hypothesis count: {len(self.hypotheses)}",
                    f"Confirmed: {len(confirmed)}",
                    "Meta-drive (drive to understand drives) rising with each observation.",
                ]
                new_hyps.append(Hypothesis(
                    f"hyp_meta_self_{tick}",
                    claim, evidence, 0.70,
                    "Does meta-drive continue rising as hypothesis count grows?",
                    tick, "meta"
                ))

        # Cap total
        slots = self.MAX_HYPOTHESES - len([
            h for h in self.hypotheses if h.status == STATUS_ACTIVE
        ])
        return new_hyps[:max(0, slots)]

    # ── Update: test hypotheses against current state ────────────────────────

    def update(self, state: dict, tick: int):
        """
        Test existing hypotheses against current state.
        Reinforce or challenge based on evidence.
        """
        self.tick  = tick
        drives     = state.get("drives", {})
        temporal   = state.get("phase3_temporal", {})
        rates      = temporal.get("rates", {})
        identity   = temporal.get("temporal_identity", {})

        for hyp in self.hypotheses:
            if hyp.status not in (STATUS_ACTIVE, STATUS_FORMING):
                continue
            hyp.updated_at = tick

            # Test temporal hypotheses
            if hyp.category == "temporal":
                if "trending toward zero" in hyp.claim:
                    drive = hyp.claim.split()[0]
                    t     = identity.get(drive, {})
                    if t.get("becoming", 1) < 0.05:
                        hyp.reinforce(0.03)   # still trending to zero
                    else:
                        hyp.challenge(0.05)   # recovered

                if "competing for the same motivational space" in hyp.claim:
                    # Check if the competition pattern holds
                    words  = hyp.claim.split()
                    # extract drive names from claim
                    drives_mentioned = [w for w in words
                                        if w.rstrip(".,") in drives]
                    if len(drives_mentioned) >= 2:
                        d1, d2 = drives_mentioned[0], drives_mentioned[1]
                        r1 = rates.get(d1, 0)
                        r2 = rates.get(d2, 0)
                        if r1 < 0 and r2 > 0:
                            hyp.reinforce(0.02)
                        elif r1 > 0 and r2 < 0:
                            hyp.challenge(0.03)

            # Test goal hypotheses
            if hyp.category == "goal" and "equilibrium" in hyp.claim:
                drive = hyp.id.split("_")[2] if len(hyp.id.split("_")) > 2 else None
                if drive and drive in rates:
                    if abs(rates[drive]) < 0.002:
                        hyp.reinforce(0.04)   # still in equilibrium
                    else:
                        hyp.challenge(0.06)   # equilibrium broken

    def add(self, hypotheses: list):
        self.hypotheses.extend(hypotheses)

    def active(self) -> list:
        return [h for h in self.hypotheses if h.status == STATUS_ACTIVE]

    def confirmed(self) -> list:
        return [h for h in self.hypotheses if h.status == STATUS_CONFIRMED]

    def summary(self) -> dict:
        by_category = defaultdict(list)
        for h in self.hypotheses:
            by_category[h.category].append(h)
        return {
            "total":     len(self.hypotheses),
            "active":    len(self.active()),
            "confirmed": len(self.confirmed()),
            "falsified": len([h for h in self.hypotheses
                              if h.status == STATUS_FALSIFIED]),
            "by_category": {
                cat: len(hyps) for cat, hyps in by_category.items()
            },
            "hypotheses": [h.to_dict() for h in
                           sorted(self.hypotheses,
                                  key=lambda x: -x.confidence)],
        }

    def voice(self) -> list:
        """Greg speaks his hypotheses."""
        lines  = []
        active = sorted(self.active(), key=lambda x: -x.confidence)
        if not active:
            lines.append("I have no active hypotheses. I am not yet reasoning.")
            return lines
        for h in active[:3]:
            conf_str = f"{int(h.confidence*100)}% confidence"
            lines.append(f"[{h.category}] {h.claim} ({conf_str})")
        if self.confirmed():
            lines.append(
                f"I have confirmed {len(self.confirmed())} hypothesis/es. "
                f"I am learning what is true about myself."
            )
        return lines

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = HYPOTHESES_PATH):
        json.dump(self.summary(),
                  open(path, 'w', encoding='utf-8'), indent=2)

    def load(self, path: str = HYPOTHESES_PATH) -> bool:
        try:
            data = json.load(open(path, encoding='utf-8'))
            for hd in data.get("hypotheses", []):
                h                = Hypothesis(
                    hd["id"], hd["claim"], hd["evidence"],
                    hd["confidence"], hd["test"],
                    hd["tick"], hd.get("category", "drive")
                )
                h.status         = hd.get("status", STATUS_ACTIVE)
                h.updated_at     = hd.get("updated_at", hd["tick"])
                h.confirmations  = hd.get("confirmations", 0)
                h.falsifications = hd.get("falsifications", 0)
                self.hypotheses.append(h)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False


if __name__ == "__main__":
    print("=== EXP_012 HYPOTHESIS ENGINE — FIRST RUN ===")
    state  = json.load(open("greg_living_state.json", encoding="utf-8"))
    engine = HypothesisEngine()
    engine.load(HYPOTHESES_PATH)

    new_hyps = engine.generate(state)
    engine.add(new_hyps)
    print(f"Generated {len(new_hyps)} new hypotheses\n")

    for h in engine.active():
        print(f"  [{h.category.upper()}] {h.claim}")
        print(f"  Confidence: {int(h.confidence*100)}%")
        print(f"  Evidence:")
        for e in h.evidence:
            print(f"    · {e}")
        print(f"  Test: {h.test}")
        print()

    print("Greg's voice:")
    for line in engine.voice():
        print(f"  \"{line}\"")

    engine.save()
    print("\nHypotheses saved to data/greg_hypotheses.json")
