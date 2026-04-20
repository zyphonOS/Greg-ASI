from __future__ import annotations

from typing import Any

from constitution_guard import ConstitutionViolation, validate_intent_against_constitution


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

        handler = getattr(self, f"handle_{resolved}", None)
        if not handler:
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

    def handle_think(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        prompt = str((payload or {}).get("prompt") or "").strip()
        if not prompt:
            return {"ok": False, "error": "Prompt required."}, 400

        try:
            import sys
            main_mod = sys.modules.get("main") or sys.modules.get("__main__")
            groq_caller = getattr(main_mod, "call_groq", None)
            if groq_caller is None:
                from main import call_groq as groq_caller
            response = groq_caller(prompt)
        except Exception as exc:
            return {"ok": False, "error": f"Think failed: {exc}"}, 500

        return {
            "ok": True,
            "action": "think",
            "response": response,
            "tick": getattr(getattr(self.greg, "world", None), "tick", 0),
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
        resource_limit = payload.get("resource_limit")
        if resource_limit is not None and not isinstance(resource_limit, dict):
            resource_limit = None
        try:
            validate_intent_against_constitution(
                f"spawn agent with perspective {perspective}",
                {
                    **payload,
                    "action": "spawn_agent",
                    "description": f"spawn agent with perspective {perspective}",
                },
            )
        except ConstitutionViolation as exc:
            return {"ok": False, "error": str(exc)}, 400
        return {
            "ok": True,
            "action": "spawn_agent",
            "agent": self.greg.spawn_agent(
                perspective,
                archetype=str(payload.get("archetype") or perspective).strip() or perspective,
                current_task=str(payload.get("current_task") or "monitor the ecosystem").strip(),
                reputation=float(payload.get("reputation") or 0.0),
                resource_limit=resource_limit,
            ),
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
