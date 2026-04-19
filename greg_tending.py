from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from greg_paths import data_path


TENDING_LOG_PATH = data_path("tending_tasks.json")
PIKKAIO_STATE_PATH = data_path("greg_pikkaio.json")

TASK_BANKS = {
    "early": [
        "Write one sentence that describes what you are building and who it is for.",
        "Name 3 specific people who would pay for what you described in your intent.",
        "Write down the single biggest obstacle standing between you and your first paying customer.",
        "Find one existing product that does something similar to your intent and write what you would do differently.",
    ],
    "market": [
        "DM or email one potential customer today and ask if they would pay for your offer.",
        "Search for 3 competitors and write why each one still leaves a gap in the market.",
        "Write a one-paragraph problem statement that could open a pitch deck.",
    ],
    "build": [
        "Write the 3 core features of your MVP and delete everything else.",
        "Define your pricing in one number and justify it in two sentences.",
        "Identify the single riskiest assumption in your plan and explain how you will test it this week.",
    ],
    "launch": [
        "Write a launch email to your first 10 potential customers.",
        "Identify 5 communities or channels where you will share your launch.",
        "Define the one launch-week metric that tells you the offer is real.",
    ],
    "revenue": [
        "Record your latest revenue event in Pikkaio with amount, date, and source.",
        "Ask your best customer for a testimonial and write what you hope they say.",
        "Calculate your current MRR and define what must happen to double it.",
    ],
}

DRIFT_TASK_OVERRIDE = {
    "re_engagement": [
        "You have been away. Write one sentence on why this intent still matters to you.",
        "Drift is rising. Write down the three most important next actions in order.",
        "Your intent is drifting. What changed? Write one honest paragraph.",
    ]
}


class TendingEngine:
    def __init__(self):
        TENDING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._log = self._load_log()

    def _load_log(self) -> dict:
        try:
            return json.loads(TENDING_LOG_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_log(self) -> None:
        TENDING_LOG_PATH.write_text(json.dumps(self._log, indent=2), encoding="utf-8")

    def _load_project(self, project_id: str) -> Optional[dict]:
        try:
            state = json.loads(PIKKAIO_STATE_PATH.read_text(encoding="utf-8"))
            return state.get("projects", {}).get(project_id)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _choose_task_bank(self, project: dict, drift: float) -> list[str]:
        if drift > 0.65:
            return DRIFT_TASK_OVERRIDE["re_engagement"]
        convergence = project.get("convergence_pct", 0)
        if convergence >= 85:
            return TASK_BANKS["revenue"]
        if convergence >= 60:
            return TASK_BANKS["launch"]
        if convergence >= 35:
            return TASK_BANKS["build"]
        if convergence >= 15:
            return TASK_BANKS["market"]
        return TASK_BANKS["early"]

    def _next_task_text(self, project_id: str, bank: list[str]) -> str:
        project_log = self._log.get(project_id, {})
        seen = set(project_log.get("seen_task_hashes", []))

        def task_hash(text: str) -> str:
            return hashlib.md5(text.encode()).hexdigest()[:8]

        for task in bank:
            if task_hash(task) not in seen:
                return task
        project_log["seen_task_hashes"] = []
        return bank[0]

    def _mark_seen(self, project_id: str, task_text: str) -> None:
        task_hash = hashlib.md5(task_text.encode()).hexdigest()[:8]
        project = self._log.setdefault(project_id, {})
        seen = project.setdefault("seen_task_hashes", [])
        if task_hash not in seen:
            seen.append(task_hash)

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def get_or_generate(self, project_id: str) -> dict:
        project = self._load_project(project_id)
        if not project:
            return {
                "task_id": str(uuid.uuid4()),
                "project_id": project_id,
                "date": self._today_key(),
                "task": TASK_BANKS["early"][0],
                "maze_layer": "declaration",
                "drift": 0.0,
                "convergence_pct": 0,
                "completed": False,
                "source": "fallback",
            }

        today = self._today_key()
        project_log = self._log.get(project_id, {})
        if (
            project_log.get("today_date") == today
            and project_log.get("today_task")
            and not project_log.get("today_completed", False)
        ):
            cached = project_log["today_task"]
            cached["completed"] = project_log.get("today_completed", False)
            return cached

        drift = float(project.get("drift_score", 0.0))
        bank = self._choose_task_bank(project, drift)
        task_text = self._next_task_text(project_id, bank)
        self._mark_seen(project_id, task_text)
        task_obj = {
            "task_id": str(uuid.uuid4()),
            "project_id": project_id,
            "date": today,
            "task": task_text,
            "maze_layer": project.get("maze_layer", "declaration"),
            "drift": drift,
            "convergence_pct": project.get("convergence_pct", 0),
            "completed": False,
            "source": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        project_log = self._log.setdefault(project_id, {})
        project_log["today_date"] = today
        project_log["today_task"] = task_obj
        project_log["today_completed"] = False
        self._save_log()
        return task_obj

    def mark_complete(self, project_id: str, task_id: str) -> dict:
        project_log = self._log.get(project_id, {})
        today = self._today_key()
        if project_log.get("today_date") != today:
            return {"ok": False, "error": "No task for today found."}

        task = project_log.get("today_task", {})
        if task.get("task_id") != task_id:
            return {"ok": False, "error": "Task ID mismatch."}
        if project_log.get("today_completed"):
            return {"ok": True, "already_done": True, "message": "Already marked complete."}

        project_log["today_completed"] = True
        history = project_log.setdefault("completion_history", [])
        history.append({"date": today, "task_id": task_id, "task_text": task.get("task", "")})
        project_log["completion_history"] = history[-90:]
        project_log["current_streak"] = self._calculate_streak(project_log["completion_history"])
        project_log["today_task"] = None
        self._save_log()
        return {
            "ok": True,
            "message": f"Tending task complete. Streak: {project_log['current_streak']} day(s).",
            "streak": project_log["current_streak"],
            "drift_signal": "decrease",
            "psi_signal": 0.01,
            "convergence_delta": 0.5,
        }

    def _calculate_streak(self, history: list[dict]) -> int:
        if not history:
            return 0
        today = datetime.now(timezone.utc).date()
        streak = 0
        dates_done = {item["date"] for item in history}
        check_date = today
        while check_date.isoformat() in dates_done:
            streak += 1
            check_date -= timedelta(days=1)
        return streak

    def summary(self, project_id: str) -> dict:
        project_log = self._log.get(project_id, {})
        history = project_log.get("completion_history", [])
        today = self._today_key()
        tasks_completed_today = sum(1 for item in history if item.get("date") == today)
        return {
            "project_id": project_id,
            "total_tasks_completed": len(history),
            "current_streak": project_log.get("current_streak", 0),
            "today_completed": tasks_completed_today > 0,
            "tasks_completed_today": tasks_completed_today,
            "today_date": today,
        }

    def generate_batch(self, all_project_ids: list[str]) -> list[dict]:
        results = []
        for project_id in all_project_ids:
            try:
                task = self.get_or_generate(project_id)
                results.append({"project_id": project_id, "task_id": task["task_id"], "ok": True})
            except Exception as exc:
                results.append({"project_id": project_id, "ok": False, "error": str(exc)})
        return results
