import { usePersisted } from './usePersisted'
import { useCallback, useEffect, useRef, useState } from 'react'
import { AudioLines, Cpu, Library, Moon, Sun, Copy } from 'lucide-react'
import { api } from './api'
import TextToSpeech from './components/TextToSpeech'
import VoiceClone from './components/VoiceClone'
import VoiceLibrary from './components/VoiceLibrary'
import VoiceModal from './components/VoiceModal'
import Player from './components/Player'

const NAV = [
  { group: null, items: [{ id: 'library', label: 'Voice Library', icon: Library }] },
  { group: 'AI Generation', items: [{ id: 'tts', label: 'Text to Speech', icon: AudioLines }] },
  { group: 'AI Tools', items: [{ id: 'clone', label: 'Voice Clone', icon: Copy }] },
]

export default function App() {
  const [page, setPage] = usePersisted('ov.page', 'tts')
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const [voices, setVoices] = useState([])
  const [history, setHistory] = useState([])
  const [languages, setLanguages] = useState(['Auto'])
  const [limits, setLimits] = useState(null) // giới hạn Voice Clone do server quy định
  const [health, setHealth] = useState({ ready: false, device: '' })
  const [selectedVoice, setSelectedVoice] = usePersisted('ov.voice', null)
  const [modalOpen, setModalOpen] = useState(false)

  // Trạng thái phát nhạc dùng chung cho Player và danh sách lịch sử
  const audioRef = useRef(null)
  const [current, setCurrent] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [pos, setPos] = useState(0)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  const refreshVoices = useCallback(async () => {
    const v = await api.voices()
    setVoices(v)
    setSelectedVoice((cur) => (cur && v.some((x) => x.key === cur) ? cur : v[0]?.key ?? null))
  }, [])
  const refreshHistory = useCallback(async () => setHistory(await api.history()), [])

  const loadMeta = useCallback(
    () => api.meta().then((m) => { setLanguages(m.languages); setLimits(m.clone) }).catch(() => {}),
    [],
  )

  useEffect(() => {
    refreshVoices().catch(() => {})
    refreshHistory().catch(() => {})
    loadMeta()
    const poll = () => api.health().then(setHealth).catch(() => setHealth({ ready: false, device: '' }))
    poll()
    const t = setInterval(poll, 5000)
    return () => clearInterval(t)
  }, [refreshVoices, refreshHistory, loadMeta])

  // Nếu mở web trước khi server sẵn sàng, nạp lại dữ liệu ngay khi engine báo ready
  useEffect(() => {
    if (!health.ready) return
    loadMeta()
    refreshVoices().catch(() => {})
    refreshHistory().catch(() => {})
  }, [health.ready, loadMeta, refreshVoices, refreshHistory])

  const play = (item) => {
    if (current?.id === item.id) {
      const a = audioRef.current
      a.paused ? a.play() : a.pause()
    } else {
      setCurrent(item)
      setTimeout(() => audioRef.current?.play().catch(() => {}), 0)
    }
  }
  const onGenerated = (item) => { setHistory((h) => [item, ...h]); setCurrent(item); setTimeout(() => audioRef.current?.play().catch(() => {}), 0) }
  const voiceOf = (item) => voices.find((v) => v.key === item?.voice_choice)
  const useVoice = (key) => { setSelectedVoice(key); setModalOpen(false); setPage('tts') }
  const voice = voices.find((v) => v.key === selectedVoice)

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-400 text-white"><AudioLines size={18} /></div>
          <span className="text-base font-extrabold tracking-tight">OMNIVOICE</span>
          <span className="ml-1 text-sm text-slate-400">Audio</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-xs dark:border-slate-800">
            <Cpu size={14} className="text-brand-500" />
            <span className={`h-1.5 w-1.5 rounded-full ${health.ready ? 'bg-emerald-500' : 'animate-pulse bg-amber-500'}`} />
            {health.ready ? health.device.toUpperCase() : 'Đang kết nối…'}
          </span>
          <button onClick={() => setDark(!dark)} className="rounded-full p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-60 shrink-0 flex-col px-3 pb-4 md:flex">
          {NAV.map(({ group, items }) => (
            <div key={group ?? 'top'} className="mb-4">
              {group && <div className="mb-2 px-3 text-xs text-slate-400">{group}</div>}
              {items.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => setPage(id)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                    page === id ? 'bg-slate-100 dark:bg-slate-800' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-900'}`}>
                  <Icon size={17} /> {label}
                </button>
              ))}
            </div>
          ))}
          <div className="mt-auto rounded-2xl bg-slate-50 p-3 text-xs dark:bg-slate-900">
            <div className="font-semibold">OmniVoice Engine</div>
            <div className="mt-0.5 text-slate-500">Chạy cục bộ · {health.ready ? health.device.toUpperCase() : '…'}</div>
          </div>
        </aside>

        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-tl-3xl border-l border-t border-slate-100 dark:border-slate-800">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-4 pt-6 md:px-8">
            <div className="mb-4 flex gap-2 md:hidden">
              {[['library', 'Library'], ['tts', 'TTS'], ['clone', 'Clone']].map(([id, l]) => (
                <button key={id} onClick={() => setPage(id)} className={`rounded-full px-3 py-1.5 text-xs ${page === id ? 'bg-slate-900 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>{l}</button>
              ))}
            </div>
            {page === 'tts' && (
              <TextToSpeech voice={voice} languages={languages} ready={health.ready} onGenerated={onGenerated}
                onOpenVoices={() => setModalOpen(true)} history={history} onHistoryChanged={refreshHistory}
                current={current} playing={playing} onPlay={play} voiceOf={voiceOf} />
            )}
            {page === 'library' && <VoiceLibrary voices={voices} limits={limits} onUse={useVoice} onChanged={refreshVoices} />}
            {page === 'clone' && <VoiceClone languages={languages} limits={limits} onSaved={refreshVoices} ready={health.ready} />}
          </div>
          <Player item={current} voice={voiceOf(current)} audioRef={audioRef} playing={playing} pos={pos} />
        </main>
      </div>

      <audio ref={audioRef} src={current?.audio_url}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setPos(e.currentTarget.currentTime)} />
      {modalOpen && <VoiceModal voices={voices} selected={selectedVoice} onUse={useVoice} onClose={() => setModalOpen(false)} onChanged={refreshVoices} />}
    </div>
  )
}
