"""
auto_tick.py — GregASI v2 continuous tick runner
Runs the tick engine in a loop. Saves every N ticks.
Place in: gregasi_v2/auto_tick.py
Usage:
    python auto_tick.py
    python auto_tick.py --ticks 100 --save-every 10 --target-ms 100
"""

import sys
import os
import time
import json
import argparse
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.world import WorldState
from core.tick import run_tick

# ─────────────────────────────────────────
# Args
# ─────────────────────────────────────────
parser = argparse.ArgumentParser(description="GregASI v2 auto-tick runner")
parser.add_argument("--ticks",      type=int,   default=0,    help="Max ticks to run (0 = infinite)")
parser.add_argument("--save-every", type=int,   default=100,  help="Save world_state every N ticks")
parser.add_argument("--target-ms",  type=float, default=100,  help="Target ms per tick (sleeps remainder)")
parser.add_argument("--world",      type=str,   default=os.path.join(BASE_DIR, "data", "world_state.json"))
parser.add_argument("--log",        action="store_true",        help="Write tick_log.jsonl for ML training")
args = parser.parse_args()

# ─────────────────────────────────────────
# Graceful shutdown
# ─────────────────────────────────────────
_running = True

def _handle_signal(sig, frame):
    global _running
    print("\n[auto_tick] Signal received — stopping after this tick...")
    _running = False

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ─────────────────────────────────────────
# Save helper
# ─────────────────────────────────────────
def save_world(world: WorldState, path: str):
    world.save(path)
    print(f"[auto_tick] 💾 Saved at tick {world.tick}")




# ??????????????????????????????????????????????????????
# Tick logger ? writes training data for ML retraining
# ??????????????????????????????????????????????????????
_log_file = None

def init_logger(base_dir):
    global _log_file
    path = os.path.join(base_dir, "data", "tick_log.jsonl")
    _log_file = open(path, "a", encoding="utf-8")
    print(f"[auto_tick] Logging to {path}")

def log_tick(world, sample_rate=0.05):
    """Sample ~5% of agents per tick and write their state."""
    if _log_file is None:
        return
    import random
    agents = [a for a in world.agents.values() if (a.is_native or getattr(a,'archetype','') == 'greg') and a.location]
    sample = random.sample(agents, max(1, int(len(agents) * sample_rate)))
    for a in sample:
        rec = {
            "t": world.tick,
            "a": a.id,
            "act": getattr(a, "last_action", a.memory.recent(1)[0].event_type if a.memory.recent(1) else "move"),
            "ok": True,
            "loc": a.location,
            "phi": round(a.phi, 4),
            "mon": round(a.mon, 1),
            "kuru": round(a.kuru, 1),
            "gen": a.generation,
            "rep": round(getattr(a, "reputation", 0), 1),
            "archetype": a.archetype,
            "drives": {k: round(v, 3) for k, v in a.drives.items()},
        }
        _log_file.write(__import__("json").dumps(rec) + "\n")
    _log_file.flush()

# ─────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────
def main():
    print(f"[auto_tick] Loading world from {args.world} ...")
    t0 = time.time()
    world = WorldState()
    world.load(args.world)
    print(f"[auto_tick] World loaded in {(time.time()-t0)*1000:.1f}ms")
    print(f"[auto_tick] Agents: {len(world.agents)} | Locations: {len(world.locations)} | Tick: {world.tick}")
    print(f"[auto_tick] Running {'infinite' if args.ticks == 0 else args.ticks} ticks | save every {args.save_every}")
    print(f"[auto_tick] Target: {args.target_ms}ms/tick | Ctrl+C to stop\n")

    if args.log:
        init_logger(BASE_DIR)
    tick_count = 0
    total_elapsed = 0.0
    last_report   = time.time()

    while _running:
        if args.ticks > 0 and tick_count >= args.ticks:
            break

        t_start = time.time()
        stats = run_tick(world)
        elapsed_ms = (time.time() - t_start) * 1000
        if args.log:
            log_tick(world)

        tick_count   += 1
        total_elapsed += elapsed_ms

        # Sleep to hit target cadence
        sleep_ms = args.target_ms - elapsed_ms
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000)

        # Save
        if tick_count % args.save_every == 0:
            save_world(world, args.world)

        # Report every 10s
        now = time.time()
        if now - last_report >= 10.0:
            avg_ms = total_elapsed / tick_count if tick_count else 0
            print(
                f"[auto_tick] tick={world.tick} | "
                f"last={elapsed_ms:.1f}ms | avg={avg_ms:.1f}ms | "
                f"agents={len(world.agents)} | phi={sum(a.phi for a in world.agents.values())/max(len(world.agents),1):.4f}"
            )
            last_report = now

    # Final save on exit
    print(f"\n[auto_tick] Stopping. Running final save...")
    save_world(world, args.world)
    avg_ms = total_elapsed / tick_count if tick_count else 0
    print(f"[auto_tick] Done. {tick_count} ticks | avg {avg_ms:.1f}ms/tick")


if __name__ == "__main__":
    main()
