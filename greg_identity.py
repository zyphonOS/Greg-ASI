from __future__ import annotations

import json
import os
import secrets
import time

from greg_paths import data_path


IDENTITY_PATH = str(data_path("greg_identity.json"))
ACCESS_REGISTRY_PATH = str(data_path("greg_access_registry.json"))

ACCESS_TIERS = {
    "public": 0,
    "explorer": 1,
    "judge": 2,
    "trainer": 3,
    "pikkaio_client": 4,
    "zyphonos_client": 5,
    "emma": 5,
    "ebuka": 6,
}

ACCESS_PREFIXES = {
    "explorer": "visitor",
    "judge": "judge",
    "trainer": "trainer",
    "pikkaio_client": "pikkaio",
    "zyphonos_client": "studio",
    "emma": "emma",
    "ebuka": "admin",
}


def _read_json(path: str, default: dict) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: str, data: dict) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def load_access_registry(path: str = ACCESS_REGISTRY_PATH) -> dict:
    data = _read_json(path, {"tokens": {}, "codes": {}, "last_updated": None})
    data.setdefault("tokens", {})
    data.setdefault("codes", {})
    return data


def save_access_registry(data: dict, path: str = ACCESS_REGISTRY_PATH) -> None:
    data["last_updated"] = time.time()
    _write_json(path, data)


def issue_access_token(
    tier_name: str = "explorer",
    label: str = "",
    metadata: dict | None = None,
    path: str = ACCESS_REGISTRY_PATH,
) -> str:
    tier_name = tier_name if tier_name in ACCESS_TIERS else "explorer"
    prefix = ACCESS_PREFIXES.get(tier_name, "visitor")
    token = f"{prefix}_{secrets.token_hex(16)}"
    registry = load_access_registry(path)
    registry["tokens"][token] = {
        "tier_name": tier_name,
        "tier_level": ACCESS_TIERS[tier_name],
        "label": label or tier_name.replace("_", " ").title(),
        "created_at": time.time(),
        "metadata": metadata or {},
    }
    save_access_registry(registry, path)
    return token


def get_access_tier(token: str) -> tuple[int, dict, str]:
    token = (token or "").strip()
    if not token:
        return 0, {}, "public"
    registry = load_access_registry()
    record = registry.get("tokens", {}).get(token)
    if record:
        tier_name = record.get("tier_name", "explorer")
        return ACCESS_TIERS.get(tier_name, 1), record, tier_name
    prefix = token.split("_", 1)[0]
    reverse = {
        "visitor": "explorer",
        "judge": "judge",
        "trainer": "trainer",
        "pikkaio": "pikkaio_client",
        "studio": "zyphonos_client",
        "emma": "emma",
        "admin": "ebuka",
    }
    tier_name = reverse.get(prefix, "explorer")
    return ACCESS_TIERS.get(tier_name, 1), {"label": prefix.title()}, tier_name
