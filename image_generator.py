from __future__ import annotations

import io
import os
import re
import time
import textwrap
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent
GENERATED_DIR = PROJECT_ROOT / "static" / "generated"
DEFAULT_IMAGE_MODEL = os.getenv(
    "HUGGINGFACE_IMAGE_MODEL",
    "runwayml/stable-diffusion-v1-5",
)
POLLINATIONS_BASE_URL = os.getenv("POLLINATIONS_IMAGE_URL", "https://image.pollinations.ai/prompt")


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
    endpoint = f"https://api-inference.huggingface.co/models/{DEFAULT_IMAGE_MODEL}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/png",
    }
    payload = {
        "inputs": prompt,
        "options": {
            "wait_for_model": True,
            "use_cache": False,
        },
    }

    last_error = None
    for _ in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=180,
        )
        content_type = response.headers.get("Content-Type", "")
        if response.ok and content_type.startswith("image/"):
            return response.content
        if response.status_code == 503:
            try:
                detail = response.json()
            except Exception:
                detail = {}
            wait_seconds = float(detail.get("estimated_time") or 8.0)
            time.sleep(max(3.0, min(wait_seconds, 20.0)))
            last_error = f"model warming for {wait_seconds:.1f}s"
            continue
        if content_type.startswith("application/json"):
            try:
                detail = response.json()
            except Exception:
                detail = {"error": response.text[:300]}
            raise RuntimeError(f"Hugging Face image generation failed: {detail}")
        response.raise_for_status()
        last_error = response.text[:300]
    raise RuntimeError(f"Hugging Face image generation failed after retries: {last_error or 'unknown error'}")


def _pollinations_image(prompt: str) -> bytes:
    encoded_prompt = urllib.parse.quote(prompt, safe="")
    url = f"{POLLINATIONS_BASE_URL}/{encoded_prompt}"
    response = requests.get(
        url,
        params={
            "width": 1024,
            "height": 1024,
            "nologo": "true",
            "enhance": "true",
            "seed": int(datetime.now(timezone.utc).timestamp()),
        },
        timeout=180,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise RuntimeError(f"Unexpected Pollinations response content type: {content_type or 'unknown'}")
    return response.content


def generate_image_asset(prompt: str, *, base_url: str | None = None) -> dict[str, Any]:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("prompt is required")

    hf_key = os.getenv("HUGGINGFACE_API_KEY", "").strip() or os.getenv("HF_TOKEN", "").strip()
    provider = "huggingface"
    try:
        if hf_key:
            raw_image = _hugging_face_image(clean_prompt, hf_key)
        else:
            provider = "pollinations"
            raw_image = _pollinations_image(clean_prompt)
    except Exception:
        if hf_key:
            provider = "pollinations"
            raw_image = _pollinations_image(clean_prompt)
        else:
            raise

    saved = _save_image_bytes(raw_image, clean_prompt)
    url = _resolve_public_url(saved["filename"], base_url=base_url)
    return {
        "ok": True,
        "prompt": clean_prompt,
        "image_url": url,
        "image_path": saved["path"],
        "provider": provider,
        "used_mock": False,
        "model": DEFAULT_IMAGE_MODEL if provider == "huggingface" else "pollinations",
    }
