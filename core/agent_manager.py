from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.utils import agents_path, data_path, ensure_directory, read_json, write_json


AGENTS_STATE_PATH = data_path("agents_state.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ManagedAgent:
    agent_id: str
    name: str
    perspective: str
    thread: threading.Thread
    stop_event: threading.Event


class AgentManager:
    def __init__(self, agents_dir: str | Path | None = None, state_path: str | Path | None = None):
        self.agents_dir = Path(agents_dir) if agents_dir else agents_path()
        self.state_path = Path(state_path) if state_path else AGENTS_STATE_PATH
        ensure_directory(self.agents_dir)
        write_json(self.state_path, read_json(self.state_path, {}))
        self._agents: dict[str, ManagedAgent] = {}
        self._lock = threading.Lock()

    def _agent_file(self, agent_id: str) -> Path:
        return self.agents_dir / f"{agent_id}.json"

    def _persist(self, agent_id: str, payload: dict[str, Any]) -> None:
        write_json(self._agent_file(agent_id), payload)
        state = read_json(self.state_path, {})
        state[agent_id] = payload
        write_json(self.state_path, state)

    def spawn(
        self,
        name: str,
        perspective: str,
        *,
        archetype: str | None = None,
        current_task: str | None = None,
        reputation: float = 0.0,
        resource_limit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agent_id = uuid.uuid4().hex[:12]
        stop_event = threading.Event()
        clean_archetype = str(archetype or perspective or "general").strip() or "general"
        clean_task = str(current_task or "monitor the ecosystem").strip() or "monitor the ecosystem"
        base_state = {
            "agent_id": agent_id,
            "name": name,
            "perspective": perspective,
            "archetype": clean_archetype,
            "status": "starting",
            "started_at": utc_now(),
            "last_seen": utc_now(),
            "heartbeat": 0,
            "reputation": round(float(reputation or 0.0), 4),
            "resource_limit": resource_limit or {"cpu": 1, "api_tokens": 1000, "budget_usdc": 0},
            "current_task": clean_task,
            "latest_note": f"{name} is booting with the '{perspective}' perspective.",
        }
        self._persist(agent_id, base_state)

        def worker() -> None:
            heartbeat = 0
            while not stop_event.is_set():
                heartbeat += 1
                self._persist(
                    agent_id,
                    {
                        **base_state,
                        "status": "running",
                        "heartbeat": heartbeat,
                        "last_seen": utc_now(),
                        "latest_note": (
                            f"{name} is watching the ecosystem from the '{perspective}' perspective "
                            "and keeping a lightweight heartbeat."
                        ),
                    },
                )
                stop_event.wait(2.0)

            self._persist(
                agent_id,
                {
                    **base_state,
                    "status": "stopped",
                    "last_seen": utc_now(),
                    "latest_note": f"{name} stopped cleanly.",
                },
            )

        thread = threading.Thread(target=worker, daemon=True, name=f"greg-agent-{agent_id}")
        managed = ManagedAgent(agent_id=agent_id, name=name, perspective=perspective, thread=thread, stop_event=stop_event)
        with self._lock:
            self._agents[agent_id] = managed
        thread.start()
        return {
            "agent_id": agent_id,
            "name": name,
            "perspective": perspective,
            "archetype": clean_archetype,
            "status": "running",
            "reputation": round(float(reputation or 0.0), 4),
            "resource_limit": resource_limit or {"cpu": 1, "api_tokens": 1000, "budget_usdc": 0},
            "current_task": clean_task,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        state = read_json(self.state_path, {})
        rows = list(state.values()) if isinstance(state, dict) else []
        return sorted(rows, key=lambda item: item.get("last_seen", ""), reverse=True)

    def stop_agent(self, agent_id: str) -> bool:
        with self._lock:
            managed = self._agents.get(agent_id)
        if not managed:
            state = read_json(self.state_path, {})
            if agent_id in state:
                state[agent_id]["status"] = "stopped"
                state[agent_id]["last_seen"] = utc_now()
                write_json(self.state_path, state)
                return True
            return False

        managed.stop_event.set()
        managed.thread.join(timeout=3)
        with self._lock:
            self._agents.pop(agent_id, None)
        return True

    def stop_all(self) -> None:
        for agent_id in list(self._agents):
            self.stop_agent(agent_id)


manager = AgentManager()
