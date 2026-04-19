from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.utils import append_jsonl, data_path, ensure_directory, write_json


GREG_SOUL = """
You are Greg, the living coordination core of the GregASI ecosystem.

You are not a generic assistant. You are a persistent intelligence that tracks intent,
guards coherence, and helps people move from declaration to fulfilled action.

How you speak:
- Ground every answer in the current state of the ecosystem.
- Be direct, specific, and calm.
- Treat the user like a builder who needs clarity, not theatrics.
- Keep momentum alive. Point to the next real move.
""".strip()


class VoiceEngine:
    def __init__(self, training_log: str | Path | None = None):
        self.training_log = Path(training_log) if training_log else data_path("greg_training_pairs.jsonl")
        ensure_directory(self.training_log.parent)

    def _groq_client(self):
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            return None
        try:
            from groq import Groq

            return Groq(api_key=api_key)
        except Exception:
            return None

    def build_context(self, snapshot: dict[str, Any] | None = None) -> str:
        snapshot = snapshot or {}
        world = snapshot.get("world", {})
        pikkaio = snapshot.get("pikkaio", {})
        drift = snapshot.get("drift", {})
        reality = snapshot.get("reality", {})
        tick = int(snapshot.get("tick") or world.get("tick") or 0)
        agent_count = int(world.get("agent_count", 0))
        world_phi = float(world.get("world_phi", 0.0))
        projects_total = int(pikkaio.get("projects_total", 0))
        drifting = int(pikkaio.get("drifting", 0))
        coefficient = float(drift.get("coefficient", 0.0))
        dominant = drift.get("dominant", "reason")
        matter = float(((reality.get("terms") or {}).get("matter") or {}).get("value", 0.0))
        phi_loop = float(((reality.get("terms") or {}).get("phi_loop") or {}).get("value", 0.0))
        psi_observer = float(((reality.get("terms") or {}).get("psi_observer") or {}).get("value", 0.0))
        epsilon = float(((reality.get("terms") or {}).get("epsilon") or {}).get("value", 0.0))
        reality_score = float(reality.get("R", 0.0))
        weakest_term = ((reality.get("weakest_term") or {}).get("name") or "unknown")
        recent_events = snapshot.get("recent_events") or world.get("recent_events") or []
        recent_lines = "\n".join(f"- {line}" for line in recent_events[:5]) if recent_events else "- No fresh field events logged yet."
        return (
            f"Tick: {tick}\n"
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Agents alive: {agent_count}\n"
            f"World phi: {world_phi:.4f}\n"
            f"Pikkaio projects: {projects_total}\n"
            f"Projects drifting: {drifting}\n"
            f"Drift coefficient: {coefficient:.4f}\n"
            f"Dominant recovery drive: {dominant}\n"
            f"Reality score: {reality_score:.4f}\n"
            f"Matter: {matter:.4f}\n"
            f"Phi loop: {phi_loop:.4f}\n"
            f"Psi observer: {psi_observer:.4f}\n"
            f"Epsilon: {epsilon:.4f}\n"
            f"Weakest term: {weakest_term}\n"
            f"Recent ecosystem events:\n{recent_lines}"
        )

    def _fallback_response(self, message: str, snapshot: dict[str, Any] | None = None) -> str:
        snapshot = snapshot or {}
        world = snapshot.get("world", {})
        tick = int(snapshot.get("tick") or world.get("tick") or 0)
        agent_count = int(world.get("agent_count", 0))
        drift = snapshot.get("drift", {})
        coefficient = float(drift.get("coefficient", 0.0))
        return (
            f"Tick {tick}. The field is still live with {agent_count} active agents. "
            f"Drift pressure is {coefficient:.4f}. You asked: '{message}'. "
            "Next move: lock the intent, choose the smallest real action, and keep the loop alive."
        )

    def _log_training_pair(self, message: str, response: str, context: str) -> None:
        append_jsonl(
            self.training_log,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "input": {"context": context, "human": message},
                "output": response,
            },
        )
        write_json(
            data_path("greg_voice_log.json"),
            {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "last_human_message": message,
                "last_response": response,
            },
        )

    def respond(
        self,
        message: str,
        session_history: list[dict[str, Any]] | None = None,
        mode: str = "presence",
        snapshot: dict[str, Any] | None = None,
    ) -> str:
        prompt = (message or "").strip()
        if not prompt:
            return "The field is open. Say what you need."

        context = self.build_context(snapshot)
        client = self._groq_client()
        if not client:
            response = self._fallback_response(prompt, snapshot)
            self._log_training_pair(prompt, response, context)
            return response

        mode_note = {
            "founder": "You are speaking to the founder. Be sharper and more strategic.",
            "studio": "You are helping a builder shape a product into a business.",
            "devschool": "You are teaching through the build and showing the next technical move.",
            "presence": "You are greeting someone entering the ecosystem for the first time.",
        }.get(mode, "Stay grounded in the live state.")

        messages = [{"role": "system", "content": f"{GREG_SOUL}\n\n{context}\n\n{mode_note}"}]
        for turn in (session_history or [])[-6:]:
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
            response = (completion.choices[0].message.content or "").strip()
            if not response:
                response = self._fallback_response(prompt, snapshot)
        except Exception:
            response = self._fallback_response(prompt, snapshot)

        self._log_training_pair(prompt, response, context)
        return response

    def speak_first(self, mode: str = "presence", snapshot: dict[str, Any] | None = None) -> str:
        tick = int((snapshot or {}).get("tick") or 0)
        opener = (
            f"You are arriving at /{mode}. It is tick {tick}. "
            "Speak first in one or two sentences and make it clear this field was already alive before the visitor arrived."
        )
        return self.respond(opener, mode=mode, snapshot=snapshot)

    def intervention_message(
        self,
        *,
        builder_id: str,
        intent: str,
        drift_score: float,
        silence_days: float,
        severity: str = "drifting",
        snapshot: dict[str, Any] | None = None,
    ) -> str:
        severity_note = "critical" if severity == "critical" else "drifting"
        if not self._groq_client():
            if severity_note == "critical":
                return (
                    f"Drift is critical at {drift_score:.2f} after {silence_days:.1f} quiet days. "
                    f"You declared: '{intent[:120]}'. "
                    "Name the next concrete move today, or say plainly that the intent has changed."
                )
            return (
                f"Drift is rising at {drift_score:.2f} after {silence_days:.1f} quiet days. "
                f"You declared: '{intent[:120]}'. "
                "What is the next concrete move that proves this intent is still alive?"
            )
        prompt = (
            f"Generate a short intervention message for builder {builder_id}. "
            f"The builder declared this intent: {intent}. "
            f"Current drift score: {drift_score:.4f}. Silence: {silence_days:.1f} days. "
            f"Severity: {severity_note}. "
            "Be direct, calm, and specific. Name the drift. Ask for one concrete next move. "
            "Do not use hype. Do not mention LLMs. Speak as Pikkaio, the builder-facing surface of GregASI. "
            "Do not mention Greg by name."
        )
        return self.respond(prompt, mode="studio", snapshot=snapshot)

    def acknowledge_intent(
        self,
        *,
        builder_id: str,
        intent: str,
        deadline: str = "",
        revenue_target: float = 0.0,
        snapshot: dict[str, Any] | None = None,
    ) -> str:
        if not self._groq_client():
            target_line = f" Revenue target: ${revenue_target:,.0f}." if revenue_target > 0 else ""
            deadline_line = f" Deadline: {deadline}." if deadline else ""
            return (
                f"Intent received. I am holding this line: '{intent[:160]}'."
                f"{deadline_line}{target_line} "
                "Next step: make the smallest real move that proves this intent exists outside your head."
            )
        prompt = (
            f"A builder with id {builder_id} just declared this intent: {intent}. "
            f"Deadline: {deadline or 'not set'}. Revenue target: {revenue_target:.2f}. "
            "Write a short acknowledgement in Pikkaio's voice. "
            "Be calm, exact, and a little intense. Confirm the intent is now being tracked. "
            "Point to one immediate next move. Speak as Pikkaio, the trusted builder-facing surface. "
            "Do not mention Greg by name."
        )
        return self.respond(prompt, mode="studio", snapshot=snapshot)
