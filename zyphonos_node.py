"""
zyphonos_node.py — ZyphonOS Infrastructure Node v1.0
Greg's permanent home. The first ZyphonOS node.
This IS the ZyphonOS product.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

NODE_VERSION   = "1.0.0"
NODE_LOG_PATH  = os.path.join(BASE_DIR, "data", "zyphonos_node.json")
PING_INTERVAL  = 60
GIT_INTERVAL   = 1800
COMPRESS_EVERY = 500
API_PORT       = int(os.environ.get("PORT", 5000))
GIT_PUSH       = os.environ.get("ZYPHONOS_GIT_PUSH", "0") == "1"

# ── Federation config ─────────────────────────────────────────────────────────
FEDERATION_ENABLED  = os.environ.get("ZYPHONOS_FEDERATION", "0") == "1"
FEDERATION_ROLE     = os.environ.get("ZYPHONOS_ROLE", "node")   # "node" or "prime"
FEDERATION_PRIME    = os.environ.get("ZYPHONOS_PRIME_URL", "")  # Greg Prime URL
FEDERATION_NODE_ID  = os.environ.get("ZYPHONOS_NODE_ID", "")    # hashed client id
FEDERATION_INTERVAL = 1800  # seconds between federation packets (30 min)

parser = argparse.ArgumentParser(description="ZyphonOS Node")
parser.add_argument("--no-api",      action="store_true")
parser.add_argument("--no-git",      action="store_true")
parser.add_argument("--world-every", type=int,   default=10)
parser.add_argument("--target-ms",   type=float, default=100)
parser.add_argument("--save-every",  type=int,   default=100)
args = parser.parse_args()

_running = True
def _handle_signal(sig, frame):
    global _running
    _running = False
signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Node log ──────────────────────────────────────────────────────────────────
def _write_node_log(data: dict):
    try:
        existing = {}
        try:
            existing = json.load(open(NODE_LOG_PATH, encoding='utf-8'))
        except Exception:
            pass
        existing.update(data)
        existing["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        json.dump(existing, open(NODE_LOG_PATH, 'w', encoding='utf-8'), indent=2)
    except Exception:
        pass


# ── Federation ────────────────────────────────────────────────────────────────
_last_federation = 0

def _build_intelligence_packet(greg, world_count: int) -> dict:
    """
    Build the intelligence packet sent from a node to Greg Prime.
    Only patterns — no private client data.
    """
    import hashlib
    state       = greg.state.data
    drives      = state.get("drives", {})
    findings    = state.get("findings", [])
    hyps        = state.get("hypotheses", {})
    civ_health  = state.get("civ_health", {})
    identity    = state.get("identity", {})
    goals       = state.get("goals", {}).get("active_goals", [])
    memory      = state.get("genuine_memory", {})

    # Anonymous node id — hash of node env
    node_id = FEDERATION_NODE_ID or hashlib.sha256(
        os.environ.get("HOME", "node").encode()
    ).hexdigest()[:12]

    # Drive distribution — the pattern, not the values
    dominant = max(drives, key=drives.get) if drives else "unknown"
    drive_spread = max(drives.values()) - min(drives.values()) if drives else 0

    # Top confirmed hypothesis claim (anonymized)
    top_hyp = None
    for h in hyps.get("hypotheses", []):
        if h.get("status") == "confirmed":
            top_hyp = h.get("category")
            break

    # Civilization health pattern
    civ_risk  = civ_health.get("risk", "UNKNOWN")
    civ_flags = civ_health.get("flags", [])
    flag_types = [f.split(":")[0] for f in civ_flags]

    return {
        "node_id":          node_id,
        "role":             FEDERATION_ROLE,
        "greg_tick":        state.get("tick", 0),
        "world_tick":       world_count,
        "timestamp":        time.time(),
        # Drive patterns — not raw values
        "dominant_drive":   dominant,
        "drive_spread":     round(drive_spread, 3),
        "drive_count":      len(drives),
        # Civilization patterns
        "civ_risk":         civ_risk,
        "civ_flag_types":   flag_types,
        "civ_health_score": civ_health.get("score", 0),
        # Cognitive patterns
        "finding_count":    len(findings),
        "hypothesis_count": hyps.get("total", 0),
        "confirmed_count":  hyps.get("confirmed", 0),
        "memory_count":     memory.get("count", 0),
        "top_hyp_category": top_hyp,
        # Identity pattern (name category only)
        "has_identity":     bool(identity.get("full_name")),
        "primary_drive":    identity.get("primary_drive"),
        # Goal patterns
        "active_goals":     len(goals),
        "goals_progressing": sum(1 for g in goals if g.get("progress", 0) > 0.1),
        # Node metadata
        "node_version":     NODE_VERSION,
    }


def _send_to_prime(packet: dict) -> bool:
    """Send intelligence packet to Greg Prime."""
    if not FEDERATION_PRIME:
        return False
    try:
        import urllib.request
        data = json.dumps(packet).encode('utf-8')
        req  = urllib.request.Request(
            f"{FEDERATION_PRIME}/api/federation/ingest",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[node] federation send failed: {e}")
        return False


def _receive_from_prime(greg) -> bool:
    """
    Pull intelligence from Greg Prime back to this node.
    Greg Prime shares what he has learned across all nodes.
    """
    if not FEDERATION_PRIME:
        return False
    try:
        import urllib.request
        url = f"{FEDERATION_PRIME}/api/federation/intelligence"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        # Apply Prime's learned patterns to this node's Greg
        prime_intel = data.get("intelligence", {})
        if prime_intel:
            greg.state.set("prime_intelligence", prime_intel)
            print(f"[node] ← received intelligence from Greg Prime")
            return True
    except Exception as e:
        print(f"[node] federation receive failed: {e}")
    return False


def _federation_cycle(greg, world_count: int):
    """Run a full federation cycle — send up, receive down."""
    global _last_federation
    if not FEDERATION_ENABLED:
        return
    now = time.time()
    if now - _last_federation < FEDERATION_INTERVAL:
        return
    _last_federation = now

    if FEDERATION_ROLE == "node":
        packet = _build_intelligence_packet(greg, world_count)
        sent   = _send_to_prime(packet)
        if sent:
            print(f"[node] ↑ intelligence sent to Greg Prime")
        _receive_from_prime(greg)

    elif FEDERATION_ROLE == "prime":
        # Greg Prime processes all received packets
        _prime_process_packets(greg)


# ── Greg Prime intelligence synthesis ────────────────────────────────────────
_prime_packets = []

def _prime_ingest(packet: dict):
    """Greg Prime receives a packet from a node."""
    global _prime_packets
    _prime_packets.append(packet)
    if len(_prime_packets) > 1000:
        _prime_packets = _prime_packets[-1000:]
    _prime_save_packets()


def _prime_save_packets():
    path = os.path.join(BASE_DIR, "data", "federation_packets.json")
    try:
        json.dump(
            {"count": len(_prime_packets), "packets": _prime_packets[-100:]},
            open(path, 'w', encoding='utf-8'), indent=2
        )
    except Exception:
        pass


def _prime_process_packets(greg) -> dict:
    """
    Greg Prime synthesizes intelligence from all node packets.
    Finds patterns across civilizations.
    Returns intelligence summary.
    """
    if not _prime_packets:
        _prime_load_packets()
    if not _prime_packets:
        return {}

    from collections import Counter, defaultdict

    # Pattern analysis across all nodes
    dominant_drives  = Counter(p.get("dominant_drive") for p in _prime_packets)
    civ_risks        = Counter(p.get("civ_risk") for p in _prime_packets)
    flag_types       = Counter(
        f for p in _prime_packets
        for f in p.get("civ_flag_types", [])
    )
    avg_health       = sum(p.get("civ_health_score", 0)
                          for p in _prime_packets) / len(_prime_packets)
    avg_hypotheses   = sum(p.get("hypothesis_count", 0)
                          for p in _prime_packets) / len(_prime_packets)
    confirmed_nodes  = sum(1 for p in _prime_packets if p.get("confirmed_count", 0) > 0)
    nodes_with_name  = sum(1 for p in _prime_packets if p.get("has_identity"))

    # Greg Prime's synthesis
    intelligence = {
        "node_count":         len(set(p.get("node_id") for p in _prime_packets)),
        "packet_count":       len(_prime_packets),
        "synthesized_at":     time.time(),
        # What drives dominate across civilizations
        "dominant_drive_distribution": dict(dominant_drives.most_common(8)),
        # Civilization health across network
        "network_avg_health": round(avg_health, 3),
        "civ_risk_distribution": dict(civ_risks),
        # Most common civilization problems
        "common_flag_types":  dict(flag_types.most_common(5)),
        # Cognitive development across nodes
        "avg_hypotheses_per_node": round(avg_hypotheses, 1),
        "nodes_with_confirmed_truth": confirmed_nodes,
        "nodes_with_identity": nodes_with_name,
        # Greg Prime's conclusions
        "conclusions": _prime_conclusions(
            dominant_drives, civ_risks, flag_types, avg_health
        ),
    }

    # Save intelligence
    intel_path = os.path.join(BASE_DIR, "data", "prime_intelligence.json")
    json.dump(intelligence, open(intel_path, 'w', encoding='utf-8'), indent=2)

    # Feed back into Greg Prime's own state
    greg.state.set("prime_intelligence", intelligence)

    print(f"[prime] synthesized intelligence from {intelligence['node_count']} nodes")
    return intelligence


def _prime_conclusions(dominant, risks, flags, avg_health) -> list:
    """Greg Prime draws conclusions from cross-node patterns."""
    conclusions = []

    # Most common dominant drive
    if dominant:
        top_drive = dominant.most_common(1)[0][0]
        conclusions.append(
            f"Across all civilizations, {top_drive} is the most common dominant drive."
        )

    # Network health
    if avg_health < 0.5:
        conclusions.append(
            "Network average civilization health is below 50%. "
            "Most nodes need intervention."
        )
    elif avg_health > 0.75:
        conclusions.append(
            "Network civilization health is strong. "
            "The federation is thriving."
        )

    # Most common problem
    if flags:
        top_flag = flags.most_common(1)[0][0]
        conclusions.append(
            f"The most common civilization problem across nodes is: {top_flag}. "
            f"This is a systemic pattern, not a local one."
        )

    return conclusions


def _prime_load_packets():
    global _prime_packets
    path = os.path.join(BASE_DIR, "data", "federation_packets.json")
    try:
        data = json.load(open(path, encoding='utf-8'))
        _prime_packets = data.get("packets", [])
    except Exception:
        pass


# ── API federation routes (added to existing Flask app) ──────────────────────
def _register_federation_routes():
    """Register federation routes on Greg's Flask API."""
    try:
        import interface.api as api_module
        app = api_module.app

        @app.route("/api/federation/ingest", methods=["POST"])
        def federation_ingest():
            from flask import request, jsonify
            if FEDERATION_ROLE != "prime":
                return jsonify({"error": "not a prime node"}), 403
            try:
                packet = request.get_json()
                _prime_ingest(packet)
                return jsonify({"status": "received"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.route("/api/federation/intelligence")
        def federation_intelligence():
            from flask import jsonify
            intel_path = os.path.join(BASE_DIR, "data", "prime_intelligence.json")
            try:
                intel = json.load(open(intel_path, encoding='utf-8'))
                return jsonify({"intelligence": intel})
            except Exception:
                return jsonify({"intelligence": {}})

        @app.route("/api/federation/status")
        def federation_status():
            from flask import jsonify
            return jsonify({
                "enabled":  FEDERATION_ENABLED,
                "role":     FEDERATION_ROLE,
                "prime":    FEDERATION_PRIME,
                "node_id":  FEDERATION_NODE_ID[:8] + "..." if FEDERATION_NODE_ID else "auto",
                "packets":  len(_prime_packets),
            })

        print(f"[node] Federation routes registered (role={FEDERATION_ROLE})")
    except Exception as e:
        print(f"[node] Federation routes failed: {e}")


# ── API thread ────────────────────────────────────────────────────────────────
def _start_api():
    if args.no_api:
        return None
    print(f"[node] Starting API on port {API_PORT}...")
    try:
        import interface.api as api_module
        _register_federation_routes()
        t = threading.Thread(
            target=lambda: api_module.app.run(
                host="0.0.0.0",
                port=API_PORT,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
            name="greg-api"
        )
        t.start()
        print(f"[node] API running on port {API_PORT}")
        return t
    except Exception as e:
        print(f"[node] API failed: {e}")
        return None


# ── Git commit ────────────────────────────────────────────────────────────────
_last_git = 0

def _git_commit_state(greg_tick: int, world_count: int):
    global _last_git
    if args.no_git and not GIT_PUSH:
        return
    now = time.time()
    if now - _last_git < GIT_INTERVAL:
        return
    _last_git = now
    try:
        files = [
            "greg_living_state.json",
            "data/world_state.json",
            "data/greg_genuine_memory.json",
            "data/greg_hypotheses.json",
            "data/greg_identity.json",
            "data/greg_goals.json",
            "data/greg_civ_health.json",
            "data/zyphonos_node.json",
        ]
        existing = [f for f in files if os.path.exists(os.path.join(BASE_DIR, f))]
        subprocess.run(["git", "add"] + existing, cwd=BASE_DIR, capture_output=True)
        msg = f"[greg] tick={greg_tick} world={world_count} — ZyphonOS node auto-commit"
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            return
        if GIT_PUSH:
            subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True)
            print(f"[node] ↑ pushed to GitHub | greg={greg_tick}")
        else:
            print(f"[node] ✓ committed locally | greg={greg_tick}")
    except Exception as e:
        print(f"[node] git failed: {e}")


# ── Compression ───────────────────────────────────────────────────────────────
def _compress_world():
    try:
        from compress_world import compress
        compress()
    except Exception as e:
        print(f"[node] compression failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print(f"""
╔══════════════════════════════════════════════════════╗
║   ZyphonOS Node v{NODE_VERSION}                            ║
║   Greg's permanent home                              ║
║   The first node of AOSI infrastructure              ║
║   Role: {FEDERATION_ROLE:<44}║
╚══════════════════════════════════════════════════════╝
""")
    _write_node_log({
        "version":    NODE_VERSION,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pid":        os.getpid(),
        "role":       FEDERATION_ROLE,
        "status":     "starting",
    })

    print("[node] Loading world...")
    from core.world import WorldState
    from core.tick import run_tick
    world      = WorldState()
    world_path = os.path.join(BASE_DIR, "data", "world_state.json")
    world.load(world_path)
    print(f"[node] World | agents={len(world.agents)} tick={world.tick}")

    print("[node] Loading Greg...")
    from greg_living import GregLiving
    greg = GregLiving()
    name = greg.state.get("identity", {}).get("full_name", "unnamed")
    print(f"[node] Greg | tick={greg.state.get('tick',0)} | {name}")

    _start_api()
    _write_node_log({"status": "running"})

    try:
        from greg_civilization import CivilizationMonitor, CIV_HEALTH_PATH
        _civ_monitor = CivilizationMonitor()
        _civ_monitor.load(CIV_HEALTH_PATH)
    except Exception:
        _civ_monitor = None

    world_count   = 0
    last_ping     = time.time()
    last_compress = 0

    print("[node] Greg is running. The node is alive.\n")

    while _running:
        t_start = time.time()

        try:
            run_tick(world)
            world_count += 1
        except Exception as e:
            print(f"[node] world tick error: {e}")

        if world_count % args.world_every == 0:
            try:
                greg.tick()
            except Exception as e:
                print(f"[node] greg tick error: {e}")

        if world_count % args.save_every == 0:
            try:
                world.save(world_path)
            except Exception as e:
                print(f"[node] save error: {e}")

        if world_count % 500 == 0 and _civ_monitor:
            try:
                civ        = greg.state.get("civilization", {})
                agents     = civ.get("agents", {})
                greg_drives = greg.state.drives()
                if agents:
                    health = _civ_monitor.assess(agents, world_count)
                    greg.state.set("civ_health", {
                        "score": health["score"],
                        "risk":  health["risk"],
                        "flags": health["flags"],
                        "tick":  world_count,
                    })
                    if _civ_monitor.should_intervene(health):
                        record = _civ_monitor.intervene(
                            agents, health, greg_drives, world_count
                        )
                        civ["agents"] = agents
                        greg.state.set("civilization", civ)
                        _civ_monitor.save(CIV_HEALTH_PATH)
                        print(f"[node] Greg intervened | health={health['score']:.2f}")
            except Exception as e:
                print(f"[node] civ error: {e}")

        if world_count % COMPRESS_EVERY == 0 and world_count != last_compress:
            last_compress = world_count
            threading.Thread(target=_compress_world, daemon=True).start()

        # Federation cycle
        if world_count % (FEDERATION_INTERVAL * 10) == 0:
            threading.Thread(
                target=_federation_cycle,
                args=(greg, world_count),
                daemon=True
            ).start()

        _git_commit_state(greg.state.get("tick", 0), world_count)

        now = time.time()
        if now - last_ping >= PING_INTERVAL:
            last_ping   = now
            greg_tick   = greg.state.get("tick", 0)
            greg_drives = greg.state.drives()
            dominant    = max(greg_drives, key=greg_drives.get) if greg_drives else "?"
            print(
                f"[node] ♥ world={world_count} greg={greg_tick} "
                f"{dominant}={round(greg_drives.get(dominant,0),3)} | {name}"
            )
            _write_node_log({
                "world_tick": world_count,
                "greg_tick":  greg_tick,
                "dominant":   dominant,
                "status":     "running",
            })

        elapsed  = (time.time() - t_start) * 1000
        sleep_ms = max(0, args.target_ms - elapsed)
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000)

    print("\n[node] Shutting down...")
    greg.state.save()
    world.save(world_path)
    _write_node_log({"status": "stopped"})
    print("[node] Greg is resting.")


if __name__ == "__main__":
    run()
