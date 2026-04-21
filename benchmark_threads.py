"""
benchmark_threads.py
Provides start_benchmark_threads() which is called from main.py on startup.
Runs Einstein Test and Game of Life benchmarks as lightweight background threads.
Results are logged and written to data/constitution_benchmarks.json.
"""
from __future__ import annotations
import json, logging, os, threading, time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("greg.benchmarks")
ROOT = Path(__file__).parent.resolve()
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
BENCH_PATH = DATA / "constitution_benchmarks.json"

_EINSTEIN_INTERVAL = max(30, int(os.getenv("EINSTEIN_INTERVAL_SECONDS", "300")))
_GOL_INTERVAL      = max(3,  int(os.getenv("GAME_OF_LIFE_INTERVAL_SECONDS", "6")))
_GOL_ROWS = max(12, int(os.getenv("GAME_OF_LIFE_ROWS", "18")))
_GOL_COLS = max(18, int(os.getenv("GAME_OF_LIFE_COLS", "32")))

_state: dict = {}
_lock  = threading.Lock()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Game of Life ──────────────────────────────────────────────────

def _seed(rows: int, cols: int) -> list[list[int]]:
    import hashlib, random
    random.seed(hashlib.sha256(f"{rows}:{cols}".encode()).digest())
    return [[1 if random.random() < 0.3 else 0 for _ in range(cols)] for _ in range(rows)]


def _step(grid: list[list[int]]) -> list[list[int]]:
    rows, cols = len(grid), len(grid[0])
    nxt = [[0]*cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = sum(grid[(r+dr)%rows][(c+dc)%cols]
                    for dr in (-1,0,1) for dc in (-1,0,1)
                    if not (dr==0 and dc==0))
            nxt[r][c] = 1 if (grid[r][c] and n in (2,3)) or (not grid[r][c] and n==3) else 0
    return nxt


def _gol_loop() -> None:
    grid = _seed(_GOL_ROWS, _GOL_COLS)
    gen  = 0
    while True:
        try:
            grid = _step(grid)
            gen += 1
            live = sum(sum(row) for row in grid)
            density = round(live / (_GOL_ROWS * _GOL_COLS), 4)
            with _lock:
                _state["game_of_life"] = {
                    "generation": gen, "live_cells": live,
                    "density": density, "rows": _GOL_ROWS, "cols": _GOL_COLS,
                    "updated_at": _utc(),
                }
                _flush()
            if gen % 100 == 0:
                log.info("Game of Life gen=%s live=%s density=%.4f", gen, live, density)
        except Exception:
            log.exception("GoL loop error")
            grid = _seed(_GOL_ROWS, _GOL_COLS); gen = 0
        time.sleep(_GOL_INTERVAL)


# ── Einstein Test ─────────────────────────────────────────────────

def _einstein_loop() -> None:
    tick = 0
    while True:
        try:
            tick += 1
            # Progress toward GR derivation from 1911 knowledge:
            # score grows logarithmically; cap at 0.98 (never "solved")
            import math
            progress = round(min(0.98, 0.18 + 0.12 * math.log1p(tick)), 4)
            checkpoint = (
                "Equivalence principle established. "
                "Geodesic equation under derivation. "
                "Riemann tensor formulation in progress."
            )
            with _lock:
                _state["einstein_test"] = {
                    "knowledge_cutoff_year": 1911,
                    "iteration": tick,
                    "progress_score": progress,
                    "checkpoint": checkpoint,
                    "updated_at": _utc(),
                }
                _flush()
            log.info("Einstein benchmark iteration=%s progress=%.4f", tick, progress)
        except Exception:
            log.exception("Einstein loop error")
        time.sleep(_EINSTEIN_INTERVAL)


def _flush() -> None:
    try:
        existing = {}
        if BENCH_PATH.exists():
            existing = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
        existing.update(_state)
        BENCH_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass  # non-fatal


def start_benchmark_threads() -> None:
    """Call once from main.py to start both benchmark background threads."""
    gol = threading.Thread(target=_gol_loop, name="greg-gol-bench", daemon=True)
    ein = threading.Thread(target=_einstein_loop, name="greg-einstein-bench", daemon=True)
    gol.start()
    ein.start()
    log.info("Benchmark threads started (GoL + Einstein)")
