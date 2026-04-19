#!/usr/bin/env python3
from __future__ import annotations

from core.drift import DriftEngine, DriftIntent, get_drift_engine


PikkaioProject = DriftIntent
PikkaioEngine = DriftEngine


def _get_engine() -> DriftEngine:
    return get_drift_engine()


def pikkaio_tick(tick_num: int, drives: dict, voice=None, snapshot=None) -> dict:
    return _get_engine().tick(tick_num, drives, voice=voice, snapshot=snapshot)

