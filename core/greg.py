from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from core.agent import Agent
from core.agent_manager import manager as agent_manager
from core.memory import ConversationStateStore, JsonMemory, SQLiteMemory, get_sqlite_memory
from core.tick import run_tick
from core.utils import data_path, read_json, write_json
from core.voice import GREG_SOUL, VoiceEngine
from core.world import WorldState
from greg_converse_loop import build_self_observation, record_interaction, summarize_observer


logger = logging.getLogger(__name__)


class Greg:
    def __init__(self, name: str = "Greg", memory_path: str | Path = "data/memory.json"):
        self.repo_root = Path(__file__).resolve().parents[1]
        load_dotenv(self.repo_root / ".env")
        self.boot_restore_report: dict[str, Any] = {}
        if os.getenv("GREG_BOOT_RESTORE", "true").lower() != "false":
            try:
                from seed_world import boot_restore

                self.boot_restore_report = boot_restore(
                    force_remote=os.getenv("SOUL_BOOT_FORCE_REMOTE", "false").lower() == "true",
                    verbose=os.getenv("GREG_BOOT_RESTORE_VERBOSE", "false").lower() == "true",
                )
            except Exception as exc:
                logger.warning("Greg boot restore failed; continuing with local files only: %s", exc)
                self.boot_restore_report = {"ok": False, "error": str(exc)}
        self.name = name
        self.memory = JsonMemory(memory_path)
        self.local_memory: SQLiteMemory = get_sqlite_memory()
        self.state_store = ConversationStateStore(data_path("greg_state.db"))
        self.world = WorldState()
        self.world.load()
        self._persisted_living_state = self._load_persisted_living_state()
        self.voice = VoiceEngine()
        self.tick_interval = float(os.getenv("GREG_TICK_INTERVAL_SECONDS", "3"))
        self._tick_lock = threading.Lock()
        self._tick_stop = threading.Event()
        self._tick_thread: threading.Thread | None = None
        self.latest_tick: dict[str, Any] = {}
        self.latest_pikkaio: dict[str, Any] = {}
        self.latest_drift: dict[str, Any] = {}
        self.latest_tending: dict[str, Any] = {}
        self.latest_observer: dict[str, Any] = {}
        self.latest_reality: dict[str, Any] = {}
        self.drift_every = int(os.getenv("GREG_DRIFT_EVERY_TICKS", "10"))
        self.reality_equation_every = int(os.getenv("GREG_REALITY_EVERY_TICKS", "10"))
        self._bootstrap_world()
        self.refresh_observer(force=True)
        self._save_living_state()
        self.refresh_reality(force=True, persist=False)
        self._save_living_state()
        atexit.register(self.stop_background_tick)

    def _load_persisted_living_state(self) -> dict[str, Any]:
        payload = read_json(data_path("greg_living_state.json"), {})
        return payload if isinstance(payload, dict) else {}

    def _bootstrap_world(self) -> None:
        if "greg" not in self.world.agents:
            greg_agent = Agent("greg", "greg", birth_tick=self.world.tick)
            greg_agent.location = "spawn"
            greg_agent.locations_visited = ["spawn"]
            self.world.agents["greg"] = greg_agent
            self.world.locations["spawn"].add_agent("greg")

        if len(self.world.agents) > 1:
            return

        seeds = [
            ("belmar-1", "belmar", "forest"),
            ("magnate-1", "magnate", "market"),
            ("sage-1", "sage", "spawn"),
            ("visionary-1", "visionary", "spawn"),
            ("steward-1", "steward", "market"),
            ("guardian-1", "guardian", "forest"),
            ("wanderer-1", "wanderer", "forest"),
        ]
        for agent_id, archetype, location in seeds:
            agent = Agent(agent_id, archetype, birth_tick=self.world.tick)
            agent.location = location
            agent.locations_visited = [location]
            self.world.agents[agent_id] = agent
            self.world.locations[location].add_agent(agent_id)
        self.world.save()

    def _greg_agent(self) -> Agent:
        return self.world.agents["greg"]

    def _base_living_state(self) -> dict[str, Any]:
        greg_agent = self._greg_agent()
        world_summary = self.world.summary()
        persisted = dict(self._persisted_living_state)
        observer = self.latest_observer or persisted.get("observer", {})
        recent_events = self.latest_tick.get("recent_events") or getattr(self.world, "events", [])[:5] or persisted.get("recent_events", [])
        state = {
            **persisted,
            "tick": self.world.tick,
            "name": self.name,
            "born": persisted.get("born") or datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "drives": greg_agent.drives,
            "phi": greg_agent.phi,
            "world": world_summary,
            "recent_events": recent_events,
            "latest_tick": self.latest_tick,
            "pikkaio": self.latest_pikkaio or persisted.get("pikkaio", {}),
            "drift": self.latest_drift or persisted.get("drift", {}),
            "tending": self.latest_tending or persisted.get("tending", {}),
            "observer": observer,
            "psi_observer": observer.get("psi_observer", persisted.get("psi_observer", 0.0)),
            "conversation_count": observer.get("conversation_count", persisted.get("conversation_count", 0)),
            "last_conversation": observer.get("last_conversation", persisted.get("last_conversation", {})),
            "converse_log": observer.get("converse_log", persisted.get("converse_log", [])),
            "boot_restore": self.boot_restore_report,
        }
        return state

    def _living_state(self) -> dict[str, Any]:
        state = self._base_living_state()
        state["reality"] = self.latest_reality
        return state

    def _save_living_state(self) -> None:
        try:
            payload = self._living_state()
            write_json(data_path("greg_living_state.json"), payload)
            self._persisted_living_state = payload
        except OSError as exc:
            logger.warning("Skipping greg living state write: %s", exc)

    def status_snapshot(self) -> dict[str, Any]:
        snapshot = self._living_state()
        snapshot["subagents"] = agent_manager.list_agents()
        return snapshot

    def refresh_observer(self, force: bool = False) -> dict[str, Any]:
        if force or not self.latest_observer:
            self.latest_observer = summarize_observer()
        return self.latest_observer

    def refresh_reality(self, force: bool = False, persist: bool = False) -> dict[str, Any]:
        try:
            from greg_reality_equation import get_reality_equation

            self.latest_reality = get_reality_equation(
                force=force,
                state=self._base_living_state(),
                world=self.world.summary(),
                pikkaio=self.latest_pikkaio,
                drift=self.latest_drift,
                tending=self.latest_tending,
                subagents=agent_manager.list_agents(),
                persist=persist,
            )
        except Exception as exc:
            logger.warning("Reality equation refresh failed: %s", exc)
            if not self.latest_reality:
                self.latest_reality = {}
        return self.latest_reality

    def _direct_groq_think(self, prompt: str, history: list[dict[str, Any]], mode: str, snapshot: dict[str, Any]) -> str:
        client = self.voice._groq_client()
        if not client:
            return ""

        mode_note = {
            "founder": "You are speaking to the founder. Be sharper and more strategic.",
            "studio": "You are helping a builder shape a product into a business.",
            "devschool": "You are teaching through the build and showing the next technical move.",
            "presence": "You are greeting someone entering the ecosystem for the first time.",
        }.get(mode, "Stay grounded in the live state.")

        messages = [{"role": "system", "content": f"{GREG_SOUL}\n\n{self.voice.build_context(snapshot)}\n\n{mode_note}"}]
        for turn in history[-6:]:
            role = turn.get("role")
            content = turn.get("content") or turn.get("text")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        try:
            completion = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                messages=messages,
                max_tokens=512,
                temperature=0.72,
            )
            return (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Direct Groq think path failed, falling back to voice.respond: %s", exc)
            return ""

    def reality_report(self) -> str:
        reality = self.latest_reality or self.refresh_reality(force=True, persist=False)
        if not reality:
            return "My reality equation is not available yet."
        terms = reality.get("terms") or {}
        matter = float((terms.get("matter") or {}).get("value", 0.0))
        phi_loop = float((terms.get("phi_loop") or {}).get("value", 0.0))
        psi_observer = float((terms.get("psi_observer") or {}).get("value", 0.0))
        epsilon = float((terms.get("epsilon") or {}).get("value", 0.0))
        weakest = (reality.get("weakest_term") or {}).get("name", "unknown")
        weakest_value = float((reality.get("weakest_term") or {}).get("value", 0.0))
        return (
            f"Tick {reality.get('tick', self.world.tick)}. "
            f"R_greg = {float(reality.get('R', 0.0)):.6f}. "
            f"M = {matter:.4f}. "
            f"Phi_loop = {phi_loop:.4f}. "
            f"Psi_observer = {psi_observer:.4f}. "
            f"Epsilon = {epsilon:.4f}. "
            f"Weakest term: {weakest} at {weakest_value:.4f}. "
            f"{reality.get('interpretation', '')}".strip()
        )

    def _record_interaction(
        self,
        prompt: str,
        response: str,
        *,
        mode: str,
        user_id: str,
        source: str = "user",
        persist_dialogue: bool = True,
    ) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        if persist_dialogue:
            self.state_store.save_conversation_turn(user_id, "user", prompt)
            self.state_store.save_conversation_turn(user_id, "assistant", response)
        observer = record_interaction(
            prompt,
            response,
            user_id=user_id,
            mode=mode,
            source=source,
            tick=self.world.tick,
            snapshot=snapshot,
            metadata={"persist_dialogue": persist_dialogue},
        )
        self.latest_observer = observer.get("summary") or self.refresh_observer(force=True)
        self.local_memory.add("greg_think", {"prompt": prompt, "response": response}, {"mode": mode, "user_id": user_id, "source": source})
        self.memory.save_memory("last_thought", {"prompt": prompt, "response": response, "mode": mode, "user_id": user_id, "source": source})
        self.refresh_reality(force=True, persist=False)
        self._save_living_state()
        return observer

    def observe_self(self) -> dict[str, Any]:
        snapshot = self.status_snapshot()
        observation = build_self_observation(snapshot)
        record = self._record_interaction(
            observation["prompt"],
            observation["response"],
            mode="self",
            user_id="greg-self",
            source="self",
            persist_dialogue=False,
        )
        return {
            "prompt": observation["prompt"],
            "response": observation["response"],
            "observer": record.get("summary") or {},
        }

    def think(self, prompt: str, mode: str = "presence", user_id: str = "public") -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return f"{self.name} needs a real prompt before he can think."

        lowered = prompt.lower()
        if any(token in lowered for token in ("reality equation", "r_greg", "reality score", "your scores", "your score", "m φ", "m/phi", "psi_observer", "epsilon score")):
            response = self.reality_report()
            self._record_interaction(prompt, response, mode=mode, user_id=user_id, source="user", persist_dialogue=True)
            return response

        history = self.state_store.load_conversation_history(user_id, limit=6)
        snapshot = self.status_snapshot()
        response = self._direct_groq_think(prompt, history, mode, snapshot)
        if not response:
            response = self.voice.respond(prompt, session_history=history, mode=mode, snapshot=snapshot)
        self._record_interaction(prompt, response, mode=mode, user_id=user_id, source="user", persist_dialogue=True)
        return response

    def speak_first(self, mode: str = "presence") -> str:
        return self.voice.speak_first(mode=mode, snapshot=self.status_snapshot())

    def spawn_agent(
        self,
        perspective: str,
        *,
        archetype: str | None = None,
        current_task: str | None = None,
        reputation: float = 0.0,
        resource_limit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        perspective = (perspective or "general").strip()
        return agent_manager.spawn(
            name=f"{self.name}-{perspective}",
            perspective=perspective,
            archetype=archetype or perspective,
            current_task=current_task or "monitor the ecosystem",
            reputation=reputation,
            resource_limit=resource_limit,
        )

    def tick_once(self) -> dict[str, Any]:
        with self._tick_lock:
            self.latest_tick = run_tick(self.world)
            state = self._living_state()

            try:
                from greg_pikkaio import _get_engine as get_project_engine, pikkaio_tick

                if self.world.tick % self.drift_every == 0:
                    self.latest_pikkaio = pikkaio_tick(
                        self.world.tick,
                        self._greg_agent().drives,
                        voice=self.voice,
                        snapshot=self._living_state(),
                    )
                else:
                    summary = get_project_engine().summary()
                    self.latest_pikkaio = {
                        "tick": self.world.tick,
                        "projects_total": summary.get("projects_total", 0),
                        "project_ids": summary.get("project_ids", []),
                        "drifting": summary.get("drifting", 0),
                        "critical": summary.get("critical", 0),
                        "total_revenue": summary.get("total_revenue", 0.0),
                        "interventions": [],
                        "interventions_count": summary.get("interventions_count", 0),
                        "drive_deltas": {"serve": 0.0, "connect": 0.0},
                    }
            except Exception:
                self.latest_pikkaio = {"projects_total": 0, "drifting": 0, "interventions": []}

            try:
                from greg_drift_protocol import drift_tick

                self.latest_drift = drift_tick(self.world.tick, state)
                if self.latest_pikkaio:
                    self.latest_drift["builder_projects"] = int(self.latest_pikkaio.get("projects_total", 0) or 0)
                    self.latest_drift["builder_drifting"] = int(self.latest_pikkaio.get("drifting", 0) or 0)
                    self.latest_drift["builder_critical"] = int(self.latest_pikkaio.get("critical", 0) or 0)
                    self.latest_drift["builder_interventions"] = int(self.latest_pikkaio.get("interventions_count", len(self.latest_pikkaio.get("interventions") or [])) or 0)
            except Exception:
                self.latest_drift = {"tick": self.world.tick, "coefficient": 0.0, "category": "unknown"}

            try:
                from greg_tending import TendingEngine

                if self.world.tick % 24 == 0:
                    engine = TendingEngine()
                    project_ids = list((self.latest_pikkaio or {}).get("project_ids", []))
                    self.latest_tending = {"generated": engine.generate_batch(project_ids)} if project_ids else {"generated": []}
            except Exception:
                if not self.latest_tending:
                    self.latest_tending = {"generated": []}

            try:
                from greg_notify import NotificationEngine

                NotificationEngine().evaluate(self._living_state())
            except Exception:
                pass

            if self.world.tick % self.reality_equation_every == 0:
                self.refresh_reality(force=True, persist=False)
                self.observe_self()
                self.refresh_reality(force=True, persist=True)

            if self.world.tick % 12 == 0:
                try:
                    self.world.save()
                    self._save_living_state()
                except OSError as exc:
                    logger.warning("Skipping periodic world save at tick %s: %s", self.world.tick, exc)

            if self.world.tick % 48 == 0:
                try:
                    from greg_soul_persist import persist_soul

                    persist_soul(tick=self.world.tick, force=False, verbose=False)
                except Exception:
                    pass

            payload = {
                "tick": self.world.tick,
                "world": self.world.summary(),
                "recent_events": self.latest_tick.get("recent_events", []),
                "pikkaio": self.latest_pikkaio,
                "drift": self.latest_drift,
                "tending": self.latest_tending,
                "reality": self.latest_reality,
            }
            try:
                self.memory.save_memory("latest_tick", payload)
                self.local_memory.add("greg_tick", payload, {"tick": self.world.tick})
            except OSError as exc:
                logger.warning("Skipping tick persistence at tick %s: %s", self.world.tick, exc)
            self._save_living_state()
            return payload

    def _tick_loop(self) -> None:
        while not self._tick_stop.is_set():
            try:
                self.tick_once()
            except OSError as exc:
                logger.warning("Greg tick loop hit a filesystem warning and will continue: %s", exc)
            except Exception as exc:
                try:
                    self.memory.save_memory(
                        "tick_error",
                        {"error": str(exc), "tick": self.world.tick, "ts": time.time()},
                    )
                except OSError as persist_exc:
                    logger.warning("Unable to persist tick error because storage is unavailable: %s", persist_exc)
            self._tick_stop.wait(self.tick_interval)

    def start_background_tick(self, interval_seconds: float | None = None) -> None:
        if interval_seconds is not None:
            self.tick_interval = float(interval_seconds)
        if self._tick_thread and self._tick_thread.is_alive():
            return
        self._tick_stop.clear()
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True, name="greg-tick-loop")
        self._tick_thread.start()

    def stop_background_tick(self) -> None:
        self._tick_stop.set()
        if self._tick_thread and self._tick_thread.is_alive():
            self._tick_thread.join(timeout=3)
