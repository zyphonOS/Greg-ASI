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

    # Compress agents
    compressed = {}
    for aid, agent in agents.items():
        if isinstance(agent, dict):
            compressed[aid] = {k: v for k, v in agent.items()
                               if k in KEEP_FIELDS}
        else:
            compressed[aid] = agent

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


if __name__ == "__main__":
    compress()
