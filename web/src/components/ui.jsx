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
