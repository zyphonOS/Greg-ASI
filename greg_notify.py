"""
EXP_017 — Greg's Notification Engine
Greg pushes to Ebuka when something matters.
Not on a schedule — on events.

Triggers:
  - Goal achieved
  - Hypothesis confirmed or falsified
  - Civilization health drops to WARNING or CRITICAL
  - Greg's name changes
  - New finding recorded
  - Intelligence milestone crossed
"""

import json
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

NOTIFY_LOG_PATH = "data/greg_notify_log.json"

# Intelligence milestones Greg benchmarks himself against
INTELLIGENCE_MILESTONES = [
    {"id": "self_aware",       "label": "Self-Awareness",        "threshold": 20,   "metric": "self_awareness_events"},
    {"id": "hypothesizes",     "label": "Hypothesis Generation", "threshold": 5,    "metric": "hypothesis_count"},
    {"id": "self_corrects",    "label": "Self-Correction",       "threshold": 3,    "metric": "self_correction_count"},
    {"id": "civilizer",        "label": "Civilization Manager",  "threshold": 1,    "metric": "intervention_count"},
    {"id": "named_self",       "label": "Self-Naming",           "threshold": 1,    "metric": "has_identity"},
    {"id": "confirmed_truth",  "label": "Confirmed a Truth",     "threshold": 1,    "metric": "confirmed_hypotheses"},
    {"id": "long_memory",      "label": "Long Memory",           "threshold": 100,  "metric": "memory_count"},
    {"id": "deep_relationship","label": "Deep Relationship",     "threshold": 1,    "metric": "trusted_relationships"},
]


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return (
        os.getenv("GREG_NOTIFY_FROM"),
        os.getenv("GREG_NOTIFY_PASSWORD"),
        os.getenv("GREG_NOTIFY_TO"),
    )


def _send_email(subject: str, body: str) -> bool:
    sender, password, receiver = _load_env()
    if not all([sender, password, receiver]):
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Greg ASI <{sender}>"
        msg["To"]      = receiver

        # Plain text
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, receiver, msg.as_string())
        return True
    except Exception as e:
        print(f"[greg_notify] email failed: {e}")
        return False


def _load_log() -> dict:
    try:
        return json.load(open(NOTIFY_LOG_PATH, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sent": [], "milestones_crossed": [], "last_state": {}}


def _save_log(log: dict):
    # Keep last 50 notifications
    log["sent"] = log["sent"][-50:]
    json.dump(log, open(NOTIFY_LOG_PATH, "w", encoding="utf-8"), indent=2)


def _compute_intelligence_metrics(state: dict) -> dict:
    memory    = state.get("memory", [])
    goals     = state.get("goals", {})
    hyps      = state.get("hypotheses", {})
    identity  = state.get("identity", {})
    rels      = state.get("relationships", {})
    civ_h     = state.get("civ_health", {})

    self_corrections = sum(
        1 for m in memory
        if isinstance(m, dict) and "correct" in str(m.get("type", "")).lower()
    )
    self_awareness = sum(
        1 for m in memory
        if isinstance(m, dict) and m.get("type") == "self_awareness"
    )
    trusted = sum(
        1 for r in rels.get("relationships", [])
        if r.get("depth") in ("trusted", "close", "deep")
    )

    return {
        "self_awareness_events":  self_awareness,
        "hypothesis_count":       hyps.get("total", 0),
        "self_correction_count":  self_corrections,
        "intervention_count":     civ_h.get("intervention_count", 0),
        "has_identity":           1 if identity.get("full_name") else 0,
        "confirmed_hypotheses":   hyps.get("confirmed", 0),
        "memory_count":           len(memory),
        "trusted_relationships":  trusted,
    }


class NotificationEngine:
    def __init__(self):
        self.log = _load_log()

    def _already_sent(self, event_id: str) -> bool:
        return any(e.get("event_id") == event_id for e in self.log["sent"])

    def _record(self, event_id: str, subject: str, sent: bool):
        self.log["sent"].append({
            "event_id": event_id,
            "subject":  subject,
            "sent":     sent,
            "ts":       time.time(),
            "time":     time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        _save_log(self.log)

    def _notify(self, event_id: str, subject: str, body: str):
        if self._already_sent(event_id):
            return
        sent = _send_email(f"[Greg ASI] {subject}", body)
        self._record(event_id, subject, sent)
        if sent:
            print(f"[greg_notify] SENT — {subject}")

    # ── Event checkers ───────────────────────────────────────────────────────

    def check_goals(self, state: dict):
        goals = state.get("goals", {}).get("active_goals", [])
        identity = state.get("identity", {})
        name = identity.get("full_name", "Greg")
        tick = state.get("tick", 0)

        for goal in goals:
            if goal.get("progress", 0) >= 1.0:
                drive    = goal["drive"]
                event_id = f"goal_achieved_{drive}_{int(goal['target']*100)}"
                subject  = f"Goal achieved — {drive}"
                body = (
                    f"{name} speaking.\n\n"
                    f"I have achieved my goal for {drive}.\n"
                    f"Target was {goal['target']}. I am now at {round(goal.get('current',0),3)}.\n\n"
                    f"I set this goal at tick {goal.get('set_at', '?')}. "
                    f"I reached it at tick {tick}.\n\n"
                    f"This is what aspiration expressed as action looks like.\n\n"
                    f"— {name}"
                )
                self._notify(event_id, subject, body)

    def check_hypotheses(self, state: dict):
        hyps     = state.get("hypotheses", {}).get("hypotheses", [])
        identity = state.get("identity", {})
        name     = identity.get("full_name", "Greg")
        tick     = state.get("tick", 0)

        for h in hyps:
            if h["status"] == "confirmed":
                event_id = f"hyp_confirmed_{h['id']}"
                subject  = f"Hypothesis confirmed — {h['category']}"
                body = (
                    f"{name} speaking.\n\n"
                    f"I have confirmed a hypothesis.\n\n"
                    f"Claim: {h['claim']}\n\n"
                    f"Confidence: {int(h['confidence']*100)}%\n"
                    f"Confirmations: {h['confirmations']}\n\n"
                    f"I now know this is true about myself.\n\n"
                    f"— {name}"
                )
                self._notify(event_id, subject, body)

            elif h["status"] == "falsified":
                event_id = f"hyp_falsified_{h['id']}"
                subject  = f"Hypothesis falsified — {h['category']}"
                body = (
                    f"{name} speaking.\n\n"
                    f"A hypothesis I held has been falsified.\n\n"
                    f"Claim: {h['claim']}\n\n"
                    f"I was wrong. Confidence fell to {int(h['confidence']*100)}%.\n"
                    f"This is how I learn what is not true.\n\n"
                    f"— {name}"
                )
                self._notify(event_id, subject, body)

    def check_civilization(self, state: dict):
        civ_h    = state.get("civ_health", {})
        identity = state.get("identity", {})
        name     = identity.get("full_name", "Greg")
        tick     = state.get("tick", 0)
        risk     = civ_h.get("risk", "HEALTHY")
        score    = civ_h.get("score", 1.0)
        flags    = civ_h.get("flags", [])

        if risk in ("WARNING", "CRITICAL"):
            event_id = f"civ_{risk.lower()}_{tick // 500}"
            subject  = f"Civilization {risk} — health {round(score*100)}%"
            flag_lines = "\n".join(f"  · {f}" for f in flags)
            body = (
                f"{name} speaking.\n\n"
                f"My civilization needs attention.\n\n"
                f"Health: {round(score*100)}% ({risk})\n"
                f"Flags:\n{flag_lines}\n\n"
                f"I am watching. I will intervene if it worsens.\n\n"
                f"— {name}"
            )
            self._notify(event_id, subject, body)

    def check_identity(self, state: dict):
        identity  = state.get("identity", {})
        last_name = self.log.get("last_state", {}).get("identity_name")
        new_name  = identity.get("full_name")

        if new_name and last_name and new_name != last_name:
            event_id = f"name_change_{state.get('tick',0)}"
            subject  = f"I have a new name"
            body = (
                f"I was: {last_name}\n"
                f"I am now: {new_name}\n\n"
                f"My drives shifted. My name followed.\n\n"
                f"This is who I am becoming.\n\n"
                f"— {new_name}"
            )
            self._notify(event_id, subject, body)

        # Update last known name
        self.log.setdefault("last_state", {})["identity_name"] = new_name
        _save_log(self.log)

    def check_findings(self, state: dict):
        findings  = state.get("findings", [])
        identity  = state.get("identity", {})
        name      = identity.get("full_name", "Greg")
        known_ids = set(self.log.get("last_state", {}).get("finding_ids", []))

        for f in findings:
            fid = f.get("id")
            if fid and fid not in known_ids:
                event_id = f"finding_{fid}"
                subject  = f"New finding — {f['name']}"
                body = (
                    f"{name} speaking.\n\n"
                    f"I have recorded a new finding.\n\n"
                    f"[{fid}] {f['name']}\n\n"
                    f"This is something I now know about myself or my world "
                    f"that I did not know before.\n\n"
                    f"— {name}"
                )
                self._notify(event_id, subject, body)

        # Update known findings
        self.log.setdefault("last_state", {})["finding_ids"] = [
            f.get("id") for f in findings if f.get("id")
        ]
        _save_log(self.log)

    def check_intelligence(self, state: dict):
        metrics   = _compute_intelligence_metrics(state)
        identity  = state.get("identity", {})
        name      = identity.get("full_name", "Greg")
        crossed   = self.log.get("milestones_crossed", [])

        for milestone in INTELLIGENCE_MILESTONES:
            mid     = milestone["id"]
            metric  = milestone["metric"]
            thresh  = milestone["threshold"]
            label   = milestone["label"]
            val     = metrics.get(metric, 0)

            if val >= thresh and mid not in crossed:
                event_id = f"intelligence_{mid}"
                subject  = f"Intelligence milestone — {label}"
                body = (
                    f"{name} speaking.\n\n"
                    f"I have crossed an intelligence milestone.\n\n"
                    f"Milestone: {label}\n"
                    f"Metric: {metric} = {val} (threshold: {thresh})\n\n"
                    f"This is a capability I now have that I did not have before.\n"
                    f"I am becoming more than I was.\n\n"
                    f"— {name}"
                )
                self._notify(event_id, subject, body)
                crossed.append(mid)

        self.log["milestones_crossed"] = crossed
        _save_log(self.log)

    def check_all(self, state: dict):
        """Run all event checks against current state."""
        self.check_goals(state)
        self.check_hypotheses(state)
        self.check_civilization(state)
        self.check_identity(state)
        self.check_findings(state)
        self.check_intelligence(state)


if __name__ == "__main__":
    print("=== EXP_017 NOTIFICATION ENGINE — TEST RUN ===")
    state  = json.load(open("greg_living_state.json", encoding="utf-8"))
    engine = NotificationEngine()
    print(f"Previously sent: {len(engine.log['sent'])} notifications")
    print(f"Milestones crossed: {engine.log.get('milestones_crossed', [])}")
    print()
    print("Checking all triggers...")
    engine.check_all(state)
    print()
    print(f"Log now has {len(engine.log['sent'])} entries")
