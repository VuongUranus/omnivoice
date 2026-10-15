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
from omnivoice.utils.audio import load_waveform
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
# Giới hạn của trang Voice Clone — nguồn duy nhất. Giao diện đọc lại qua /api/meta
# nên số liệu hiển thị luôn trùng với những gì server thực sự kiểm tra.
# Mốc 20s và khuyến nghị 3-10s lấy từ OmniVoice.create_voice_clone_prompt():
# audio mẫu >20s bị model cảnh báo (chậm, tốn RAM, chất lượng giảm).
# ----------------------------------------------------------------------------
CLONE_LIMITS = {
    "max_upload_mb": 20,
    "extensions": [".wav", ".mp3", ".flac", ".ogg", ".m4a"],
    "ref_min_seconds": 1.0,
    "ref_recommended_seconds": [3.0, 10.0],
    "ref_max_seconds": 20.0,
    "preview_max_chars": 300,
    "name_max_chars": 40,
    "style_max_chars": 40,
    "avatar_max_chars": 8,
}
PREVIEW_TTL_SECONDS = 3600
LANGUAGES = set(legacy._ALL_LANGUAGES)


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


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _upload_ext(upload: UploadFile) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in CLONE_LIMITS["extensions"]:
        allowed = ", ".join(CLONE_LIMITS["extensions"])
        raise HTTPException(400, f"Định dạng '{ext or 'không rõ'}' không được hỗ trợ. Chỉ nhận: {allowed}")
    return ext


def _save_upload(upload: UploadFile, dest: str) -> int:
    """Ghi file upload ra đĩa, từ chối (413) nếu vượt giới hạn dung lượng."""
    limit_mb = CLONE_LIMITS["max_upload_mb"]
    size = 0
    try:
        with open(dest, "wb") as f:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit_mb * 1024 * 1024:
                    raise HTTPException(413, f"File vượt quá {limit_mb}MB")
                f.write(chunk)
    except Exception:
        _rm(dest)
        raise
    return size


def _inspect_audio(path: str) -> dict:
    """Đọc audio mẫu rồi đối chiếu giới hạn: {duration, errors, warnings}.

    errors   -> server sẽ từ chối.
    warnings -> vẫn chạy được nhưng chất lượng clone có thể kém.
    """
    lim = CLONE_LIMITS
    try:
        data, sr = load_waveform(path)
        duration = float(data.shape[-1]) / sr
        rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
    except Exception as e:
        msg = f"Không đọc được file âm thanh ({type(e).__name__}). File có thể bị hỏng, hoặc máy chủ thiếu ffmpeg để đọc định dạng này."
        return {"duration": None, "errors": [msg], "warnings": []}

    errors, warnings = [], []
    lo, hi = lim["ref_recommended_seconds"]
    if rms < 1e-4:
        errors.append("Audio gần như im lặng, không có giọng nói để clone.")
    if duration < lim["ref_min_seconds"]:
        errors.append(f"Audio quá ngắn ({duration:.1f}s). Cần tối thiểu {lim['ref_min_seconds']:g}s.")
    elif duration > lim["ref_max_seconds"]:
        errors.append(f"Audio quá dài ({duration:.1f}s). Tối đa {lim['ref_max_seconds']:g}s, hãy cắt bớt.")
    elif duration < lo or duration > hi:
        warnings.append(f"Audio dài {duration:.1f}s. Độ dài {lo:g}–{hi:g}s cho chất lượng clone tốt nhất.")
    return {"duration": round(duration, 2), "errors": errors, "warnings": warnings}


def _validate_audio(path: str) -> dict:
    info = _inspect_audio(path)
    if info["errors"]:
        raise HTTPException(400, " ".join(info["errors"]))
    return info


def _check_language(language: str) -> None:
    # Model âm thầm bỏ qua ngôn ngữ lạ (chuyển sang tự nhận diện) nên phải chặn ở đây.
    if language not in LANGUAGES:
        raise HTTPException(400, f"Ngôn ngữ không được hỗ trợ: '{language}'")


def _prune_previews() -> None:
    cutoff = time.time() - PREVIEW_TTL_SECONDS
    if not os.path.isdir(PREVIEW_DIR):
        return
    for name in os.listdir(PREVIEW_DIR):
        path = os.path.join(PREVIEW_DIR, name)
        if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
            _rm(path)


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
    return {"languages": legacy._ALL_LANGUAGES, "device": STATE["device"], "clone": CLONE_LIMITS}


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


@app.post("/api/voices/inspect")
def inspect_voice(audio: UploadFile = File(...)):
    """Kiểm tra audio mẫu theo đúng luật của server (độ dài, dung lượng, định dạng) trước khi clone."""
    tmp = os.path.join(tempfile.gettempdir(), f"inspect_{uuid.uuid4().hex}{os.path.splitext(audio.filename or '')[1].lower()}")
    try:
        _upload_ext(audio)
        _save_upload(audio, tmp)
        return _inspect_audio(tmp)
    except HTTPException as e:
        return {"duration": None, "errors": [str(e.detail)], "warnings": []}
    finally:
        _rm(tmp)


@app.post("/api/voices")
def create_voice(
    audio: UploadFile = File(...),
    name: str = Form(...),
    avatar: str = Form("🎙️"),
    style_tag: str = Form("Custom Voice"),
    ref_text: str = Form(""),
):
    lim = CLONE_LIMITS
    name, avatar, style_tag = name.strip(), avatar.strip() or "🎙️", style_tag.strip() or "Custom Voice"
    if not name:
        raise HTTPException(400, "Vui lòng nhập tên giọng")
    for label, value, key in (("Tên giọng", name, "name_max_chars"), ("Phong cách", style_tag, "style_max_chars"), ("Icon", avatar, "avatar_max_chars")):
        if len(value) > lim[key]:
            raise HTTPException(400, f"{label} tối đa {lim[key]} ký tự")

    key = f"{avatar} {name} - {style_tag}"
    if key in legacy.get_all_voices():
        raise HTTPException(409, f"Đã có giọng '{name}' với icon và phong cách này. Hãy đổi tên hoặc phong cách.")

    ext = _upload_ext(audio)
    vid = f"voice_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    saved = os.path.join(legacy.CUSTOM_VOICES_DIR, f"{vid}{ext}")
    _save_upload(audio, saved)
    try:
        _validate_audio(saved)
        ref_text = ref_text.strip()
        if not ref_text:
            try:
                ref_text = _model().transcribe(saved).strip()
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(500, f"Không thể nhận diện lời thoại: {e}")
            if not ref_text:
                raise HTTPException(422, "Không nhận diện được lời thoại trong audio. Hãy nhập lời thoại thủ công.")
    except Exception:
        _rm(saved)
        raise

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
    if len(text) > CLONE_LIMITS["preview_max_chars"]:
        raise HTTPException(400, f"Văn bản nghe thử tối đa {CLONE_LIMITS['preview_max_chars']} ký tự")
    _check_language(language)
    ext = _upload_ext(audio)

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    _prune_previews()
    pid = f"preview_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    src = os.path.join(PREVIEW_DIR, f"{pid}_ref{ext}")
    out = os.path.join(PREVIEW_DIR, f"{pid}.wav")
    _save_upload(audio, src)
    try:
        _validate_audio(src)
        ref_text = ref_text.strip()
        if not ref_text:
            ref_text = model.transcribe(src).strip()
            if not ref_text:
                raise HTTPException(422, "Không nhận diện được lời thoại trong audio. Hãy nhập lời thoại thủ công.")
        prompt = model.create_voice_clone_prompt(ref_audio=src, ref_text=ref_text, preprocess_prompt=preprocess_prompt)
        cfg = OmniVoiceGenerationConfig(denoise=denoise, preprocess_prompt=preprocess_prompt)
        wav = model.generate(
            text=text,
            language=None if language == "Auto" else language,
            generation_config=cfg,
            voice_clone_prompt=prompt,
        )
        data = (wav[0] * 32767).astype(np.int16)
        sf.write(out, data, model.sampling_rate)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Lỗi nghe thử: {type(e).__name__}: {e}")
    finally:
        _rm(src)
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
def transcribe(audio: UploadFile = File(...)):
    ext = _upload_ext(audio)
    tmp = os.path.join(tempfile.gettempdir(), f"asr_{uuid.uuid4().hex}{ext}")
    _save_upload(audio, tmp)
    try:
        _validate_audio(tmp)
        t0 = time.time()
        try:
            text = _model().transcribe(tmp).strip()
        except Exception as e:
            raise HTTPException(500, f"Lỗi ASR: {e}")
        if not text:
            raise HTTPException(422, "Không nhận diện được lời thoại trong audio.")
        return {"text": text, "elapsed": round(time.time() - t0, 1)}
    finally:
        _rm(tmp)


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
