"""
Ví dụ tạo giọng nói bằng Python API với OmniVoice trên Apple Silicon (Mac M1 Pro - MPS).
"""
import torch
import soundfile as sf
from omnivoice import OmniVoice

print("--- Đang tải mô hình OmniVoice (lần đầu sẽ tải weights ~2.5GB từ Hugging Face) ---")
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Thiết bị sử dụng: {device}")

# Khởi tạo model với Apple Silicon MPS
model = OmniVoice.from_pretrained(
    "k2-fsa/OmniVoice",
    device_map=device,
    dtype=torch.float32 if device == "mps" else torch.float16,
)

text_prompt = "Xin chào! Đây là bản thử nghiệm tạo giọng nói nhân tạo OmniVoice chạy trực tiếp trên chip Apple M1 Pro."
print(f"Đang tạo giọng nói cho văn bản:\n\"{text_prompt}\"")

# Tạo âm thanh (có thể truyền ref_audio và ref_text để clone giọng nếu muốn)
audio = model.generate(
    text=text_prompt,
)

output_filename = "output_demo.wav"
sf.write(output_filename, audio[0], 24000)
print(f" Hoàn tất! File âm thanh đã được lưu tại: {output_filename}")
