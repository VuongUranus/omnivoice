import { useConfirm } from '../confirm'
import { Download, Pause, Play, Trash2 } from 'lucide-react'
import { api } from '../api'

const dayKey = (ts) => new Date(ts * 1000).toLocaleDateString('vi-VN', { day: 'numeric', month: 'long', year: 'numeric' })
const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })

export default function HistoryPanel({ items, current, playing, onPlay, onChanged, onRestore }) {
  const confirm = useConfirm()
  if (!items.length) return <p className="py-16 text-center text-sm text-slate-400">Chưa có bản ghi nào.</p>

  const groups = []
  items.forEach((it) => {
    const k = dayKey(it.timestamp)
    const g = groups[groups.length - 1]
    g?.k === k ? g.items.push(it) : groups.push({ k, items: [it] })
  })

  return (
    <div>
      {groups.map((g) => (
        <section key={g.k} className="mb-3">
          <h3 className="px-1 py-2 text-xs font-medium text-slate-500">{g.k}</h3>
          {g.items.map((it) => {
            const active = current?.id === it.id
            return (
              <div key={it.id} className={`group flex items-center gap-3 rounded-xl px-2 py-2 ${active ? 'bg-slate-100 dark:bg-slate-800' : 'hover:bg-slate-50 dark:hover:bg-slate-900'}`}>
                <button onClick={() => onPlay(it)} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 dark:bg-slate-800">
                  {active && playing ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" className="ml-0.5" />}
                </button>
                <button type="button" onClick={() => onRestore?.(it)} disabled={!onRestore || !it.text} title="Bấm để khôi phục văn bản này vào ô nhập"
                  className="min-w-0 flex-1 cursor-pointer rounded text-left disabled:cursor-default">
                  <div className="truncate text-[13px]">{it.text}</div>
                  <div className="truncate text-[11px] uppercase text-slate-400">{it.voice_name} · {hhmm(it.timestamp)}</div>
                </button>
                <div className="hidden items-center gap-0.5 text-slate-400 group-hover:flex">
                  <button onClick={async () => { await api.deleteHistory(it.id); onChanged() }} className="rounded p-1 hover:text-red-600"><Trash2 size={14} /></button>
                  <a href={it.audio_url} download={`${it.id}.wav`} className="rounded p-1 hover:text-slate-700"><Download size={14} /></a>
                </div>
              </div>
            )
          })}
        </section>
      ))}
      <button onClick={async () => {
        const ok = await confirm({ title: 'Xoá toàn bộ lịch sử?', message: 'Tất cả bản âm thanh đã tạo sẽ bị xoá vĩnh viễn.', confirmText: 'Xoá tất cả' })
        if (ok) { await api.clearHistory(); onChanged() }
      }}
        className="mt-2 flex items-center gap-1.5 px-1 text-xs text-slate-400 hover:text-red-600"><Trash2 size={13} /> Xoá tất cả</button>
    </div>
  )
}
