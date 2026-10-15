import { useEffect, useState } from 'react'
import { AlertTriangle, Loader2, RotateCcw, X } from 'lucide-react'
import { VoiceAvatar } from './ui'

const fmtElapsed = (s) => (s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`)

// Hàng đợi tạo giọng: job đang chờ / đang chạy / bị lỗi. Job xong thì chuyển sang History.
export default function JobsStrip({ jobs, offset, onCancel, onRetry, onDismiss }) {
  const [, tick] = useState(0)
  const hasRunning = jobs.some((j) => j.status === 'running')
  useEffect(() => {
    if (!hasRunning) return
    const t = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [hasRunning])
  if (!jobs.length) return null

  const now = (Date.now() + offset) / 1000
  const btn = 'rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800'

  return (
    <div className="mb-3 space-y-2" data-testid="jobs-strip">
      {jobs.map((j) => (
        <div key={j.id} data-status={j.status} className={`flex items-center gap-3 rounded-xl border p-2.5 ${j.status === 'failed' ? 'border-red-200 bg-red-50/60 dark:border-red-500/30 dark:bg-red-500/5' : 'border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-900'}`}>
          <VoiceAvatar voice={{ avatar: j.avatar, grad: j.grad }} size="h-9 w-9" text="text-sm" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px]" title={j.text_preview}>{j.text_preview}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500">
              {j.status === 'running' && <><Loader2 size={11} className="animate-spin text-brand-500" /><span title="Model không hiển thị phần trăm tiến độ">Đang tạo · {fmtElapsed(Math.max(0, now - j.started_at))}</span></>}
              {j.status === 'queued' && <span>Đang chờ · vị trí #{j.queue_position}</span>}
              {j.status === 'failed' && <><AlertTriangle size={11} className="shrink-0 text-red-600" /><span className="line-clamp-2 break-words text-red-700 dark:text-red-300" title={j.error}>{j.error}</span></>}
            </div>
          </div>
          {j.status === 'queued' && <button onClick={() => onCancel(j.id)} title="Huỷ yêu cầu này" aria-label="Huỷ" className={btn}><X size={15} /></button>}
          {j.status === 'failed' && (
            <div className="flex shrink-0 items-center">
              <button onClick={() => onRetry(j.id)} title="Thử lại" aria-label="Thử lại" className={btn}><RotateCcw size={15} /></button>
              <button onClick={() => onDismiss(j.id)} title="Bỏ" aria-label="Bỏ" className={btn}><X size={15} /></button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
