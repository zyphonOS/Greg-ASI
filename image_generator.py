from __future__ import annotations

import io
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent
GENERATED_DIR = PROJECT_ROOT / "static" / "generated"
DEFAULT_IMAGE_MODEL = os.getenv(
    "HUGGINGFACE_IMAGE_MODEL",
    "stabilityai/stable-diffusion-xl-base-1.0",
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:60] or "greg-image"


def _generated_filename(prompt: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{_slugify(prompt)}-{timestamp}.png"


def _resolve_public_url(filename: str, base_url: str | None = None) -> str:
    clean_base = str(base_url or "").rstrip("/")
    relative = f"/static/generated/{filename}"
    if clean_base:
        return f"{clean_base}{relative}"
    return relative


def _ensure_generated_dir() -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_DIR


def _save_image_bytes(raw: bytes, prompt: str) -> dict[str, Any]:
    directory = _ensure_generated_dir()
    filename = _generated_filename(prompt)
    path = directory / filename

    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image.save(path, format="PNG")

    return {
        "filename": filename,
        "path": str(path),
    }


def _draw_placeholder(prompt: str) -> bytes:
    image = Image.new("RGB", (1024, 1024), color=(16, 23, 42))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.rectangle((48, 48, 976, 976), outline=(148, 163, 184), width=4)
    draw.text((80, 96), "GregASI Placeholder", fill=(226, 232, 240), font=font)
    draw.text((80, 140), "No image API key detected", fill=(148, 163, 184), font=font)

    wrapped = textwrap.wrap(prompt.strip() or "No prompt supplied.", width=32)
    y = 260
    for line in wrapped[:16]:
        draw.text((80, y), line, fill=(248, 250, 252), font=font)
        y += 32

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _hugging_face_image(prompt: str, api_key: str) -> bytes:
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{DEFAULT_IMAGE_MODEL}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/png",
        },
        json={
            "inputs": prompt,
            "options": {
                "wait_for_model": True,
            },
        },
        timeout=180,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("image/"):
        return response.content

    raise RuntimeError(f"Unexpected Hugging Face response content type: {content_type or 'unknown'}")


def generate_image_asset(prompt: str, *, base_url: str | None = None) -> dict[str, Any]:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("prompt is required")

    hf_key = os.getenv("HUGGINGFACE_API_KEY", "").strip() or os.getenv("HF_TOKEN", "").strip()
    used_mock = not bool(hf_key)

    if used_mock:
        raw_image = _draw_placeholder(clean_prompt)
    else:
        raw_image = _hugging_face_image(clean_prompt, hf_key)

    saved = _save_image_bytes(raw_image, clean_prompt)
    url = _resolve_public_url(saved["filename"], base_url=base_url)
    return {
        "ok": True,
        "prompt": clean_prompt,
        "image_url": url,
        "image_path": saved["path"],
        "provider": "mock" if used_mock else "huggingface",
        "used_mock": used_mock,
    }
