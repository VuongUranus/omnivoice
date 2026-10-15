export const Card = ({ className = '', children }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>{children}</div>
)

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="mb-6 flex items-end justify-between gap-4">
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
    </div>
    {children}
  </div>
)

export const Button = ({ variant = 'primary', className = '', ...p }) => {
  const styles = {
    primary: 'bg-brand-500 text-white shadow-lg shadow-brand-500/25 hover:bg-brand-600 disabled:opacity-50',
    ghost: 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
    danger: 'text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10',
  }
  return (
    <button {...p}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed ${styles[variant]} ${className}`} />
  )
}

export const inputCls =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-900'

export const Field = ({ label, hint, children }) => (
  <label className="block">
    <span className="mb-1.5 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
      {label}{hint && <span className="font-mono normal-case text-brand-500">{hint}</span>}
    </span>
    {children}
  </label>
)

export const VoiceAvatar = ({ voice, size = 'h-10 w-10 text-lg' }) => (
  <span className={`grid shrink-0 place-items-center rounded-xl ${size}`} style={{ background: voice?.grad || '#334155' }}>
    {voice?.avatar || '🎙️'}
  </span>
)

export const fmtDur = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
