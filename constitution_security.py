from __future__ import annotations

import os
from typing import Any


DEFAULT_FOUNDER_AMENDMENT_TOKEN = "9f0f7a4af0d44f8fbf0fe3d257e2a6da4b8306f6f6bc4fb3"
SUBSTANTIVE_CORRECTION_KEYWORDS = (
    "40/40/20",
    "51%",
    "equity",
    "revenue split",
    "stipend",
    "phase",
    "valuation",
)


def founder_amendment_token() -> str:
    return os.getenv("FOUNDER_AMENDMENT_TOKEN", DEFAULT_FOUNDER_AMENDMENT_TOKEN).strip()


def touches_substantive_keywords(*values: Any) -> bool:
    combined = " ".join(str(value or "") for value in values).lower()
    return any(keyword.lower() in combined for keyword in SUBSTANTIVE_CORRECTION_KEYWORDS)
