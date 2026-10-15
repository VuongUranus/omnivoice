import { usePersisted } from '../usePersisted'
import { useConfirm } from '../confirm'
import { useToast } from '../toast'
import JobsStrip from './JobsStrip'
import { clip } from '../audioCheck'
import { useRef, useState } from 'react'
import { ArrowLeftRight, Eraser, Globe, Loader2, RotateCcw, Sparkles, Upload, Wand2 } from 'lucide-react'
import HistoryPanel from './HistoryPanel'
import { Button, Select, Slider, Toggle, VoiceAvatar, inputCls, langOptions } from './ui'

const DEFAULTS = { speed: 1, cfg: 2, steps: 32, denoise: true, pre: true, post: true }

export default function TextToSpeech({ voice, languages, ttsLimits, ready, onSubmit, jobs, jobsOffset, onCancelJob, onRetryJob, onDismissJob, onOpenVoices, history, onHistoryChanged, current, playing, onPlay }) {
  const [tab, setTab] = usePersisted('ov.tts.tab', 'settings')
  const [text, setText] = useState('')
  const [instruct, setInstruct] = usePersisted('ov.tts.instruct', '')
  const [showInstruct, setShowInstruct] = usePersisted('ov.tts.showInstruct', false)
  const [language, setLanguage] = usePersisted('ov.tts.language', 'Auto')
  const [s, setS] = usePersisted('ov.tts.settings', DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const fileRef = useRef(null)
  const areaRef = useRef(null)
  const confirm = useConfirm()
  const toast = useToast()
  // Giới hạn do server quy định (/api/meta); chưa tải xong thì chưa cho Generate
  const max = ttsLimits?.max_chars
  const chars = Array.from(text).length
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  const fit = (s) => (max ? clip(s, max) : s)
  const set = (k) => (v) => setS((o) => ({ ...o, [k]: v }))

  const generate = async () => {
    setBusy(true); setError(null)
    try {
      // Gửi vào hàng đợi và trả về ngay; khi xong, kết quả tự xuất hiện trong History
      const job = await onSubmit({
        text, voice: voice.key, instruct, language, speed: s.speed, guidance_scale: s.cfg, num_step: s.steps,
        denoise: s.denoise, preprocess_prompt: s.pre, postprocess_output: s.post,
      })
      setTab('history')
      toast.push({ kind: 'info', title: job.ahead > 0 ? `Đã thêm vào hàng đợi · phía trước còn ${job.ahead} yêu cầu` : 'Đang tạo giọng nói…', duration: 3000 })
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const loadFile = async (e) => {
    const f = e.target.files[0]; e.target.value = ''
    if (!f) return
    const content = await f.text(), n = Array.from(content).length
    setText(fit(content))
    setNotice(max && n > max ? `File dài ${n.toLocaleString()} ký tự, đã cắt còn ${max.toLocaleString()} (giới hạn của server).` : null)
  }

  // Bấm vào một dòng lịch sử: hỏi có đưa văn bản đó trở lại ô nhập không
  const restore = async (it) => {
    if (!it.text) return
    const n = Array.from(it.text).length
    const parts = [text.trim() ? 'Văn bản đang có trong ô nhập sẽ bị thay thế.' : 'Đưa văn bản này trở lại ô nhập để tạo lại giọng nói.']
    if (max && n > max) parts.push(`Văn bản dài ${n.toLocaleString()} ký tự, vượt giới hạn hiện tại nên sẽ bị cắt còn ${max.toLocaleString()}.`)
    const ok = await confirm({ title: 'Khôi phục văn bản?', message: parts.join(' '), detail: it.text, confirmText: 'Khôi phục', cancelText: 'Giữ nguyên', danger: false, icon: RotateCcw })
    if (!ok) return
    setText(fit(it.text)); setNotice(null); areaRef.current?.focus()
  }

  return (
    <div className="flex h-full min-h-[560px] flex-col">
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Speech Synthesis</h1>
      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[1fr_340px]">
        {/* Khung soạn thảo */}
        <div className="flex min-h-0 flex-col rounded-2xl border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-900/40">
          <textarea ref={areaRef} value={text} onChange={(e) => { setText(fit(e.target.value)); setNotice(null) }}
            placeholder="Nhập hoặc dán văn bản tại đây để bắt đầu tạo giọng nói…"
            className="min-h-[280px] w-full flex-1 resize-none bg-transparent text-[15px] leading-relaxed outline-none placeholder:text-slate-400" />
          {showInstruct && (
            <input value={instruct} onChange={(e) => setInstruct(e.target.value)} placeholder="Chỉ dẫn giọng, ví dụ: male, low pitch, calm"
              className={`${inputCls} mb-3`} />
          )}
          <div className="flex items-center justify-between pb-3">
            <button onClick={() => setShowInstruct(!showInstruct)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${showInstruct ? 'bg-brand-500 text-white' : 'bg-brand-100 text-brand-600 dark:bg-brand-500/20'}`}>
              <Wand2 size={13} /> Instruct
            </button>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span>{chars.toLocaleString()}{max ? ` / ${max.toLocaleString()}` : ''} ký tự · {words.toLocaleString()} từ</span>
              <button onClick={() => { setText(''); setNotice(null) }} title="Xoá văn bản" className="hover:text-slate-800"><Eraser size={14} /></button>
            </div>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-3 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Select value={language} onChange={setLanguage} options={langOptions(languages)} icon={Globe} up searchable searchPlaceholder="Tìm ngôn ngữ…" className="w-44" />
              <button onClick={() => fileRef.current.click()} title="Nạp file .txt" className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"><Upload size={16} /></button>
              <input ref={fileRef} type="file" accept=".txt,text/plain" hidden onChange={loadFile} />
            </div>
            <Button onClick={generate} disabled={busy || !ready || !max || !text.trim() || !voice} className="px-6 py-2.5">
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} {busy ? 'Đang gửi…' : 'Generate'}
            </Button>
          </div>
          {notice && <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">{notice}</p>}
          {error && <p className="mt-3 whitespace-pre-line rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-500/10 dark:text-red-300">{error}</p>}
        </div>

        {/* Panel phải */}
        <div className="flex min-h-0 flex-col rounded-2xl border border-slate-100 p-4 dark:border-slate-800">
          <JobsStrip jobs={jobs} offset={jobsOffset} onCancel={onCancelJob} onRetry={onRetryJob} onDismiss={onDismissJob} />
          <div className="mb-3 flex gap-5 border-b border-slate-100 dark:border-slate-800">
            {[['settings', 'Settings'], ['history', 'History']].map(([id, l]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`-mb-px border-b-2 pb-2 text-base font-semibold ${tab === id ? 'border-slate-900 dark:border-slate-100' : 'border-transparent text-slate-400'}`}>{l}</button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {tab === 'settings' ? (
              <>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold">Voice</span>
                  <button onClick={() => setS(DEFAULTS)} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"><RotateCcw size={12} /> Reset Value</button>
                </div>
                <button onClick={onOpenVoices} className="flex w-full items-center gap-3 rounded-xl bg-slate-50 p-2.5 text-left hover:bg-slate-100 dark:bg-slate-900 dark:hover:bg-slate-800">
                  <VoiceAvatar voice={voice} size="h-12 w-12" text="text-lg" />
                  <span className="flex-1 truncate font-semibold">{voice?.name ?? 'Chọn giọng…'}</span>
                  <ArrowLeftRight size={14} className="text-slate-400" />
                </button>
                <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
                  <Slider label="Speed" value={s.speed} min={0.5} max={2} step={0.05} onChange={set('speed')} fmt={(v) => v.toFixed(2)} />
                  <Slider label="Guidance Scale" value={s.cfg} min={0.5} max={6} step={0.1} onChange={set('cfg')} fmt={(v) => v.toFixed(1)} />
                  <Slider label="Steps" value={s.steps} min={8} max={64} step={1} onChange={set('steps')} />
                </div>
                <div className="mt-3 border-t border-slate-100 pt-2 dark:border-slate-800">
                  <Toggle checked={s.denoise} onChange={set('denoise')} label="Khử nhiễu" />
                  <Toggle checked={s.pre} onChange={set('pre')} label="Tiền xử lý audio mẫu" />
                  <Toggle checked={s.post} onChange={set('post')} label="Hậu xử lý đầu ra" />
                </div>
              </>
            ) : (
              <HistoryPanel items={history} current={current} playing={playing} onPlay={onPlay} onChanged={onHistoryChanged} onRestore={restore} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
