import { useEffect, useState } from 'react'
import { api } from './api'

export const IDLE = { status: 'idle', duration: null, errors: [], warnings: [] }

export const clip = (s, n) => Array.from(s).slice(0, n).join('')
export const mb = (bytes) => (bytes / 1024 / 1024).toFixed(1)
export const extLabel = (exts) => exts.map((e) => e.replace('.', '').toUpperCase()).join(', ')
export const extOf = (name) => (name.match(/\.[^.]+$/)?.[0] || '').toLowerCase()

// Kiểm tra nhanh phía client theo đúng giới hạn server công bố qua /api/meta (server vẫn là nơi quyết định cuối cùng)
export function precheckFile(f, limits) {
  const ext = extOf(f.name)
  if (!limits.extensions.includes(ext)) {
    return `Định dạng '${ext || 'không rõ'}' không được hỗ trợ. Chỉ nhận: ${extLabel(limits.extensions)}.`
  }
  if (f.size > limits.max_upload_mb * 1024 * 1024) {
    return `File ${mb(f.size)}MB vượt quá giới hạn ${limits.max_upload_mb}MB.`
  }
  return null
}

// Hỏi server kiểm tra audio mẫu (độ dài, định dạng, dung lượng) ngay khi chọn file
export function useAudioInspect(file) {
  const [info, setInfo] = useState(IDLE)
  useEffect(() => {
    if (!file) { setInfo(IDLE); return }
    let stale = false
    setInfo({ ...IDLE, status: 'checking' })
    const f = new FormData(); f.append('audio', file)
    api.inspectAudio(f)
      .then((r) => !stale && setInfo({ status: 'done', ...r }))
      .catch((e) => !stale && setInfo({ ...IDLE, status: 'done', errors: [e.message] }))
    return () => { stale = true }
  }, [file])
  return info
}
