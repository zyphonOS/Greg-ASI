from __future__ import annotations

import os


def safe_save(temp_path: str, final_path: str) -> None:
    os.replace(temp_path, final_path)
