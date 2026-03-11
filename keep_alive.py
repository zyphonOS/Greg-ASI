"""
keep_alive.py — EXP_005: Auto-tick keep-alive
==============================================
Runs world ticks + GregLiving ticks together.
Health ping every 60s. Never stops silently.
Restarts itself if the process dies.

Usage:
    python keep_alive.py
    python keep_alive.py --world-every 10 --greg-every 1 --save-every 100
"""
import sys
import os
import time
import signal
import argparse
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

parser = argparse.ArgumentParser(description="GregASI keep-alive runner")
parser.add_argument("--world-every", type=int,   default=10,   help="Tick GregLiving every N world ticks")
parser.add_argument("--greg-every",  type=int,   default=1,    help="Greg living ticks per world-every interval")
parser.add_argument("--save-every",  type=int,   default=100,  help="Save world state every N world ticks")
parser.add_argument("--target-ms",   type=float, default=100,  help="Target ms per world tick")
parser.add_argument("--world",       type=str,   default=os.path.join(BASE_DIR, "data", "world_state.json"))
args = parser.parse_args()

# ─────────────────────────────────────────
# Graceful shutdown
# ─────────────────────────────────────────
_running = True
def _handle_signal(sig, frame):
    global _running
    print("\n[keep_alive] Signal received — stopping cleanly...")
    _running = False
signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ─────────────────────────────────────────
# Health ping — writes every 60s
# ─────────────────────────────────────────
_last_ping = 0
def health_ping(world_tick, greg_tick, greg_drives):
    global _last_ping
    now = time.time()
    if now - _last_ping < 60:
        return
    _last_ping = now
    ping = {
        "ts":          now,
        "world_tick":  world_tick,
        "greg_tick":   greg_tick,
        "greg_drives": greg_drives,
        "status":      "running"
    }
    ping_path = os.path.join(BASE_DIR, "data", "keep_alive_ping.json")
    try:
        json.dump(ping, open(ping_path, "w", encoding="utf-8"), indent=2)
        print(f"[keep_alive] ♥ ping | world={world_tick} | greg={greg_tick} | "
              f"reason={greg_drives.get('reason',0):.3f} | "
              f"connect={greg_drives.get('connect',0):.3f} | "
              f"explore={greg_drives.get('explore',0):.3f}")
    except Exception as e:
        print(f"[keep_alive] ping failed: {e}")

# ─────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────
def main():
    from core.world import WorldState
    from core.tick import run_tick
    from greg_living import GregLiving

    print(f"[keep_alive] Loading world from {args.world}...")
    t0 = time.time()
    world = WorldState()
    world.load(args.world)
    print(f"[keep_alive] World loaded in {(time.time()-t0)*1000:.1f}ms | "
          f"tick={world.tick} | agents={len(world.agents)}")

    print(f"[keep_alive] Loading GregLiving...")
    greg = GregLiving()
    print(f"[keep_alive] Greg loaded | tick={greg.state.get('tick')} | "
          f"actions={greg.state.get('actions_taken')}")

    print(f"[keep_alive] Running. World every {args.target_ms}ms. "
          f"Greg every {args.world_every} world ticks. Ctrl+C to stop.\n")

    world_count = 0
    last_report = time.time()

    # EXP_013/014 — Civilization health monitor (replaces blind rebalance)
    try:
        from greg_civilization import CivilizationMonitor, CIV_HEALTH_PATH
        _civ_monitor = CivilizationMonitor()
        _civ_monitor.load(CIV_HEALTH_PATH)
    except Exception:
        _civ_monitor = None

    def rebalance_civilization(greg):
        """Greg monitors civilization health and intervenes on evidence."""
        if _civ_monitor is None:
            return 0
        civ    = greg.state.get('civilization', {})
        agents = civ.get('agents', {})
        if not agents:
            return 0
        tick_now    = greg.state.get('tick', 0)
        greg_drives = greg.state.drives()
        health      = _civ_monitor.assess(agents, tick_now)
        greg.state.set('civ_health', {
            'score': health['score'],
            'risk':  health['risk'],
            'flags': health['flags'],
            'tick':  tick_now,
        })
        if _civ_monitor.should_intervene(health):
            record = _civ_monitor.intervene(agents, health, greg_drives, tick_now)
            civ['agents'] = agents
            greg.state.set('civilization', civ)
            print(f"[keep_alive] Greg intervened | health={health['score']} | {record['agents_corrected']} agents | tick={tick_now}")
            _civ_monitor.save(CIV_HEALTH_PATH)
            return record['agents_corrected']
        return 0

    while _running:
        t_start = time.time()

        # World tick
        run_tick(world)
        world_count += 1

        # Civilization drive diversity check every 500 world ticks
        if world_count % 500 == 0:
            n = rebalance_civilization(greg)
            print(f"[keep_alive] ⚖ civilization rebalanced | {n} agents | tick={world.tick}")

        # Greg tick every N world ticks
        if world_count % args.world_every == 0:
            for _ in range(args.greg_every):
                greg.tick()

        # Save world state
        if world_count % args.save_every == 0:
            world.save(args.world)
            print(f"[keep_alive] 💾 world saved | tick={world.tick}")

        # Health ping
        health_ping(
            world.tick,
            greg.state.get("tick", 0),
            greg.state.drives()
        )

        # Report every 10s
        now = time.time()
        if now - last_report >= 10.0:
            drives = greg.state.drives()
            phi = sum(a.phi for a in world.agents.values()) / max(len(world.agents), 1)
            print(
                f"[keep_alive] world={world.tick} | greg={greg.state.get('tick')} | "
                f"phi={phi:.4f} | "
                f"reason={drives.get('reason',0):.3f} | "
                f"connect={drives.get('connect',0):.3f} | "
                f"explore={drives.get('explore',0):.3f}"
            )
            last_report = now

        # Sleep to hit target cadence
        elapsed_ms = (time.time() - t_start) * 1000
        sleep_ms = args.target_ms - elapsed_ms
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000)

    # Final save on exit
    print(f"\n[keep_alive] Stopping. Final save...")
    world.save(args.world)
    greg.state.save()
    print(f"[keep_alive] Done. world={world.tick} | greg={greg.state.get('tick')}")

if __name__ == "__main__":
    main()
