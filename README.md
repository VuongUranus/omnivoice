# omnivoice - OmniVoice Studio Web UI

Giao diện Studio hiện đại cho mô hình chuyển văn bản thành giọng nói (Text-to-Speech) và nhân bản giọng nói (Voice Cloning) **OmniVoice**, được tối ưu hóa tăng tốc phần cứng Apple Silicon GPU (`mps`) trên macOS.

---

## 1. Khởi động giao diện Web UI (Gradio)
Để sử dụng giao diện web trực quan, nhập văn bản và nghe thử hoặc clone giọng qua micro/file ghi âm:

```bash
./run_demo.sh
```
Sau đó mở trình duyệt tại: **http://127.0.0.1:7860**

*(Lưu ý: Lần đầu tiên chạy, hệ thống sẽ tự động tải trọng số mô hình ~2.5 GB từ Hugging Face về lưu vào bộ nhớ đệm).*

---

## 2. Chạy thử nghiệm bằng Python Script
Để tạo file âm thanh trực tiếp bằng code:

```bash
source .venv/bin/activate
python test_generate.py
```
File âm thanh sinh ra sẽ được lưu thành `output_demo.wav`.

---

## 3. Sử dụng Command Line (CLI)
OmniVoice cung cấp sẵn các lệnh dòng lệnh trong môi trường ảo:
```bash
source .venv/bin/activate

# Tạo giọng nói từ dòng lệnh
omnivoice-infer --text "Xin chào thế giới" --output out.wav --device mps
```

---

## 4. Giao diện React + Tailwind (mới)
Phiên bản web hiện đại hơn, dùng chung model, lịch sử và thư viện giọng với bản Gradio:

```bash
./run_react.sh          # build frontend (lần đầu) + chạy API
```
Mở **http://127.0.0.1:8000**.

Chế độ phát triển (hot reload): chạy `python api_server.py --device mps`, rồi `cd web && npm install && npm run dev` và mở http://127.0.0.1:5173.
