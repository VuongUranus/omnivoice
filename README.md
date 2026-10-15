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

Giới hạn độ dài văn bản mỗi lần tạo giọng do server quy định (mặc định 5000 ký tự; bản thân model không giới hạn, văn bản dài được tự tách theo dấu câu). Đổi bằng `python api_server.py --device mps --max-chars 10000`, giao diện tự cập nhật theo.

### Tạo giọng nói bất đồng bộ (hàng đợi)
Bấm **Generate** là yêu cầu được xếp vào hàng đợi và trả về ngay; một worker duy nhất chạy model lần lượt từng yêu cầu. Bạn có thể gửi thêm đoạn khác, đổi trang hoặc tải lại trang trong lúc chờ: tiến trình hiện ở đầu panel phải của trang Text to Speech và ở thẻ trên header, kết quả tự vào History kèm thông báo.

- Hàng đợi nằm trong RAM: tắt server là mất các yêu cầu đang chờ/đang chạy (giao diện sẽ báo "đã bị mất"). Các bản đã tạo xong vẫn nằm trong History.
- Chỉ huỷ được yêu cầu đang chờ; yêu cầu đang chạy không dừng giữa chừng được vì model không hỗ trợ. Model cũng không báo tiến độ phần trăm, giao diện chỉ hiện thời gian đã chạy.
- Số yêu cầu chờ tối đa mặc định là 20, đổi bằng `python api_server.py --max-queue 50`.
- Nghe thử giọng clone và nhận diện chữ dùng chung model nên phải chờ tới lượt khi hàng đợi đang bận (tối đa 300 giây).
- API: `POST /api/jobs`, `GET /api/jobs`, `GET|DELETE /api/jobs/{id}`, `POST /api/jobs/{id}/retry`. `POST /api/generate` vẫn dùng được (đồng bộ, đi qua cùng hàng đợi).

