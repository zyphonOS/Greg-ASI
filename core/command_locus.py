from __future__ import annotations

from typing import Any


class CommandLocus:
    """Authoritative command surface for Greg actions."""

    def __init__(self, greg: Any, agent_manager: Any):
        self.greg = greg
        self.agent_manager = agent_manager
        self._aliases = {
            "ask": "think",
            "message": "think",
            "say": "think",
            "hello": "speak_first",
            "spawn": "spawn_agent",
            "stop": "stop_agent",
        }

    def _normalize_action(self, action: str | None) -> str:
        raw = str(action or "").strip().lower().replace("-", "_")
        return self._aliases.get(raw, raw)

    def dispatch(self, action: str | None, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
        payload = payload or {}
        resolved = self._normalize_action(action)
        if not resolved:
            return {"ok": False, "error": "Action required."}, 400

        handler = getattr(self, f"_action_{resolved}", None)
        if not handler:
            return {
                "ok": False,
                "error": f"Unknown action: {resolved}",
                "available_actions": [
                    "think",
                    "speak_first",
                    "tick",
                    "spawn_agent",
                    "stop_agent",
                ],
            }, 400
        return handler(payload)

    def _action_think(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        prompt = str(payload.get("prompt") or "").strip()
        mode = str(payload.get("mode") or "presence").strip() or "presence"
        user_id = str(payload.get("user_id") or "public").strip() or "public"
        if not prompt:
            return {"ok": False, "error": "Prompt required."}, 400
        return {
            "ok": True,
            "action": "think",
            "response": self.greg.think(prompt, mode=mode, user_id=user_id),
            "tick": self.greg.world.tick,
        }, 200

    def _action_speak_first(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        mode = str(payload.get("mode") or "presence").strip() or "presence"
        return {
            "ok": True,
            "action": "speak_first",
            "response": self.greg.speak_first(mode=mode),
            "tick": self.greg.world.tick,
        }, 200

    def _action_tick(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        return {
            "ok": True,
            "action": "tick",
            "result": self.greg.tick_once(),
            "tick": self.greg.world.tick,
        }, 200

    def _action_spawn_agent(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        perspective = str(payload.get("perspective") or "general").strip() or "general"
        return {
            "ok": True,
            "action": "spawn_agent",
            "agent": self.greg.spawn_agent(perspective),
            "tick": self.greg.world.tick,
        }, 200

    def _action_stop_agent(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        agent_id = str(payload.get("agent_id") or "").strip()
        if not agent_id:
            return {"ok": False, "error": "agent_id required."}, 400
        stopped = self.agent_manager.stop_agent(agent_id)
        if not stopped:
            return {"ok": False, "error": "Agent not found."}, 404
        return {
            "ok": True,
            "action": "stop_agent",
            "agent_id": agent_id,
            "tick": self.greg.world.tick,
        }, 200
