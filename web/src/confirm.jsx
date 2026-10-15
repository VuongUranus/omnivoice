import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'

// Hộp thoại xác nhận tự code, thay cho window.confirm.
// Dùng: const confirm = useConfirm(); if (await confirm({ title, message, confirmText })) { ... }
// Tuỳ chọn: detail (khung trích dẫn), icon (component lucide), danger (false = nút trung tính), cancelText
const Ctx = createContext(async () => false)
export const useConfirm = () => useContext(Ctx)

export function ConfirmProvider({ children }) {
  const [req, setReq] = useState(null)
  const pending = useRef(null)

  const confirm = useCallback((opts) => new Promise((resolve) => {
    pending.current?.(false) // đang có hộp thoại khác thì coi như huỷ
    pending.current = resolve
    setReq(opts)
  }), [])

  const close = useCallback((ok) => {
    pending.current?.(ok)
    pending.current = null
    setReq(null)
  }, [])

  useEffect(() => {
    if (!req) return
    const onKey = (e) => { if (e.key === 'Escape') close(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [req, close])

  const danger = req?.danger !== false
  const Icon = req?.icon || AlertTriangle

  return (
    <Ctx.Provider value={confirm}>
      {children}
      {req && (
        <div className="fixed inset-0 z-[60] grid place-items-center bg-black/40 p-4 backdrop-blur-[1px]"
          onMouseDown={(e) => e.target === e.currentTarget && close(false)}>
          <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-title"
            className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl dark:bg-slate-900">
            <div className="flex items-start gap-3">
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${danger ? 'bg-red-50 text-red-600 dark:bg-red-500/10' : 'bg-brand-50 text-brand-600 dark:bg-brand-500/10'}`}>
                <Icon size={20} />
              </span>
              <div className="min-w-0">
                <h2 id="confirm-title" className="text-base font-semibold">{req.title}</h2>
                {req.message && <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{req.message}</p>}
                {req.detail && (
                  <div className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">{req.detail}</div>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => close(false)}
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                {req.cancelText || 'Huỷ'}
              </button>
              <button autoFocus onClick={() => close(true)}
                className={`rounded-full px-5 py-2 text-sm font-semibold text-white ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-slate-900 hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900'}`}>
                {req.confirmText || 'Xác nhận'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Ctx.Provider>
  )
}
