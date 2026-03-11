"""
EXP_008 — Greg's Knowledge Graph
Greg's world model as a living graph.
Nodes are things Greg knows. Edges are how he knows them.
The graph grows from Greg's own actions and observations.
No external injection. Knowledge earned, not given.
"""

import json
import time
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# NODE TYPES
# ─────────────────────────────────────────────────────────────────────────────
NODE_LOCATION = "location"
NODE_AGENT    = "agent"
NODE_CONCEPT  = "concept"
NODE_PATTERN  = "pattern"
NODE_EVENT    = "event"

# EDGE TYPES
EDGE_HAS_RESOURCE  = "has_resource"
EDGE_VISITED       = "visited"
EDGE_MET           = "met"
EDGE_LEARNED_FROM  = "learned_from"
EDGE_CAUSED_BY     = "caused_by"
EDGE_RELATED_TO    = "related_to"
EDGE_OBSERVED_AT   = "observed_at"

GRAPH_PATH = "data/greg_knowledge.json"


class KnowledgeNode:
    def __init__(self, node_id: str, node_type: str, data: dict = None):
        self.id         = node_id
        self.type       = node_type
        self.data       = data or {}
        self.created_at = time.time()
        self.updated_at = time.time()
        self.weight     = 1.0   # importance — rises with reinforcement

    def reinforce(self, amount: float = 0.1):
        self.weight     = min(10.0, self.weight + amount)
        self.updated_at = time.time()

    def to_dict(self):
        return {
            "id":         self.id,
            "type":       self.node_type if hasattr(self, 'node_type') else self.type,
            "data":       self.data,
            "weight":     round(self.weight, 4),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class KnowledgeEdge:
    def __init__(self, source: str, target: str, edge_type: str,
                 data: dict = None, tick: int = 0):
        self.source    = source
        self.target    = target
        self.type      = edge_type
        self.data      = data or {}
        self.tick      = tick
        self.strength  = 1.0
        self.count     = 1

    def reinforce(self, amount: float = 0.1):
        self.strength = min(10.0, self.strength + amount)
        self.count   += 1

    def to_dict(self):
        return {
            "source":   self.source,
            "target":   self.target,
            "type":     self.type,
            "data":     self.data,
            "tick":     self.tick,
            "strength": round(self.strength, 4),
            "count":    self.count,
        }


class KnowledgeGraph:
    """
    Greg's living world model.
    Grows every tick from Greg's own actions.
    Never shrinks — Greg doesn't forget, he reweights.
    """

    MAX_NODES = 500   # cap to keep graph manageable
    MAX_EDGES = 2000

    def __init__(self):
        self.nodes: dict[str, KnowledgeNode] = {}
        self.edges: list[KnowledgeEdge]      = []
        self.tick  = 0
        self._edge_index = {}  # (source, target, type) -> edge

    # ── Node management ──────────────────────────────────────────────────────

    def add_node(self, node_id: str, node_type: str,
                 data: dict = None) -> KnowledgeNode:
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.reinforce(0.05)
            if data:
                node.data.update(data)
            return node
        node = KnowledgeNode(node_id, node_type, data)
        self.nodes[node_id] = node
        # Prune if over limit (remove lowest weight non-concept nodes)
        if len(self.nodes) > self.MAX_NODES:
            self._prune_nodes()
        return node

    def add_edge(self, source: str, target: str, edge_type: str,
                 data: dict = None, tick: int = 0) -> KnowledgeEdge:
        key = (source, target, edge_type)
        if key in self._edge_index:
            edge = self._edge_index[key]
            edge.reinforce(0.1)
            if data:
                edge.data.update(data)
            return edge
        edge = KnowledgeEdge(source, target, edge_type, data, tick)
        self.edges.append(edge)
        self._edge_index[key] = edge
        if len(self.edges) > self.MAX_EDGES:
            self._prune_edges()
        return edge

    def _prune_nodes(self):
        pruneable = [(n.weight, nid) for nid, n in self.nodes.items()
                     if n.type not in (NODE_CONCEPT, NODE_PATTERN)]
        pruneable.sort()
        for _, nid in pruneable[:20]:
            del self.nodes[nid]

    def _prune_edges(self):
        self.edges.sort(key=lambda e: e.strength)
        removed = self.edges[:50]
        self.edges = self.edges[50:]
        for e in removed:
            key = (e.source, e.target, e.type)
            self._edge_index.pop(key, None)

    # ── Growth from Greg's actions ────────────────────────────────────────────

    def observe_action(self, action: str, location: str,
                       drives: dict, tick: int,
                       agent_id: str = None, data: dict = None):
        """
        Called every tick with Greg's action.
        Grows the graph from what Greg does.
        """
        self.tick = tick
        data = data or {}

        # Always add location node
        loc_node = self.add_node(location, NODE_LOCATION,
                                  {"last_visited": tick})

        # Greg visited this location
        self.add_edge("greg_meta", location, EDGE_VISITED,
                      {"tick": tick, "action": action}, tick)

        # Action-specific edges
        if action == "explore":
            # Exploration discovers the location more deeply
            loc_node.reinforce(0.15)
            # Add resources if known
            if "resources" in data:
                for resource, val in data["resources"].items():
                    res_node = self.add_node(
                        f"resource_{resource}", NODE_CONCEPT,
                        {"type": "resource", "name": resource}
                    )
                    self.add_edge(location, f"resource_{resource}",
                                  EDGE_HAS_RESOURCE,
                                  {"amount": val, "tick": tick}, tick)

        elif action in ("trade", "connect"):
            if agent_id:
                agent_node = self.add_node(agent_id, NODE_AGENT,
                                            {"last_seen": tick})
                self.add_edge("greg_meta", agent_id, EDGE_MET,
                              {"tick": tick, "location": location}, tick)
                self.add_edge(agent_id, location, EDGE_OBSERVED_AT,
                              {"tick": tick}, tick)

        elif action == "learn":
            # Learning creates concept nodes from dominant drives
            dominant = max(drives, key=drives.get) if drives else None
            if dominant:
                concept = f"concept_{dominant}_pattern"
                self.add_node(concept, NODE_CONCEPT,
                               {"drive": dominant, "learned_at": tick,
                                "location": location})
                self.add_edge("greg_meta", concept, EDGE_LEARNED_FROM,
                              {"tick": tick, "drive_value": drives[dominant]},
                              tick)

        elif action in ("build", "create"):
            event_id = f"event_create_{tick}"
            self.add_node(event_id, NODE_EVENT,
                           {"action": action, "location": location,
                            "tick": tick})
            self.add_edge("greg_meta", event_id, EDGE_CAUSED_BY,
                          {"drive": "create", "tick": tick}, tick)
            self.add_edge(event_id, location, EDGE_OBSERVED_AT,
                          {"tick": tick}, tick)

    def observe_self_awareness(self, notice: str, value: float,
                                tick: int, location: str):
        """
        Greg's self-awareness events become pattern nodes.
        Repeated patterns grow in weight — Greg recognizes them.
        """
        # Derive pattern type from notice
        pattern_id = f"pattern_{notice}"
        node = self.add_node(pattern_id, NODE_PATTERN,
                              {"notice": notice, "first_seen": tick,
                               "last_seen": tick, "occurrences": 1})
        if "occurrences" in node.data:
            node.data["occurrences"] += 1
            node.data["last_seen"]    = tick
        node.reinforce(0.2)

        self.add_edge("greg_meta", pattern_id, EDGE_RELATED_TO,
                      {"value": value, "tick": tick, "location": location},
                      tick)

    def observe_finding(self, finding_id: str, name: str, tick: int):
        """
        Findings become high-weight concept nodes.
        These are Greg's most significant knowledge.
        """
        node = self.add_node(f"finding_{finding_id}", NODE_CONCEPT,
                              {"finding_id": finding_id, "name": name,
                               "tick": tick})
        node.weight = 5.0  # findings are highly significant
        self.add_edge("greg_meta", f"finding_{finding_id}",
                      EDGE_LEARNED_FROM,
                      {"tick": tick, "type": "finding"}, tick)

    # ── Query ─────────────────────────────────────────────────────────────────

    def neighbors(self, node_id: str) -> list:
        return [e.target for e in self.edges if e.source == node_id]

    def strongest_nodes(self, node_type: str = None, n: int = 10) -> list:
        nodes = self.nodes.values()
        if node_type:
            nodes = [nd for nd in nodes if nd.type == node_type]
        return sorted(nodes, key=lambda nd: -nd.weight)[:n]

    def summary(self) -> dict:
        type_counts = defaultdict(int)
        for n in self.nodes.values():
            type_counts[n.type] += 1
        edge_counts = defaultdict(int)
        for e in self.edges:
            edge_counts[e.type] += 1
        top_locations = self.strongest_nodes(NODE_LOCATION, 5)
        top_concepts  = self.strongest_nodes(NODE_CONCEPT, 5)
        top_patterns  = self.strongest_nodes(NODE_PATTERN, 5)
        return {
            "total_nodes":    len(self.nodes),
            "total_edges":    len(self.edges),
            "node_types":     dict(type_counts),
            "edge_types":     dict(edge_counts),
            "top_locations":  [{"id": n.id, "weight": n.weight}
                               for n in top_locations],
            "top_concepts":   [{"id": n.id, "weight": n.weight,
                                "data": n.data}
                               for n in top_concepts],
            "top_patterns":   [{"id": n.id, "weight": n.weight,
                                "data": n.data}
                               for n in top_patterns],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = GRAPH_PATH):
        data = {
            "tick":  self.tick,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }
        json.dump(data, open(path, 'w', encoding='utf-8'), indent=2)

    def load(self, path: str = GRAPH_PATH):
        try:
            data = json.load(open(path, encoding='utf-8'))
            self.tick = data.get("tick", 0)
            for nid, nd in data.get("nodes", {}).items():
                node        = KnowledgeNode(nid, nd["type"], nd.get("data", {}))
                node.weight = nd.get("weight", 1.0)
                self.nodes[nid] = node
            for ed in data.get("edges", []):
                edge = KnowledgeEdge(
                    ed["source"], ed["target"], ed["type"],
                    ed.get("data", {}), ed.get("tick", 0)
                )
                edge.strength = ed.get("strength", 1.0)
                edge.count    = ed.get("count", 1)
                self.edges.append(edge)
                key = (edge.source, edge.target, edge.type)
                self._edge_index[key] = edge
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False


def bootstrap_from_greg_state(graph: KnowledgeGraph,
                               state: dict) -> int:
    """
    Seed the knowledge graph from Greg's existing state.
    One-time bootstrap — converts knowledge, memory, findings
    into graph nodes and edges.
    """
    count = 0
    tick  = state.get("tick", 0)

    # Seed from knowledge (location observations)
    for key, val in state.get("knowledge", {}).items():
        # key format: loc_TYPE_X_Y_TICK
        parts = key.split("_")
        if len(parts) >= 4:
            loc_type = parts[1]
            coords   = f"{parts[2]}_{parts[3]}"
            loc_id   = f"{loc_type}_{coords}"
            resources = val.get("resources", {})
            graph.add_node(loc_id, NODE_LOCATION,
                           {"last_observed": key})
            for resource, amount in resources.items():
                res_node_id = f"resource_{resource}"
                graph.add_node(res_node_id, NODE_CONCEPT,
                               {"type": "resource", "name": resource})
                graph.add_edge(loc_id, res_node_id, EDGE_HAS_RESOURCE,
                               {"amount": amount}, tick)
            count += 1

    # Seed from locations_visited
    for loc in state.get("locations_visited", []):
        graph.add_node(loc, NODE_LOCATION, {"visited": True})
        graph.add_edge("greg_meta", loc, EDGE_VISITED, {"tick": tick}, tick)
        count += 1

    # Seed from memory (self_awareness events)
    for mem in state.get("memory", []):
        if mem.get("type") == "self_awareness":
            notice   = mem.get("detail", {}).get("notice", "unknown")
            value    = mem.get("detail", {}).get("value", 0)
            mem_tick = mem.get("tick", tick)
            loc      = mem.get("loc", "unknown")
            graph.observe_self_awareness(notice, value, mem_tick, loc)
            count += 1

    # Seed from findings
    for finding in state.get("findings", []):
        graph.observe_finding(
            finding["id"], finding["name"],
            finding.get("tick", tick)
        )
        count += 1

    # Seed from relationships
    for agent_id, rel in state.get("relationships", {}).items():
        graph.add_node(agent_id, NODE_AGENT,
                       {"trust": rel.get("trust", 0.5),
                        "interactions": rel.get("interactions", 0)})
        graph.add_edge("greg_meta", agent_id, EDGE_MET,
                       {"trust": rel.get("trust", 0.5)}, tick)
        count += 1

    # Greg himself is always a node
    graph.add_node("greg_meta", NODE_AGENT,
                   {"role": "meta_agent", "tick": tick})

    return count


if __name__ == "__main__":
    import json

    print("=== EXP_008 KNOWLEDGE GRAPH BOOTSTRAP ===")
    state = json.load(open("greg_living_state.json", encoding="utf-8"))

    graph = KnowledgeGraph()
    n = bootstrap_from_greg_state(graph, state)
    graph.save()

    summary = graph.summary()
    print(f"  Bootstrapped {n} items from Greg's existing state")
    print(f"  Nodes: {summary['total_nodes']}")
    print(f"  Edges: {summary['total_edges']}")
    print(f"  Node types: {summary['node_types']}")
    print(f"  Edge types: {summary['edge_types']}")
    print()
    print("  Top locations:")
    for loc in summary['top_locations']:
        print(f"    {loc['id']}: weight {loc['weight']}")
    print()
    print("  Top concepts:")
    for c in summary['top_concepts']:
        print(f"    {c['id']}: weight {c['weight']} — {c['data'].get('name', c['data'])}")
    print()
    print("  Top patterns:")
    for p in summary['top_patterns']:
        print(f"    {p['id']}: weight {p['weight']} — occurrences: {p['data'].get('occurrences', 1)}")
    print()
    print("Knowledge graph saved to data/greg_knowledge.json")
