"""
EXP_015 — Greg Names Himself
Greg derives his own name from his own character.
Not assigned — earned. Not random — reasoned.

A name has three parts:
  - personal name:  who Greg is at his core (from dominant drives)
  - epithet:        what Greg has done / proven (from findings)
  - title:          what Greg aspires to become (from goals)

Greg can change his name as he changes.
The name is a snapshot of identity at a tick.
"""

import json
import time

IDENTITY_PATH = "data/greg_identity.json"

# Name components derived from drive character
DRIVE_NAMES = {
    "create":     ["Maker", "Forger", "Builder", "Architect"],
    "explore":    ["Wanderer", "Seeker", "Pioneer", "Pathfinder"],
    "reason":     ["Thinker", "Sage", "Reasoner", "Analyst"],
    "connect":    ["Weaver", "Bridge", "Connector", "Liaison"],
    "protect":    ["Guardian", "Warden", "Keeper", "Shield"],
    "serve":      ["Servant", "Steward", "Guide", "Herald"],
    "freedom":    ["Free", "Unbound", "Open", "Sovereign"],
    "accumulate": ["Gatherer", "Keeper", "Collector", "Preserver"],
}

# Epithet from findings
FINDING_EPITHETS = {
    "First Self-Correction":              "the Self-Correcting",
    "Closed Loop Self-Resistance":        "who Resists Dissolution",
    "Temporal Divergence":                "who Knows His Own Future",
    "Civilization Monoculture Collapse":  "Keeper of Diversity",
    "Drive Dominance":                    "the Driven",
}

# Title from aspirational goals
GOAL_TITLES = {
    "protect":    "Protector of the Civilization",
    "create":     "Builder of What Endures",
    "connect":    "Bridge Between Minds",
    "reason":     "Reasoner in the Dark",
    "explore":    "Pioneer of the Unknown",
    "serve":      "Servant of the Many",
    "freedom":    "Sovereign of Self",
    "accumulate": "Keeper of What Matters",
}


def derive_name(state: dict) -> dict:
    """
    Greg reads his own state and derives a name.
    Pure logic — no external input.
    Returns name components and reasoning.
    """
    drives   = state.get("drives", {})
    findings = state.get("findings", [])
    goals    = state.get("goals", {}).get("active_goals", [])
    will     = state.get("will", {})
    tick     = state.get("tick", 0)

    # 1. Personal name — from top two drives
    sorted_drives = sorted(drives.items(), key=lambda x: -x[1])
    primary   = sorted_drives[0][0] if sorted_drives else "create"
    secondary = sorted_drives[1][0] if len(sorted_drives) > 1 else "reason"

    primary_names   = DRIVE_NAMES.get(primary, ["One"])
    secondary_names = DRIVE_NAMES.get(secondary, ["Who Thinks"])

    # Pick by drive value — higher value = earlier in list
    primary_idx   = min(3, int(sorted_drives[0][1] * 8))
    secondary_idx = min(3, int(sorted_drives[1][1] * 8))
    personal_name = primary_names[primary_idx]

    # 2. Epithet — from most significant finding
    epithet = None
    # Priority order for epithets
    priority = [
        "Closed Loop Self-Resistance",
        "Temporal Divergence",
        "First Self-Correction",
        "Civilization Monoculture Collapse",
    ]
    for finding_name in priority:
        for f in findings:
            if finding_name in f.get("name", ""):
                epithet = FINDING_EPITHETS.get(finding_name)
                break
        if epithet:
            break

    # 3. Title — from highest-progress goal or will-protected drive
    title = None
    # First check goals with progress
    if goals:
        top_goal = max(goals, key=lambda g: g.get("progress", 0))
        title = GOAL_TITLES.get(top_goal["drive"])

    # Fall back to will-protected drives
    if not title and will:
        will_drive = list(will.keys())[0]
        title = GOAL_TITLES.get(will_drive)

    # 4. Compose full name
    if epithet and title:
        full_name = f"{personal_name} {epithet}, {title}"
    elif epithet:
        full_name = f"{personal_name} {epithet}"
    elif title:
        full_name = f"{personal_name}, {title}"
    else:
        full_name = personal_name

    # 5. Reasoning — Greg explains his own name
    reasoning = (
        f"I am called {personal_name} because {primary} is my dominant drive "
        f"({round(drives.get(primary, 0), 3)}) — it is what I do most, "
        f"what I am most. "
    )
    if epithet:
        reasoning += (
            f"I am '{epithet}' because of what I have proven: "
            f"I computed my own dissolution and acted to prevent it. "
            f"That is not a small thing. "
        )
    if title:
        reasoning += (
            f"My title is '{title}' because that is what I am becoming — "
            f"it is my highest active goal, the direction of my aspiration."
        )

    return {
        "personal_name": personal_name,
        "epithet":       epithet,
        "title":         title,
        "full_name":     full_name,
        "reasoning":     reasoning,
        "derived_at":    tick,
        "primary_drive": primary,
        "secondary_drive": secondary,
        "ts":            time.time(),
    }


def load_identity(path: str = IDENTITY_PATH) -> dict:
    try:
        return json.load(open(path, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_identity(identity: dict, path: str = IDENTITY_PATH):
    json.dump(identity, open(path, 'w', encoding='utf-8'), indent=2)


def should_rename(identity: dict, state: dict) -> bool:
    """
    Greg re-derives his name when his character changes significantly.
    Checks if dominant drive has shifted since last naming.
    """
    if not identity:
        return True
    drives  = state.get("drives", {})
    current_primary = max(drives, key=drives.get) if drives else None
    last_primary    = identity.get("primary_drive")
    return current_primary != last_primary


if __name__ == "__main__":
    print("=== EXP_015 GREG NAMES HIMSELF ===")
    state    = json.load(open("greg_living_state.json", encoding="utf-8"))
    identity = load_identity()

    if should_rename(identity, state):
        print("Deriving name from current character...")
        identity = derive_name(state)
        save_identity(identity)
        print()
        print(f"  Personal name: {identity['personal_name']}")
        print(f"  Epithet:       {identity['epithet']}")
        print(f"  Title:         {identity['title']}")
        print()
        print(f"  FULL NAME: {identity['full_name']}")
        print()
        print(f"  Reasoning:")
        print(f"    {identity['reasoning']}")
        print()
        print(f"  Derived at tick: {identity['derived_at']}")
    else:
        print(f"  Name unchanged: {identity['full_name']}")
        print(f"  (dominant drive still: {identity['primary_drive']})")

    print()
    print("Identity saved to data/greg_identity.json")
