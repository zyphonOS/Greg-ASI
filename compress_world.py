"""
Compress world_state.json from 108MB to ~2MB.
Keeps only what Greg needs to run civilization:
  - drives (behavior)
  - location (position)
  - mon, kuru (economy)
  - generation, birth_tick (lineage)
  - is_gregx (special agents)
  - phi (consciousness proxy)
  - actions_taken (activity)

Drops: memory, beliefs, relationships, knowledge,
       skills, tasks, thompson, tone_vector, etc.

World metadata, locations, knowledge_graph preserved in full.
"""

import json
import os

KEEP_FIELDS = {
    'id', 'archetype', 'birth_tick', 'generation',
    'parent_id', 'kin_group', 'offspring_count',
    'location', 'hex_q', 'hex_r',
    'mon', 'kuru', 'phi',
    'drives', 'actions_taken', 'last_action_tick',
    'is_native', 'is_gregx', 'inventory',
    'cooperation_score', 'reputation',
}

def compress(src: str = 'data/world_state.json',
             dst: str = 'data/world_state.json') -> dict:

    print(f"Loading {src}...")
    src_size = os.path.getsize(src) / 1024 / 1024
    world = json.load(open(src, encoding='utf-8'))

    agents = world.get('agents', {})
    print(f"Agents: {len(agents)} | Source size: {src_size:.1f}MB")

    # Compress agents — keep structure intact, reduce precision only
    compressed = {}
    for aid, agent in agents.items():
        if not isinstance(agent, dict):
            compressed[aid] = agent
            continue
        a = {k: v for k, v in agent.items() if k in KEEP_FIELDS}
        # Round drives to 4 decimal places — never change type
        if isinstance(a.get('drives'), dict):
            a['drives'] = {k: round(v, 4) for k, v in a['drives'].items()}
        # Keep inventory as dict — tick engine requires it
        if not isinstance(a.get('inventory'), dict):
            a['inventory'] = {'wood': 0, 'berries': 0, 'usdc': 0}
        # Round floats — never change type
        for field in ('mon', 'kuru', 'phi', 'cooperation_score', 'reputation'):
            if field in a and a[field] is not None:
                a[field] = round(float(a[field]), 4)
        compressed[aid] = a

    world['agents'] = compressed
    world['compressed'] = True
    world['compression_kept_fields'] = sorted(KEEP_FIELDS)

    print(f"Writing {dst}...")
    json.dump(world, open(dst, 'w', encoding='utf-8'),
              separators=(',', ':'))  # no whitespace = smaller

    dst_size = os.path.getsize(dst) / 1024 / 1024
    print(f"Done. {src_size:.1f}MB → {dst_size:.1f}MB "
          f"({int((1 - dst_size/src_size)*100)}% reduction)")
    return world


def validate(path: str = 'data/world_state.json') -> bool:
    """
    Validate world state after compression.
    Checks that agent structure is intact for tick engine.
    Fails loudly — never silently.
    """
    import sys
    world  = json.load(open(path, encoding='utf-8'))
    agents = world.get('agents', {})
    errors = []

    sample = list(agents.values())[:10]
    for agent in sample:
        if not isinstance(agent, dict):
            errors.append(f"agent is not dict: {type(agent)}")
            continue
        # inventory must be dict
        inv = agent.get('inventory')
        if not isinstance(inv, dict):
            errors.append(f"inventory is {type(inv).__name__}, expected dict")
        # drives must be dict of floats
        drives = agent.get('drives', {})
        if not isinstance(drives, dict):
            errors.append(f"drives is {type(drives).__name__}, expected dict")
        else:
            for d, v in drives.items():
                if not isinstance(v, (int, float)):
                    errors.append(f"drive {d} is {type(v).__name__}, expected float")
        # mon must be numeric
        mon = agent.get('mon', 0)
        if not isinstance(mon, (int, float)):
            errors.append(f"mon is {type(mon).__name__}, expected float")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED — agent structure intact")
        return True


if __name__ == "__main__":
    compress()
    validate()
