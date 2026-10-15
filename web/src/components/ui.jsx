import { useEffect, useRef, useState } from 'react'
import { Check, ChevronsUpDown, Search } from 'lucide-react'

export const fmtDur = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`

export const inputCls =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-brand-500 dark:border-slate-800 dark:bg-slate-900'

export const Card = ({ className = '', children }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 ${className}`}>{children}</div>
)

export const Button = ({ variant = 'primary', className = '', ...p }) => {
  const styles = {
    primary: 'rounded-full bg-gradient-to-r from-brand-500 to-brand-400 text-white hover:opacity-90 disabled:opacity-40',
    dark: 'rounded-full bg-slate-900 text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900',
    outline: 'rounded-full border border-brand-500 text-brand-500 hover:bg-brand-50 dark:hover:bg-brand-500/10 disabled:opacity-40',
    ghost: 'rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
    danger: 'rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10',
  }
  return (
    <button {...p}
      className={`inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${styles[variant]} ${className}`} />
  )
}

export const Toggle = ({ checked, onChange, label, hint }) => (
  <div className="flex items-center gap-2.5 py-1.5">
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={`relative h-4 w-7 shrink-0 rounded-full transition ${checked ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-700'}`}>
      <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${checked ? 'left-3.5' : 'left-0.5'}`} />
    </button>
    <span className="text-sm">{label}</span>
    {hint && <span className="text-xs text-slate-400">{hint}</span>}
  </div>
)

export const Slider = ({ label, value, min, max, step, onChange, fmt = (v) => v }) => (
  <div className="py-2.5">
    <div className="mb-2 flex items-center justify-between">
      <span className="text-sm font-medium">{label}</span>
      <span className="min-w-[44px] rounded-md bg-slate-100 px-2 py-0.5 text-center text-xs dark:bg-slate-800">{fmt(value)}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} className="h-1 w-full" />
  </div>
)

export const Tag = ({ children }) => (
  <span className="whitespace-nowrap rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">{children}</span>
)

// Avatar vuông bo góc, phủ radial-gradient để giống ảnh trừu tượng của MiniMax
export const VoiceAvatar = ({ voice, size = 'h-14 w-14', text = 'text-xl' }) => (
  <span className={`relative grid shrink-0 place-items-center overflow-hidden rounded-xl ${size} ${text}`}
    style={{ background: voice?.grad || 'linear-gradient(135deg,#64748b,#334155)' }}>
    <span className="absolute inset-0" style={{ background: 'radial-gradient(circle at 25% 20%, rgba(255,255,255,.55), transparent 55%), radial-gradient(circle at 80% 90%, rgba(0,0,0,.25), transparent 60%)' }} />
    <span className="relative">{voice?.avatar || '🎙️'}</span>
  </span>
)

// Dropdown tùy chỉnh thay cho <select> của hệ thống
// options: [{ value, label, trigger? }] — trigger là nhãn hiển thị trên nút (mặc định là label)
// searchable: thêm ô tìm kiếm (không phân biệt hoa thường và dấu), hỗ trợ ↑ ↓ Enter Esc
const norm = (s) => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

export const Select = ({ value, options, onChange, icon: Icon, up = false, searchable = false, searchPlaceholder = 'Tìm kiếm…', className = '', triggerClass = '' }) => {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hi, setHi] = useState(0)
  const ref = useRef(null)
  const listRef = useRef(null)
  const current = options.find((o) => o.value === value)

  const needle = norm(q.trim())
  const shown = needle ? options.filter((o) => norm(`${o.label} ${o.trigger ?? ''}`).includes(needle)) : options

  const close = () => { setOpen(false); setQ('') }
  const pick = (o) => { onChange(o.value); close() }
  const toggle = () => {
    if (open) return close()
    setHi(Math.max(0, options.findIndex((o) => o.value === value)))
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    const onDown = (e) => { if (!ref.current?.contains(e.target)) close() }
    const onKey = (e) => { if (e.key === 'Escape') close() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Giữ mục đang được tô sáng trong vùng nhìn thấy
  useEffect(() => {
    if (open) listRef.current?.querySelector('[data-hi="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [open, hi, q])

  const onSearchKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(h + 1, shown.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); if (shown[hi]) pick(shown[hi]) }
  }

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button type="button" onClick={toggle} aria-haspopup="listbox" aria-expanded={open}
        className={`flex w-full items-center gap-2 rounded-xl bg-slate-100 px-3 py-2.5 text-left text-xs text-slate-600 transition hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 ${triggerClass}`}>
        {Icon && <Icon size={14} className="shrink-0 text-slate-400" />}
        <span className="flex-1 truncate">{current?.trigger ?? current?.label ?? value}</span>
        <ChevronsUpDown size={13} className="shrink-0 text-slate-400" />
      </button>
      {open && (
        <div className={`absolute left-0 z-30 w-full min-w-[240px] rounded-2xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-800 dark:bg-slate-900 ${up ? 'bottom-full mb-2' : 'top-full mt-2'}`}>
          {searchable && (
            <div className="relative mb-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setHi(0) }} onKeyDown={onSearchKey}
                placeholder={searchPlaceholder}
                className="w-full rounded-xl bg-slate-50 py-2.5 pl-9 pr-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 dark:bg-slate-800 dark:text-slate-100" />
            </div>
          )}
          <ul ref={listRef} role="listbox" className="max-h-64 overflow-y-auto">
            {shown.length === 0 && <li className="px-3 py-6 text-center text-sm text-slate-400">Không tìm thấy kết quả</li>}
            {shown.map((o, i) => {
              const active = o.value === value
              return (
                <li key={o.value} role="option" aria-selected={active}>
                  <button type="button" data-hi={i === hi} onClick={() => pick(o)} onMouseEnter={() => setHi(i)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm text-slate-800 transition dark:text-slate-100 ${
                      i === hi ? 'bg-slate-100 dark:bg-slate-800' : ''} ${active ? 'font-medium' : ''}`}>
                    {o.label}
                    {active && <Check size={14} className="text-brand-500" />}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}

// Nhãn 'Auto' hiển thị là 'Detect Language' trên nút chọn
export const langOptions = (languages) => languages.map((l) => ({ value: l, label: l, trigger: l === 'Auto' ? 'Detect Language' : l }))
