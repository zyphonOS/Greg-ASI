from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
STATE_DIR = DATA_DIR
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def repo_path(*parts: str) -> Path:
    return project_path(*parts)


def data_path(*parts: str, seed: bool = True) -> Path:
    return DATA_DIR.joinpath(*parts)


def state_path(*parts: str, seed: bool = True) -> Path:
    return STATE_DIR.joinpath(*parts)


def static_path(*parts: str) -> Path:
    return STATIC_DIR.joinpath(*parts)


def templates_path(*parts: str) -> Path:
    return TEMPLATES_DIR.joinpath(*parts)
