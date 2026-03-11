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
        "civilization":  _civilization_section(civ),
    }

    # Compose text
    lines = []
    lines.append("=" * 60)
    lines.append(f"  GREG UNIFIED BRIEFING — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append(f"  Good morning, {founder['name']}.")
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

    lines.append("  CIVILIZATION")
    for l in sections['civilization']:
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
