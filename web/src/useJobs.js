import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

const ACTIVE = ['queued', 'running']
const SHOWN = ['queued', 'running', 'failed']

// Theo dõi hàng đợi tạo giọng trên server bằng polling (1s khi có job đang hoạt động, dừng khi rảnh).
// onDone(job) / onFailed(job) / onLost(id) được gọi một lần cho mỗi job đã thấy đang hoạt động trong phiên này.
export function useJobs({ onDone, onFailed, onLost }) {
  const [all, setAll] = useState([])
  const [offset, setOffset] = useState(0) // lệch giờ server - trình duyệt (ms), để đồng hồ "đang tạo" đúng
  const seen = useRef(new Set())
  const cb = useRef({})
  cb.current = { onDone, onFailed, onLost }
  const timer = useRef(0), fails = useRef(0), alive = useRef(true), running = useRef(false)

  const apply = useCallback((list) => {
    const byId = new Map(list.map((j) => [j.id, j]))
    for (const id of [...seen.current]) {
      const j = byId.get(id)
      if (!j) { seen.current.delete(id); cb.current.onLost?.(id) } // biến mất khỏi danh sách: server đã khởi động lại
      else if (j.status === 'done') { seen.current.delete(id); cb.current.onDone?.(j) }
      else if (j.status === 'failed') { seen.current.delete(id); cb.current.onFailed?.(j) }
      else if (j.status === 'cancelled') seen.current.delete(id)
    }
    list.forEach((j) => ACTIVE.includes(j.status) && seen.current.add(j.id))
    setAll(list)
  }, [])

  const schedule = useCallback((ms, fn) => {
    clearTimeout(timer.current)
    if (alive.current && ms > 0) timer.current = setTimeout(fn, ms)
  }, [])

  const poll = useCallback(async () => {
    if (running.current) return
    running.current = true
    try {
      const r = await api.jobs()
      fails.current = 0
      setOffset(r.server_time * 1000 - Date.now())
      apply(r.jobs)
      schedule(r.jobs.some((j) => ACTIVE.includes(j.status)) ? 1000 : 0, poll)
    } catch {
      fails.current += 1
      // Mất kết nối khi đang theo dõi job thì thử lại với thời gian chờ tăng dần
      schedule(seen.current.size ? Math.min(1000 * 2 ** fails.current, 10000) : 0, poll)
    } finally { running.current = false }
  }, [apply, schedule])

  const kick = useCallback(() => { clearTimeout(timer.current); poll() }, [poll])

  useEffect(() => {
    alive.current = true
    poll() // một lần lúc mở trang để khôi phục các job còn đang chạy sau khi tải lại
    return () => { alive.current = false; clearTimeout(timer.current) }
  }, [poll])

  const submit = useCallback(async (payload) => {
    const job = await api.submitJob(payload)
    seen.current.add(job.id)
    setAll((js) => [job, ...js.filter((j) => j.id !== job.id)])
    kick()
    return job
  }, [kick])

  const drop = (id) => { seen.current.delete(id); setAll((js) => js.filter((j) => j.id !== id)) }
  const cancel = useCallback(async (id) => { await api.cancelJob(id); drop(id); kick() }, [kick])
  const dismiss = useCallback(async (id) => { await api.cancelJob(id); drop(id) }, [])
  const retry = useCallback(async (id) => {
    const job = await api.retryJob(id)
    drop(id); seen.current.add(job.id)
    setAll((js) => [job, ...js])
    kick()
    return job
  }, [kick])

  const jobs = all.filter((j) => SHOWN.includes(j.status)).sort((a, b) => a.created_at - b.created_at)
  const runningN = all.filter((j) => j.status === 'running').length
  const queuedN = all.filter((j) => j.status === 'queued').length
  return { jobs, running: runningN, queued: queuedN, active: runningN + queuedN, offset, submit, cancel, dismiss, retry, kick }
}
