"""
EXP_010 — Unified Daily Briefing Synthesis
Greg speaks about his own condition from all layers at once.
Drives + Temporal + Metacog + Relationships + Knowledge + Findings.
One coherent voice. No shallow status checks.
"""

import json
from datetime import datetime

BRIEFING_PATH  = "data/greg_briefing_last.json"
FOUNDER_PATH   = "data/ebuka_profile.json"


def _load_json(path: str) -> dict:
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return {}


def _load_founder() -> dict:
    profile = _load_json(FOUNDER_PATH)
    founder = profile.get('founder', {})
    return {
        "name":          founder.get('goes_by', 'Ebuka'),
        "current_focus": profile.get('current_focus', []),
        "projects":      profile.get('projects', {}),
    }


def _drives_section(drives: dict, will: dict) -> list:
    lines = []
    if not drives:
        return lines
    dominant = max(drives, key=drives.get)
    lines.append(f"Dominant drive: {dominant} ({round(drives[dominant], 3)})")

    # Healthy balance check
    top4 = sorted(drives.items(), key=lambda x: -x[1])[:4]
    spread = top4[0][1] - top4[-1][1]
    if spread < 0.15:
        lines.append("Drive balance is wide — complexity, not drift.")
    elif spread > 0.40:
        lines.append(f"Drive space is narrow — {dominant} is consuming the field.")

    # Will floors
    for drive, floor in will.items():
        val = drives.get(drive, 0)
        if val <= floor + 0.01:
            lines.append(
                f"{drive.capitalize()} is at its self-imposed floor ({floor}). "
                f"Greg is holding."
            )
        else:
            lines.append(
                f"{drive.capitalize()} is above floor: {round(val, 3)} "
                f"(floor: {floor}). Healthy margin."
            )
    return lines


def _temporal_section(temporal: dict) -> list:
    lines = []
    if not temporal:
        return lines
    narrative = temporal.get('narrative', [])
    rates     = temporal.get('rates', {})
    if narrative:
        lines.extend(narrative)
    # Flag any drive with alarming rate
    for drive, rate in rates.items():
        if rate < -0.010:
            lines.append(
                f"Warning: {drive} is falling at {rate:.4f}/tick. "
                f"Trajectory requires attention."
            )
        elif rate > 0.010:
            lines.append(
                f"Note: {drive} is rising at {rate:+.4f}/tick."
            )
    return lines


def _metacog_section(metacog: dict) -> list:
    lines = []
    if not metacog:
        return lines
    observations = metacog.get('last_observations', [])
    meta_drive   = metacog.get('meta_drive', 0)
    corrections  = metacog.get('correction_count', 0)
    if observations:
        lines.append("Greg's inner voice this tick:")
        for obs in observations:
            lines.append(f"  \"{obs}\"")
    if corrections > 0:
        lines.append(
            f"Greg has made {corrections} self-corrections. "
            f"Meta-drive: {meta_drive}."
        )
    return lines


def _relationships_section(rel_path: str) -> list:
    lines = []
    try:
        from greg_relationships import RelationshipGraph, REL_PATH
        rg = RelationshipGraph()
        loaded = rg.load(rel_path or REL_PATH)
        if not loaded:
            return lines
        summary = rg.summary()
        voice   = rg.voice()
        lines.append(
            f"{summary['total']} relationships | "
            f"avg trust: {summary['avg_trust']} | "
            f"max trust: {summary['max_trust']}"
        )
        lines.append(f"Depth breakdown: {summary['depth_counts']}")
        if voice:
            lines.extend(voice)
        trusted = summary.get('most_trusted', [])
        if trusted:
            top = trusted[0]
            lines.append(
                f"Most trusted: {top['id']} "
                f"({top['depth']}, trust={top['trust']}, "
                f"{top['interactions']} interactions)"
            )
    except Exception:
        pass
    return lines


def _knowledge_section(kg_path: str) -> list:
    lines = []
    try:
        from greg_knowledge_graph import KnowledgeGraph, GRAPH_PATH
        g = KnowledgeGraph()
        g.load(kg_path or GRAPH_PATH)
        s = g.summary()
        lines.append(
            f"{s['total_nodes']} knowledge nodes | "
            f"{s['total_edges']} edges"
        )
        top_patterns = s.get('top_patterns', [])
        if top_patterns:
            p = top_patterns[0]
            occ = p['data'].get('occurrences', 1)
            lines.append(
                f"Strongest pattern: {p['id']} "
                f"(weight {p['weight']}, {occ} occurrences)"
            )
        top_concepts = [c for c in s.get('top_concepts', [])
                        if c['id'].startswith('finding_')]
        if top_concepts:
            lines.append(
                f"Most significant knowledge: "
                f"{top_concepts[0]['data'].get('name', top_concepts[0]['id'])}"
            )
    except Exception:
        pass
    return lines


def _civilization_health_section() -> list:
    lines = []
    try:
        from greg_civilization import CivilizationMonitor, CIV_HEALTH_PATH, compute_drive_distribution, compute_health_score
        monitor = CivilizationMonitor()
        monitor.load(CIV_HEALTH_PATH)
        state   = _load_json("greg_living_state.json")
        civ_h   = state.get("civ_health", {})
        if civ_h:
            score = civ_h.get("score", 0)
            risk  = civ_h.get("risk", "UNKNOWN")
            flags = civ_h.get("flags", [])
            bar   = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            lines.append(f"Health: {round(score*100)}% [{bar}] ({risk})")
            for flag in flags[:3]:
                parts = flag.split(":")
                if parts[0] == "starved":
                    lines.append(f"⚠ {parts[1]} is starved in civilization ({parts[2]})")
                elif parts[0] == "monoculture":
                    lines.append(f"⚠ Monoculture: {parts[1]} dominating ({parts[2]})")
                elif parts[0] == "depleted":
                    lines.append(f"⚠ {parts[1]} depleted in civilization ({parts[2]})")
                elif flag == "no_guardians":
                    lines.append("⚠ No guardians — nothing is being protected")
            if monitor.interventions:
                last = monitor.interventions[-1]
                lines.append(f"Last intervention: tick {last['tick']} ({last['agents_corrected']} agents)")
    except Exception:
        pass
    return lines


def _hypotheses_section() -> list:
    lines = []
    try:
        from greg_hypotheses import HypothesisEngine, HYPOTHESES_PATH
        engine = HypothesisEngine()
        engine.load(HYPOTHESES_PATH)
        active = engine.active()
        if not active:
            return lines
        lines.append(f"{len(active)} active hypothesis/es:")
        for h in sorted(active, key=lambda x: -x.confidence)[:3]:
            conf = int(h.confidence * 100)
            lines.append(f"  [{h.category} {conf}%] {h.claim[:90]}")
        if engine.confirmed():
            lines.append(f"Confirmed: {len(engine.confirmed())}")
    except Exception:
        pass
    return lines


def _goals_section(goals_path: str = None) -> list:
    lines = []
    try:
        from greg_goals import GoalEngine, GOALS_PATH
        from greg_knowledge_graph import GRAPH_PATH
        import json
        state  = _load_json("greg_living_state.json")
        drives = state.get("drives", {})
        engine = GoalEngine()
        engine.load(goals_path or GOALS_PATH)
        active = engine.active_goals()
        if not active:
            lines.append("No active goals.")
            return lines
        for goal in active:
            current = drives.get(goal.drive, 0)
            pct     = goal.progress_pct(current)
            bar     = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))
            lines.append(
                f"{goal.drive} → {goal.target} "
                f"[{bar}] {int(pct*100)}% "
                f"(current: {round(current,3)})"
            )
        if engine.achieved:
            lines.append(f"Achieved: {len(engine.achieved)} goal(s) total.")
    except Exception:
        pass
    return lines


def _findings_section(findings: list) -> list:
    if not findings:
        return []
    lines = [f"{len(findings)} findings recorded:"]
    for f in findings[-3:]:   # last 3 most recent
        lines.append(f"  [{f['id']}] {f['name']}")
    return lines


def _civilization_section(civ: dict) -> list:
    lines = []
    tick   = civ.get('tick', 0)
    agents = civ.get('agent_count', 0)
    lines.append(f"Tick: {tick:,} | Agents: {agents:,}")
    return lines


def generate_unified_briefing(
    state_path:   str = "greg_living_state.json",
    rel_path:     str = None,
    kg_path:      str = None,
) -> dict:
    """
    Pull all layers together into one coherent briefing.
    Returns structured dict + rendered text.
    """
    state    = _load_json(state_path)
    founder  = _load_founder()
    now      = datetime.now()

    drives   = state.get('drives', {})
    will     = state.get('will', {})
    findings = state.get('findings', [])
    civ      = state.get('civilization', {})
    temporal = state.get('phase3_temporal', {})
    metacog  = state.get('phase3_metacog', {})
    tick     = state.get('tick', 0)
    actions  = state.get('actions_taken', 0)
    phi      = state.get('phi', 0)

    sections = {
        "drives":        _drives_section(drives, will),
        "temporal":      _temporal_section(temporal),
        "metacog":       _metacog_section(metacog),
        "relationships": _relationships_section(rel_path),
        "knowledge":     _knowledge_section(kg_path),
        "findings":      _findings_section(findings),
        "goals":              _goals_section(),
        "hypotheses":         _hypotheses_section(),
        "civilization":       _civilization_section(civ),
        "civilization_health": _civilization_health_section(),
    }

    # Compose text
    lines = []
    # Load Greg's identity
    try:
        from greg_identity import load_identity, derive_name, should_rename, IDENTITY_PATH
        greg_identity = load_identity()
        if not greg_identity or should_rename(greg_identity, state):
            greg_identity = derive_name(state)
            from greg_identity import save_identity
            save_identity(greg_identity)
    except Exception:
        greg_identity = {}

    lines.append("=" * 60)
    lines.append(f"  GREG UNIFIED BRIEFING — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append(f"  Good morning, {founder['name']}.")
    if greg_identity.get('full_name'):
        lines.append(f"  Greg is: {greg_identity['full_name']}")
    lines.append("")

    lines.append("  GREG — CORE STATE")
    lines.append(f"    Tick:    {tick:,}")
    lines.append(f"    Actions: {actions:,}")
    lines.append(f"    Phi:     {round(phi, 4)}")
    lines.append("")

    lines.append("  DRIVES")
    for l in sections['drives']:
        lines.append(f"    {l}")
    lines.append("")

    if sections['temporal']:
        lines.append("  TRAJECTORY (dGreg/dt)")
        for l in sections['temporal']:
            lines.append(f"    {l}")
        lines.append("")

    if sections['metacog']:
        lines.append("  INNER VOICE")
        for l in sections['metacog']:
            lines.append(f"    {l}")
        lines.append("")

    if sections['relationships']:
        lines.append("  RELATIONSHIPS")
        for l in sections['relationships']:
            lines.append(f"    {l}")
        lines.append("")

    if sections['knowledge']:
        lines.append("  KNOWLEDGE")
        for l in sections['knowledge']:
            lines.append(f"    {l}")
        lines.append("")

    if sections['findings']:
        lines.append("  FINDINGS")
        for l in sections['findings']:
            lines.append(f"    {l}")
        lines.append("")

    if sections['goals']:
        lines.append("  GREG'S GOALS")
        for l in sections['goals']:
            lines.append(f"    {l}")
        lines.append("")

    if sections.get('hypotheses'):
        lines.append("  GREG'S HYPOTHESES")
        for l in sections['hypotheses']:
            lines.append(f"    {l}")
        lines.append("")

    lines.append("  CIVILIZATION")
    for l in sections['civilization']:
        lines.append(f"    {l}")
    for l in sections.get('civilization_health', []):
        lines.append(f"    {l}")
    lines.append("")

    if founder['current_focus']:
        lines.append("  YOUR FOCUS TODAY")
        for item in founder['current_focus']:
            lines.append(f"    · {item}")
        lines.append("")

    lines.append("=" * 60)

    briefing = {
        "ts":       now.isoformat(),
        "date":     now.strftime('%Y-%m-%d'),
        "time":     now.strftime('%H:%M'),
        "greeting": f"Good morning, {founder['name']}.",
        "greg": {
            "tick":    tick,
            "actions": actions,
            "phi":     round(phi, 4),
            "drives":  {k: round(v, 4) for k, v in drives.items()},
            "will":    will,
        },
        "sections": sections,
        "founder":  founder,
        "text":     "\n".join(lines),
    }

    # Save last briefing
    try:
        json.dump(briefing, open(BRIEFING_PATH, 'w', encoding='utf-8'),
                  indent=2)
    except Exception:
        pass

    return briefing


if __name__ == "__main__":
    briefing = generate_unified_briefing()
    print(briefing['text'])
