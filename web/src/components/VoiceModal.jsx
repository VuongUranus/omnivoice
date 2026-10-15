import { useConfirm } from '../confirm'
import { useRef, useState } from 'react'
import { Pause, Play, Search, Trash2, X } from 'lucide-react'
import { api } from '../api'
import { Tag, VoiceAvatar } from './ui'

const SUGGESTIONS = ['Tiếng Việt', 'Nam', 'Podcast', 'Documentary']

export function VoiceRow({ voice, selected, onUse, onDelete }) {
  const audio = useRef(null)
  const [on, setOn] = useState(false)
  const tags = voice.tags || []
  const toggle = () => (audio.current.paused ? audio.current.play() : audio.current.pause())

  return (
    <div className={`flex items-center gap-4 rounded-2xl p-2.5 transition hover:bg-slate-50 dark:hover:bg-slate-900 ${selected ? 'bg-brand-50/60 dark:bg-brand-500/10' : ''}`}>
      <VoiceAvatar voice={voice} size="h-14 w-14" text="text-2xl" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold">{voice.name} - {voice.style_tag}</div>
        <div className="mt-1 truncate text-xs text-slate-500">{voice.desc}</div>
      </div>
      <div className="hidden items-center gap-1.5 sm:flex">
        {tags.slice(0, 2).map((t) => <Tag key={t}>{t}</Tag>)}
        {tags.length > 2 && <Tag>+{tags.length - 2}</Tag>}
      </div>
      {voice.audio_url && (
        <>
          <audio ref={audio} src={voice.audio_url} onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => setOn(false)} />
          <button onClick={toggle} title="Nghe mẫu" className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
            {on ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" className="ml-0.5" />}
          </button>
        </>
      )}
      <button onClick={() => onUse(voice.key)} className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900">Use</button>
      {onDelete && voice.custom && (
        <button onClick={() => onDelete(voice)} title="Xoá giọng" className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 size={16} /></button>
      )}
    </div>
  )
}

// Lọc + tìm kiếm dùng chung cho modal và trang Voice Library
export function VoiceBrowser({ voices, selected, onUse, onChanged, scrollClass = '' }) {
  const confirm = useConfirm()
  const [tab, setTab] = useState('library')
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const list = voices
    .filter((v) => (tab === 'mine' ? v.custom : !v.custom))
    .filter((v) => !needle || [v.name, v.style_tag, v.desc, ...(v.tags || [])].join(' ').toLowerCase().includes(needle))

  const remove = async (v) => {
    const ok = await confirm({
      title: 'Xoá giọng?',
      message: `Giọng "${v.name}" sẽ bị xoá khỏi thư viện. Hành động này không thể hoàn tác.`,
      confirmText: 'Xoá',
    })
    if (ok) { await api.deleteVoice(v.key); onChanged() }
  }

  return (
    <>
      <div className="mb-4 flex gap-6">
        {[['library', 'Library'], ['mine', 'My Voices']].map(([id, l]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`-mb-px border-b-2 pb-1.5 text-lg font-semibold ${tab === id ? 'border-slate-900 dark:border-slate-100' : 'border-transparent text-slate-400'}`}>{l}</button>
        ))}
      </div>
      <div className="relative mb-3">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search voices"
          className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-brand-500 dark:border-slate-800 dark:bg-slate-900" />
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        Try:
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => setQ(s)} className="rounded-full border border-dashed border-slate-300 px-3 py-1 hover:border-brand-500 hover:text-brand-600 dark:border-slate-700">{s}</button>
        ))}
      </div>
      <div className={`space-y-1 overflow-y-auto ${scrollClass}`}>
        {list.length === 0 && <p className="py-12 text-center text-sm text-slate-400">{tab === 'mine' ? 'Chưa có giọng tuỳ chỉnh. Hãy tạo ở Voice Clone.' : 'Không tìm thấy giọng phù hợp.'}</p>}
        {list.map((v) => <VoiceRow key={v.key} voice={v} selected={v.key === selected} onUse={onUse} onDelete={remove} />)}
      </div>
    </>
  )
}

export default function VoiceModal({ voices, selected, onUse, onClose, onChanged }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-[1px]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-3xl bg-white p-7 shadow-2xl dark:bg-slate-950">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Voice Selection</h2>
          <button onClick={onClose} className="rounded-full p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"><X size={20} /></button>
        </div>
        <VoiceBrowser voices={voices} selected={selected} onUse={onUse} onChanged={onChanged} scrollClass="min-h-0 flex-1" />
      </div>
    </div>
  )
}
