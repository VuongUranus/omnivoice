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
import json
import logging
import os
import re
import shutil
import tempfile
import threading
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

try:
    from omnivoice.models.omnivoice import _resolve_instruct  # luật kiểm tra instruct mà model áp dụng khi Generate
except ImportError:  # bản OmniVoice khác: bỏ qua kiểm tra, để model tự báo lỗi
    _resolve_instruct = None

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

# Giới hạn độ dài văn bản cho Text to Speech. Bản thân model KHÔNG giới hạn (văn bản dài được tự tách theo
# dấu câu thành các đoạn ~15s, xem docs/generation-parameters.md của OmniVoice); đây là chốt chặn để một
# request không chạy quá lâu. Đổi bằng: python api_server.py --max-chars 10000
TTS_LIMITS = {"max_chars": 5000}

# Giới hạn khi thêm/sửa thông tin giọng (Voice Library)
DEFAULT_GRAD = "linear-gradient(135deg,#ec4899,#8b5cf6)"
GRADIENTS = [f"linear-gradient(135deg,{a},{b})" for a, b in (
    ("#6366f1", "#8b5cf6"), ("#0ea5e9", "#06b6d4"), ("#f59e0b", "#f97316"), ("#ec4899", "#8b5cf6"),
    ("#10b981", "#14b8a6"), ("#ef4444", "#f97316"), ("#84cc16", "#22c55e"), ("#64748b", "#334155"),
)]
CLONE_LIMITS.update({
    "desc_max_chars": 200,
    "tags_max_count": 8,
    "tag_max_chars": 20,
    "gradients": GRADIENTS,
    "instruct_validation": _resolve_instruct is not None,
})
GRAD_RE = re.compile(r"^linear-gradient\(135deg,\s*#[0-9a-fA-F]{6}\s*,\s*#[0-9a-fA-F]{6}\)$")

# Giọng có sẵn (PRESET_VOICES) nằm trong code nên không sửa trực tiếp: mọi chỉnh sửa/xoá được lưu
# thành lớp "ghi đè" riêng, file wav gốc trong presets/ không bao giờ bị đụng tới.
OVERRIDES_FILE = os.path.join(legacy.CUSTOM_VOICES_DIR, "preset_overrides.json")
EDITABLE_FIELDS = ("name", "avatar", "style_tag", "desc", "tags", "grad", "instruct", "ref_text", "audio")
VOICE_LOCK = threading.RLock()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _model() -> OmniVoice:
    if STATE["model"] is None:
        raise HTTPException(503, "Model chưa sẵn sàng")
    return STATE["model"]


def _audio_url(path: Optional[str]) -> str:
    return f"/api/files?path={path}" if path else ""


def _write_json(path: str, obj) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_overrides() -> dict:
    try:
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {"overrides": dict(data.get("overrides", {})), "deleted": list(data.get("deleted", []))}


def _save_overrides(data: dict) -> None:
    _write_json(OVERRIDES_FILE, data)


def _preset_view(key: str, ov: dict) -> Optional[dict]:
    """Giọng có sẵn sau khi áp dụng chỉnh sửa; None nếu thiếu file audio."""
    base = legacy.PRESET_VOICES[key]
    v = {**base, **ov["overrides"].get(key, {})}
    if not v.get("audio") or not os.path.exists(v["audio"]):
        v["audio"] = base.get("audio")  # audio thay thế bị mất -> quay về bản gốc
    return v if v.get("audio") and os.path.exists(v["audio"]) else None


def all_voices() -> dict:
    """Giọng có sẵn (đã áp dụng sửa/xoá) + giọng tùy chỉnh."""
    ov = _load_overrides()
    voices = {}
    for key in legacy.PRESET_VOICES:
        if key in ov["deleted"]:
            continue
        v = _preset_view(key, ov)
        if v:
            voices[key] = v
    voices.update(legacy.load_custom_voices())
    return voices


def _instruct_error(instruct: Optional[str]) -> Optional[str]:
    """Thông báo lỗi nếu instruct không nằm trong từ vựng của model, ngược lại None."""
    if not instruct or not instruct.strip() or _resolve_instruct is None:
        return None
    try:
        _resolve_instruct(instruct)
    except ValueError as e:
        return str(e)
    return None


def _voice_json(key: str, v: dict) -> dict:
    preset = key in legacy.PRESET_VOICES
    return {
        "key": key,
        "name": v.get("name"),
        "avatar": v.get("avatar", "🎙️"),
        "style_tag": v.get("style_tag", ""),
        "desc": v.get("desc", ""),
        "tags": v.get("tags", []),
        "grad": v.get("grad", ""),
        "ref_text": v.get("ref_text", ""),
        "instruct": v.get("instruct", ""),
        "instruct_error": _instruct_error(v.get("instruct")),
        "audio_url": _audio_url(v.get("audio")),
        "custom": not preset,
        "preset": preset,
        "modified": preset and key in _load_overrides()["overrides"],
    }


def _history_json(it: dict) -> dict:
    voice = all_voices().get(it.get("voice_choice"), {})
    return {
        **{k: v for k, v in it.items() if k != "file_path"},
        "grad": voice.get("grad", ""),
        "audio_url": _audio_url(it["file_path"]),
    }


def _parse_tags(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
    except ValueError:
        items = raw.split(",")
    return [str(t).strip() for t in items if str(t).strip()]


def _clean_voice_fields(*, name, avatar, style_tag, desc, tags, grad, instruct, exclude_key=None) -> dict:
    """Chuẩn hóa và kiểm tra thông tin giọng theo CLONE_LIMITS (dùng cho cả thêm lẫn sửa)."""
    lim = CLONE_LIMITS
    name, avatar, style_tag = name.strip(), avatar.strip() or "🎙️", style_tag.strip() or "Custom Voice"
    desc, instruct, grad = desc.strip(), instruct.strip(), grad.strip()
    if not name:
        raise HTTPException(400, "Vui lòng nhập tên giọng")
    for label, value, key in (("Tên giọng", name, "name_max_chars"), ("Phong cách", style_tag, "style_max_chars"),
                              ("Icon", avatar, "avatar_max_chars"), ("Mô tả", desc, "desc_max_chars")):
        if len(value) > lim[key]:
            raise HTTPException(400, f"{label} tối đa {lim[key]} ký tự")

    tag_list = []
    for t in _parse_tags(tags):
        if len(t) > lim["tag_max_chars"]:
            raise HTTPException(400, f"Mỗi tag tối đa {lim['tag_max_chars']} ký tự: '{t[:20]}…'")
        if t not in tag_list:
            tag_list.append(t)
    if len(tag_list) > lim["tags_max_count"]:
        raise HTTPException(400, f"Tối đa {lim['tags_max_count']} tag")

    if grad and not GRAD_RE.match(grad):
        raise HTTPException(400, "Màu nền không hợp lệ")
    err = _instruct_error(instruct)
    if err:
        raise HTTPException(400, f"Instruct không hợp lệ:\n{err}")

    for k, v in all_voices().items():
        if k != exclude_key and (v.get("avatar"), v.get("name"), v.get("style_tag")) == (avatar, name, style_tag):
            raise HTTPException(409, f"Đã có giọng '{name}' với icon và phong cách này. Hãy đổi tên hoặc phong cách.")
    return {"name": name, "avatar": avatar, "style_tag": style_tag, "desc": desc, "tags": tag_list,
            "grad": grad, "instruct": instruct}


def _ref_text_or_asr(path: str, ref_text: str) -> str:
    ref_text = ref_text.strip()
    if ref_text:
        return ref_text
    try:
        text = _model().transcribe(path).strip()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Không thể nhận diện lời thoại: {e}")
    if not text:
        raise HTTPException(422, "Không nhận diện được lời thoại trong audio. Hãy nhập lời thoại thủ công.")
    return text


def _own_audio(path: Optional[str]) -> bool:
    """Chỉ file nằm trong custom_voices/ mới là của người dùng; file trong presets/ thì không được xoá."""
    return bool(path) and os.path.realpath(os.path.dirname(path)) == os.path.realpath(legacy.CUSTOM_VOICES_DIR)


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
    v = all_voices().get(key)
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
    return {"languages": legacy._ALL_LANGUAGES, "device": STATE["device"], "clone": CLONE_LIMITS, "tts": TTS_LIMITS}


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
        for k, v in all_voices().items()
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
    desc: str = Form(""),
    tags: str = Form(""),
    grad: str = Form(""),
    instruct: str = Form(""),
):
    with VOICE_LOCK:
        fields = _clean_voice_fields(name=name, avatar=avatar, style_tag=style_tag, desc=desc, tags=tags,
                                     grad=grad, instruct=instruct)
        ext = _upload_ext(audio)
        vid = f"voice_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        saved = os.path.join(legacy.CUSTOM_VOICES_DIR, f"{vid}{ext}")
        _save_upload(audio, saved)
        try:
            _validate_audio(saved)
            ref_text = _ref_text_or_asr(saved, ref_text)
        except Exception:
            _rm(saved)
            raise

        # Key là định danh cố định (không đổi khi sửa tên) nên phải duy nhất, kể cả với giọng đã đổi tên/đã xoá
        key = f"{fields['avatar']} {fields['name']} - {fields['style_tag']}"
        custom = legacy.load_custom_voices()
        if key in custom or key in legacy.PRESET_VOICES or key in all_voices():
            key = f"{key} ({vid})"
        entry = {
            "id": vid, "audio": saved, "audio_url": "", "ref_text": ref_text, **fields,
            "desc": fields["desc"] or f"Giọng nhân bản tùy chỉnh: {ref_text[:60]}...",
            "tags": fields["tags"] or ["Tùy chỉnh", fields["style_tag"]],
            "grad": fields["grad"] or DEFAULT_GRAD,
        }
        custom[key] = entry
        legacy.save_custom_voices(custom)
        STATE["voice_cache"].pop(key, None)
        return _voice_json(key, entry)


@app.put("/api/voices")
def update_voice(
    key: str,
    audio: Optional[UploadFile] = File(None),
    name: str = Form(...),
    avatar: str = Form("🎙️"),
    style_tag: str = Form("Custom Voice"),
    desc: str = Form(""),
    tags: str = Form(""),
    grad: str = Form(""),
    instruct: str = Form(""),
    ref_text: str = Form(""),
):
    """Sửa giọng (cả giọng có sẵn lẫn giọng tùy chỉnh). `audio` là tùy chọn: có thì thay file mẫu."""
    with VOICE_LOCK:
        current = all_voices().get(key)
        if current is None:
            raise HTTPException(404, "Không tìm thấy giọng")
        preset = key in legacy.PRESET_VOICES
        fields = _clean_voice_fields(name=name, avatar=avatar, style_tag=style_tag, desc=desc, tags=tags,
                                     grad=grad, instruct=instruct, exclude_key=key)
        fields["grad"] = fields["grad"] or current.get("grad") or DEFAULT_GRAD

        new_audio = None
        ref_text = ref_text.strip()
        if audio is not None and audio.filename:
            ext = _upload_ext(audio)
            new_audio = os.path.join(legacy.CUSTOM_VOICES_DIR, f"voice_{int(time.time())}_{uuid.uuid4().hex[:4]}{ext}")
            _save_upload(audio, new_audio)
            try:
                _validate_audio(new_audio)
                ref_text = _ref_text_or_asr(new_audio, ref_text)  # audio mới thì lời thoại cũ không còn đúng
            except Exception:
                _rm(new_audio)
                raise
        elif not ref_text:
            ref_text = current.get("ref_text", "")

        desired = {**current, **fields, "ref_text": ref_text}
        old_audio = current.get("audio")
        if new_audio:
            desired["audio"] = new_audio

        if preset:
            data = _load_overrides()
            base = legacy.PRESET_VOICES[key]
            diff = {f: desired.get(f) for f in EDITABLE_FIELDS if desired.get(f) != base.get(f)}
            if diff:
                data["overrides"][key] = diff
            else:
                data["overrides"].pop(key, None)
            _save_overrides(data)
        else:
            custom = legacy.load_custom_voices()
            custom[key].update({f: desired[f] for f in EDITABLE_FIELDS if f in desired})
            legacy.save_custom_voices(custom)

        if new_audio and _own_audio(old_audio):
            _rm(old_audio)  # chỉ xoá file mẫu cũ do người dùng tải lên, không bao giờ xoá file trong presets/
        STATE["voice_cache"].pop(key, None)
        return _voice_json(key, all_voices()[key])


@app.get("/api/voices/deleted")
def list_deleted_voices():
    ov = _load_overrides()
    out = []
    for key in ov["deleted"]:
        if key in legacy.PRESET_VOICES:
            v = _preset_view(key, ov)
            if v:
                out.append(_voice_json(key, v))
    return out


@app.post("/api/voices/restore")
def restore_voice(key: str):
    with VOICE_LOCK:
        data = _load_overrides()
        if key not in data["deleted"]:
            raise HTTPException(404, "Giọng này không nằm trong danh sách đã xoá")
        data["deleted"].remove(key)
        _save_overrides(data)
        return _voice_json(key, all_voices()[key])


@app.post("/api/voices/reset")
def reset_voice(key: str):
    """Bỏ mọi chỉnh sửa của một giọng có sẵn, trả về bản mặc định."""
    if key not in legacy.PRESET_VOICES:
        raise HTTPException(404, "Chỉ giọng có sẵn mới có bản mặc định")
    with VOICE_LOCK:
        data = _load_overrides()
        old = data["overrides"].pop(key, None)
        _save_overrides(data)
        if old and _own_audio(old.get("audio")):
            _rm(old["audio"])
        STATE["voice_cache"].pop(key, None)
        v = all_voices().get(key)
        return _voice_json(key, v) if v else {"ok": True}


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
    with VOICE_LOCK:
        STATE["voice_cache"].pop(key, None)
        if key in legacy.PRESET_VOICES:
            # Giọng có sẵn chỉ bị ẩn (file wav trong presets/ giữ nguyên) và có thể khôi phục
            data = _load_overrides()
            if key not in data["deleted"]:
                data["deleted"].append(key)
                _save_overrides(data)
            return {"ok": True}
        voices = legacy.load_custom_voices()
        entry = voices.pop(key, None)
        if entry is None:
            raise HTTPException(404, "Không tìm thấy giọng")
        legacy.save_custom_voices(voices)
        _rm(entry["audio"])
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
    if len(text) > TTS_LIMITS["max_chars"]:
        raise HTTPException(400, f"Văn bản dài {len(text):,} ký tự, vượt giới hạn {TTS_LIMITS['max_chars']:,}. Hãy tách thành nhiều phần.")
    voices = all_voices()
    if req.voice not in voices:
        raise HTTPException(404, "Giọng không tồn tại")

    # Kiểm tra instruct trước khi tốn thời gian tạo prompt giọng
    instruct = req.instruct.strip() or voices[req.voice].get("instruct")
    err = _instruct_error(instruct)
    if err:
        hint = "" if req.instruct.strip() else " Vào Voice Library → Sửa giọng này để chỉnh lại instruct."
        raise HTTPException(400, f"Instruct không hợp lệ.{hint}\n{err}")

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
    p.add_argument("--max-chars", type=int, default=TTS_LIMITS["max_chars"],
                   help="Số ký tự tối đa mỗi lần tạo giọng (model không giới hạn, đây là chốt chặn thời gian xử lý)")
    args = p.parse_args()
    TTS_LIMITS["max_chars"] = max(1, args.max_chars)

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
