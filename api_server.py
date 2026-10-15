#!/usr/bin/env python3
"""
OmniVoice Studio - REST API (FastAPI)

Backend cho giao diện React + Tailwind trong thư mục `web/`.
Tái sử dụng toàn bộ logic của app_omnivoice.py (preset, lịch sử, giọng tùy chỉnh)
nên dữ liệu `history/` và `custom_voices/` dùng chung với bản Gradio.

Chạy:  python api_server.py --device mps --port 8000
Dev :  cd web && npm run dev      (Vite proxy /api -> :8000)
Prod:  cd web && npm run build    (api_server tự phục vụ web/dist)
"""

import argparse
import logging
import os
import shutil
import tempfile
import time
import uuid
from typing import Optional

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.common import get_best_device
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name

import app_omnivoice as legacy

logging.basicConfig(level=logging.INFO)

DIST_DIR = os.path.join(legacy.SCRIPT_DIR, "web", "dist")
PREVIEW_DIR = os.path.join(legacy.HISTORY_DIR, "previews")
ALLOWED_DIRS = [legacy.PRESETS_DIR, legacy.HISTORY_DIR, legacy.CUSTOM_VOICES_DIR]

app = FastAPI(title="OmniVoice Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: dict = {"model": None, "device": "cpu", "voice_cache": {}}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _model() -> OmniVoice:
    if STATE["model"] is None:
        raise HTTPException(503, "Model chưa sẵn sàng")
    return STATE["model"]


def _audio_url(path: Optional[str]) -> str:
    return f"/api/files?path={path}" if path else ""


def _voice_json(key: str, v: dict) -> dict:
    return {
        "key": key,
        "name": v.get("name"),
        "avatar": v.get("avatar", "🎙️"),
        "style_tag": v.get("style_tag", ""),
        "desc": v.get("desc", ""),
        "tags": v.get("tags", []),
        "grad": v.get("grad", ""),
        "ref_text": v.get("ref_text", ""),
        "audio_url": _audio_url(v.get("audio")),
        "custom": key not in legacy.PRESET_VOICES,
    }


def _history_json(it: dict) -> dict:
    voice = legacy.get_all_voices().get(it.get("voice_choice"), {})
    return {
        **{k: v for k, v in it.items() if k != "file_path"},
        "grad": voice.get("grad", ""),
        "audio_url": _audio_url(it["file_path"]),
    }


def _voice_prompt(key: str):
    cache = STATE["voice_cache"]
    if key in cache:
        return cache[key]
    v = legacy.get_all_voices().get(key)
    if not v or not v.get("audio"):
        return None
    prompt = _model().create_voice_clone_prompt(ref_audio=v["audio"], ref_text=v.get("ref_text") or None)
    cache[key] = prompt
    return prompt


# ----------------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    text: str
    voice: str
    instruct: str = ""
    language: str = "Auto"
    speed: float = 1.0
    guidance_scale: float = 2.0
    num_step: int = 32
    denoise: bool = True
    preprocess_prompt: bool = True
    postprocess_output: bool = True


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ready": STATE["model"] is not None, "device": STATE["device"]}


@app.get("/api/meta")
def meta():
    return {"languages": legacy._ALL_LANGUAGES, "device": STATE["device"]}


@app.get("/api/files")
def files(path: str):
    real = os.path.realpath(path)
    if not any(real.startswith(os.path.realpath(d) + os.sep) for d in ALLOWED_DIRS) or not os.path.isfile(real):
        raise HTTPException(404, "Không tìm thấy file")
    return FileResponse(real)


@app.get("/api/voices")
def list_voices():
    return [
        _voice_json(k, v)
        for k, v in legacy.get_all_voices().items()
        if v.get("audio")  # bỏ mục "Tùy chỉnh" trống của bản Gradio
    ]


@app.post("/api/voices")
async def create_voice(
    audio: UploadFile = File(...),
    name: str = Form(...),
    avatar: str = Form("🎙️"),
    style_tag: str = Form("Custom Voice"),
    ref_text: str = Form(""),
):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Vui lòng nhập tên giọng")
    vid = f"voice_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    saved = os.path.join(legacy.CUSTOM_VOICES_DIR, f"{vid}.wav")
    with open(saved, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    ref_text = ref_text.strip()
    if not ref_text:
        try:
            ref_text = _model().transcribe(saved).strip()
        except Exception as e:
            os.remove(saved)
            raise HTTPException(500, f"Không thể nhận diện lời thoại: {e}")

    key = f"{avatar} {name} - {style_tag}"
    entry = {
        "id": vid, "name": name, "avatar": avatar, "style_tag": style_tag,
        "audio": saved, "audio_url": "", "ref_text": ref_text,
        "desc": f"Giọng nhân bản tùy chỉnh: {ref_text[:60]}...",
        "tags": ["Tùy chỉnh", style_tag], "grad": "linear-gradient(135deg,#ec4899,#8b5cf6)",
        "instruct": "",
    }
    voices = legacy.load_custom_voices()
    voices[key] = entry
    legacy.save_custom_voices(voices)
    STATE["voice_cache"].pop(key, None)
    return _voice_json(key, entry)


@app.post("/api/voices/preview")
def preview_voice(
    audio: UploadFile = File(...),
    text: str = Form(...),
    language: str = Form("Auto"),
    ref_text: str = Form(""),
    denoise: bool = Form(False),
    preprocess_prompt: bool = Form(True),
):
    """Nghe thử giọng clone từ file mẫu mà không lưu vào thư viện hay lịch sử."""
    model = _model()
    text = text.strip()
    if not text:
        raise HTTPException(400, "Vui lòng nhập văn bản nghe thử")
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    pid = f"preview_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    src = os.path.join(PREVIEW_DIR, f"{pid}_ref.wav")
    out = os.path.join(PREVIEW_DIR, f"{pid}.wav")
    with open(src, "wb") as f:
        shutil.copyfileobj(audio.file, f)
    try:
        ref_text = ref_text.strip()
        if not ref_text:
            ref_text = model.transcribe(src).strip()
        prompt = model.create_voice_clone_prompt(ref_audio=src, ref_text=ref_text)
        cfg = OmniVoiceGenerationConfig(denoise=denoise, preprocess_prompt=preprocess_prompt)
        wav = model.generate(
            text=text,
            language=None if language == "Auto" else language,
            generation_config=cfg,
            voice_clone_prompt=prompt,
        )
        data = (wav[0] * 32767).astype(np.int16)
        sf.write(out, data, model.sampling_rate)
    except Exception as e:
        raise HTTPException(500, f"Lỗi nghe thử: {type(e).__name__}: {e}")
    finally:
        os.remove(src)
    return {"audio_url": _audio_url(out), "duration": round(len(data) / model.sampling_rate, 1), "ref_text": ref_text}


@app.delete("/api/voices")
def delete_voice(key: str):
    voices = legacy.load_custom_voices()
    entry = voices.pop(key, None)
    if entry is None:
        raise HTTPException(404, "Không tìm thấy giọng tùy chỉnh")
    legacy.save_custom_voices(voices)
    STATE["voice_cache"].pop(key, None)
    try:
        os.remove(entry["audio"])
    except OSError:
        pass
    return {"ok": True}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        shutil.copyfileobj(audio.file, tmp)
    try:
        t0 = time.time()
        text = _model().transcribe(tmp.name).strip()
        return {"text": text, "elapsed": round(time.time() - t0, 1)}
    except Exception as e:
        raise HTTPException(500, f"Lỗi ASR: {e}")
    finally:
        os.remove(tmp.name)


@app.post("/api/generate")
def generate(req: GenerateRequest):
    model = _model()
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Vui lòng nhập văn bản")
    voices = legacy.get_all_voices()
    if req.voice not in voices:
        raise HTTPException(404, "Giọng không tồn tại")

    cfg = OmniVoiceGenerationConfig(
        num_step=req.num_step, guidance_scale=req.guidance_scale, denoise=req.denoise,
        preprocess_prompt=req.preprocess_prompt, postprocess_output=req.postprocess_output,
    )
    kw = {
        "text": text,
        "language": None if req.language == "Auto" else req.language,
        "generation_config": cfg,
        "voice_clone_prompt": _voice_prompt(req.voice),
    }
    if req.speed != 1.0:
        kw["speed"] = req.speed
    instruct = req.instruct.strip() or voices[req.voice].get("instruct")
    if instruct:
        kw["instruct"] = instruct

    try:
        t0 = time.time()
        audio = model.generate(**kw)
        elapsed = time.time() - t0
    except Exception as e:
        raise HTTPException(500, f"Lỗi tổng hợp: {type(e).__name__}: {e}")

    waveform = (audio[0] * 32767).astype(np.int16)
    dur = len(waveform) / model.sampling_rate
    items = legacy.add_to_history(waveform, model.sampling_rate, text, req.voice, dur, elapsed)
    return _history_json(items[0])


@app.get("/api/history")
def history():
    return [_history_json(it) for it in legacy.load_history()]


@app.delete("/api/history")
def clear_history():
    legacy.clear_all_history()
    return {"ok": True}


@app.delete("/api/history/{item_id}")
def delete_history(item_id: str):
    items = legacy.load_history()
    keep = [it for it in items if it["id"] != item_id]
    for it in items:
        if it["id"] == item_id:
            try:
                os.remove(it["file_path"])
            except OSError:
                pass
    legacy.save_history(keep)
    return {"ok": True}


# Phục vụ bản build của React (nếu có) — đặt cuối cùng
if os.path.isdir(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="web")


def main():
    p = argparse.ArgumentParser(description="OmniVoice Studio API + React UI")
    p.add_argument("--model", default="k2-fsa/OmniVoice")
    p.add_argument("--device", default=None)
    p.add_argument("--ip", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    device = args.device or get_best_device()
    dtype = torch.float32 if str(device).startswith("mps") else torch.float16
    logging.info(f"Loading OmniVoice from {args.model} on {device}...")
    STATE["model"] = OmniVoice.from_pretrained(
        args.model, device_map=device, dtype=dtype,
        load_asr=True, asr_model_name="openai/whisper-large-v3-turbo",
    )
    STATE["device"] = str(device)
    logging.info("OmniVoice model ready.")
    uvicorn.run(app, host=args.ip, port=args.port)


if __name__ == "__main__":
    main()
