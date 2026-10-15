import { Download, Pause, Play, RotateCcw, RotateCw } from 'lucide-react'
import { VoiceAvatar, fmtDur } from './ui'

export default function Player({ item, voice, audioRef, playing, pos }) {
  if (!item) return null
  const dur = item.duration || 0
  const a = audioRef.current
  const seek = (d) => { if (a) a.currentTime = Math.max(0, Math.min(dur, a.currentTime + d)) }

  return (
    <div className="mx-4 mb-4 grid shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-4 rounded-2xl bg-slate-50 px-4 py-3 dark:bg-slate-900">
      <div className="flex min-w-0 items-center gap-3">
        <VoiceAvatar voice={voice} size="h-12 w-12" text="text-lg" />
        <div className="truncate text-sm font-semibold">{item.voice_name}: <span className="font-medium">{item.text}</span></div>
      </div>
      <div className="flex w-[min(520px,40vw)] flex-col items-center gap-1">
        <div className="flex items-center gap-5">
          <button onClick={() => seek(-10)} title="Lùi 10s" className="text-slate-600 hover:text-slate-900 dark:text-slate-400"><RotateCcw size={20} /></button>
          <button onClick={() => (playing ? a.pause() : a.play())}
            className="grid h-10 w-10 place-items-center rounded-full bg-slate-900 text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900">
            {playing ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" className="ml-0.5" />}
          </button>
          <button onClick={() => seek(10)} title="Tới 10s" className="text-slate-600 hover:text-slate-900 dark:text-slate-400"><RotateCw size={20} /></button>
        </div>
        <div className="flex w-full items-center gap-3 text-xs tabular-nums text-slate-500">
          <span>{fmtDur(pos)}</span>
          <input type="range" min="0" max={dur} step="0.1" value={Math.min(pos, dur)}
            onChange={(e) => { a.currentTime = +e.target.value }} className="h-1 flex-1" />
          <span>{fmtDur(dur)}</span>
        </div>
      </div>
      <div className="flex justify-end">
        <a href={item.audio_url} download={`${item.id}.wav`} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800" title="Tải xuống"><Download size={18} /></a>
      </div>
    </div>
  )
}
