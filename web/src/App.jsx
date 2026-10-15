import { useCallback, useEffect, useState } from 'react'
import { AudioLines, History as HistoryIcon, Mic2, Moon, Sun, Cpu } from 'lucide-react'
import { api } from './api'
import TextToSpeech from './components/TextToSpeech'
import VoiceCreator from './components/VoiceCreator'
import History from './components/History'
import Player from './components/Player'

const NAV = [
  { id: 'tts', label: 'Text to Speech', icon: AudioLines },
  { id: 'creator', label: 'Voice Creator', icon: Mic2 },
  { id: 'history', label: 'Lịch sử', icon: HistoryIcon },
]

export default function App() {
  const [page, setPage] = useState('tts')
  const [dark, setDark] = useState(() => localStorage.getItem('theme') !== 'light')
  const [voices, setVoices] = useState([])
  const [history, setHistory] = useState([])
  const [languages, setLanguages] = useState(['Auto'])
  const [health, setHealth] = useState({ ready: false, device: '' })
  const [nowPlaying, setNowPlaying] = useState(null)
  const [selectedVoice, setSelectedVoice] = useState(null)

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

  useEffect(() => {
    refreshVoices().catch(() => {})
    refreshHistory().catch(() => {})
    api.meta().then((m) => setLanguages(m.languages)).catch(() => {})
    const poll = () => api.health().then(setHealth).catch(() => setHealth({ ready: false, device: '' }))
    poll()
    const t = setInterval(poll, 5000)
    return () => clearInterval(t)
  }, [refreshVoices, refreshHistory])

  const onGenerated = (item) => {
    setHistory((h) => [item, ...h])
    setNowPlaying(item)
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:flex">
        <div className="mb-8 flex items-center gap-2 px-2 pt-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-white shadow-lg shadow-brand-500/30">
            <AudioLines size={20} />
          </div>
          <span className="text-lg font-bold tracking-tight">OmniVoice</span>
        </div>
        <nav className="space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                page === id
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
              }`}
            >
              <Icon size={18} /> {label}
            </button>
          ))}
        </nav>
        <div className="mt-auto space-y-3">
          <button
            onClick={() => setDark(!dark)}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />} {dark ? 'Chế độ sáng' : 'Chế độ tối'}
          </button>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
            <Cpu size={18} className="text-brand-500" />
            <div className="min-w-0 text-xs">
              <div className="font-semibold">OmniVoice Engine</div>
              <div className="flex items-center gap-1.5 text-slate-500">
                <span className={`h-2 w-2 rounded-full ${health.ready ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
                {health.ready ? health.device.toUpperCase() : 'Đang kết nối…'}
              </div>
            </div>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 pb-32 pt-6 md:px-10">
        {/* thanh điều hướng mobile */}
        <div className="mb-6 flex gap-2 md:hidden">
          {NAV.map(({ id, label }) => (
            <button key={id} onClick={() => setPage(id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${page === id ? 'bg-brand-500 text-white' : 'bg-slate-200 dark:bg-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="mx-auto max-w-5xl">
          {page === 'tts' && (
            <TextToSpeech voices={voices} languages={languages} selected={selectedVoice} onSelect={setSelectedVoice}
              ready={health.ready} onGenerated={onGenerated} />
          )}
          {page === 'creator' && <VoiceCreator voices={voices} onChanged={refreshVoices} onUse={(k) => { setSelectedVoice(k); setPage('tts') }} />}
          {page === 'history' && (
            <History items={history} onPlay={setNowPlaying} onChanged={refreshHistory} />
          )}
        </div>
      </main>
      <Player item={nowPlaying} />
    </div>
  )
}
