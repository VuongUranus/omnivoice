import { useEffect, useState } from 'react'

// Giống useState nhưng nhớ giá trị trong localStorage của trình duyệt.
// Mọi thao tác storage đều bọc try/catch: chế độ riêng tư hoặc bị chặn vẫn chạy bình thường, chỉ không nhớ.
export function usePersisted(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw == null) return initial
      const parsed = JSON.parse(raw)
      return initial && typeof initial === 'object' ? { ...initial, ...parsed } : parsed
    } catch {
      return initial
    }
  })

  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(value)) } catch {}
  }, [key, value])

  return [value, setValue]
}
