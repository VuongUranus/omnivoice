import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

// Thông báo nhỏ ở góc màn hình (tự code, không dùng alert của trình duyệt).
// Dùng: const toast = useToast(); toast.push({ kind: 'success'|'error'|'info', title, message, action: { label, onClick } })
const Ctx = createContext({ push: () => {}, dismiss: () => {} })
export const useToast = () => useContext(Ctx)

const STYLE = {
  success: { icon: CheckCircle2, color: 'text-emerald-600' },
  error: { icon: AlertTriangle, color: 'text-red-600' },
  info: { icon: Info, color: 'text-brand-500' },
}

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    clearTimeout(timers.current[id])
    delete timers.current[id]
    setItems((xs) => xs.filter((x) => x.id !== id))
  }, [])

  const push = useCallback((t) => {
    const id = Math.random().toString(36).slice(2)
    setItems((xs) => [...xs.slice(-3), { kind: 'info', ...t, id }])
    timers.current[id] = setTimeout(() => dismiss(id), t.duration ?? 8000)
    return id
  }, [dismiss])

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss])

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-28 right-6 z-[70] flex w-80 flex-col gap-2" aria-live="polite">
        {items.map((t) => {
          const { icon: Icon, color } = STYLE[t.kind] || STYLE.info
          return (
            <div key={t.id} role="status" className="pointer-events-auto flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-xl dark:border-slate-800 dark:bg-slate-900">
              <Icon size={18} className={`mt-0.5 shrink-0 ${color}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{t.title}</div>
                {t.message && <div className="mt-0.5 line-clamp-3 break-words text-xs text-slate-500">{t.message}</div>}
                {t.action && (
                  <button onClick={() => { t.action.onClick(); dismiss(t.id) }} className="mt-1.5 text-xs font-semibold text-brand-600 hover:underline">{t.action.label}</button>
                )}
              </div>
              <button onClick={() => dismiss(t.id)} aria-label="Đóng" className="rounded p-0.5 text-slate-400 hover:text-slate-700"><X size={14} /></button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}
