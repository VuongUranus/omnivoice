"""
Hàng đợi job chạy nền cho OmniVoice Studio.

Một worker thread duy nhất lấy job theo thứ tự FIFO, nên model chỉ phải xử lý một yêu cầu tại một thời điểm.
Module này không phụ thuộc FastAPI hay model: `run_fn(request)` do nơi gọi truyền vào.
Hàng đợi nằm trong RAM; tắt tiến trình là mất các job đang chờ/đang chạy.
"""

import threading
import time
import uuid
from collections import OrderedDict, deque
from typing import Any, Callable, Optional

ACTIVE = ("queued", "running")


class QueueFull(Exception):
    """Hàng chờ đã đầy."""


class JobNotFound(Exception):
    pass


class JobConflict(Exception):
    """Thao tác không hợp lệ với trạng thái hiện tại của job (vd: huỷ job đang chạy)."""


class Job:
    def __init__(self, request: Any, meta: dict):
        self.id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.request = request
        self.meta = meta  # thông tin hiển thị: text_preview, voice_name, avatar, grad…
        self.status = "queued"
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.error_status = 500
        self.ahead = 0  # số yêu cầu phải xong trước job này, tính đúng tại thời điểm xếp hàng
        self.done = threading.Event()  # được set khi job kết thúc (xong, lỗi hoặc huỷ)


class JobQueue:
    def __init__(self, run_fn: Callable[[Any], Any], max_pending: int = 20, keep_finished: int = 30):
        self._run = run_fn
        self.max_pending = max_pending
        self.keep_finished = keep_finished
        self._cv = threading.Condition(threading.RLock())
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._pending: deque = deque()
        self._worker: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ gửi / hỏi
    def submit(self, request: Any, meta: Optional[dict] = None) -> Job:
        with self._cv:
            if len(self._pending) >= self.max_pending:
                raise QueueFull(f"Hàng đợi đã đầy ({self.max_pending} yêu cầu đang chờ). Hãy thử lại sau.")
            job = Job(request, dict(meta or {}))
            job.ahead = sum(1 for j in self._jobs.values() if j.status == "running") + len(self._pending)
            self._jobs[job.id] = job
            self._pending.append(job.id)
            self._ensure_worker()
            self._cv.notify()
            return job

    def get(self, job_id: str) -> Job:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            return job

    def position(self, job: Job) -> int:
        """Vị trí trong hàng chờ (1 = kế tiếp); 0 nếu job không còn chờ."""
        with self._cv:
            try:
                return list(self._pending).index(job.id) + 1
            except ValueError:
                return 0

    def counts(self) -> dict:
        with self._cv:
            running = sum(1 for j in self._jobs.values() if j.status == "running")
            return {"running": running, "queued": len(self._pending)}

    def snapshot(self) -> list:
        """Danh sách job (mới nhất trước) dưới dạng dict gọn nhẹ để trả về qua API."""
        with self._cv:
            return [self.to_dict(j) for j in reversed(self._jobs.values())]

    def to_dict(self, job: Job) -> dict:
        with self._cv:
            return {
                "id": job.id, "status": job.status, "queue_position": self.position(job),
                "ahead": job.ahead, "created_at": job.created_at, "started_at": job.started_at, "finished_at": job.finished_at,
                "result": job.result, "error": job.error, **job.meta,
            }

    # ------------------------------------------------------------------ huỷ / thử lại
    def cancel(self, job_id: str) -> None:
        """Huỷ job đang chờ; job đã kết thúc thì xoá khỏi danh sách; job đang chạy thì từ chối."""
        with self._cv:
            job = self.get(job_id)
            if job.status == "running":
                raise JobConflict("Không thể huỷ job đang chạy: model không dừng giữa chừng được.")
            if job.status == "queued":
                self._pending.remove(job.id)
                job.status = "cancelled"
                job.finished_at = time.time()
                job.done.set()
            else:
                del self._jobs[job.id]

    def retry(self, job_id: str) -> Job:
        """Gửi lại một job đã lỗi hoặc đã huỷ (xoá bản cũ, tạo bản mới ở cuối hàng chờ)."""
        with self._cv:
            job = self.get(job_id)
            if job.status not in ("failed", "cancelled"):
                raise JobConflict("Chỉ thử lại được job đã lỗi hoặc đã huỷ.")
            new = self.submit(job.request, job.meta)  # có thể ném QueueFull; khi đó bản cũ vẫn còn
            self._jobs.pop(job.id, None)
            return new

    # ------------------------------------------------------------------ worker
    def _ensure_worker(self) -> None:
        # Khởi động lười ở lần submit đầu tiên (chạy được cả khi không có lifespan của ứng dụng)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._loop, name="job-worker", daemon=True)
            self._worker.start()

    def _loop(self) -> None:
        while True:
            with self._cv:
                while not self._pending:
                    self._cv.wait()
                job = self._jobs[self._pending.popleft()]
                job.status = "running"
                job.started_at = time.time()
            result, error, status = None, None, 500
            try:
                result = self._run(job.request)
            except Exception as e:  # một job lỗi không được làm chết worker
                error = str(getattr(e, "detail", None) or f"{type(e).__name__}: {e}")
                status = getattr(e, "status_code", 500)
            with self._cv:
                job.finished_at = time.time()
                if error is None:
                    job.status, job.result = "done", result
                else:
                    job.status, job.error, job.error_status = "failed", error, status
                job.done.set()
                self._prune()

    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.status not in ACTIVE]
        for j in finished[: max(0, len(finished) - self.keep_finished)]:
            del self._jobs[j.id]
