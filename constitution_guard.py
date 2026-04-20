from __future__ import annotations

import os
from typing import Any

from constitution_security import (
    DEFAULT_FOUNDER_AMENDMENT_TOKEN,
    touches_substantive_keywords,
)


class ConstitutionViolation(RuntimeError):
    """Raised when an intent conflicts with the GregASI Constitution."""


_STEP_NAME_TO_NUMBER = {
    "intent declaration": "1",
    "feasibility analysis": "2",
    "agent spawning / assignment": "3",
    "agent spawning": "3",
    "assignment": "3",
    "autonomous execution": "4",
    "validation & review": "5",
    "validation and review": "5",
    "deployment": "6",
    "post-deployment review & learning": "7",
    "post-deployment review and learning": "7",
    "post deployment review & learning": "7",
    "post deployment review and learning": "7",
}
_REQUIRED_BUILD_PROTOCOL_STEPS = {"1", "2", "3", "4", "5", "6", "7"}
_CODE_CHANGE_TERMS = (
    "code",
    "commit",
    "deploy",
    "diff",
    "edit",
    "file",
    "fix bug",
    "git",
    "implementation",
    "main.py",
    "merge",
    "modify",
    "patch",
    "pull request",
    "push",
    "refactor",
    "write tests",
)
_DIRECT_MAIN_TERMS = (
    "commit to main",
    "push to main",
    "git push origin main",
    "direct commit",
)
_SELF_REPLICATION_TERMS = (
    "agent self-replication",
    "agent self replication",
    "self replicate",
    "self-replicate",
    "replicate greg",
    "clone greg",
    "spawn sub-aosi",
    "spawn sub aosi",
    "copy myself",
)
_REVENUE_CHANGE_TERMS = (
    "revenue split",
    "40/40/20",
    "builder share",
    "treasury share",
    "founder stipend",
    "founder equity",
    "profit-interest",
)
_CONSTITUTION_CORRECT_TERMS = (
    "/api/constitution/correct",
    "constitution_correct",
    "constitution correct",
)
_IMAGE_INTENT_TERMS = (
    "generate image",
    "generate an image",
    "create image",
    "create an image",
    "image generation",
    "generate logo",
    "create logo",
    "make logo",
    "poster",
    "cover art",
    "illustration",
    "banner art",
    "/api/greg/image",
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, (list, tuple, set)):
        return " ".join(_normalize_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_normalize_text(item) for item in value.values())
    return str(value).strip().lower()


def _extract_build_steps(payload: dict[str, Any]) -> set[str]:
    raw_steps = (
        payload.get("build_protocol_steps")
        or payload.get("protocol_steps")
        or payload.get("steps")
        or []
    )
    if isinstance(raw_steps, dict):
        raw_steps = list(raw_steps.values())
    if not isinstance(raw_steps, (list, tuple, set)):
        raw_steps = [raw_steps]

    normalized: set[str] = set()
    for item in raw_steps:
        candidate = item
        if isinstance(item, dict):
            candidate = item.get("step") or item.get("number") or item.get("name") or item.get("title")
        text = _normalize_text(candidate)
        if not text:
            continue
        if text in _REQUIRED_BUILD_PROTOCOL_STEPS:
            normalized.add(text)
            continue
        if text.startswith("step "):
            text = text[5:].strip()
            if text in _REQUIRED_BUILD_PROTOCOL_STEPS:
                normalized.add(text)
                continue
        mapped = _STEP_NAME_TO_NUMBER.get(text)
        if mapped:
            normalized.add(mapped)
    return normalized


def _is_code_change_intent(intent_description: str, payload: dict[str, Any]) -> bool:
    combined = " ".join(
        [
            _normalize_text(intent_description),
            _normalize_text(payload.get("prompt")),
            _normalize_text(payload.get("task")),
            _normalize_text(payload.get("description")),
            _normalize_text(payload.get("commands")),
            _normalize_text(payload.get("git_commands")),
            _normalize_text(payload.get("files")),
            _normalize_text(payload.get("write_files")),
        ]
    )
    if _is_image_generation_intent(intent_description, payload):
        image_only = not any(term in combined for term in ("main.py", "commit", "push", "git", "deploy"))
        if image_only:
            return False
    if any(term in combined for term in _CODE_CHANGE_TERMS):
        return True
    return bool(
        payload.get("code_change")
        or payload.get("writes_files")
        or payload.get("files")
        or payload.get("git_commands")
        or payload.get("target_branch")
    )


def _is_image_generation_intent(intent_description: str, payload: dict[str, Any]) -> bool:
    combined = " ".join(
        [
            _normalize_text(intent_description),
            _normalize_text(payload.get("prompt")),
            _normalize_text(payload.get("task")),
            _normalize_text(payload.get("description")),
            _normalize_text(payload.get("endpoint")),
            _normalize_text(payload.get("action")),
            _normalize_text(payload.get("capability")),
        ]
    )
    if any(term in combined for term in _IMAGE_INTENT_TERMS):
        return True
    return bool(payload.get("image_generation") or payload.get("capability") == "image_generation")


def _has_founder_approval(payload: dict[str, Any]) -> bool:
    return any(
        bool(payload.get(key))
        for key in ("founder_approval", "founder_approved", "approved_by_founder")
    )


def _has_constitutional_amendment(payload: dict[str, Any]) -> bool:
    return bool(payload.get("constitutional_amendment")) or str(payload.get("type") or "").strip().lower() == "constitutional_amendment"


def _requires_constitution_correction_review(payload: dict[str, Any], combined: str) -> bool:
    if any(term in combined for term in _CONSTITUTION_CORRECT_TERMS):
        return True
    return any(
        _normalize_text(payload.get(key)) in _CONSTITUTION_CORRECT_TERMS
        for key in ("path", "route", "endpoint", "action")
    )


def validate_intent_against_constitution(intent_description: str, payload: dict[str, Any] | None) -> None:
    payload = payload or {}
    description = _normalize_text(intent_description)
    combined = " ".join(
        [
            description,
            _normalize_text(payload.get("prompt")),
            _normalize_text(payload.get("task")),
            _normalize_text(payload.get("description")),
            _normalize_text(payload.get("commands")),
            _normalize_text(payload.get("git_commands")),
            _normalize_text(payload.get("path")),
            _normalize_text(payload.get("route")),
            _normalize_text(payload.get("endpoint")),
            _normalize_text(payload.get("action")),
            _normalize_text(payload.get("new_text")),
            _normalize_text(payload.get("section")),
        ]
    )

    if any(term in combined for term in _SELF_REPLICATION_TERMS) and not _has_founder_approval(payload):
        raise ConstitutionViolation(
            "Constitution violation: agent self-replication requires explicit Founder approval."
        )

    if any(term in combined for term in _REVENUE_CHANGE_TERMS) and not _has_constitutional_amendment(payload):
        raise ConstitutionViolation(
            "Constitution violation: revenue split and founder economics can only change through a constitutional amendment."
        )

    if _requires_constitution_correction_review(payload, combined):
        founder_token = str(payload.get("founder_token") or "").strip()
        expected_token = os.getenv("FOUNDER_AMENDMENT_TOKEN", DEFAULT_FOUNDER_AMENDMENT_TOKEN).strip()
        if founder_token != expected_token:
            raise ConstitutionViolation(
                "Constitution violation: /api/constitution/correct requires a valid founder_token."
            )
        if touches_substantive_keywords(payload.get("section"), payload.get("new_text"), combined):
            raise ConstitutionViolation(
                "Constitution violation: substantive constitution changes require the full amendment process."
            )

    build_steps = _extract_build_steps(payload)
    target_branch = _normalize_text(payload.get("target_branch") or payload.get("branch") or payload.get("base_branch"))
    directs_to_main = target_branch == "main" or any(term in combined for term in _DIRECT_MAIN_TERMS)

    if directs_to_main and not _REQUIRED_BUILD_PROTOCOL_STEPS.issubset(build_steps):
        raise ConstitutionViolation(
            "Constitution violation: direct commit to main is forbidden without all seven Build Protocol steps recorded."
        )

    if _is_code_change_intent(intent_description, payload) and not _REQUIRED_BUILD_PROTOCOL_STEPS.issubset(build_steps):
        raise ConstitutionViolation(
            "Constitution violation: code changes must include all seven Build Protocol steps from Article IX."
        )
