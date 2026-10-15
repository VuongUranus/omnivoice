import { useEffect, useRef, useState } from 'react'
import { Pause, Play, Download } from 'lucide-react'
import { fmtDur } from './ui'

export default function Player({ item }) {
  const ref = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [pos, setPos] = useState(0)

  useEffect(() => {
    if (item && ref.current) ref.current.play().catch(() => {})
  }, [item])

  if (!item) return null
  const dur = item.duration || 0

  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90 md:left-64">
      <audio ref={ref} src={item.audio_url}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setPos(e.currentTarget.currentTime)} />
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <button onClick={() => (playing ? ref.current.pause() : ref.current.play())}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-500 text-white shadow-lg shadow-brand-500/30 hover:bg-brand-600">
          {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{item.text}</div>
          <div className="mt-1.5 flex items-center gap-3">
            <span className="w-9 text-xs tabular-nums text-slate-500">{fmtDur(pos)}</span>
            <input type="range" min="0" max={dur} step="0.1" value={Math.min(pos, dur)}
              onChange={(e) => { ref.current.currentTime = +e.target.value }} className="h-1 flex-1" />
            <span className="w-9 text-xs tabular-nums text-slate-500">{fmtDur(dur)}</span>
          </div>
        </div>
        <a href={item.audio_url} download={`${item.id}.wav`} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" title="Tải xuống">
          <Download size={18} />
        </a>
      </div>
    </div>
  )
}
